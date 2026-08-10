from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.classifier import classify_question  # noqa: E402
from ai.models import AnalysisIntent  # noqa: E402


TEST_CASES = [
    (
        "Compare diabetes burden among Black and White adults.",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
    ),
    (
        "Show the trend in ischemic heart disease from 2000 to 2019.",
        AnalysisIntent.TREND_COMPARISON,
    ),
    (
        "Which counties had the highest diabetes YLL rates in 2019?",
        AnalysisIntent.COUNTY_RANKING,
    ),
    (
        "Tell me about Albany County, Wyoming.",
        AnalysisIntent.COUNTY_PROFILE,
    ),
    (
        "Which counties improved most since 2000?",
        AnalysisIntent.LONG_TERM_CHANGE,
    ),
]


def main() -> None:
    print("=" * 80)
    print("AI Question Classifier Validation")
    print("=" * 80)

    for question, expected_intent in TEST_CASES:
        result = classify_question(question)

        print()
        print(f"Question: {question}")
        print(f"Intent: {result.intent.value}")
        print(f"Confidence: {result.confidence}")
        print(f"Entities: {result.extracted_entities}")

        if result.intent != expected_intent:
            raise AssertionError(
                f"Expected {expected_intent.value}, "
                f"received {result.intent.value}."
            )

    print()
    print("=" * 80)
    print("AI classifier validation completed successfully")
    print("=" * 80)


if __name__ == "__main__":
    main()