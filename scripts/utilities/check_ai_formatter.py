from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# The AI submodules depend on the project root being on sys.path.
# isort: off
from ai.classifier import classify_question
from ai.executor import execute_plan
from ai.formatter import format_evidence_table, table_caption
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan
# isort: on


QUESTIONS = [
    "Tell me about Albany County, Wyoming.",
    (
        "Which counties had the highest diabetes "
        "YLL rates in 2019?"
    ),
    (
        "Show the trend in ischemic heart disease "
        "in Albany County, Wyoming from 2000 to 2019."
    ),
    (
        "Compare diabetes burden among Black and "
        "White adults in 2019."
    ),
]


EXPECTED_MAXIMUM_COLUMNS = {
    "get_bmi_summary": 4,
    "get_top_causes": 7,
    "get_long_term_change": 6,
    "get_county_ranking": 7,
    "get_cause_trend": 4,
    "filter_dataframe": 4,
    "get_county_disparity_ranking": 7,
}


def main() -> None:
    print("=" * 80)
    print("AI Evidence Table Formatter Validation")
    print("=" * 80)

    for question in QUESTIONS:
        classified = classify_question(
            question
        )

        plan = build_analysis_plan(
            classified
        )

        resolved = resolve_plan(
            classified,
            plan,
        )

        evidence = execute_plan(
            resolved
        )

        print()
        print("-" * 80)
        print(f"Question: {question}")

        for item in evidence.items:
            if not isinstance(
                item.data,
                pd.DataFrame,
            ):
                continue

            formatted = format_evidence_table(
                item.source_function,
                item.data,
                context=evidence.context,
            )

            caption = table_caption(
                item.source_function,
                item.title,
            )

            print()
            print(f"Caption: {caption}")
            print(
                f"Source: {item.source_function}"
            )
            print(
                f"Raw shape: {item.data.shape}"
            )
            print(
                f"Formatted shape: {formatted.shape}"
            )
            print(
                formatted.head(5).to_string(
                    index=False
                )
            )

            maximum_columns = (
                EXPECTED_MAXIMUM_COLUMNS.get(
                    item.source_function
                )
            )

            if (
                maximum_columns is not None
                and len(formatted.columns)
                > maximum_columns
            ):
                raise AssertionError(
                    f"{item.source_function} returned "
                    f"{len(formatted.columns)} formatted columns; "
                    f"expected at most {maximum_columns}."
                )

            if formatted.empty:
                raise AssertionError(
                    f"{item.source_function} returned "
                    "an empty formatted table."
                )

    print()
    print("=" * 80)
    print(
        "AI formatter validation completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()