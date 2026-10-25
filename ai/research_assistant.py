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

        if bundle.context.get("multidimensional"):
            from ai.multidimensional_evidence import validate_language
            trusted = set(interpretation_input.limitations + interpretation_input.warnings)
            for text in result.limitations + result.warnings + result.follow_up_questions:
                if text not in trusted:
                    validate_language(text)

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
    telemetry_context: TelemetryContext | None = None,
    fixture_context=None,
    capability_catalog=None,
    conversation_mode: bool = False,
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
        if outcome.status not in {"answer", "capability_summary"}:
            from ai.capability_conversation import fallback
            outcome.failure_reason = (outcome.failure_reason or outcome.policy_result.failure_reason
                                      or (outcome.resolved_plan.resolved_context.get("failure_reason") if outcome.resolved_plan else None))
            outcome.conversation_response = fallback(outcome, capability_catalog)
            outcome.failure_reason = outcome.conversation_response.reason

        latency_ms = (
            perf_counter() - started_at
        ) * 1000.0

        persist_research_telemetry(
            outcome,
            latency_ms=latency_ms,
            context=telemetry_context,
        )

        return outcome

    cleaned = question_text.strip()

    if not cleaned:
        raise ResearchAssistantError(
            "The research question cannot be empty."
        )

    from ai.capability_conversation import summary_topic, capability_summary
    topic = summary_topic(cleaned)
    if topic:
        from ai.models import SemanticAnalysisRequest, AnalysisIntent, RequestPolicyResult
        request = SemanticAnalysisRequest(ResearchQuestion(cleaned), AnalysisIntent.UNKNOWN, 1.0)
        return finalize(ResearchAssistantOutcome("capability_summary", request,
            RequestPolicyResult(request, RequestPolicyDecision.CLARIFY, "Deterministic capability description; no analytics"),
            conversation_response=capability_summary(topic, capability_catalog)))

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
        if conversation_mode and policy_result.decision is not RequestPolicyDecision.REJECT:
            from ai.conversation_state import conversation_preflight
            preflight = conversation_preflight(semantic_request)
            clarification_text = (semantic_request.clarification_question or "").casefold()
            slot_clarification = preflight and (
                (preflight.failure_reason.value == "SOURCE_REQUIRED" and any(w in clarification_text for w in ("source", "places", "ihme"))) or
                (preflight.failure_reason.value == "YEAR_REQUIRED" and "year" in clarification_text))
            if semantic_request.needs_clarification and not slot_clarification:
                from ai.models import RequestPolicyResult
                policy_result = RequestPolicyResult(semantic_request, RequestPolicyDecision.CLARIFY,
                    "Follow-up clarification is required", clarification_question=semantic_request.clarification_question)
            else:
                policy_result = preflight or policy_result

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

        if policy_result.normalized_multidimensional is not None:
            from ai.resolver import resolve_multidimensional_request
            classified.extracted_entities["multidimensional_resolution"] = resolve_multidimensional_request(
                policy_result.request, policy_result.normalized_multidimensional, fixture_context=fixture_context)

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

        if resolved_plan.resolved_context.get("multidimensional"):
            decision = resolved_plan.resolved_context["capability_decision"]
            if decision.reason == "clarification_required" or decision.reason == "data_unavailable" or (
                fixture_context is None or not fixture_context.allow_execution
            ):
                status = ("clarify" if decision.reason == "clarification_required" else
                          "unavailable" if decision.reason == "data_unavailable" else "planned")
                return finalize(ResearchAssistantOutcome(status=status, semantic_request=semantic_request,
                    policy_result=policy_result, classified_question=classified, resolved_plan=resolved_plan,
                    capability_decision=decision,
                    clarification_question=" ".join(resolved_plan.unresolved_items) or None))

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

        evidence = (execute_plan(resolved_plan, fixture_context=fixture_context)
                    if resolved_plan.resolved_context.get("multidimensional") else execute_plan(resolved_plan))

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
                capability_decision=resolved_plan.resolved_context.get("capability_decision"),
            )
        )

    except ResearchAssistantError:
        raise

    except Exception as exc:
        if conversation_mode:
            from ai.models import SemanticAnalysisRequest, AnalysisIntent, RequestPolicyResult
            from ai.conversation_contracts import FailureReason
            request = locals().get("semantic_request") or SemanticAnalysisRequest(
                ResearchQuestion(cleaned), AnalysisIntent.UNKNOWN, 0.0)
            return finalize(ResearchAssistantOutcome("infrastructure_error", request,
                RequestPolicyResult(request, RequestPolicyDecision.CLARIFY,
                    "A required service could not complete the request",
                    failure_reason=FailureReason.INFRASTRUCTURE_UNAVAILABLE),
                failure_reason=FailureReason.INFRASTRUCTURE_UNAVAILABLE))
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
    telemetry_context: TelemetryContext | None = None,
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
        telemetry_context=telemetry_context,
    )

    if outcome.status in {"planned", "unavailable"}:
        raise ResearchAssistantError("Multidimensional execution is awaiting real-data activation or availability validation")

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