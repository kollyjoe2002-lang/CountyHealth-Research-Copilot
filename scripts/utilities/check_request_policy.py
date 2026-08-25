from __future__ import annotations

from ai.models import (
    AnalysisIntent,
    RequestPolicyDecision,
    ResearchQuestion,
    SemanticAnalysisRequest,
)
from ai.request_policy import apply_request_policy


def request(
    text: str,
    intent: AnalysisIntent,
    **kwargs,
) -> SemanticAnalysisRequest:
    return SemanticAnalysisRequest(
        question=ResearchQuestion(
            raw_text=text
        ),
        intent=intent,
        confidence=1.0,
        **kwargs,
    )


cases = [
    (
        "snapshot defaults",
        request(
            "Breast cancer in Milwaukee County",
            AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
            county_name="Milwaukee County",
            cause_name="breast cancer",
        ),
        RequestPolicyDecision.EXECUTE,
    ),
    (
        "trend defaults",
        request(
            "Did diabetes improve in Milwaukee County?",
            AnalysisIntent.TREND_COMPARISON,
            county_name="Milwaukee County",
            cause_name="diabetes",
        ),
        RequestPolicyDecision.EXECUTE,
    ),
    (
        "ranking defaults",
        request(
            "Where is diabetes worst?",
            AnalysisIntent.COUNTY_RANKING,
            cause_name="diabetes",
        ),
        RequestPolicyDecision.EXECUTE,
    ),
    (
        "disparity defaults",
        request(
            "Compare Black and White diabetes burden",
            AnalysisIntent.DEMOGRAPHIC_DISPARITY,
            cause_name="diabetes",
            demographic_dimension="Race / ethnicity",
            demographic_groups=[
                "Black",
                "White",
            ],
        ),
        RequestPolicyDecision.EXECUTE,
    ),
    (
        "missing trend subject",
        request(
            "Show me the trend",
            AnalysisIntent.TREND_COMPARISON,
        ),
        RequestPolicyDecision.CLARIFY,
    ),
    (
        "missing ranking cause",
        request(
            "Which counties are worst?",
            AnalysisIntent.COUNTY_RANKING,
        ),
        RequestPolicyDecision.CLARIFY,
    ),
    (
        "ambiguous unknown",
        request(
            "Compare them",
            AnalysisIntent.UNKNOWN,
            needs_clarification=True,
            clarification_question=(
                "What would you like to compare?"
            ),
        ),
        RequestPolicyDecision.CLARIFY,
    ),
    (
        "unsupported forecast",
        request(
            "Predict diabetes in 2035",
            AnalysisIntent.UNKNOWN,
            cause_name="diabetes",
            year=2035,
        ),
        RequestPolicyDecision.REJECT,
    ),
    (
        "long-term change unavailable",
        request(
            "Where has diabetes improved most?",
            AnalysisIntent.LONG_TERM_CHANGE,
            cause_name="diabetes",
        ),
        RequestPolicyDecision.REJECT,
    ),
    (
        "invalid year",
        request(
            "Diabetes in Milwaukee County in 1995",
            AnalysisIntent.COUNTY_CAUSE_SNAPSHOT,
            county_name="Milwaukee County",
            cause_name="diabetes",
            year=1995,
        ),
        RequestPolicyDecision.REJECT,
    ),
]


def main() -> None:
    failures: list[str] = []

    print("=" * 100)
    print("EpiCounty Deterministic Request Policy Validation")
    print("=" * 100)

    for name, semantic_request, expected in cases:
        result = apply_request_policy(
            semantic_request
        )

        status = (
            "PASS"
            if result.decision is expected
            else "FAIL"
        )

        print("-" * 100)
        print(name)
        print("STATUS:", status)
        print("EXPECTED:", expected.value)
        print("ACTUAL:", result.decision.value)
        print("REASON:", result.reason)

        if result.clarification_question:
            print(
                "CLARIFICATION:",
                result.clarification_question,
            )

        if result.assumptions:
            print("ASSUMPTIONS:")
            for assumption in result.assumptions:
                print(" -", assumption)

        normalized = result.request

        print(
            "NORMALIZED:",
            {
                "year": normalized.year,
                "start_year": normalized.start_year,
                "end_year": normalized.end_year,
                "geographic_scope": (
                    normalized.geographic_scope
                ),
            },
        )

        if result.decision is not expected:
            failures.append(
                f"{name}: expected {expected.value}, "
                f"received {result.decision.value}"
            )

    print()
    print("=" * 100)

    if failures:
        print(
            f"REQUEST POLICY: "
            f"{len(cases) - len(failures)}/"
            f"{len(cases)} PASS"
        )

        for failure in failures:
            print("-", failure)

        raise AssertionError(
            "Request-policy validation failed."
        )

    print(
        f"REQUEST POLICY: ALL {len(cases)} CASES PASSED"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()