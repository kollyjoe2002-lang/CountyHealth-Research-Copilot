from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from ai.classifier import classify_question
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan
from ai.validation import (
    QuestionValidationError,
    validate_question,
)


TEST_CASES = [
    {
        "question": (
            "Show the trend in unicorn disease "
            "in Albany County, Wyoming."
        ),
        "expected": "cause",
    },
    {
        "question": (
            "Show ischemic heart disease in "
            "Albany County, Wyoming from "
            "1990 to 2025."
        ),
        "expected": "year",
    },
    {
        "question": (
            "What is the weather in Albany "
            "County tomorrow?"
        ),
        "expected": "unsupported",
    },
]


def main() -> None:
    print("=" * 80)
    print(
        "AI Negative Research Question Validation"
    )
    print("=" * 80)

    for case in TEST_CASES:
        question = case["question"]

        print()
        print("-" * 80)
        print(
            f"Question: {question}"
        )

        classified = classify_question(
            question
        )

        try:
            validate_question(
                classified
            )

            plan = build_analysis_plan(
                classified
            )

            resolved = resolve_plan(
                classified,
                plan,
            )

            if resolved.unresolved_items:
                print(
                    "Safely rejected:"
                )

                for item in (
                    resolved.unresolved_items
                ):
                    print(
                        f"  - {item}"
                    )

            else:
                raise AssertionError(
                    "Invalid research question "
                    "was unexpectedly resolved."
                )

        except QuestionValidationError as exc:
            print(
                f"Safely rejected: {exc}"
            )

    print()
    print("=" * 80)
    print(
        "Negative research question validation "
        "completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()