from __future__ import annotations

from ai.classifier import classify_question
from ai.executor import execute_plan
from ai.interpreter import build_interpretation_input
from ai.models import InterpretationInput
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan


QUESTIONS = [
    "Tell me about Albany County, Wyoming.",
    (
        "Show the trend in ischemic heart disease in Albany County, "
        "Wyoming from 2000 to 2019."
    ),
    "Which counties had the highest diabetes YLL rates in 2019?",
    "Compare diabetes burden among Black and White adults in 2019.",
]


def main() -> None:
    print("=" * 80)
    print("AI Interpretation Input Validation")
    print("=" * 80)

    for text in QUESTIONS:
        print("\n" + "-" * 80)
        print(f"Question: {text}")

        classified = classify_question(
            text
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

        assert isinstance(
            interpretation_input,
            InterpretationInput,
        )

        assert interpretation_input.claims

        assert (
            interpretation_input.question.raw_text
            == text
        )

        assert (
            interpretation_input.intent
            == bundle.intent
        )

        assert (
            interpretation_input.context
            == bundle.context
        )

        assert (
            interpretation_input.warnings
            == bundle.warnings
        )

        assert interpretation_input.limitations

        assert any(
            "do not establish causation"
            in limitation
            for limitation
            in interpretation_input.limitations
        )

        print(
            f"Intent: "
            f"{interpretation_input.intent.value}"
        )

        print(
            f"Claims: "
            f"{len(interpretation_input.claims)}"
        )

        print(
            f"Limitations: "
            f"{len(interpretation_input.limitations)}"
        )

        print(
            "Claim IDs:"
        )

        for claim in interpretation_input.claims:
            print(
                f"  - {claim.claim_id}"
            )

    print("\n" + "=" * 80)
    print(
        "AI interpretation input validation "
        "completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()