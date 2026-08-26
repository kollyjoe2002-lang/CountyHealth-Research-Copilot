from __future__ import annotations

from time import perf_counter

from ai.entailment_judge import OpenAIEntailmentJudge, validate_model_entailment
from ai.executor import execute_plan
from ai.interpreter import build_interpretation_input
from ai.interpretation_validator import validate_interpretation_result
from ai.models import (
    EvidenceBundle,
    InterpretationInput,
    InterpretationResult,
    RequestPolicyDecision,
    ResearchAssistantOutcome,
    ResearchQuestion,
)
from ai.openai_interpretation_provider import OpenAIInterpretationProvider
from ai.openai_semantic_parser import OpenAISemanticParser
from ai.planner import build_analysis_plan
from ai.request_policy import apply_request_policy
from ai.resolver import resolve_plan
from ai.semantic_adapter import semantic_request_to_classified
from ai.semantic_entailment import validate_semantic_entailment
from ai.telemetry import persist_research_telemetry
from ai.validation import validate_question

class ResearchAssistantError(RuntimeError):
    """
    Raised when the research-assistant pipeline cannot produce
    an approved grounded interpretation.
    """


def interpret_evidence_bundle(
    bundle: EvidenceBundle,
    *,
    provider: OpenAIInterpretationProvider | None = None,
    judge: OpenAIEntailmentJudge | None = None,
) -> tuple[InterpretationInput, InterpretationResult]:
    """
    Generate and validate a grounded narrative interpretation from an
    already-executed EvidenceBundle.

    The function performs no new analytics.

    Pipeline:
    1. build grounded InterpretationInput;
    2. generate structured narrative interpretation;
    3. validate structural grounding;
    4. validate deterministic semantic grounding;
    5. validate model-based semantic entailment.

    Only an interpretation that passes every validation stage is
    returned.
    """
    try:
        interpretation_input = (
            build_interpretation_input(
                bundle
            )
        )

        active_provider = (
            provider
            if provider is not None
            else OpenAIInterpretationProvider()
        )

        result = active_provider.interpret(
            interpretation_input
        )

        validate_interpretation_result(
            interpretation_input,
            result,
        )

        validate_semantic_entailment(
            interpretation_input,
            result,
        )

        active_judge = (
            judge
            if judge is not None
            else OpenAIEntailmentJudge()
        )

        validate_model_entailment(
            interpretation_input,
            result,
            judge=active_judge,
        )

        return (
            interpretation_input,
            result,
        )

    except ResearchAssistantError:
        raise

    except Exception as exc:
        raise ResearchAssistantError(
            "The research assistant could not produce "
            f"a validated interpretation: {exc}"
        ) from exc

