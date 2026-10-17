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

    fixed_parser = cast(
        Any,
        FixedSemanticParser(semantic_request),
    )

    outcome = run_research_assistant(
        semantic_request.question.raw_text,
        semantic_parser=fixed_parser,
    )

    # ------------------------------------------------------------
    # P03: PLACES year outside supported measurement-year range
    # ------------------------------------------------------------
    if case_id == "P03":
        if outcome.status != "reject":
            return (
                False,
                f"Expected reject status, got {outcome.status}.",
            )

        if outcome.evidence_bundle is not None:
            return (
                False,
                "P03 unexpectedly produced analytical evidence.",
            )

        return True, "PASS: unsupported PLACES year rejected"

    # ------------------------------------------------------------
    # P04: PLACES-only trend is not yet supported semantically
    # ------------------------------------------------------------
    if case_id == "P04":
        if outcome.status != "reject":
            return (
                False,
                f"Expected reject status, got {outcome.status}.",
            )

        if outcome.evidence_bundle is not None:
            return (
                False,
                "P04 unexpectedly produced analytical evidence.",
            )

        return True, "PASS: unsupported PLACES trend rejected"

    # ------------------------------------------------------------
    # P05: breast cancer must not map to generic PLACES CANCER
    # ------------------------------------------------------------
    if case_id == "P05":
        if outcome.status == "answer":
            return (
                False,
                "P05 unexpectedly produced an answer for breast cancer.",
            )

        if outcome.evidence_bundle is not None:
            return (
                False,
                "P05 unexpectedly produced analytical evidence.",
            )

        return True, "PASS: unsupported breast-cancer mapping blocked"
    if case_id in {"P06", "P07"}:
        if outcome.status != "clarify":
            return (
                False,
                f"Expected clarification, got {outcome.status}.",
            )

        if outcome.evidence_bundle is not None:
            return (
                False,
                f"{case_id} unexpectedly produced analytical evidence.",
            )

        if not outcome.clarification_question:
            return (
                False,
                f"{case_id} did not return a clarification question.",
            )

        return True, "PASS: missing required entity safely clarified"

    # ------------------------------------------------------------
    # P01 / P02: supported PLACES county prevalence snapshots
    # ------------------------------------------------------------
    if outcome.status != "answer":
        return (
            False,
            f"Expected answer status, got {outcome.status}: "
            f"{outcome.ai_error or outcome.rejection_reason}",
        )

    if outcome.ai_error is not None:
        return (
            False,
            f"Unexpected AI interpretation error: {outcome.ai_error}",
        )

    if outcome.resolved_plan is None:
        return False, "No resolved plan returned."

    if outcome.evidence_bundle is None:
        return False, "No evidence bundle returned."

    bundle = outcome.evidence_bundle

    if bundle.context.get("evidence_domain") != "PLACES":
        return False, "Incorrect evidence domain."

    if bundle.context.get("places_measure_id") != "DIABETES":
        return (
            False,
            "Expected PLACES DIABETES measure, got "
            f"{bundle.context.get('places_measure_id')}.",
        )

    if bundle.context.get("measurement_year") != 2023:
        return (
            False,
            "Expected canonical measurement year 2023, got "
            f"{bundle.context.get('measurement_year')}.",
        )

    if len(bundle.items) != 1:
        return (
            False,
            f"Expected one evidence item, got {len(bundle.items)}.",
        )

    item = bundle.items[0]

    if item.source_function != "get_places_county_measure_trend":
        return (
            False,
            "Unexpected evidence source function: "
            f"{item.source_function}",
        )

    data = item.data

    if not hasattr(data, "columns"):
        return False, "Expected dataframe evidence."

    if len(data) != 1:
        return (
            False,
            f"Expected exactly one PLACES observation, got {len(data)}.",
        )

    row = data.iloc[0]

    if int(row["measurement_year"]) != 2023:
        return (
            False,
            "Evidence did not use measurement year 2023.",
        )

    if bool(row["carry_forward"]):
        return (
            False,
            "Canonical PLACES snapshot included a carry-forward row.",
        )

    if str(row["measure_id"]) != "DIABETES":
        return (
            False,
            f"Unexpected measure ID: {row['measure_id']}.",
        )

    prevalence = float(
        row["age_adjusted_prevalence"]
    )

    if abs(prevalence - 12.4) > 0.0001:
        return (
            False,
            f"Unexpected age-adjusted prevalence: {prevalence}.",
        )

    if outcome.interpretation_input is None:
        return False, "No interpretation input returned."

    claim_ids = {
        claim.claim_id
        for claim in outcome.interpretation_input.claims
    }

    required_claim_ids = {
        "snapshot.context",
        "snapshot.places_prevalence",
        "snapshot.places_confidence_interval",
        "snapshot.places_release_provenance",
        "snapshot.places_carry_forward",
    }

    missing_claim_ids = required_claim_ids.difference(
        claim_ids
    )

    if missing_claim_ids:
        return (
            False,
            "Missing expected PLACES claim IDs: "
            f"{sorted(missing_claim_ids)}.",
        )

    if outcome.interpretation_result is None:
        return False, "No validated interpretation returned."

    limitations = " ".join(
        outcome.interpretation_result.limitations
    )

    if "IHME" in limitations:
        return (
            False,
            "PLACES-only interpretation contains IHME limitation text.",
        )

    if "CDC PLACES" not in limitations:
        return (
            False,
            "PLACES-specific limitation was not present.",
        )

    if case_id == "P02":
        assumptions = " ".join(
            outcome.resolved_plan.assumptions
        ).lower()

        if "no year was specified" not in assumptions:
            return (
                False,
                "P02 did not record the default-year assumption.",
            )

    return True, "PASS"


