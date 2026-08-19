from __future__ import annotations

from ai.classifier import classify_question
from ai.executor import execute_plan
from ai.interpreter import build_interpretation_input
from ai.interpretation_validator import (
    validate_interpretation_result,
)
from ai.openai_interpretation_provider import (
    OpenAIInterpretationProvider,
)
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan


QUESTION = (
    "Show the trend in ischemic heart disease in Albany County, "
    "Wyoming from 2000 to 2019."
)


def main() -> None:
    print("=" * 80)
    print("OpenAI Interpretation Provider Live Validation")
    print("=" * 80)

    classified = classify_question(
        QUESTION
    )

    plan = build_analysis_plan(
        classified
    )

    resolved_plan = resolve_plan(
        classified,
        plan,
    )

    bundle = execute_plan(
        resolved_plan
    )

    interpretation_input = (
        build_interpretation_input(
            bundle
        )
    )

    provider = OpenAIInterpretationProvider(
        model="gpt-5.6"
    )

    result = provider.interpret(
        interpretation_input
    )

    validate_interpretation_result(
        interpretation_input,
        result,
    )

    print("\nDirect answer:")
    print(result.direct_answer.text)

    print("\nDirect-answer claims:")
    for claim_id in result.direct_answer.supporting_claim_ids:
        print(f"  - {claim_id}")

    print("\nInterpretation statements:")

    for index, statement in enumerate(
        result.interpretation,
        start=1,
    ):
        print(
            f"\n{index}. {statement.text}"
        )
        print(
            "   Supporting claims: "
            f"{statement.supporting_claim_ids}"
        )

    print("\nLimitations:")

    for limitation in result.limitations:
        print(
            f"  - {limitation}"
        )

    print("\nFollow-up questions:")

    for question in result.follow_up_questions:
        print(
            f"  - {question}"
        )

    print("\nWarnings:")

    for warning in result.warnings:
        print(
            f"  - {warning}"
        )

    print("\nStructural grounding validator: PASS")

    print("\n" + "=" * 80)
    print(
        "OpenAI live interpretation validation "
        "completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()