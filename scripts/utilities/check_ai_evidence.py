from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.classifier import classify_question  # noqa: E402
from ai.evidence import interpret_evidence  # noqa: E402
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
    print("AI Evidence Interpretation Validation")
    print("=" * 80)

    for question in QUESTIONS:
        classified = classify_question(question)
        plan = build_analysis_plan(classified)
        resolved = resolve_plan(
            classified,
            plan,
        )
        bundle = execute_plan(resolved)
        findings = interpret_evidence(bundle)

        print()
        print("-" * 80)
        print(f"Question: {question}")
        print(f"Intent: {bundle.intent.value}")
        print("Findings:")

        if not findings:
            raise AssertionError(
                "Evidence interpreter returned no findings."
            )

        for finding in findings:
            print(f"  - {finding}")

    print()
    print("=" * 80)
    print(
        "AI evidence interpretation validation "
        "completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()