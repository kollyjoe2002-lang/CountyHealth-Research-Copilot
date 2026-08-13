from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so local `ai` package can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.classifier import classify_question
from ai.executor import execute_plan
from ai.figures import build_evidence_figure, export_evidence_figure_png
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan



TEST_QUESTIONS = [
    "Tell me about Albany County, Wyoming.",
    (
        "Show the trend in ischemic heart disease "
        "in Albany County, Wyoming from 2000 to 2019."
    ),
    (
        "Which counties had the highest diabetes "
        "YLL rates in 2019?"
    ),
    (
        "Compare diabetes burden among Black and "
        "White adults in 2019."
    ),
]


def main() -> None:
    print("=" * 80)
    print("AI Research Figure Validation")
    print("=" * 80)

    for question in TEST_QUESTIONS:
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

        figure = build_evidence_figure(
            evidence
        )

        png_bytes = export_evidence_figure_png(
            evidence
        )

        print()
        print("-" * 80)
        print(
            f"Question: {question}"
        )
        print(
            f"Intent: {evidence.intent.value}"
        )
        print(
            f"Figure type: "
            f"{type(figure).__name__}"
        )
        print(
            f"PNG bytes: "
            f"{len(png_bytes):,}"
        )

        if len(png_bytes) < 1_000:
            raise AssertionError(
                "Generated PNG appears unexpectedly small."
            )

    print()
    print("=" * 80)
    print(
        "AI research figure validation completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()