def main() -> None:
    print("=" * 100)
    print("EpiCounty PLACES Semantic Validation")
    print("=" * 100)

    cases = [
        (
            "P01",
            "Milwaukee diabetes PLACES snapshot, explicit 2023",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "What was the CDC PLACES diabetes prevalence "
                        "in Milwaukee County, Wisconsin in 2023?"
                    )
                ),
                intent=AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name="diabetes",
                year=2023,
                evidence_domain="PLACES",
                explanation=(
                    "Explicit CDC PLACES county prevalence snapshot."
                ),
            ),
        ),
        (
            "P02",
            "Milwaukee diabetes PLACES snapshot, default year",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "What is the CDC PLACES diabetes prevalence "
                        "in Milwaukee County, Wisconsin?"
                    )
                ),
                intent=AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name="diabetes",
                year=None,
                evidence_domain="PLACES",
                explanation=(
                    "CDC PLACES snapshot without an explicit year."
                ),
            ),
        ),
        (
            "P03",
            "Milwaukee diabetes PLACES snapshot, unsupported 2024",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "What was the CDC PLACES diabetes prevalence "
                        "in Milwaukee County, Wisconsin in 2024?"
                    )
                ),
                intent=AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name="diabetes",
                year=2024,
                evidence_domain="PLACES",
                explanation=(
                    "CDC PLACES snapshot outside supported "
                    "measurement-year range."
                ),
            ),
        ),
        (
            "P04",
            "PLACES-only diabetes trend remains unsupported",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "How did CDC PLACES diabetes prevalence change "
                        "in Milwaukee County, Wisconsin from 2018 to 2023?"
                    )
                ),
                intent=AnalysisIntent.TREND_COMPARISON,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name="diabetes",
                start_year=2018,
                end_year=2023,
                evidence_domain="PLACES",
                explanation=(
                    "PLACES-only trend request is intentionally "
                    "not yet supported."
                ),
            ),
        ),
        (
            "P05",
            "Breast cancer must not map to generic PLACES cancer",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "What was the CDC PLACES breast cancer "
                        "prevalence in Milwaukee County, Wisconsin "
                        "in 2023?"
                    )
                ),
                intent=AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name="breast cancer",
                year=2023,
                evidence_domain="PLACES",
                explanation=(
                    "Breast cancer is not an approved PLACES "
                    "measure alias."
                ),
            ),
        ),
        (
            "P06",
            "PLACES snapshot missing county",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "What was the CDC PLACES diabetes prevalence "
                        "in 2023?"
                    )
                ),
                intent=AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
                confidence=1.0,
                county_name=None,
                cause_name="diabetes",
                year=2023,
                evidence_domain="PLACES",
                explanation=(
                    "CDC PLACES snapshot missing required county."
                ),
            ),
        ),
        (
            "P07",
            "PLACES snapshot missing disease or health measure",
            SemanticAnalysisRequest(
                question=ResearchQuestion(
                    raw_text=(
                        "What was the CDC PLACES prevalence "
                        "in Milwaukee County, Wisconsin in 2023?"
                    )
                ),
                intent=AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
                confidence=1.0,
                county_name="Milwaukee County, Wisconsin",
                cause_name=None,
                year=2023,
                evidence_domain="PLACES",
                explanation=(
                    "CDC PLACES snapshot missing required "
                    "disease or health measure."
                ),
            ),
        ),
    ]

    passed = 0

    for case_id, description, request in cases:
        ok, message = _run_case(
            case_id,
            description,
            request,
        )

        print(message)

        if ok:
            passed += 1

    print("=" * 100)
    print(f"RESULT: {passed}/{len(cases)} PASS")
    print("=" * 100)

    if passed != len(cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
