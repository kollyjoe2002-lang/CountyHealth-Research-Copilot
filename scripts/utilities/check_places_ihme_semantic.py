from __future__ import annotations

from typing import Any, cast

from ai.models import (
    AnalysisIntent,
    ResearchQuestion,
    SemanticAnalysisRequest,
)
from ai.research_assistant import run_research_assistant


def _run_case(
    case_id: str,
    description: str,
    semantic_request: SemanticAnalysisRequest,
) -> tuple[bool, str]:
    print("-" * 100)
    print(f"{case_id}: {description}")

    class FixedSemanticParser:
        def __init__(
            self,
            request: SemanticAnalysisRequest,
        ) -> None:
            self.request = request

        def parse(
            self,
            question: ResearchQuestion,
        ) -> SemanticAnalysisRequest:
            return self.request

    fixed_parser = cast(Any, FixedSemanticParser(semantic_request))
    outcome = run_research_assistant(
        semantic_request.question.raw_text,
        semantic_parser=fixed_parser,
    )

    if case_id == "P03":
        if outcome.status != "clarify":
            return (
                False,
                f"Expected safe clarification, got {outcome.status}.",
            )

        if outcome.evidence_bundle is not None:
            return (
                False,
                "P03 unexpectedly produced analytical evidence.",
            )

        return True, "PASS: safely clarified"

    if case_id == "P04":
        if outcome.status != "clarify":
            return (
                False,
                f"Expected safe clarification, got {outcome.status}.",
            )

        if outcome.evidence_bundle is not None:
            return (
                False,
                "P04 unexpectedly produced analytical evidence.",
            )

        expected_message = (
            "STROKE and IHME cause 976"
        )

        if expected_message not in (
            outcome.clarification_question or ""
        ):
            return (
                False,
                "P04 did not report the expected incompatible pair.",
            )

        return True, "PASS: incompatible pair blocked"
    expected_pairs = {
        "P01": ("DIABETES", 976),
        "P02": ("DIABETES", 976),
        "P05": ("STROKE", 494),
        "P06": ("CASTHMA", 515),
    }

    expected_pair = expected_pairs.get(
        case_id
    )

    if outcome.status != "answer":
        return (
            False,
            f"Expected answer status, got {outcome.status}: "
            f"{outcome.ai_error or outcome.rejection_reason}",
        )

    if outcome.resolved_plan is None:
        return False, "No resolved plan returned."

    if outcome.evidence_bundle is None:
        return False, "No evidence bundle returned."

    bundle = outcome.evidence_bundle

    if expected_pair is not None:
        expected_measure_id, expected_cause_id = (
            expected_pair
        )

        context = outcome.evidence_bundle.context

        if context.get("places_measure_id") != expected_measure_id:
            return (
                False,
                f"Expected PLACES {expected_measure_id}, got "
                f"{context.get('places_measure_id')}.",
            )

        if context.get("cause_id") != expected_cause_id:
            return (
                False,
                f"Expected IHME cause {expected_cause_id}, got "
                f"{context.get('cause_id')}.",
            )

    if bundle.context.get("evidence_domain") != "PLACES_IHME":
        return False, "Incorrect evidence domain."

    if len(bundle.items) != 1:
        return (
            False,
            f"Expected one evidence item, got {len(bundle.items)}.",
        )

    item = bundle.items[0]

    if (
        item.source_function
        != "get_places_ihme_county_trend_context"
    ):
        return (
            False,
            "Unexpected evidence source function: "
            f"{item.source_function}",
        )

    data = item.data

    if not hasattr(data, "columns"):
        return False, "Expected dataframe evidence."

    years = set(
        int(year)
        for year in data["analysis_year"].tolist()
    )

    if case_id == "P01":
        if years != {2018, 2019}:
            return (
                False,
                f"P01 returned unexpected years: {sorted(years)}",
            )

        if not data["places_available"].all():
            return False, "P01 has missing PLACES evidence."

        if not data["ihme_available"].all():
            return False, "P01 has missing IHME evidence."

        if not data["same_year_overlap"].all():
            return False, "P01 expected overlap in both years."

    elif case_id == "P02":
        if years != {
            2018,
            2019,
            2020,
            2021,
            2022,
            2023,
        }:
            return (
                False,
                f"P02 returned unexpected years: {sorted(years)}",
            )

        if not data["places_available"].all():
            return False, "P02 should have PLACES in all years."

        overlap_years = set(
            int(year)
            for year in data.loc[
                data["same_year_overlap"],
                "analysis_year",
            ].tolist()
        )

        if overlap_years != {2018, 2019}:
            return (
                False,
                "P02 overlap years were "
                f"{sorted(overlap_years)}.",
            )

        post_2019 = data[
            data["analysis_year"] > 2019
        ]

        if post_2019["ihme_available"].any():
            return (
                False,
                "P02 unexpectedly reports IHME availability "
                "after 2019."
            )

        if post_2019["ihme_yll_rate"].notna().any():
            return (
                False,
                "P02 contains IHME YLL values after 2019."
            )

    return True, "PASS"


