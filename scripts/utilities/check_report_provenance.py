from __future__ import annotations

from ai.exporter import _data_source_note
from ai.models import (
    AnalysisIntent,
    EvidenceBundle,
    EvidenceItem,
    ResearchQuestion,
    ResearchReport,
)
from ai.report_writer import (
    _limitations,
    _methods_text,
)


def _bundle(
    *,
    intent: AnalysisIntent,
    evidence_domain: str,
    context: dict | None = None,
) -> EvidenceBundle:
    bundle_context = {
        "evidence_domain": evidence_domain,
    }

    if context:
        bundle_context.update(context)

    return EvidenceBundle(
        question=ResearchQuestion(
            raw_text="Synthetic provenance validation question."
        ),
        intent=intent,
        items=[
            EvidenceItem(
                evidence_type="validation",
                title="Synthetic validation evidence",
                data=None,
                source_function="validation_source",
                parameters={},
            )
        ],
        warnings=[],
        context=bundle_context,
    )


def _report(
    bundle: EvidenceBundle,
) -> ResearchReport:
    return ResearchReport(
        title="Synthetic Validation Report",
        question=bundle.question.raw_text,
        executive_summary="Synthetic validation summary.",
        methods=_methods_text(bundle),
        findings=["Synthetic validation finding."],
        limitations=_limitations(bundle),
        evidence=bundle,
    )


def _contains_all(
    text: str,
    terms: list[str],
) -> bool:
    normalized = text.casefold()

    return all(
        term.casefold() in normalized
        for term in terms
    )


def main() -> int:
    print("=" * 100)
    print("EpiCounty Report Provenance Validation")
    print("=" * 100)

    passed = 0
    total = 6

    # ------------------------------------------------------------------
    # R01: IHME-only report remains IHME-specific.
    # ------------------------------------------------------------------
    ihme_bundle = _bundle(
        intent=AnalysisIntent.TREND_COMPARISON,
        evidence_domain="IHME",
    )

    ihme_report = _report(
        ihme_bundle
    )

    ihme_note = _data_source_note(
        ihme_report
    )

    if (
        "years-of-life-lost" in ihme_report.methods.casefold()
        and "ihme" in ihme_note.casefold()
        and "cdc places" not in ihme_note.casefold()
    ):
        print(
            "R01 PASS: IHME-only report retains IHME provenance."
        )
        passed += 1
    else:
        print(
            "R01 FAIL: IHME-only provenance is incorrect."
        )

    # ------------------------------------------------------------------
    # R02: PLACES report identifies modeled prevalence and year meaning.
    # ------------------------------------------------------------------
    places_bundle = _bundle(
        intent=AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        evidence_domain="PLACES",
    )

    places_report = _report(
        places_bundle
    )

    places_note = _data_source_note(
        places_report
    )

    if (
        _contains_all(
            places_report.methods,
            [
                "CDC PLACES",
                "modeled prevalence",
                "measurement year",
                "release year",
            ],
        )
        and _contains_all(
            places_note,
            [
                "CDC PLACES",
                "measurement year",
                "release year",
            ],
        )
        and "IHME-derived" not in places_note
    ):
        print(
            "R02 PASS: PLACES provenance and year semantics are explicit."
        )
        passed += 1
    else:
        print(
            "R02 FAIL: PLACES provenance is incomplete or incorrect."
        )

    # ------------------------------------------------------------------
    # R03: Cross-source trend keeps PLACES and IHME measures distinct.
    # ------------------------------------------------------------------
    trend_bundle = _bundle(
        intent=AnalysisIntent.TREND_COMPARISON,
        evidence_domain="PLACES_IHME",
    )

    trend_report = _report(
        trend_bundle
    )

    trend_note = _data_source_note(
        trend_report
    )

    if (
        _contains_all(
            trend_report.methods,
            [
                "PLACES",
                "prevalence",
                "IHME",
                "YLL",
                "distinct measures",
            ],
        )
        and _contains_all(
            trend_note,
            [
                "CDC PLACES",
                "IHME",
                "distinct measures",
            ],
        )
    ):
        print(
            "R03 PASS: cross-source trend preserves measure separation."
        )
        passed += 1
    else:
        print(
            "R03 FAIL: cross-source trend provenance is not sufficiently separated."
        )

    # ------------------------------------------------------------------
    # R04: Rurality provenance includes USDA RUCC.
    # ------------------------------------------------------------------
    rurality_bundle = _bundle(
        intent=AnalysisIntent.RURALITY_COMPARISON,
        evidence_domain="PLACES_IHME",
    )

    rurality_report = _report(
        rurality_bundle
    )

    rurality_note = _data_source_note(
        rurality_report
    )

    if (
        _contains_all(
            rurality_report.methods,
            [
                "USDA",
                "Rural-Urban Continuum Codes",
                "CDC PLACES",
                "IHME",
            ],
        )
        and _contains_all(
            rurality_note,
            [
                "CDC PLACES",
                "IHME",
                "USDA",
            ],
        )
    ):
        print(
            "R04 PASS: rurality report includes USDA provenance."
        )
        passed += 1
    else:
        print(
            "R04 FAIL: rurality provenance is incomplete."
        )

    # ------------------------------------------------------------------
    # R05: Cross-source disparity keeps PLACES contextual only.
    # ------------------------------------------------------------------
    disparity_bundle = _bundle(
        intent=AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        evidence_domain="PLACES_IHME",
        context={
            "group_a_name": "Non-Latino, Black",
            "group_b_name": "Non-Latino, White",
            "dimension": "Race / ethnicity",
        },
    )

    disparity_report = _report(
        disparity_bundle
    )

    if (
        _contains_all(
            disparity_report.methods,
            [
                "PLACES",
                "population-health context",
                "IHME",
                "demographic disparity",
                "not interpreted as a demographic disparity measure",
            ],
        )
    ):
        print(
            "R05 PASS: PLACES context is not represented as disparity evidence."
        )
        passed += 1
    else:
        print(
            "R05 FAIL: disparity source roles are not sufficiently explicit."
        )

    # ------------------------------------------------------------------
    # R06: Cross-source limitations explicitly reject causal inference.
    # ------------------------------------------------------------------
    combined_limitations = " ".join(
        trend_report.limitations
    )

    if (
        _contains_all(
            combined_limitations,
            [
                "descriptive",
                "do not establish",
                "PLACES prevalence",
                "IHME burden",
            ],
        )
    ):
        print(
            "R06 PASS: cross-source limitations explicitly reject causal inference."
        )
        passed += 1
    else:
        print(
            "R06 FAIL: cross-source causal guardrail is missing."
        )

    print("=" * 100)
    print(f"REPORT PROVENANCE VALIDATION: {passed}/{total} PASSED")
    print("=" * 100)

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())