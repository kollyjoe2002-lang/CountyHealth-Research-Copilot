from __future__ import annotations

from dataclasses import dataclass

from ai.classifier import classify_question


@dataclass(frozen=True)
class Case:
    case_id: str
    category: str
    question: str
    expected_intent: str


CASES = [
    # ------------------------------------------------------------------
    # COUNTY PROFILE
    # ------------------------------------------------------------------
    Case(
        "P01",
        "profile",
        "Tell me about Albany County, Wyoming.",
        "county_profile",
    ),
    Case(
        "P02",
        "profile",
        "Give me an overview of Albany County, Wyoming.",
        "county_profile",
    ),
    Case(
        "P03",
        "profile",
        "How is Albany County, Wyoming doing?",
        "county_profile",
    ),
    Case(
        "P04",
        "profile",
        "Describe Yuma County, Arizona.",
        "county_profile",
    ),
    Case(
        "P05",
        "profile",
        "What is the health picture in Lancaster County, Pennsylvania?",
        "county_profile",
    ),
    Case(
        "P06",
        "profile",
        "Summarize Ada County, Idaho.",
        "county_profile",
    ),
    Case(
        "P07",
        "profile",
        "What is happening in Yuba County, California?",
        "county_profile",
    ),
    Case(
        "P08",
        "profile",
        "Give me the health status of Abbeville County, South Carolina.",
        "county_profile",
    ),

    # ------------------------------------------------------------------
    # TREND
    # ------------------------------------------------------------------
    Case(
        "T01",
        "trend",
        "Show the trend in diabetes in Albany County, Wyoming.",
        "trend_comparison",
    ),
    Case(
        "T02",
        "trend",
        "How has diabetes changed over time in Albany County, Wyoming?",
        "trend_comparison",
    ),
    Case(
        "T03",
        "trend",
        "Has breast cancer gone up or down in Lancaster County, Pennsylvania?",
        "trend_comparison",
    ),
    Case(
        "T04",
        "trend",
        "What happened to stroke over the years in Yuma County, Arizona?",
        "trend_comparison",
    ),
    Case(
        "T05",
        "trend",
        "Has diabetes decreased since 2000 in Albany County, Wyoming?",
        "trend_comparison",
    ),
    Case(
        "T06",
        "trend",
        "Has breast cancer increased since 2000 in Lancaster County, Pennsylvania?",
        "trend_comparison",
    ),
    Case(
        "T07",
        "trend",
        "Show me pancreatic cancer from 2000 to 2019 in Yuba County, California.",
        "trend_comparison",
    ),
    Case(
        "T08",
        "trend",
        "How did ischemic heart disease change from 2000 through 2019 in Ada County, Idaho?",
        "trend_comparison",
    ),
    Case(
        "T09",
        "trend",
        "Show stroke over the years in Lamar County, Texas.",
        "trend_comparison",
    ),
    Case(
        "T10",
        "trend",
        "Has heart disease changed in Albany County, Wyoming?",
        "trend_comparison",
    ),

    # ------------------------------------------------------------------
    # COUNTY RANKING
    # ------------------------------------------------------------------
    Case(
        "R01",
        "ranking",
        "Which counties have the most diabetes?",
        "county_ranking",
    ),
    Case(
        "R02",
        "ranking",
        "Which counties have the highest breast cancer rates?",
        "county_ranking",
    ),
    Case(
        "R03",
        "ranking",
        "Where is diabetes highest?",
        "county_ranking",
    ),
    Case(
        "R04",
        "ranking",
        "Where are breast cancer rates lowest?",
        "county_ranking",
    ),
    Case(
        "R05",
        "ranking",
        "What counties are worst for stroke?",
        "county_ranking",
    ),
    Case(
        "R06",
        "ranking",
        "Show me the top counties for ischemic heart disease.",
        "county_ranking",
    ),
    Case(
        "R07",
        "ranking",
        "Which counties are most affected by diabetes?",
        "county_ranking",
    ),
    Case(
        "R08",
        "ranking",
        "Which counties are least affected by breast cancer?",
        "county_ranking",
    ),
    Case(
        "R09",
        "ranking",
        "Rank counties by pancreatic cancer rate.",
        "county_ranking",
    ),
    Case(
        "R10",
        "ranking",
        "Which counties lead the nation in diabetes?",
        "county_ranking",
    ),

    # ------------------------------------------------------------------
    # RACE / ETHNICITY DISPARITY
    # ------------------------------------------------------------------
    Case(
        "D01",
        "race_disparity",
        "Compare breast cancer between Blacks and whites.",
        "demographic_disparity",
    ),
    Case(
        "D02",
        "race_disparity",
        "Are Black people more affected by breast cancer than White people?",
        "demographic_disparity",
    ),
    Case(
        "D03",
        "race_disparity",
        "How different are Black and White breast cancer rates?",
        "demographic_disparity",
    ),
    Case(
        "D04",
        "race_disparity",
        "Compare breast cancer among African Americans and Whites.",
        "demographic_disparity",
    ),
    Case(
        "D05",
        "race_disparity",
        "Is diabetes worse for Black people than White people?",
        "demographic_disparity",
    ),
    Case(
        "D06",
        "race_disparity",
        "What is the racial gap in stroke between Black and White people?",
        "demographic_disparity",
    ),
    Case(
        "D07",
        "race_disparity",
        "Compare diabetes for Hispanics and Whites.",
        "demographic_disparity",
    ),
    Case(
        "D08",
        "race_disparity",
        "How does breast cancer differ between Latino and White groups?",
        "demographic_disparity",
    ),
    Case(
        "D09",
        "race_disparity",
        "Compare diabetes between American Indians and Whites.",
        "demographic_disparity",
    ),
    Case(
        "D10",
        "race_disparity",
        "Compare stroke between Asians and Whites.",
        "demographic_disparity",
    ),

    # ------------------------------------------------------------------
    # SEX DISPARITY
    # ------------------------------------------------------------------
    Case(
        "S01",
        "sex_disparity",
        "Compare diabetes between men and women.",
        "demographic_disparity",
    ),
    Case(
        "S02",
        "sex_disparity",
        "Is diabetes worse for males than females?",
        "demographic_disparity",
    ),
    Case(
        "S03",
        "sex_disparity",
        "How different are breast cancer rates for men and women?",
        "demographic_disparity",
    ),
    Case(
        "S04",
        "sex_disparity",
        "Compare stroke in males versus females.",
        "demographic_disparity",
    ),
    Case(
        "S05",
        "sex_disparity",
        "Are women more affected by stroke than men?",
        "demographic_disparity",
    ),

    # ------------------------------------------------------------------
    # AGE DISPARITY
    # ------------------------------------------------------------------
    Case(
        "A01",
        "age_disparity",
        "Compare diabetes between ages 40 to 44 and 65 to 69.",
        "demographic_disparity",
    ),
    Case(
        "A02",
        "age_disparity",
        "Compare stroke between ages 55-59 and 75-79.",
        "demographic_disparity",
    ),
    Case(
        "A03",
        "age_disparity",
        "How different is diabetes for ages 60 to 64 versus 80 to 84?",
        "demographic_disparity",
    ),
    Case(
        "A04",
        "age_disparity",
        "Compare heart disease between ages 50 to 54 and 70 to 74.",
        "demographic_disparity",
    ),

    # ------------------------------------------------------------------
    # SAFE UNKNOWN / UNSUPPORTED NATIONAL LONG-TERM CHANGE
    # ------------------------------------------------------------------
    Case(
        "U01",
        "unsupported",
        "Which counties improved most since 2000?",
        "unknown",
    ),
    Case(
        "U02",
        "unsupported",
        "Which counties worsened most since 2000?",
        "unknown",
    ),
    Case(
        "U03",
        "unsupported",
        "Where has diabetes decreased the most since 2000?",
        "unknown",
    ),
    Case(
        "U04",
        "unsupported",
        "Where has breast cancer increased the most since 2000?",
        "unknown",
    ),
    Case(
        "U05",
        "unsupported",
        "Which counties had the biggest increase in stroke since 2000?",
        "unknown",
    ),
    Case(
        "U06",
        "unsupported",
        "Which counties had the largest decrease in diabetes since 2000?",
        "unknown",
    ),
]


