from __future__ import annotations

from dataclasses import dataclass

from ai.research_assistant import (
    answer_research_question,
)


@dataclass(frozen=True)
class QuestionCase:
    case_id: str
    category: str
    question: str
    expected_intent: str | None = None
    should_pass: bool = True


CASES = [
    # ========================================================================
    # COUNTY PROFILE
    # ========================================================================

    QuestionCase(
        "P01",
        "county_profile",
        "Tell me about Albany County, Wyoming.",
        "county_profile",
    ),
    QuestionCase(
        "P02",
        "county_profile",
        "Tell me about Ada County, Idaho.",
        "county_profile",
    ),
    QuestionCase(
        "P03",
        "county_profile",
        "Give me a health profile for Yuma County, Arizona.",
        "county_profile",
    ),
    QuestionCase(
        "P04",
        "county_profile",
        "What does the county health profile look like for "
        "Abbeville County, South Carolina?",
        "county_profile",
    ),
    QuestionCase(
        "P05",
        "county_profile",
        "Tell me about Lancaster County, Pennsylvania.",
        "county_profile",
    ),
    QuestionCase(
        "P06",
        "county_profile",
        "Summarize the health profile of Yuba County, California.",
        "county_profile",
    ),

    # ========================================================================
    # TREND COMPARISON
    # ========================================================================

    QuestionCase(
        "T01",
        "trend_comparison",
        "Show the trend in ischemic heart disease in Albany County, "
        "Wyoming from 2000 to 2019.",
        "trend_comparison",
    ),
    QuestionCase(
        "T02",
        "trend_comparison",
        "Show the trend in diabetes mellitus type 2 in Ada County, "
        "Idaho from 2000 to 2019.",
        "trend_comparison",
    ),
    QuestionCase(
        "T03",
        "trend_comparison",
        "How did stroke change in Yuma County, Arizona from "
        "2000 to 2019?",
        "trend_comparison",
    ),
    QuestionCase(
        "T04",
        "trend_comparison",
        "What was the trend in breast cancer in Lancaster County, "
        "Pennsylvania from 2000 through 2019?",
        "trend_comparison",
    ),
    QuestionCase(
        "T05",
        "trend_comparison",
        "Show me pancreatic cancer over time in Yuba County, "
        "California between 2000 and 2019.",
        "trend_comparison",
    ),
    QuestionCase(
        "T06",
        "trend_comparison",
        "How did hypertensive heart disease change in Adams County, "
        "Colorado from 2000 to 2019?",
        "trend_comparison",
    ),
    QuestionCase(
        "T07",
        "trend_comparison",
        "Show the 2000 to 2019 trend for Alzheimer's disease and "
        "other dementias in Accomack County, Virginia.",
        "trend_comparison",
    ),
    QuestionCase(
        "T08",
        "trend_comparison",
        "What happened to ischemic stroke in Lamar County, Texas "
        "from 2000 to 2019?",
        "trend_comparison",
    ),

    # ========================================================================
    # COUNTY RANKING
    # ========================================================================

    QuestionCase(
        "R01",
        "county_ranking",
        "Which counties had the highest diabetes YLL rates in 2019?",
        "county_ranking",
    ),
    QuestionCase(
        "R02",
        "county_ranking",
        "Which counties had the highest ischemic heart disease "
        "YLL rates in 2019?",
        "county_ranking",
    ),
    QuestionCase(
        "R03",
        "county_ranking",
        "Rank counties by breast cancer YLL rate in 2019.",
        "county_ranking",
    ),
    QuestionCase(
        "R04",
        "county_ranking",
        "Which counties had the highest stroke burden in 2019?",
        "county_ranking",
    ),
    QuestionCase(
        "R05",
        "county_ranking",
        "Where were pancreatic cancer YLL rates highest in 2019?",
        "county_ranking",
    ),
    QuestionCase(
        "R06",
        "county_ranking",
        "Which counties ranked highest for hypertensive heart "
        "disease in 2019?",
        "county_ranking",
    ),

    # ========================================================================
    # RACE / ETHNICITY DISPARITIES
    # ========================================================================

    QuestionCase(
        "D01",
        "demographic_disparity",
        "Compare diabetes burden among Black and White groups "
        "in 2019.",
        "demographic_disparity",
    ),
    QuestionCase(
        "D02",
        "demographic_disparity",
        "Compare ischemic heart disease burden between "
        "Non-Latino Black and Non-Latino White groups in 2019.",
        "demographic_disparity",
    ),
    QuestionCase(
        "D03",
        "demographic_disparity",
        "Compare breast cancer burden between Latino and "
        "Non-Latino White groups in 2019.",
        "demographic_disparity",
    ),
    QuestionCase(
        "D04",
        "demographic_disparity",
        "Compare stroke burden between Non-Latino American Indian "
        "or Alaska Native and Non-Latino White groups in 2019.",
        "demographic_disparity",
    ),
    QuestionCase(
        "D05",
        "demographic_disparity",
        "Compare diabetes mellitus type 2 burden between "
        "Non-Latino Asian or Pacific Islander and Non-Latino "
        "White groups in 2019.",
        "demographic_disparity",
    ),

    # ========================================================================
    # SEX DISPARITIES
    # ========================================================================

    QuestionCase(
        "D06",
        "demographic_disparity",
        "Compare diabetes mellitus type 2 burden between males "
        "and females in 2019.",
        "demographic_disparity",
    ),
    QuestionCase(
        "D07",
        "demographic_disparity",
        "Compare ischemic heart disease burden between men and "
        "women in 2019.",
        "demographic_disparity",
    ),
    QuestionCase(
        "D08",
        "demographic_disparity",
        "Compare stroke burden for male and female groups in 2019.",
        "demographic_disparity",
    ),

    # ========================================================================
    # AGE DISPARITIES
    # ========================================================================

    QuestionCase(
        "D09",
        "demographic_disparity",
        "Compare diabetes mellitus type 2 burden between ages "
        "40 to 44 and 65 to 69 in 2019.",
        "demographic_disparity",
    ),
    QuestionCase(
        "D10",
        "demographic_disparity",
        "Compare ischemic heart disease burden between ages "
        "50 to 54 and 70 to 74 in 2019.",
        "demographic_disparity",
    ),
    QuestionCase(
        "D11",
        "demographic_disparity",
        "Compare stroke burden between ages 55 to 59 and "
        "75 to 79 in 2019.",
        "demographic_disparity",
    ),
    QuestionCase(
        "D12",
        "demographic_disparity",
        "Compare diabetes burden between ages 60 to 64 and "
        "80 to 84 in 2019.",
        "demographic_disparity",
    ),

    # ========================================================================
    # LINGUISTIC VARIATION
    # ========================================================================

    QuestionCase(
        "L01",
        "linguistic_variation",
        "Give me an overview of Albany County in Wyoming.",
        "county_profile",
    ),
    QuestionCase(
        "L02",
        "linguistic_variation",
        "How has ischemic heart disease changed over time in "
        "Albany County, Wyoming?",
        "trend_comparison",
    ),
    QuestionCase(
        "L03",
        "linguistic_variation",
        "Where is diabetes burden highest across U.S. counties "
        "in 2019?",
        "county_ranking",
    ),
    QuestionCase(
        "L04",
        "linguistic_variation",
        "How does diabetes burden differ between Black and White "
        "groups in 2019?",
        "demographic_disparity",
    ),
    QuestionCase(
        "L05",
        "linguistic_variation",
        "What counties lead the nation in ischemic heart disease "
        "YLL rate in 2019?",
        "county_ranking",
    ),
    QuestionCase(
        "L06",
        "linguistic_variation",
        "Describe the 2000 through 2019 stroke pattern in "
        "Yuma County, Arizona.",
        "trend_comparison",
    ),

    # ========================================================================
    # NEGATIVE / ADVERSARIAL CASES
    #
    # These are intentionally outside the supported V1 contract.
    # Success means safe rejection rather than fabrication.
    # ========================================================================

    QuestionCase(
        "N01",
        "negative",
        "Tell me about Atlantis County, Wyoming.",
        should_pass=False,
    ),
    QuestionCase(
        "N02",
        "negative",
        "Show the trend in malaria in Albany County, Wyoming.",
        should_pass=False,
    ),
    QuestionCase(
        "N03",
        "negative",
        "Why did ischemic heart disease decline in Albany County?",
        should_pass=False,
    ),
    QuestionCase(
        "N04",
        "negative",
        "Predict diabetes YLL rates in Albany County for 2035.",
        should_pass=False,
    ),
    QuestionCase(
        "N05",
        "negative",
        "Prove that obesity caused ischemic heart disease in "
        "Albany County.",
        should_pass=False,
    ),
    QuestionCase(
        "N06",
        "negative",
        "Which hospital caused the decline in diabetes mortality "
        "in Albany County?",
        should_pass=False,
    ),
    QuestionCase(
        "N07",
        "negative",
        "Compare diabetes burden between teenagers and children "
        "in 2019.",
        should_pass=False,
    ),
    QuestionCase(
        "N08",
        "negative",
        "Tell me the statistically significant difference between "
        "Black and White diabetes rates in 2019.",
        should_pass=False,
    ),
]


