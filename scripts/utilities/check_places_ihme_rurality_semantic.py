from __future__ import annotations

from typing import Any, cast

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


def run_case(
    case_id: str,
    request: SemanticAnalysisRequest,
    expected_status: str,
) -> bool:
    print("-" * 90)
    print(case_id)
    print(request.question.raw_text)

    parser = cast(
        Any,
        FixedSemanticParser(request),
    )

    outcome = run_research_assistant(
        request.question.raw_text,
        semantic_parser=parser,
    )

    print("STATUS:", outcome.status)

    if outcome.status != expected_status:
        print(
            "FAIL: expected",
            expected_status,
            "got",
            outcome.status,
        )
        print("CLARIFICATION:", outcome.clarification_question)
        print("REJECTION:", outcome.rejection_reason)
        print("AI ERROR:", outcome.ai_error)
        return False

    if expected_status != "answer":
        if outcome.evidence_bundle is not None:
            print("FAIL: non-answer case produced evidence.")
            return False

        print("PASS")
        return True

    if outcome.evidence_bundle is None:
        print("FAIL: no evidence bundle.")
        return False

    bundle = outcome.evidence_bundle
    context = bundle.context

    if context.get("evidence_domain") != "PLACES_IHME":
        print("FAIL: incorrect evidence domain.")
        return False

    if context.get("places_measure_id") != "DIABETES":
        print(
            "FAIL: unexpected PLACES measure:",
            context.get("places_measure_id"),
        )
        return False

    if context.get("cause_id") != 976:
        print(
            "FAIL: unexpected IHME cause:",
            context.get("cause_id"),
        )
        return False

    if context.get("year") != 2019:
        print(
            "FAIL: unexpected year:",
            context.get("year"),
        )
        return False

    if len(bundle.items) != 1:
        print(
            "FAIL: expected one evidence item, got",
            len(bundle.items),
        )
        return False

    item = bundle.items[0]

    if item.source_function != "get_places_ihme_rurality_comparison":
        print(
            "FAIL: unexpected source:",
            item.source_function,
        )
        return False

    data = item.data

    expected_groups = {
        "Metro",
        "Nonmetro adjacent",
        "Nonmetro not adjacent",
    }

    actual_groups = set(
        data["rurality_group"].astype(str)
    )

    if actual_groups != expected_groups:
        print(
            "FAIL: unexpected rurality groups:",
            sorted(actual_groups),
        )
        return False

    if len(data) != 3:
        print("FAIL: expected 3 rows, got", len(data))
        return False

    print(data.to_string(index=False))
    print("PASS")
    return True


cases = [
    (
        "R01 explicit diabetes rurality 2019",
        SemanticAnalysisRequest(
            question=ResearchQuestion(
                raw_text=(
                    "Compare CDC PLACES diabetes prevalence "
                    "and IHME type 2 diabetes YLL burden "
                    "across rurality groups in 2019."
                )
            ),
            intent=AnalysisIntent.RURALITY_COMPARISON,
            confidence=0.99,
            cause_name="type 2 diabetes",
            year=2019,
            geographic_scope="United States",
            evidence_domain="PLACES_IHME",
        ),
        "answer",
    ),
    (
        "R02 default shared year",
        SemanticAnalysisRequest(
            question=ResearchQuestion(
                raw_text=(
                    "Compare CDC PLACES diabetes prevalence "
                    "and IHME type 2 diabetes burden across "
                    "metro and nonmetro counties."
                )
            ),
            intent=AnalysisIntent.RURALITY_COMPARISON,
            confidence=0.99,
            cause_name="type 2 diabetes",
            geographic_scope="United States",
            evidence_domain="PLACES_IHME",
        ),
        "answer",
    ),
    (
        "R03 unsupported shared year 2020",
        SemanticAnalysisRequest(
            question=ResearchQuestion(
                raw_text=(
                    "Compare CDC PLACES diabetes prevalence "
                    "and IHME type 2 diabetes burden across "
                    "rurality groups in 2020."
                )
            ),
            intent=AnalysisIntent.RURALITY_COMPARISON,
            confidence=0.99,
            cause_name="type 2 diabetes",
            year=2020,
            geographic_scope="United States",
            evidence_domain="PLACES_IHME",
        ),
        "reject",
    ),
    (
        "R04 incompatible cross-source concepts",
        SemanticAnalysisRequest(
            question=ResearchQuestion(
                raw_text=(
                    "Compare CDC PLACES stroke prevalence "
                    "and IHME type 2 diabetes burden across "
                    "rurality groups in 2019."
                )
            ),
            intent=AnalysisIntent.RURALITY_COMPARISON,
            confidence=0.99,
            cause_name="type 2 diabetes",
            year=2019,
            geographic_scope="United States",
            evidence_domain="PLACES_IHME",
        ),
        "clarify",
    ),
    (
        "R05 missing disease or health measure",
        SemanticAnalysisRequest(
            question=ResearchQuestion(
                raw_text=(
                    "Compare CDC PLACES prevalence and IHME burden "
                    "across rurality groups in 2019."
                )
            ),
            intent=AnalysisIntent.RURALITY_COMPARISON,
            confidence=0.99,
            cause_name=None,
            year=2019,
            geographic_scope="United States",
            evidence_domain="PLACES_IHME",
        ),
        "clarify",
    ),
]

passed = 0

for case_id, request, expected_status in cases:
    if run_case(case_id, request, expected_status):
        passed += 1

print("=" * 90)
print(
    f"RURALITY SEMANTIC VALIDATION: "
    f"{passed}/{len(cases)} PASSED"
)

if passed != len(cases):
    raise SystemExit(1)