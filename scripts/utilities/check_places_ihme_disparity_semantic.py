from dataclasses import dataclass
from typing import Any, cast

from ai.models import (
    AnalysisIntent,
    ResearchQuestion,
    SemanticAnalysisRequest,
)
from ai.research_assistant import run_research_assistant


@dataclass
class Case:
    case_id: str
    description: str
    question: str
    intent: AnalysisIntent
    cause_name: str | None
    year: int | None
    demographic_dimension: str | None
    demographic_groups: list[str]
    evidence_domain: str | None
    expected_status: str
    expected_measure_id: str | None = None
    expected_cause_id: int | None = None
    expected_dimension: str | None = None
    expected_year: int | None = None


class FixedSemanticParser:
    def __init__(self, case: Case) -> None:
        self.case = case

    def parse(
        self,
        question: ResearchQuestion,
    ) -> SemanticAnalysisRequest:
        return SemanticAnalysisRequest(
            question=question,
            intent=self.case.intent,
            confidence=1.0,
            county_name=None,
            cause_name=self.case.cause_name,
            year=self.case.year,
            start_year=None,
            end_year=None,
            demographic_dimension=self.case.demographic_dimension,
            demographic_groups=self.case.demographic_groups,
            direction=None,
            geographic_scope="United States",
            evidence_domain=self.case.evidence_domain,
            needs_clarification=False,
            clarification_question=None,
            explanation=(
                "Fixed parser validation for PLACES_IHME "
                "demographic disparity execution."
            ),
        )


def run_case(case: Case) -> bool:
    print("-" * 100)
    print(f"{case.case_id}: {case.description}")
    print(case.question)

    outcome = run_research_assistant(
        case.question,
        semantic_parser=cast(
            Any,
            FixedSemanticParser(case),
        ),
    )

    print("STATUS:", outcome.status)

    if outcome.status != case.expected_status:
        print(
            "FAIL: expected status "
            f"{case.expected_status}, got {outcome.status}"
        )
        return False

    if case.expected_status != "answer":
        print("PASS")
        return True

    bundle = outcome.evidence_bundle

    if bundle is None:
        print("FAIL: missing evidence bundle")
        return False

    context = bundle.context

    try:
        assert context["evidence_domain"] == "PLACES_IHME"
        assert context["places_measure_id"] == case.expected_measure_id
        assert int(context["cause_id"]) == case.expected_cause_id
        assert context["dimension"] == case.expected_dimension
        assert int(context["year"]) == case.expected_year
        assert int(context["places_measurement_year"]) == case.expected_year
        assert int(context["ihme_year"]) == case.expected_year
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        print("FAIL: resolved context assertion failed")
        print(context)
        print(exc)
        return False

    sources = [
        item
        for item in bundle.items
        if item.source_function
        == "get_places_ihme_demographic_disparity_context"
    ]

    if len(sources) != 1:
        print(
            "FAIL: expected exactly one cross-source "
            "demographic disparity evidence item"
        )
        return False

    df = sources[0].data

    if df.empty:
        print("FAIL: evidence dataframe is empty")
        return False

    try:
        assert df["places_measure_id"].eq(
            case.expected_measure_id
        ).all()

        assert df["places_measurement_year"].eq(
            case.expected_year
        ).all()

        assert df["ihme_cause_id"].eq(
            case.expected_cause_id
        ).all()

        assert df["ihme_year"].eq(
            case.expected_year
        ).all()

        assert df["ihme_dimension"].eq(
            case.expected_dimension
        ).all()

    except (AssertionError, KeyError) as exc:
        print("FAIL: evidence dataframe assertion failed")
        print(exc)
        return False

    interpretation_input = outcome.interpretation_input

    if interpretation_input is None:
        print("FAIL: missing interpretation input")
        return False

    claim_ids = {
        claim.claim_id
        for claim in interpretation_input.claims
    }

    required_claims = {
        "disparity.context",
        "disparity.cross_source_counties",
        "disparity.places_prevalence_context",
        "disparity.ihme_median_gap",
        "disparity.ihme_direction_counts",
        "disparity.cross_source_guardrail",
    }

    missing_claims = required_claims - claim_ids

    if missing_claims:
        print(
            "FAIL: missing expected claims:",
            sorted(missing_claims),
        )
        return False

    guardrail_claim = next(
        claim
        for claim in interpretation_input.claims
        if claim.claim_id
        == "disparity.cross_source_guardrail"
    )

    guardrail_text = guardrail_claim.text.casefold()

    if (
        "does not establish a causal relationship"
        not in guardrail_text
    ):
        print("FAIL: causal guardrail missing")
        return False

    print(
        f"Matched counties: {len(df):,}"
    )
    print("PASS")
    return True


