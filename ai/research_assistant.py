from __future__ import annotations

from ai.entailment_judge import OpenAIEntailmentJudge, validate_model_entailment
from ai.executor import execute_plan
from ai.interpreter import build_interpretation_input
from ai.interpretation_validator import validate_interpretation_result
from ai.models import (
    EvidenceBundle,
    InterpretationInput,
    InterpretationResult,
    RequestPolicyDecision,
    ResearchQuestion,
)
from ai.openai_interpretation_provider import OpenAIInterpretationProvider
from ai.openai_semantic_parser import OpenAISemanticParser
from ai.planner import build_analysis_plan
from ai.request_policy import apply_request_policy
from ai.resolver import resolve_plan
from ai.semantic_adapter import semantic_request_to_classified
from ai.semantic_entailment import validate_semantic_entailment
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


def answer_research_question(
    question_text: str,
    *,
    provider: OpenAIInterpretationProvider | None = None,
    judge: OpenAIEntailmentJudge | None = None,
    semantic_parser: OpenAISemanticParser | None = None,
) -> tuple[InterpretationInput, InterpretationResult]:
    """
    Run the complete validated EpiCounty research-assistant pipeline
    from natural-language question through approved narrative
    interpretation.

    Pipeline:
    1. semantic parsing;
    2. deterministic request policy;
    3. semantic adaptation;
    4. question validation;
    5. deterministic planning and entity resolution;
    6. deterministic analytical execution;
    7. evidence-grounded narrative interpretation;
    8. structural and semantic entailment validation.
    """
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

            raise ResearchAssistantError(
                "The research question requires clarification: "
                f"{clarification}"
            )

        if (
            policy_result.decision
            is RequestPolicyDecision.REJECT
        ):
            raise ResearchAssistantError(
                "The research question cannot be executed: "
                f"{policy_result.reason}"
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
            raise ResearchAssistantError(
                "The research question could not be resolved safely: "
                + " ".join(
                    resolved_plan.unresolved_items
                )
            )

        bundle = execute_plan(
            resolved_plan
        )

        return interpret_evidence_bundle(
            bundle,
            provider=provider,
            judge=judge,
        )

    except ResearchAssistantError:
        raise

    except Exception as exc:
        raise ResearchAssistantError(
            "The research assistant could not produce "
            f"a validated answer: {exc}"
        ) from exc