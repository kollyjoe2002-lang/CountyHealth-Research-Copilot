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
class SemanticCase:
    case_id: str
    question: str
    expected_intent: AnalysisIntent
    expected_dimension: str | None = None
    expect_county: bool = False
    expect_cause: bool = False


CASES = [
    SemanticCase(
        "S01",
        "Breast cancer in Milwaukee County, Wisconsin",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    SemanticCase(
        "S02",
        "What's going on with diabetes in Albany County, Wyoming?",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    SemanticCase(
        "S03",
        "Is stroke getting worse in Yuma County, Arizona?",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    SemanticCase(
        "S04",
        "Where is breast cancer worst?",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    SemanticCase(
        "S05",
        "Are Black people more affected by diabetes than White people?",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Race / ethnicity",
        expect_cause=True,
    ),
    SemanticCase(
        "S06",
        "Which counties have gotten better for heart disease since 2000?",
        AnalysisIntent.LONG_TERM_CHANGE,
        expect_cause=True,
    ),
    SemanticCase(
        "S07",
        "Tell me how Milwaukee County, Wisconsin is doing",
        AnalysisIntent.COUNTY_PROFILE,
        expect_county=True,
    ),
    SemanticCase(
        "S08",
        "What is the diabetes burden in Milwaukee County?",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    SemanticCase(
        "S09",
        "Show me diabetes in Milwaukee County, Wisconsin",
        AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        expect_county=True,
        expect_cause=True,
    ),
    SemanticCase(
        "S10",
        "How has breast cancer changed in Milwaukee County?",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    SemanticCase(
        "S11",
        "Which counties have the highest diabetes burden?",
        AnalysisIntent.COUNTY_RANKING,
        expect_cause=True,
    ),
    SemanticCase(
        "S12",
        "Compare stroke between men and women",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Sex",
        expect_cause=True,
    ),
    SemanticCase(
        "S13",
        "How different is diabetes between ages 60 to 64 and 80 to 84?",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        expected_dimension="Age group",
        expect_cause=True,
    ),
    SemanticCase(
        "S14",
        "What happened to ischemic heart disease in Albany County from 2000 to 2019?",
        AnalysisIntent.TREND_COMPARISON,
        expect_county=True,
        expect_cause=True,
    ),
    SemanticCase(
        "S15",
        "Predict diabetes rates in Milwaukee County in 2035",
        AnalysisIntent.UNKNOWN,
        expect_county=True,
        expect_cause=True,
    ),
]


def main() -> None:
    parser = OpenAISemanticParser()

    failures: list[str] = []

    print("=" * 100)
    print("EpiCounty Semantic Parser Validation")
    print("=" * 100)

    for case in CASES:
        result = parser.parse(
            ResearchQuestion(
                raw_text=case.question
            )
        )

        errors: list[str] = []

        if result.intent != case.expected_intent:
            errors.append(
                f"intent expected "
                f"{case.expected_intent.value}, "
                f"received {result.intent.value}"
            )

        if (
            case.expected_dimension is not None
            and result.demographic_dimension
            != case.expected_dimension
        ):
            errors.append(
                "dimension expected "
                f"{case.expected_dimension!r}, "
                "received "
                f"{result.demographic_dimension!r}"
            )

        if (
            case.expect_county
            and not result.county_name
        ):
            errors.append(
                "county was not extracted"
            )

        if (
            case.expect_cause
            and not result.cause_name
        ):
            errors.append(
                "cause was not extracted"
            )

        status = (
            "PASS"
            if not errors
            else "FAIL"
        )

        print("-" * 100)
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

        if errors:
            for error in errors:
                print("ERROR:", error)

            failures.append(
                f"{case.case_id}: "
                + "; ".join(errors)
            )

    print()
    print("=" * 100)

    if failures:
        print(
            f"SEMANTIC PARSER: "
            f"{len(CASES) - len(failures)}/"
            f"{len(CASES)} PASS"
        )

        for failure in failures:
            print(" -", failure)

        raise AssertionError(
            "Semantic-parser validation failed."
        )

    print(
        f"SEMANTIC PARSER: "
        f"ALL {len(CASES)} CASES PASSED"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()