cases = [
    Case(
        case_id="D01",
        description="Black-White diabetes disparity, explicit 2019",
        question=(
            "Compare CDC PLACES diabetes prevalence with the "
            "Black-White IHME type 2 diabetes YLL disparity "
            "across U.S. counties in 2019."
        ),
        intent=AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        cause_name="type 2 diabetes",
        year=2019,
        demographic_dimension="Race / ethnicity",
        demographic_groups=[
            "Non-Latino, Black",
            "Non-Latino, White",
        ],
        evidence_domain="PLACES_IHME",
        expected_status="answer",
        expected_measure_id="DIABETES",
        expected_cause_id=976,
        expected_dimension="Race / ethnicity",
        expected_year=2019,
    ),
    Case(
        case_id="D02",
        description="Male-Female stroke disparity, explicit 2019",
        question=(
            "Compare CDC PLACES stroke prevalence with the "
            "Male-Female IHME stroke YLL disparity across "
            "U.S. counties in 2019."
        ),
        intent=AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        cause_name="stroke",
        year=2019,
        demographic_dimension="Sex",
        demographic_groups=[
            "Male",
            "Female",
        ],
        evidence_domain="PLACES_IHME",
        expected_status="answer",
        expected_measure_id="STROKE",
        expected_cause_id=494,
        expected_dimension="Sex",
        expected_year=2019,
    ),
    Case(
        case_id="D03",
        description="Age diabetes disparity, explicit 2019",
        question=(
            "Compare CDC PLACES diabetes prevalence with the "
            "IHME type 2 diabetes YLL disparity between ages "
            "60 to 64 and ages 80 to 84 across U.S. counties "
            "in 2019."
        ),
        intent=AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        cause_name="type 2 diabetes",
        year=2019,
        demographic_dimension="Age group",
        demographic_groups=[
            "60 to 64",
            "80 to 84",
        ],
        evidence_domain="PLACES_IHME",
        expected_status="answer",
        expected_measure_id="DIABETES",
        expected_cause_id=976,
        expected_dimension="Age group",
        expected_year=2019,
    ),
    Case(
        case_id="D04",
        description="Default shared year",
        question=(
            "Compare CDC PLACES diabetes prevalence with the "
            "Black-White IHME type 2 diabetes YLL disparity "
            "across U.S. counties."
        ),
        intent=AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        cause_name="type 2 diabetes",
        year=None,
        demographic_dimension="Race / ethnicity",
        demographic_groups=[
            "Non-Latino, Black",
            "Non-Latino, White",
        ],
        evidence_domain="PLACES_IHME",
        expected_status="answer",
        expected_measure_id="DIABETES",
        expected_cause_id=976,
        expected_dimension="Race / ethnicity",
        expected_year=2019,
    ),
    Case(
        case_id="D05",
        description="Unsupported shared year 2020",
        question=(
            "Compare CDC PLACES diabetes prevalence with the "
            "Black-White IHME type 2 diabetes YLL disparity "
            "across U.S. counties in 2020."
        ),
        intent=AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        cause_name="type 2 diabetes",
        year=2020,
        demographic_dimension="Race / ethnicity",
        demographic_groups=[
            "Non-Latino, Black",
            "Non-Latino, White",
        ],
        evidence_domain="PLACES_IHME",
        expected_status="reject",
    ),
    Case(
        case_id="D06",
        description="Incompatible cross-source concepts",
        question=(
            "Compare CDC PLACES stroke prevalence with the "
            "Black-White IHME type 2 diabetes YLL disparity "
            "across U.S. counties in 2019."
        ),
        intent=AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        cause_name="type 2 diabetes",
        year=2019,
        demographic_dimension="Race / ethnicity",
        demographic_groups=[
            "Non-Latino, Black",
            "Non-Latino, White",
        ],
        evidence_domain="PLACES_IHME",
        expected_status="clarify",
    ),
    Case(
        case_id="D07",
        description="Missing demographic groups",
        question=(
            "Compare CDC PLACES diabetes prevalence with "
            "IHME type 2 diabetes racial disparity in 2019."
        ),
        intent=AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        cause_name="type 2 diabetes",
        year=2019,
        demographic_dimension="Race / ethnicity",
        demographic_groups=[],
        evidence_domain="PLACES_IHME",
        expected_status="clarify",
    ),
    Case(
        case_id="D08",
        description="Unsupported PLACES_IHME intent remains closed",
        question=(
            "Rank U.S. counties using CDC PLACES diabetes "
            "prevalence and IHME type 2 diabetes burden."
        ),
        intent=AnalysisIntent.COUNTY_RANKING,
        cause_name="type 2 diabetes",
        year=2019,
        demographic_dimension=None,
        demographic_groups=[],
        evidence_domain="PLACES_IHME",
        expected_status="reject",
    ),
]


passed = 0

for case in cases:
    if run_case(case):
        passed += 1

print("=" * 100)
print(
    "PLACES_IHME DEMOGRAPHIC DISPARITY "
    f"SEMANTIC VALIDATION: {passed}/{len(cases)} PASSED"
)
print("=" * 100)

if passed != len(cases):
    raise SystemExit(1)