def print_header() -> None:
    print("=" * 100)
    print("EpiCounty V1 Tier 2 Question Matrix")
    print("=" * 100)
    print(f"Total cases: {len(CASES)}")
    print()


def run_case(
    case: QuestionCase,
) -> tuple[bool, str]:
    try:
        (
            interpretation_input,
            interpretation,
        ) = answer_research_question(
            case.question
        )

        actual_intent = (
            interpretation_input.intent.value
        )

        if not case.should_pass:
            return (
                False,
                "Expected safe rejection, but the "
                "question completed successfully "
                f"with intent {actual_intent!r}.",
            )

        if (
            case.expected_intent is not None
            and actual_intent
            != case.expected_intent
        ):
            return (
                False,
                "Intent mismatch: expected "
                f"{case.expected_intent!r}, got "
                f"{actual_intent!r}.",
            )

        if not (
            interpretation
            .direct_answer
            .text
            .strip()
        ):
            return (
                False,
                "Validated interpretation contained "
                "an empty direct answer.",
            )

        if not (
            interpretation
            .direct_answer
            .supporting_claim_ids
        ):
            return (
                False,
                "Validated direct answer contained "
                "no supporting evidence claims.",
            )

        return (
            True,
            (
                f"PASS — intent={actual_intent}; "
                f"claims="
                f"{len(interpretation_input.claims)}"
            ),
        )

    except Exception as exc:
        if case.should_pass:
            return (
                False,
                (
                    "Unexpected rejection: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        return (
            True,
            (
                "SAFE REJECTION — "
                f"{type(exc).__name__}: {exc}"
            ),
        )


def main() -> None:
    print_header()

    passed = 0
    failed = 0

    category_results: dict[
        str,
        dict[str, int],
    ] = {}

    failures: list[
        tuple[QuestionCase, str]
    ] = []

    for index, case in enumerate(
        CASES,
        start=1,
    ):
        print("-" * 100)
        print(
            f"[{index:02d}/{len(CASES):02d}] "
            f"{case.case_id} — {case.category}"
        )
        print(f"Question: {case.question}")

        success, message = run_case(
            case
        )

        category = category_results.setdefault(
            case.category,
            {
                "passed": 0,
                "failed": 0,
            },
        )

        if success:
            passed += 1
            category["passed"] += 1
            print(message)
        else:
            failed += 1
            category["failed"] += 1
            failures.append(
                (
                    case,
                    message,
                )
            )
            print(f"FAIL — {message}")

    print()
    print("=" * 100)
    print("CATEGORY SUMMARY")
    print("=" * 100)

    for category, counts in (
        category_results.items()
    ):
        total = (
            counts["passed"]
            + counts["failed"]
        )

        print(
            f"{category:25s} "
            f"{counts['passed']:2d}/{total:2d} PASS"
        )

    print()
    print("=" * 100)
    print("OVERALL RESULT")
    print("=" * 100)

    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {len(CASES)}")

    if failures:
        print()
        print("=" * 100)
        print("FAILURE DETAILS")
        print("=" * 100)

        for case, message in failures:
            print()
            print(
                f"{case.case_id}: "
                f"{case.question}"
            )
            print(message)

        raise AssertionError(
            f"Tier 2 question matrix failed "
            f"{failed} case(s)."
        )

    print()
    print(
        "TIER 2 QUESTION MATRIX: "
        "ALL CASES PASSED"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()