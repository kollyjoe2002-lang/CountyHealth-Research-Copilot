from __future__ import annotations

from ai.evidence import build_evidence_claims
from ai.models import (
    EvidenceBundle,
    InterpretationInput,
)
from ai.report_writer import _limitations


def build_interpretation_input(
    bundle: EvidenceBundle,
) -> InterpretationInput:
    """
    Build the evidence-grounded contract supplied to downstream
    narrative interpretation.

    This function does not call a generative model and does not
    execute analytics. It packages only validated deterministic
    claims, resolved context, warnings, and established limitations.
    """
    claims = build_evidence_claims(
        bundle
    )

    if not claims:
        raise ValueError(
            "The evidence bundle produced no structured claims."
        )

    return InterpretationInput(
        question=bundle.question,
        intent=bundle.intent,
        claims=claims,
        context=dict(
            bundle.context
        ),
        warnings=list(
            bundle.warnings
        ),
        limitations=_limitations(
            bundle
        ),
    )