from __future__ import annotations

from ai.models import (
    InterpretationInput,
    InterpretationResult,
)


class InterpretationValidationError(ValueError):
    """Raised when a narrative interpretation is not properly grounded."""


def validate_interpretation_result(
    interpretation_input: InterpretationInput,
    result: InterpretationResult,
) -> InterpretationResult:
    """
    Validate that the direct answer and every narrative statement
    are explicitly grounded in supplied deterministic evidence claims.
    """

    if not result.direct_answer.text.strip():
        raise InterpretationValidationError(
            "The interpretation must include a direct answer."
        )

    if not result.direct_answer.supporting_claim_ids:
        raise InterpretationValidationError(
            "The direct answer must cite at least one supporting claim."
        )

    available_claim_ids = {
        claim.claim_id
        for claim in interpretation_input.claims
    }

    unknown_direct_claim_ids = set(
        result.direct_answer.supporting_claim_ids
    ).difference(
        available_claim_ids
    )

    if unknown_direct_claim_ids:
        raise InterpretationValidationError(
            "The direct answer references unknown evidence claims: "
            f"{sorted(unknown_direct_claim_ids)}."
        )

    if not result.interpretation:
        raise InterpretationValidationError(
            "The interpretation must include at least one narrative statement."
        )

    for index, statement in enumerate(
        result.interpretation,
        start=1,
    ):
        if not statement.text.strip():
            raise InterpretationValidationError(
                f"Interpretation statement {index} is empty."
            )

        if not statement.supporting_claim_ids:
            raise InterpretationValidationError(
                f"Interpretation statement {index} has no supporting claims."
            )

        unknown_claim_ids = set(
            statement.supporting_claim_ids
        ).difference(
            available_claim_ids
        )

        if unknown_claim_ids:
            raise InterpretationValidationError(
                f"Interpretation statement {index} references "
                "unknown evidence claims: "
                f"{sorted(unknown_claim_ids)}."
            )

    if not result.limitations:
        raise InterpretationValidationError(
            "The interpretation must preserve analytical limitations."
        )

    required_limitations = set(
        interpretation_input.limitations
    )

    returned_limitations = set(
        result.limitations
    )

    missing_limitations = required_limitations.difference(
        returned_limitations
    )

    if missing_limitations:
        raise InterpretationValidationError(
            "The interpretation omitted required limitations: "
            f"{sorted(missing_limitations)}."
        )

    return result