def main() -> None:
    print("=" * 100)
    print("EpiCounty V1.2 Lay-Language Intent Regression Suite")
    print("=" * 100)
    print(f"Total cases: {len(CASES)}")
    print()

    passed = 0
    failures: list[
        tuple[Case, str]
    ] = []

    category_counts: dict[
        str,
        dict[str, int],
    ] = {}

    for index, case in enumerate(
        CASES,
        start=1,
    ):
        result = classify_question(
            case.question
        )

        actual = result.intent.value

        success = (
            actual == case.expected_intent
        )

        category = category_counts.setdefault(
            case.category,
            {
                "passed": 0,
                "failed": 0,
            },
        )

        print("-" * 100)
        print(
            f"[{index:02d}/{len(CASES):02d}] "
            f"{case.case_id} — {case.category}"
        )
        print(f"Question: {case.question}")
        print(f"Expected: {case.expected_intent}")
        print(f"Actual:   {actual}")
        print(
            f"Confidence: {result.confidence}"
        )
        print(
            f"Entities: {result.extracted_entities}"
        )

        if success:
            passed += 1
            category["passed"] += 1
            print("PASS")
        else:
            category["failed"] += 1

            message = (
                f"expected {case.expected_intent!r}, "
                f"received {actual!r}"
            )

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
        category_counts.items()
    ):
        total = (
            counts["passed"]
            + counts["failed"]
        )

        print(
            f"{category:20s} "
            f"{counts['passed']:2d}/{total:2d} PASS"
        )

    print()
    print("=" * 100)
    print("OVERALL RESULT")
    print("=" * 100)

    print(f"Passed: {passed}")
    print(f"Failed: {len(failures)}")
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
            f"V1.2 lay-language suite failed "
            f"{len(failures)} case(s)."
        )

    print()
    print("=" * 100)
    print(
        "V1.2 LAY-LANGUAGE INTENT REGRESSION: "
        "ALL CASES PASSED"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()