def main() -> None:
    print("=" * 100)
    print("EpiCounty PLACES_IHME Semantic Validation")
    print("=" * 100)

    cases = [
        (
            "P01",
            "Milwaukee diabetes cross-source trend, 2018-2019",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "Compare CDC PLACES diabetes prevalence "
                        "with IHME diabetes burden in Milwaukee "
                        "County, Wisconsin from 2018 to 2019."
                    )
                ),
                intent=AnalysisIntent.TREND_COMPARISON,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name="diabetes",
                start_year=2018,
                end_year=2019,
                evidence_domain="PLACES_IHME",
                explanation="Explicit cross-source county trend request.",
            ),
        ),
        (
            "P02",
            "Milwaukee diabetes cross-source trend, 2018-2023",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "Compare CDC PLACES diabetes prevalence "
                        "with IHME diabetes burden in Milwaukee "
                        "County, Wisconsin from 2018 to 2023."
                    )
                ),
                intent=AnalysisIntent.TREND_COMPARISON,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name="diabetes",
                start_year=2018,
                end_year=2023,
                evidence_domain="PLACES_IHME",
                explanation="Explicit cross-source county trend request.",
            ),
        ),
        (
            "P03",
            "Milwaukee breast cancer cross-source request fails safely",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "Compare CDC PLACES breast cancer prevalence "
                        "with IHME breast cancer burden in Milwaukee "
                        "County, Wisconsin from 2018 to 2019."
                    )
                ),
                intent=AnalysisIntent.TREND_COMPARISON,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name="breast cancer",
                start_year=2018,
                end_year=2019,
                evidence_domain="PLACES_IHME",
                explanation=(
                    "Explicit cross-source breast cancer trend request."
                ),
            ),
        ),
        (
            "P04",
            "Incompatible PLACES and IHME concepts fail safely",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "Compare CDC PLACES stroke prevalence "
                        "with IHME diabetes burden in Milwaukee "
                        "County, Wisconsin from 2018 to 2019."
                    )
                ),
                intent=AnalysisIntent.TREND_COMPARISON,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name="diabetes",
                start_year=2018,
                end_year=2019,
                evidence_domain="PLACES_IHME",
                explanation=(
                    "Deliberately incompatible cross-source concepts."
                ),
            ),
        ),
        (
            "P05",
            "Milwaukee stroke cross-source trend",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "Compare CDC PLACES stroke prevalence "
                        "with IHME stroke burden in Milwaukee "
                        "County, Wisconsin from 2018 to 2019."
                    )
                ),
                intent=AnalysisIntent.TREND_COMPARISON,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name="stroke",
                start_year=2018,
                end_year=2019,
                evidence_domain="PLACES_IHME",
                explanation=(
                    "Validated cross-source stroke trend request."
                ),
            ),
        ),
        (
            "P06",
            "Milwaukee asthma cross-source trend",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "Compare CDC PLACES asthma prevalence "
                        "with IHME asthma burden in Milwaukee "
                        "County, Wisconsin from 2018 to 2019."
                    )
                ),
                intent=AnalysisIntent.TREND_COMPARISON,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name="asthma",
                start_year=2018,
                end_year=2019,
                evidence_domain="PLACES_IHME",
                explanation=(
                    "Validated cross-source asthma trend request."
                ),
            ),
        ),
    ]

    passed = 0
    failed = 0

    for case_id, description, semantic_request in cases:
        ok, message = _run_case(
            case_id,
            description,
            semantic_request,
        )

        if ok:
            passed += 1
            print(message)
        else:
            failed += 1
            print("FAIL")
            print(message)

    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")

    if failed:
        raise SystemExit(1)

    print()
    print(
        "PLACES_IHME SEMANTIC VALIDATION: "
        "ALL CASES PASSED"
    )


if __name__ == "__main__":
    main()
