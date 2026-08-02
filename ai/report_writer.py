from __future__ import annotations

from ai.evidence import interpret_evidence
from ai.models import (
    AnalysisIntent,
    EvidenceBundle,
    ResearchReport,
)


def _report_title(
    bundle: EvidenceBundle,
) -> str:
    title_map = {
        AnalysisIntent.COUNTY_PROFILE:
            "County Public Health Profile",
        AnalysisIntent.TREND_COMPARISON:
            "County Disease-Burden Trend Report",
        AnalysisIntent.DEMOGRAPHIC_DISPARITY:
            "County Demographic Disparity Report",
        AnalysisIntent.COUNTY_RANKING:
            "National County Ranking Report",
        AnalysisIntent.LONG_TERM_CHANGE:
            "Long-Term County Change Report",
    }

    return title_map.get(
        bundle.intent,
        "CountyHealth Research Report",
    )


def _methods_text(
    bundle: EvidenceBundle,
) -> str:
    methods_map = {
        AnalysisIntent.COUNTY_PROFILE: (
            "The analysis combined county-level BMI indicators, "
            "high-BMI-attributable years-of-life-lost rates, "
            "leading-cause rankings, and long-term cause change. "
            "Only validated current-county records were used."
        ),
        AnalysisIntent.TREND_COMPARISON: (
            "The analysis examined annual county-level "
            "high-BMI-attributable years-of-life-lost rates over "
            "the requested period. Absolute and relative changes "
            "were calculated from the first and last available years."
        ),
        AnalysisIntent.DEMOGRAPHIC_DISPARITY: (
            "The analysis compared two demographic groups using "
            "county-level high-BMI-attributable years-of-life-lost "
            "rates. The signed gap was calculated as Group A minus "
            "Group B. Positive values indicate higher burden in "
            "Group A, while negative values indicate higher burden "
            "in Group B."
        ),
        AnalysisIntent.COUNTY_RANKING: (
            "The analysis ranked harmonized current U.S. counties "
            "by high-BMI-attributable years-of-life-lost rate for "
            "the selected cause and year."
        ),
    }

    return methods_map.get(
        bundle.intent,
        (
            "The report was generated from validated analytical "
            "outputs in the CountyHealth Research Copilot."
        ),
    )


def _limitations(
    bundle: EvidenceBundle,
) -> list[str]:
    limitations = [
        (
            "The results are descriptive and do not establish "
            "causation."
        ),
        (
            "County estimates may contain uncertainty, suppression, "
            "or unavailable demographic combinations."
        ),
        (
            "Differences were not treated as statistically significant "
            "unless formal statistical testing was separately performed."
        ),
        (
            "The analysis should be interpreted alongside the original "
            "IHME data-release documentation."
        ),
    ]

    if bundle.intent == AnalysisIntent.DEMOGRAPHIC_DISPARITY:
        limitations.append(
            (
                "Relative disparity estimates use Group B as the "
                "reference denominator."
            )
        )

    return limitations


def write_research_report(
    bundle: EvidenceBundle,
) -> ResearchReport:
    """
    Convert an evidence bundle into a structured, deterministic
    research report.

    No generative model is used at this stage.
    """
    findings = interpret_evidence(bundle)

    if not findings:
        raise ValueError(
            "The evidence bundle produced no findings."
        )

    executive_summary = " ".join(
        findings[:3]
    )

    return ResearchReport(
        title=_report_title(bundle),
        question=bundle.question.raw_text,
        executive_summary=executive_summary,
        methods=_methods_text(bundle),
        findings=findings,
        limitations=_limitations(bundle),
        evidence=bundle,
    )


def report_to_markdown(
    report: ResearchReport,
) -> str:
    """
    Render a structured report as Markdown.
    """
    finding_lines = "\n".join(
        f"- {finding}"
        for finding in report.findings
    )

    limitation_lines = "\n".join(
        f"- {limitation}"
        for limitation in report.limitations
    )

    warning_lines = ""

    if report.evidence.warnings:
        warning_lines = "\n\n## Data Warnings\n\n" + "\n".join(
            f"- {warning}"
            for warning in report.evidence.warnings
        )

    return f"""# {report.title}

## Research Question

{report.question}

## Executive Summary

{report.executive_summary}

## Methods

{report.methods}

## Key Findings

{finding_lines}

## Limitations

{limitation_lines}{warning_lines}

## Analytical Provenance

This report was generated from validated CountyHealth Research Copilot
analytics. The underlying evidence bundle contains the source function,
parameters, and returned analytical dataset for each finding.
"""