from __future__ import annotations

from typing import Any, cast

from ai.evidence import interpret_evidence
from ai.models import (
    AnalysisIntent,
    ResearchQuestion,
    SemanticAnalysisRequest,
)
from ai.research_assistant import run_research_assistant


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


def run_request(
    request: SemanticAnalysisRequest,
) -> tuple[object, list[str]]:
    parser = cast(
        Any,
        FixedSemanticParser(request),
    )

    outcome = run_research_assistant(
        request.question.raw_text,
        semantic_parser=parser,
    )

    if outcome.status != "answer":
        raise AssertionError(
            f"Expected answer, got {outcome.status}: "
            f"{outcome.ai_error or outcome.rejection_reason}"
        )

    if outcome.evidence_bundle is None:
        raise AssertionError(
            "Missing evidence bundle."
        )

    findings = interpret_evidence(
        outcome.evidence_bundle
    )

    return outcome, findings


def joined(findings: list[str]) -> str:
    return " ".join(findings).casefold()


def check(
    case_id: str,
    description: str,
    test,
) -> bool:
    print("-" * 100)
    print(f"{case_id}: {description}")

    try:
        test()
    except Exception as exc:
        print("FAIL:", exc)
        return False

    print("PASS")
    return True


def places_snapshot():
    request = SemanticAnalysisRequest(
        question=ResearchQuestion(
            raw_text=(
                "What was the CDC PLACES diabetes prevalence "
                "in Milwaukee County, Wisconsin in 2019?"
            )
        ),
        intent=AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        confidence=1.0,
        county_name="Milwaukee County, Wisconsin",
        cause_name="diabetes",
        year=2019,
        evidence_domain="PLACES",
        explanation="Evidence-language guardrail validation.",
    )

    return run_request(request)


def ihme_snapshot():
    request = SemanticAnalysisRequest(
        question=ResearchQuestion(
            raw_text=(
                "What was the type 2 diabetes YLL rate "
                "in Milwaukee County, Wisconsin in 2019?"
            )
        ),
        intent=AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
        confidence=1.0,
        county_name="Milwaukee County, Wisconsin",
        cause_name="type 2 diabetes",
        year=2019,
        evidence_domain="IHME",
        explanation="Evidence-language guardrail validation.",
    )

    return run_request(request)


def cross_source_trend():
    request = SemanticAnalysisRequest(
        question=ResearchQuestion(
            raw_text=(
                "Compare CDC PLACES diabetes prevalence with "
                "IHME type 2 diabetes burden in Milwaukee County, "
                "Wisconsin from 2018 to 2019."
            )
        ),
        intent=AnalysisIntent.TREND_COMPARISON,
        confidence=1.0,
        county_name="Milwaukee County, Wisconsin",
        cause_name="type 2 diabetes",
        start_year=2018,
        end_year=2019,
        evidence_domain="PLACES_IHME",
        explanation="Evidence-language guardrail validation.",
    )

    return run_request(request)


def rurality_comparison():
    request = SemanticAnalysisRequest(
        question=ResearchQuestion(
            raw_text=(
                "Compare CDC PLACES diabetes prevalence and "
                "IHME type 2 diabetes burden by rurality "
                "across U.S. counties in 2019."
            )
        ),
        intent=AnalysisIntent.RURALITY_COMPARISON,
        confidence=1.0,
        county_name=None,
        cause_name="type 2 diabetes",
        year=2019,
        geographic_scope="United States",
        evidence_domain="PLACES_IHME",
        explanation="Evidence-language guardrail validation.",
    )

    return run_request(request)


def disparity_comparison():
    request = SemanticAnalysisRequest(
        question=ResearchQuestion(
            raw_text=(
                "Compare CDC PLACES diabetes prevalence with the "
                "Black-White IHME type 2 diabetes YLL disparity "
                "across U.S. counties in 2019."
            )
        ),
        intent=AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        confidence=1.0,
        county_name=None,
        cause_name="type 2 diabetes",
        year=2019,
        demographic_dimension="Race / ethnicity",
        demographic_groups=[
            "Non-Latino, Black",
            "Non-Latino, White",
        ],
        geographic_scope="United States",
        evidence_domain="PLACES_IHME",
        explanation="Evidence-language guardrail validation.",
    )

    return run_request(request)