def run_research_assistant(
    question_text: str,
    *,
    provider: OpenAIInterpretationProvider | None = None,
    judge: OpenAIEntailmentJudge | None = None,
    semantic_parser: OpenAISemanticParser | None = None,
) -> ResearchAssistantOutcome:
    """
    Run the complete validated EpiCounty research-assistant
    orchestration while preserving intermediate analytical artifacts.

    This function is intended for application interfaces, audit
    inspection, and integration tests.

    It distinguishes three high-level outcomes:

    - answer:
        The request executed successfully and produced validated
        analytical evidence.

    - clarify:
        The analytical intent is potentially supported, but additional
        information is required before safe deterministic execution.

    - reject:
        The requested analytical capability is not supported by the
        current validated engine.
    """
    started_at = perf_counter()

    def finalize(
        outcome: ResearchAssistantOutcome,
    ) -> ResearchAssistantOutcome:
        latency_ms = (
            perf_counter() - started_at
        ) * 1000.0

        persist_research_telemetry(
            outcome,
            latency_ms=latency_ms,
        )

        return outcome

    cleaned = question_text.strip()

    if not cleaned:
        raise ResearchAssistantError(
            "The research question cannot be empty."
        )

    try:
        active_semantic_parser = (
            semantic_parser
            if semantic_parser is not None
            else OpenAISemanticParser()
        )

        semantic_request = active_semantic_parser.parse(
            ResearchQuestion(
                raw_text=cleaned
            )
        )

        policy_result = apply_request_policy(
            semantic_request
        )

        if (
            policy_result.decision
            is RequestPolicyDecision.CLARIFY
        ):
            clarification = (
                policy_result.clarification_question
                or (
                    "Please provide the additional information "
                    "needed to complete this analysis."
                )
            )

            return finalize(
                ResearchAssistantOutcome(
                    status="clarify",
                    semantic_request=semantic_request,
                    policy_result=policy_result,
                    clarification_question=clarification,
                )
            )

        if (
            policy_result.decision
            is RequestPolicyDecision.REJECT
        ):
            return finalize(
                ResearchAssistantOutcome(
                    status="reject",
                    semantic_request=semantic_request,
                    policy_result=policy_result,
                    rejection_reason=policy_result.reason,
                )
            )

        classified = semantic_request_to_classified(
            policy_result.request
        )

        validate_question(
            classified
        )

        plan = build_analysis_plan(
            classified
        )

        resolved_plan = resolve_plan(
            classified,
            plan,
        )

        if policy_result.assumptions:
            resolved_plan.assumptions.extend(
                assumption
                for assumption in policy_result.assumptions
                if assumption not in resolved_plan.assumptions
            )

        if resolved_plan.unresolved_items:
            return finalize(
                ResearchAssistantOutcome(
                    status="clarify",
                    semantic_request=semantic_request,
                    policy_result=policy_result,
                    classified_question=classified,
                    resolved_plan=resolved_plan,
                    clarification_question=(
                        " ".join(
                            resolved_plan.unresolved_items
                        )
                    ),
                )
            )

        evidence = execute_plan(
            resolved_plan
        )

        interpretation_input = None
        interpretation_result = None
        ai_error = None

        try:
            (
                interpretation_input,
                interpretation_result,
            ) = interpret_evidence_bundle(
                evidence,
                provider=provider,
                judge=judge,
            )

        except ResearchAssistantError as exc:
            ai_error = str(exc)

        return finalize(
            ResearchAssistantOutcome(
                status="answer",
                semantic_request=semantic_request,
                policy_result=policy_result,
                classified_question=classified,
                resolved_plan=resolved_plan,
                evidence_bundle=evidence,
                interpretation_input=interpretation_input,
                interpretation_result=interpretation_result,
                ai_error=ai_error,
            )
        )

    except ResearchAssistantError:
        raise

    except Exception as exc:
        raise ResearchAssistantError(
            "The research assistant could not produce "
            f"a validated orchestration result: {exc}"
        ) from exc
        
        

def answer_research_question(
    question_text: str,
    *,
    provider: OpenAIInterpretationProvider | None = None,
    judge: OpenAIEntailmentJudge | None = None,
    semantic_parser: OpenAISemanticParser | None = None,
) -> tuple[InterpretationInput, InterpretationResult]:
    """
    Run the complete validated EpiCounty research-assistant pipeline
    and return the approved narrative interpretation.

    This function preserves the original research-assistant API for
    callers that require only the final validated interpretation.

    Application interfaces that need access to intermediate analytical
    artifacts should use run_research_assistant().
    """
    outcome = run_research_assistant(
        question_text,
        provider=provider,
        judge=judge,
        semantic_parser=semantic_parser,
    )

    if outcome.status == "clarify":
        message = (
            outcome.clarification_question
            or outcome.policy_result.reason
            or (
                "The research question requires additional "
                "information before it can be executed safely."
            )
        )

        raise ResearchAssistantError(
            "The research question could not be resolved safely: "
            f"{message}"
        )

    if outcome.status == "reject":
        message = (
            outcome.rejection_reason
            or outcome.policy_result.reason
            or (
                "The requested analytical operation is not "
                "supported by the current EpiCounty analytical engine."
            )
        )

        raise ResearchAssistantError(
            "The research question cannot be executed: "
            f"{message}"
        )

    if outcome.evidence_bundle is None:
        raise ResearchAssistantError(
            "The research assistant completed without producing "
            "a validated evidence bundle."
        )

    if (
        outcome.interpretation_input is None
        or outcome.interpretation_result is None
    ):
        message = (
            outcome.ai_error
            or (
                "The analytical evidence was produced, but a "
                "validated narrative interpretation was not available."
            )
        )

        raise ResearchAssistantError(
            message
        )

    return (
        outcome.interpretation_input,
        outcome.interpretation_result,
    )