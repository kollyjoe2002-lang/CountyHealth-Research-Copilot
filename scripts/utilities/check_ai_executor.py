from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.classifier import classify_question  # noqa: E402
from ai.executor import execute_plan  # noqa: E402
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
    print("AI Plan Executor Validation")
    print("=" * 80)

    for question in QUESTIONS:
        classified = classify_question(question)
        plan = build_analysis_plan(classified)
        resolved_plan = resolve_plan(
            classified,
            plan,
        )

        bundle = execute_plan(
            resolved_plan
        )

        print()
        print("-" * 80)
        print(f"Question: {question}")
        print(f"Intent: {bundle.intent.value}")
        print(f"Evidence items: {len(bundle.items)}")

        for item in bundle.items:
            print(
                f"  - {item.title} "
                f"[{item.source_function}]"
            )

            if isinstance(item.data, pd.DataFrame):
                print(
                    f"    Rows: {len(item.data):,}; "
                    f"Columns: {len(item.data.columns)}"
                )

                if item.data.empty:
                    raise AssertionError(
                        f"Evidence item '{item.title}' is empty."
                    )

        if bundle.warnings:
            print("Warnings:")

            for warning in bundle.warnings:
                print(f"  - {warning}")

    print()
    print("=" * 80)
    print(
        "AI executor validation completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()