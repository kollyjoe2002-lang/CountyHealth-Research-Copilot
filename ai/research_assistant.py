from __future__ import annotations

from ai.classifier import classify_question
from ai.entailment_judge import (
    OpenAIEntailmentJudge,
    validate_model_entailment,
)
from ai.executor import execute_plan
from ai.interpreter import build_interpretation_input
from ai.interpretation_validator import (
    validate_interpretation_result,
)
from ai.models import (
    EvidenceBundle,
    InterpretationInput,
    InterpretationResult,
)
from ai.openai_interpretation_provider import (
    OpenAIInterpretationProvider,
)
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan
from ai.validation import validate_question
from ai.semantic_entailment import (
    validate_semantic_entailment,
)


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
) -> tuple[InterpretationInput, InterpretationResult]:
    """
    Run the complete validated EpiCounty research-assistant pipeline
    from research question through approved narrative interpretation.
    """
    cleaned = question_text.strip()

    if not cleaned:
        raise ResearchAssistantError(
            "The research question cannot be empty."
        )

    try:
        classified = classify_question(
            cleaned
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