def main() -> None:
    print("=" * 100)
    print("EpiCounty Evidence-Language Guardrail Validation")
    print("=" * 100)

    cache: dict[str, tuple[object, list[str]]] = {}

    def get(name: str):
        if name not in cache:
            functions = {
                "places": places_snapshot,
                "ihme": ihme_snapshot,
                "trend": cross_source_trend,
                "rurality": rurality_comparison,
                "disparity": disparity_comparison,
            }
            cache[name] = functions[name]()

        return cache[name]

    def g01():
        _, findings = get("places")
        text = joined(findings)

        assert "cdc places age-adjusted prevalence" in text
        assert "brfss measurement year 2019" in text
        assert "burden" not in text

    def g02():
        _, findings = get("places")
        text = joined(findings)

        assert "95% confidence interval" in text
        assert "uncertainty interval" not in text

    def g03():
        _, findings = get("ihme")
        text = joined(findings)

        assert "yll rate" in text
        assert "uncertainty interval" in text
        assert "95% confidence interval" not in text

    def g04():
        _, findings = get("trend")
        text = joined(findings)

        assert "cdc places age-adjusted prevalence" in text
        assert "ihme yll rate" in text
        assert "different measures" in text

    def g05():
        _, findings = get("trend")
        text = joined(findings)

        assert (
            "do not by themselves establish a causal relationship"
            in text
        )

    def g06():
        _, findings = get("rurality")
        text = joined(findings)

        assert "distinct measures" in text
        assert "descriptive" in text
        assert "do not establish a causal relationship" in text

    def g07():
        _, findings = get("disparity")
        text = joined(findings)

        assert (
            "does not represent the demographic disparity itself"
            in text
        )

    def g08():
        _, findings = get("disparity")
        text = joined(findings)

        assert (
            "demographic disparity is derived from ihme yll rates"
            in text
        )

    def g09():
        _, findings = get("places")

        for finding in findings:
            lowered = finding.casefold()

            if "cdc places" in lowered:
                assert "burden" not in lowered

    def g10():
        cross_source_names = [
            "trend",
            "rurality",
            "disparity",
        ]

        prohibited_positive_phrases = [
            "caused by",
            "causes the",
            "caused the",
            "causal effect",
            "drives",
            "led to",
            "leads to",
            "because of",
            "associated with",
            "association between",
        ]

        for name in cross_source_names:
            _, findings = get(name)

            for finding in findings:
                lowered = finding.casefold()

                for phrase in prohibited_positive_phrases:
                    assert phrase not in lowered, (
                        f"{name} contains prohibited causal/"
                        f"association wording: {finding}"
                    )

    tests = [
        (
            "G01",
            "PLACES uses prevalence and BRFSS measurement year",
            g01,
        ),
        (
            "G02",
            "PLACES interval is labeled 95% confidence interval",
            g02,
        ),
        (
            "G03",
            "IHME uses YLL rate and uncertainty interval",
            g03,
        ),
        (
            "G04",
            "Cross-source trend keeps prevalence and YLL distinct",
            g04,
        ),
        (
            "G05",
            "Cross-source trend rejects causal interpretation",
            g05,
        ),
        (
            "G06",
            "Rurality evidence is descriptive and non-causal",
            g06,
        ),
        (
            "G07",
            "PLACES context is not demographic disparity",
            g07,
        ),
        (
            "G08",
            "Demographic disparity derives from IHME YLL",
            g08,
        ),
        (
            "G09",
            "PLACES prevalence is never labeled burden",
            g09,
        ),
        (
            "G10",
            "Cross-source findings contain no positive causal language",
            g10,
        ),
    ]

    results = [
        check(case_id, description, test)
        for case_id, description, test in tests
    ]

    passed = sum(results)
    total = len(results)

    print("=" * 100)
    print(
        "EVIDENCE-LANGUAGE GUARDRAILS: "
        f"{passed}/{total} PASSED"
    )
    print("=" * 100)

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()