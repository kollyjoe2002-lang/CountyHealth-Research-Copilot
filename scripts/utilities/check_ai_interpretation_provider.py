from __future__ import annotations

from ai.classifier import classify_question
from ai.executor import execute_plan
from ai.interpreter import build_interpretation_input
from ai.interpretation_provider import (
    DeterministicInterpretationProvider,
)
from ai.interpretation_validator import (
    validate_interpretation_result,
)
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan


QUESTION = (
    "Show the trend in ischemic heart disease in Albany County, "
    "Wyoming from 2000 to 2019."
)


def main() -> None:
    print("=" * 80)
    print("AI Interpretation Provider Validation")
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

    interpretation_input = build_interpretation_input(
        bundle
    )

    provider = DeterministicInterpretationProvider()

    result = provider.interpret(
        interpretation_input
    )

    validate_interpretation_result(
        interpretation_input,
        result,
    )

    print(f"Intent: {interpretation_input.intent.value}")
    print(f"Evidence claims: {len(interpretation_input.claims)}")
    print(
        "Interpretation statements: "
        f"{len(result.interpretation)}"
    )

    print("\nDirect answer:")
    print(result.direct_answer)

    print("\nStatement grounding:")

    for statement in result.interpretation:
        print(
            f"  {statement.supporting_claim_ids} "
            f"-> {statement.text}"
        )

    print("\nProvider result validation: PASS")

    print("\n" + "=" * 80)
    print(
        "AI interpretation provider validation "
        "completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()