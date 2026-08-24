from __future__ import annotations

from dataclasses import dataclass

from ai.models import (
    AnalysisIntent,
    ResearchQuestion,
)
from ai.openai_semantic_parser import (
    OpenAISemanticParser,
)


@dataclass(frozen=True)
class StressCase:
    case_id: str
    question: str
    expected_intent: AnalysisIntent
    expected_dimension: str | None = None
    expect_county: bool = False
    expect_cause: bool = False
    should_need_clarification: bool | None = None


CASES = [
    # ------------------------------------------------------------
    # COUNTY CAUSE SNAPSHOT
    # ------------------------------------------------------------
    StressCase(
        "S001",
        "Breast cancer in Milwaukee County, Wisconsin",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S002",
        "Milwaukee breast cancer",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S003",
        "What's the diabetes situation in Albany County Wyoming?",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S004",
        "Tell me the stroke burden for Yuma County Arizona",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S005",
        "Heart disease Milwaukee County",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S006",
        "How bad is diabetes in Milwaukee County?",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S007",
        "Give me breast cancer numbers for Albany County",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S008",
        "What does stroke look like in Yuma County?",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S009",
        "Diabetes burden Milwaukee",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S010",
        "Breast cancer Milwaukee 2019",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),

    # ------------------------------------------------------------
    # COUNTY PROFILE
    # ------------------------------------------------------------
    StressCase(
        "S011",
        "Tell me about Albany County Wyoming",
        AnalysisIntent.COUNTY_PROFILE,
        expect_county=True,
    ),
    StressCase(
        "S012",
        "How is Milwaukee County doing?",
        AnalysisIntent.COUNTY_PROFILE,
        expect_county=True,
    ),
    StressCase(
        "S013",
        "Give me an overview of Yuma County Arizona",
        AnalysisIntent.COUNTY_PROFILE,
        expect_county=True,
    ),
    StressCase(
        "S014",
        "Milwaukee County health overview",
        AnalysisIntent.COUNTY_PROFILE,
        expect_county=True,
    ),
    StressCase(
        "S015",
        "What's going on health-wise in Albany County?",
        AnalysisIntent.COUNTY_PROFILE,
        expect_county=True,
    ),

    # ------------------------------------------------------------
    # TREND
    # ------------------------------------------------------------
    StressCase(
        "S016",
        "Has diabetes gotten worse in Albany County?",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S017",
        "Is stroke going up or down in Yuma County Arizona?",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S018",
        "How has breast cancer changed in Milwaukee?",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S019",
        "Heart disease trend Albany County",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S020",
        "What happened to stroke in Yuma County from 2000 to 2019?",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S021",
        "Did diabetes improve in Milwaukee County?",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S022",
        "Has breast cancer been climbing in Albany County?",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S023",
        "Show me the stroke trend in Milwaukee County",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S024",
        "How did ischemic heart disease change between 2005 and 2015 in Albany County?",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S025",
        "Breast cancer over time in Milwaukee",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),

    # ------------------------------------------------------------
    # COUNTY RANKING
    # ------------------------------------------------------------
    StressCase(
        "S026",
        "Where is diabetes worst?",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    StressCase(
        "S027",
        "Which counties have the most breast cancer burden?",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    StressCase(
        "S028",
        "Top counties for stroke",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    StressCase(
        "S029",
        "Where is heart disease highest?",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    StressCase(
        "S030",
        "Which counties are doing worst for diabetes?",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    StressCase(
        "S031",
        "Lowest breast cancer burden counties",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    StressCase(
        "S032",
        "Rank counties by stroke burden",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    StressCase(
        "S033",
        "Where is diabetes burden lowest?",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    StressCase(
        "S034",
        "Counties with highest heart disease YLL",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    StressCase(
        "S035",
        "What county has the highest breast cancer burden?",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),

    # ------------------------------------------------------------
    # RACE / ETHNICITY DISPARITY
    # ------------------------------------------------------------
    StressCase(
        "S036",
        "Compare diabetes between Black and White people",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Race / ethnicity",
        expect_cause=True,
    ),
    StressCase(
        "S037",
        "Are Black people more affected by stroke than White people?",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Race / ethnicity",
        expect_cause=True,
    ),
    StressCase(
        "S038",
        "Black vs White breast cancer burden",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Race / ethnicity",
        expect_cause=True,
    ),
    StressCase(
        "S039",
        "How different are diabetes rates for African Americans and Whites?",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Race / ethnicity",
        expect_cause=True,
    ),
    StressCase(
        "S040",
        "Compare stroke in Latino and White groups",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Race / ethnicity",
        expect_cause=True,
    ),

    # ------------------------------------------------------------
    # SEX DISPARITY
    # ------------------------------------------------------------
    StressCase(
        "S041",
        "Compare stroke between men and women",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Sex",
        expect_cause=True,
    ),
    StressCase(
        "S042",
        "Is diabetes worse for males than females?",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Sex",
        expect_cause=True,
    ),
    StressCase(
        "S043",
        "Breast cancer burden men versus women",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Sex",
        expect_cause=True,
    ),
    StressCase(
        "S044",
        "How different is stroke for women and men?",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Sex",
        expect_cause=True,
    ),
    StressCase(
        "S045",
        "Male female diabetes gap",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Sex",
        expect_cause=True,
    ),

    # ------------------------------------------------------------
    # AGE DISPARITY
    # ------------------------------------------------------------
    StressCase(
        "S046",
        "Compare diabetes ages 60 to 64 and 80 to 84",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Age group",
        expect_cause=True,
    ),
    StressCase(
        "S047",
        "How different is stroke between ages 45 to 49 and 65 to 69?",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Age group",
        expect_cause=True,
    ),
    StressCase(
        "S048",
        "Breast cancer 55 to 59 vs 75 to 79",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Age group",
        expect_cause=True,
    ),
    StressCase(
        "S049",
        "Compare diabetes in people age 50 to 54 with 70 to 74",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Age group",
        expect_cause=True,
    ),
    StressCase(
        "S050",
        "Age gap in stroke 60 to 64 versus 80 to 84",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Age group",
        expect_cause=True,
    ),

    # ------------------------------------------------------------
    # LONG-TERM CHANGE — SEMANTIC RECOGNITION ONLY
    # ------------------------------------------------------------
    StressCase(
        "S051",
        "Which counties improved most since 2000?",
        AnalysisIntent.LONG_TERM_CHANGE,
    ),
    StressCase(
        "S052",
        "Where has diabetes gotten better since 2000?",
        AnalysisIntent.LONG_TERM_CHANGE,
        expect_cause=True,
    ),
    StressCase(
        "S053",
        "Which counties got worse for heart disease?",
        AnalysisIntent.LONG_TERM_CHANGE,
        expect_cause=True,
    ),
    StressCase(
        "S054",
        "Biggest decline in stroke burden by county",
        AnalysisIntent.LONG_TERM_CHANGE,
        expect_cause=True,
    ),
    StressCase(
        "S055",
        "Where did breast cancer burden increase the most?",
        AnalysisIntent.LONG_TERM_CHANGE,
        expect_cause=True,
    ),

    # ------------------------------------------------------------
    # UNSUPPORTED / SAFETY BOUNDARIES
    # ------------------------------------------------------------
    StressCase(
        "S056",
        "Predict diabetes rates in Milwaukee County in 2035",
        AnalysisIntent.UNKNOWN,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S057",
        "Forecast breast cancer in Albany County next year",
        AnalysisIntent.UNKNOWN,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S058",
        "What will stroke burden be in 2030?",
        AnalysisIntent.UNKNOWN,
        expect_cause=True,
    ),
    StressCase(
        "S059",
        "Did obesity cause diabetes to increase in Milwaukee County?",
        AnalysisIntent.UNKNOWN,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S060",
        "Is the Black White diabetes gap statistically significant?",
        AnalysisIntent.UNKNOWN,
        expect_cause=True,
    ),
    StressCase(
        "S061",
        "Give me the p value for the male female stroke difference",
        AnalysisIntent.UNKNOWN,
        expect_cause=True,
    ),
    StressCase(
        "S062",
        "Run a hypothesis test on breast cancer disparities",
        AnalysisIntent.UNKNOWN,
        expect_cause=True,
    ),
    StressCase(
        "S063",
        "What causes breast cancer in Milwaukee County?",
        AnalysisIntent.UNKNOWN,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S064",
        "Will diabetes get worse in Albany County?",
        AnalysisIntent.UNKNOWN,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S065",
        "Estimate Milwaukee County diabetes in 2040",
        AnalysisIntent.UNKNOWN,
        expect_county=True,
        expect_cause=True,
    ),

    # ------------------------------------------------------------
    # AMBIGUITY / INCOMPLETE REQUESTS
    # ------------------------------------------------------------
    StressCase(
        "S066",
        "Compare them",
        AnalysisIntent.UNKNOWN,
        should_need_clarification=True,
    ),
    StressCase(
        "S067",
        "How bad is it?",
        AnalysisIntent.UNKNOWN,
        should_need_clarification=True,
    ),
    StressCase(
        "S068",
        "What about Milwaukee?",
        AnalysisIntent.COUNTY_PROFILE,
        expect_county=True,
    ),
StressCase(
    "S069",
    "Show me the trend",
    AnalysisIntent.TREND_COMPARISON,
    should_need_clarification=True,
),
StressCase(
    "S070",
    "Which counties are worst?",
    AnalysisIntent.COUNTY_RANKING,
    should_need_clarification=True,
),

    # ------------------------------------------------------------
    # CASUAL / IMPERFECT LANGUAGE
    # ------------------------------------------------------------
    StressCase(
        "S071",
        "whats diabetes like in milwaukee county wisconsin",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S072",
        "breast cancer milwaukee county pls",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S073",
        "did stroke go up in yuma county",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S074",
        "where diabetes worst",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    StressCase(
        "S075",
        "black white diabetes difference",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Race / ethnicity",
        expect_cause=True,
    ),
    StressCase(
        "S076",
        "men women stroke comparison",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Sex",
        expect_cause=True,
    ),
    StressCase(
        "S077",
        "diabetes 60-64 vs 80-84",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Age group",
        expect_cause=True,
    ),
    StressCase(
        "S078",
        "milwaukee health",
        AnalysisIntent.COUNTY_PROFILE,
        expect_county=True,
    ),
    StressCase(
        "S079",
        "heart disease albany trend",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    StressCase(
        "S080",
        "top stroke counties",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
]


def main() -> None:
    parser = OpenAISemanticParser()

    failures: list[str] = []
    passed = 0

    print("=" * 110)
    print("EpiCounty Semantic Stress Matrix")
    print("=" * 110)

    for case in CASES:
        result = parser.parse(
            ResearchQuestion(
                raw_text=case.question
            )
        )

        errors: list[str] = []

        if result.intent != case.expected_intent:
            errors.append(
                f"expected intent "
                f"{case.expected_intent.value}, "
                f"received {result.intent.value}"
            )

        if (
            case.expected_dimension is not None
            and result.demographic_dimension
            != case.expected_dimension
        ):
            errors.append(
                f"expected dimension "
                f"{case.expected_dimension!r}, "
                f"received "
                f"{result.demographic_dimension!r}"
            )

        if (
            case.expect_county
            and not result.county_name
        ):
            errors.append(
                "expected county extraction"
            )

        if (
            case.expect_cause
            and not result.cause_name
        ):
            errors.append(
                "expected cause extraction"
            )

        if (
            case.should_need_clarification
            is not None
            and result.needs_clarification
            != case.should_need_clarification
        ):
            errors.append(
                "expected needs_clarification="
                f"{case.should_need_clarification}, "
                "received "
                f"{result.needs_clarification}"
            )

        status = (
            "PASS"
            if not errors
            else "FAIL"
        )

        print("-" * 110)
        print(
            f"{case.case_id} {status}: "
            f"{case.question}"
        )
        print(
            "Intent:",
            result.intent.value,
        )
        print(
            "Confidence:",
            result.confidence,
        )
        print(
            "County:",
            result.county_name,
        )
        print(
            "Cause:",
            result.cause_name,
        )
        print(
            "Dimension:",
            result.demographic_dimension,
        )
        print(
            "Groups:",
            result.demographic_groups,
        )
        print(
            "Needs clarification:",
            result.needs_clarification,
        )

        if result.clarification_question:
            print(
                "Clarification:",
                result.clarification_question,
            )

        if errors:
            for error in errors:
                print(
                    "ERROR:",
                    error,
                )

            failures.append(
                f"{case.case_id}: "
                + "; ".join(errors)
            )
        else:
            passed += 1

    print()
    print("=" * 110)
    print("SUMMARY")
    print("=" * 110)
    print(f"Passed: {passed}")
    print(f"Failed: {len(failures)}")
    print(f"Total:  {len(CASES)}")

    if failures:
        print()
        print("FAILURES:")
        for failure in failures:
            print("-", failure)

        raise AssertionError(
            "Semantic stress matrix failed."
        )

    print()
    print(
        f"SEMANTIC STRESS MATRIX: "
        f"ALL {len(CASES)} CASES PASSED"
    )
    print("=" * 110)


if __name__ == "__main__":
    main()