from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.classifier import classify_question  # noqa: E402
from ai.planner import build_analysis_plan  # noqa: E402


QUESTIONS = [
    "Compare diabetes burden among Black and White adults in 2019.",
    "Show the trend in ischemic heart disease from 2000 to 2019.",
    "Which counties had the highest diabetes YLL rates in 2019?",
    "Tell me about Albany County, Wyoming.",
    "Which counties improved most since 2000?",
]


def main() -> None:
    print("=" * 80)
    print("AI Analysis Planner Validation")
    print("=" * 80)

    for question in QUESTIONS:
        classified = classify_question(question)
        plan = build_analysis_plan(classified)

        print()
        print("-" * 80)
        print(f"Question: {question}")
        print(f"Intent: {plan.intent.value}")
        print("Steps:")

        for step in plan.steps:
            print(
                f"  {step.step_number}. "
                f"{step.operation} -> "
                f"{step.function_name}"
            )
            print(
                f"     Parameters: {step.parameters}"
            )
            print(
                f"     Purpose: {step.purpose}"
            )

        if plan.assumptions:
            print("Assumptions:")

            for assumption in plan.assumptions:
                print(f"  - {assumption}")

        if plan.unresolved_items:
            print("Unresolved items:")

            for item in plan.unresolved_items:
                print(f"  - {item}")

        if not plan.steps and not plan.unresolved_items:
            raise AssertionError(
                "Planner produced neither steps nor unresolved items."
            )

    print()
    print("=" * 80)
    print("AI planner validation completed successfully")
    print("=" * 80)


if __name__ == "__main__":
    main()