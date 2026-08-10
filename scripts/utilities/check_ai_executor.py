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


TEST_CASES = [
    {
        "question": (
            "Compare diabetes burden among Black and "
            "White adults in 2019."
        ),
        "expected_evidence_items": 1,
        "expected_source_functions": {
            "get_county_disparity_ranking",
        },
    },
    {
        "question": (
            "Show the trend in ischemic heart disease "
            "in Albany County, Wyoming from 2000 to 2019."
        ),
        "expected_evidence_items": 1,
        "expected_source_functions": {
            "filter_dataframe",
        },
    },
    {
        "question": (
            "Which counties had the highest diabetes "
            "YLL rates in 2019?"
        ),
        "expected_evidence_items": 1,
        "expected_source_functions": {
            "get_county_ranking",
        },
    },
    {
        "question": (
            "Tell me about Albany County, Wyoming."
        ),
        "expected_evidence_items": 3,
        "expected_source_functions": {
            "get_bmi_summary",
            "get_top_causes",
            "get_long_term_change",
        },
    },
]


def main() -> None:
    print("=" * 80)
    print("AI Plan Executor Validation")
    print("=" * 80)

    for test_case in TEST_CASES:
        question = test_case["question"]

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

        bundle = execute_plan(
            resolved_plan
        )

        print()
        print("-" * 80)
        print(f"Question: {question}")
        print(f"Intent: {bundle.intent.value}")
        print(
            f"Evidence items: "
            f"{len(bundle.items)}"
        )

        expected_count = int(
            test_case[
                "expected_evidence_items"
            ]
        )

        if len(bundle.items) != expected_count:
            raise AssertionError(
                f"Expected {expected_count} evidence item(s), "
                f"received {len(bundle.items)}."
            )

        actual_source_functions = {
            item.source_function
            for item in bundle.items
        }

        expected_source_functions = set(
            test_case[
                "expected_source_functions"
            ]
        )

        if (
            actual_source_functions
            != expected_source_functions
        ):
            raise AssertionError(
                "Unexpected evidence sources. "
                f"Expected {sorted(expected_source_functions)}, "
                f"received {sorted(actual_source_functions)}."
            )

        for item in bundle.items:
            print(
                f"  - {item.title} "
                f"[{item.source_function}]"
            )

            if isinstance(
                item.data,
                pd.DataFrame,
            ):
                print(
                    f"    Rows: "
                    f"{len(item.data):,}; "
                    f"Columns: "
                    f"{len(item.data.columns)}"
                )

                if item.data.empty:
                    raise AssertionError(
                        f"Evidence item "
                        f"'{item.title}' is empty."
                    )

        if bundle.warnings:
            print("Warnings:")

            for warning in bundle.warnings:
                print(
                    f"  - {warning}"
                )

    print()
    print("=" * 80)
    print(
        "AI executor validation completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()