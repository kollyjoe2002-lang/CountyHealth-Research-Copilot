from __future__ import annotations

from ai.classifier import classify_question
from ai.evidence import build_evidence_claims
from ai.executor import execute_plan
from ai.models import EvidenceClaim
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan


QUESTIONS = [
    "Tell me about Albany County, Wyoming.",
    (
        "Show the trend in ischemic heart disease in Albany County, "
        "Wyoming from 2000 to 2019."
    ),
    "Which counties had the highest diabetes YLL rates in 2019?",
    "Compare diabetes burden among Black and White adults in 2019.",
]


def main() -> None:
    print("=" * 80)
    print("AI Evidence Claim Validation")
    print("=" * 80)

    for text in QUESTIONS:
        print("\n" + "-" * 80)
        print(f"Question: {text}")

        classified = classify_question(
            text
        )

        plan = build_analysis_plan(
            classified
        )

        resolved_plan = resolve_plan(
            classified,
            plan,
        )

        bundle = execute_plan(
            resolved_plan
        )

        claims = build_evidence_claims(
            bundle
        )

        assert claims, (
            "No evidence claims were produced."
        )

        claim_ids = [
            claim.claim_id
            for claim in claims
        ]

        assert len(claim_ids) == len(
            set(claim_ids)
        ), "Evidence claim IDs are not unique."

        expected_context_claims = {
            "county_profile": "profile.context",
            "trend_comparison": "trend.context",
            "county_ranking": "ranking.context",
            "demographic_disparity": "disparity.context",
        }

        expected_context_claim = expected_context_claims[
            bundle.intent.value
        ]

        assert expected_context_claim in claim_ids, (
            f"Missing required context claim: "
            f"{expected_context_claim}"
        )

        assert not any(
            ".finding." in claim_id
            for claim_id in claim_ids
        ), (
            "At least one finding fell back to a generic claim ID. "
            "Every supported validation finding should have a semantic ID."
        )

        for claim in claims:
            assert isinstance(
                claim,
                EvidenceClaim,
            )

            assert claim.claim_id.strip()
            assert claim.text.strip()

            assert claim.source_function in {
                "deterministic_interpretation",
                "resolved_context",
            }

            assert (
                claim.metadata.get("intent")
                == bundle.intent.value
            )

            print(
                f"{claim.claim_id}: "
                f"{claim.text}"
            )

        print(
            f"Claims produced: {len(claims)}"
        )

    print("\n" + "=" * 80)
    print(
        "AI evidence claim validation "
        "completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()