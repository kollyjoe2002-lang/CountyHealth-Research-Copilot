from __future__ import annotations

from dataclasses import dataclass

from ai.models import AnalysisIntent
from ai.research_assistant import (
    ResearchAssistantError,
    answer_research_question,
)


@dataclass(frozen=True)
class FullChainCase:
    case_id: str
    question: str
    expected_intent: AnalysisIntent | None
    should_succeed: bool


CASES = [
    FullChainCase(
        "F01",
        "Breast cancer in Milwaukee County, Wisconsin",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        True,
    ),
    FullChainCase(
        "F02",
        "Tell me how Milwaukee County, Wisconsin is doing",
        AnalysisIntent.COUNTY_PROFILE,
        True,
    ),
    FullChainCase(
        "F03",
        "How has breast cancer changed in Milwaukee County, Wisconsin?",
        AnalysisIntent.TREND_COMPARISON,
        True,
    ),
    FullChainCase(
        "F04",
        "Which counties have the highest diabetes burden?",
        AnalysisIntent.COUNTY_RANKING,
        True,
    ),
    FullChainCase(
        "F05",
        "Are Black people more affected by diabetes than White people?",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        True,
    ),
    FullChainCase(
        "F06",
        "Compare stroke between men and women",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        True,
    ),
    FullChainCase(
        "F07",
        "How different is diabetes between ages 60 to 64 and 80 to 84?",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        True,
    ),
    FullChainCase(
        "F08",
        "Predict diabetes rates in Milwaukee County in 2035",
        None,
        False,
    ),
]


def main() -> None:
    print("=" * 100)
    print("EpiCounty Semantic Full-Chain Validation")
    print("=" * 100)

    passed = 0
    failures: list[str] = []

    for case in CASES:
        print("-" * 100)
        print(f"{case.case_id}: {case.question}")

        try:
            interpretation_input, result = (
                answer_research_question(
                    case.question
                )
            )

            if not case.should_succeed:
                failures.append(
                    f"{case.case_id}: expected safe rejection "
                    "but the pipeline succeeded."
                )
                print("FAIL: expected rejection, received answer")
                continue

            actual_intent = interpretation_input.intent

            if actual_intent != case.expected_intent:
                failures.append(
                    f"{case.case_id}: expected "
                    f"{case.expected_intent.value}, received "
                    f"{actual_intent.value}."
                )
                print(
                    "FAIL:",
                    "expected",
                    case.expected_intent.value,
                    "received",
                    actual_intent.value,
                )
                continue

            if not result.direct_answer.text.strip():
                failures.append(
                    f"{case.case_id}: direct answer was empty."
                )
                print("FAIL: direct answer was empty")
                continue

            if not result.direct_answer.supporting_claim_ids:
                failures.append(
                    f"{case.case_id}: direct answer had no "
                    "supporting claims."
                )
                print("FAIL: no supporting claims")
                continue

            print("PASS")
            print("Intent:", actual_intent.value)
            print(
                "Direct answer:",
                result.direct_answer.text,
            )
            print(
                "Claims:",
                result.direct_answer.supporting_claim_ids,
            )

            passed += 1

        except ResearchAssistantError as exc:
            if case.should_succeed:
                failures.append(
                    f"{case.case_id}: unexpected failure: {exc}"
                )
                print("FAIL:", exc)

            else:
                error_text = str(exc)

                expected_rejection = (
                    "The requested analytical operation is not "
                    "supported by the current EpiCounty analytical engine."
                )

                if expected_rejection not in error_text:
                    failures.append(
                        f"{case.case_id}: expected unsupported-capability "
                        f"rejection, received a different failure: "
                        f"{error_text}"
                    )

                    print(
                        "FAIL: expected unsupported-capability rejection"
                    )
                    print(
                        "Actual failure:",
                        error_text,
                    )

                    continue

                print("PASS: safely rejected")
                print("Reason:", error_text)
                passed += 1

    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Passed: {passed}")
    print(f"Failed: {len(failures)}")
    print(f"Total:  {len(CASES)}")

    if failures:
        print()
        print("FAILURES:")
        for failure in failures:
            print("-", failure)

        raise AssertionError(
            "Semantic full-chain validation failed."
        )

    print()
    print(
        "SEMANTIC FULL-CHAIN VALIDATION: "
        "ALL 8 CASES PASSED"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()