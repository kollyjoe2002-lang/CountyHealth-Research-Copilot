from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.classifier import classify_question  # noqa: E402
from ai.planner import build_analysis_plan  # noqa: E402
from ai.resolver import resolve_plan  # noqa: E402


QUESTIONS = [
    (
        "Compare diabetes burden among Black and "
        "White adults in 2019."
    ),
    (
        "Show the trend in ischemic heart disease "
        "in Albany County, Wyoming from 2000 to 2019."
    ),
    (
        "Which counties had the highest diabetes "
        "YLL rates in 2019?"
    ),
    (
        "Tell me about Albany County, Wyoming."
    ),
]


def main() -> None:
    print("=" * 80)
    print("AI Entity Resolver Validation")
    print("=" * 80)

    for question in QUESTIONS:
        classified = classify_question(
            question
        )

        plan = build_analysis_plan(
            classified
        )

        resolved_plan = resolve_plan(
            classified,
            plan,
        )

        print()
        print("-" * 80)
        print(f"Question: {question}")
        print(
            f"Intent: "
            f"{resolved_plan.intent.value}"
        )

        for step in resolved_plan.steps:
            print(
                f"{step.step_number}. "
                f"{step.operation}: "
                f"{step.parameters}"
            )

        if resolved_plan.assumptions:
            print("Resolved assumptions:")

            for assumption in (
                resolved_plan.assumptions
            ):
                print(f"  - {assumption}")

        if resolved_plan.unresolved_items:
            print("Unresolved items:")

            for item in (
                resolved_plan.unresolved_items
            ):
                print(f"  - {item}")

    print()
    print("=" * 80)
    print(
        "AI resolver validation completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()