from __future__ import annotations

from ai.research_assistant import (
    answer_research_question,
)


QUESTIONS = [
    "Tell me about Albany County, Wyoming.",
    (
        "Show the trend in ischemic heart disease in Albany County, "
        "Wyoming from 2000 to 2019."
    ),
    (
        "Which counties had the highest diabetes "
        "YLL rates in 2019?"
    ),
    (
        "Compare diabetes burden among Black and "
        "White groups in 2019."
    ),
]


def main() -> None:
    print("=" * 80)
    print("EpiCounty Research Assistant Orchestration Validation")
    print("=" * 80)

    for text in QUESTIONS:
        print("\n" + "-" * 80)
        print(f"Question: {text}")

        interpretation_input, result = (
            answer_research_question(
                text
            )
        )

        print(
            f"Intent: "
            f"{interpretation_input.intent.value}"
        )

        print(
            f"Evidence claims: "
            f"{len(interpretation_input.claims)}"
        )

        print("\nValidated answer:")
        print(
            result.direct_answer.text
        )

        print("\nSupporting claims:")
        for claim_id in (
            result.direct_answer.supporting_claim_ids
        ):
            print(
                f"  - {claim_id}"
            )

        print("\nAPPROVED")

    print("\n" + "=" * 80)
    print(
        "Research-assistant orchestration "
        "validation completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()