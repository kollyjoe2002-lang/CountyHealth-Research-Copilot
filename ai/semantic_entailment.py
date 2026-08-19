from __future__ import annotations

import re

from ai.models import (
    InterpretationInput,
    InterpretationResult,
)


class SemanticEntailmentError(ValueError):
    """Raised when generated language exceeds its cited evidence."""


CAUSAL_PATTERNS = (
    r"\bcaused by\b",
    r"\bwas caused by\b",
    r"\bwere caused by\b",
    r"\bdue to\b",
    r"\bresulted from\b",
    r"\bresults from\b",
    r"\bled to\b",
    r"\bleads to\b",
    r"\bdriven by\b",
    r"\bbecause of\b",
    r"\bexplains the\b",
    r"\bexplains why\b",
    r"\bresponsible for\b",
)


UNSUPPORTED_CAPABILITY_PATTERNS = (
    r"\bforecast\b",
    r"\bpredict\b",
    r"\bstatistical testing\b",
    r"\bsignificance test\b",
    r"\bregression\b",
    r"\bcausal analysis\b",
)


DECREASE_PATTERNS = (
    r"\bdecrease",
    r"\bdeclin",
    r"\bfell\b",
    r"\bdropped\b",
    r"\breduction\b",
)


INCREASE_PATTERNS = (
    r"\bincrease",
    r"\brose\b",
    r"\brisen\b",
    r"\bgrew\b",
    r"\bgrowth\b",
)


def _extract_numbers(
    text: str,
) -> list[tuple[float, bool]]:
    """
    Extract numeric values and whether they were percentages.

    Commas are removed and values are converted to floats.
    """
    matches = re.findall(
        r"-?\d[\d,]*(?:\.\d+)?%?",
        text,
    )

    numbers: list[tuple[float, bool]] = []

    for match in matches:
        is_percent = match.endswith("%")

        cleaned = (
            match.replace(",", "")
            .removesuffix("%")
        )

        try:
            value = float(cleaned)
        except ValueError:
            continue

        numbers.append(
            (
                value,
                is_percent,
            )
        )

    return numbers


def _number_is_supported(
    value: float,
    is_percent: bool,
    evidence_numbers: list[tuple[float, bool]],
) -> bool:
    """
    Determine whether a generated numeric value is supported.

    Signed analytical changes may be expressed in natural language
    using their unsigned magnitude, for example:

        evidence: -193.79
        narrative: declined by 193.79

    Therefore both exact value and absolute magnitude are accepted.
    Percentage and non-percentage values remain distinct.
    """
    tolerance = 1e-9

    for evidence_value, evidence_is_percent in evidence_numbers:
        if is_percent != evidence_is_percent:
            continue

        if abs(
            value - evidence_value
        ) <= tolerance:
            return True

        if abs(
            abs(value) - abs(evidence_value)
        ) <= tolerance:
            return True

    return False


def _claim_text(
    interpretation_input: InterpretationInput,
    claim_ids: list[str],
) -> str:
    claim_map = {
        claim.claim_id: claim.text
        for claim in interpretation_input.claims
    }

    return " ".join(
        claim_map[claim_id]
        for claim_id in claim_ids
        if claim_id in claim_map
    )


def _validate_numbers(
    statement_text: str,
    evidence_text: str,
    *,
    label: str,
) -> None:
    statement_numbers = _extract_numbers(
        statement_text
    )

    evidence_numbers = _extract_numbers(
        evidence_text
    )

    unsupported = [
        value
        for value, is_percent in statement_numbers
        if not _number_is_supported(
            value,
            is_percent,
            evidence_numbers,
        )
    ]

    if unsupported:
        raise SemanticEntailmentError(
            f"{label} contains numeric values not present "
            f"in its cited evidence: {unsupported}."
        )


def _contains_pattern(
    text: str,
    patterns: tuple[str, ...],
) -> bool:
    lowered = text.casefold()

    return any(
        re.search(
            pattern,
            lowered,
        )
        for pattern in patterns
    )


def _validate_direction(
    statement_text: str,
    evidence_text: str,
    *,
    label: str,
) -> None:
    """
    Reject obvious direction contradictions between generated
    narrative and deterministic evidence.
    """
    statement_decrease = _contains_pattern(
        statement_text,
        DECREASE_PATTERNS,
    )

    statement_increase = _contains_pattern(
        statement_text,
        INCREASE_PATTERNS,
    )

    evidence_decrease = _contains_pattern(
        evidence_text,
        DECREASE_PATTERNS,
    )

    evidence_increase = _contains_pattern(
        evidence_text,
        INCREASE_PATTERNS,
    )

    if (
        statement_decrease
        and evidence_increase
        and not evidence_decrease
    ):
        raise SemanticEntailmentError(
            f"{label} describes a decrease but the cited "
            "evidence describes an increase."
        )

    if (
        statement_increase
        and evidence_decrease
        and not evidence_increase
    ):
        raise SemanticEntailmentError(
            f"{label} describes an increase but the cited "
            "evidence describes a decrease."
        )


def _validate_causal_language(
    statement_text: str,
    *,
    label: str,
) -> None:
    lowered = statement_text.casefold()

    for pattern in CAUSAL_PATTERNS:
        if re.search(
            pattern,
            lowered,
        ):
            raise SemanticEntailmentError(
                f"{label} contains unsupported causal language."
            )


def _validate_capability_language(
    statement_text: str,
    *,
    label: str,
) -> None:
    lowered = statement_text.casefold()

    for pattern in UNSUPPORTED_CAPABILITY_PATTERNS:
        if re.search(
            pattern,
            lowered,
        ):
            raise SemanticEntailmentError(
                f"{label} refers to an unsupported analytical capability."
            )


def _validate_grounded_text(
    interpretation_input: InterpretationInput,
    text: str,
    supporting_claim_ids: list[str],
    *,
    label: str,
) -> None:
    evidence_text = _claim_text(
        interpretation_input,
        supporting_claim_ids,
    )

    if not evidence_text.strip():
        raise SemanticEntailmentError(
            f"{label} has no usable supporting evidence."
        )

    _validate_numbers(
        text,
        evidence_text,
        label=label,
    )

    _validate_direction(
        text,
        evidence_text,
        label=label,
    )

    _validate_causal_language(
        text,
        label=label,
    )


def validate_semantic_entailment(
    interpretation_input: InterpretationInput,
    result: InterpretationResult,
) -> InterpretationResult:
    """
    Apply deterministic semantic-grounding checks to generated
    interpretation output.

    The validator checks:
    - direct-answer grounding;
    - numeric consistency;
    - direction consistency;
    - unsupported causal language;
    - unsupported follow-up capabilities.
    """

    _validate_grounded_text(
        interpretation_input,
        result.direct_answer.text,
        result.direct_answer.supporting_claim_ids,
        label="Direct answer",
    )

    for index, statement in enumerate(
        result.interpretation,
        start=1,
    ):
        _validate_grounded_text(
            interpretation_input,
            statement.text,
            statement.supporting_claim_ids,
            label=(
                f"Interpretation statement {index}"
            ),
        )

    for index, follow_up in enumerate(
        result.follow_up_questions,
        start=1,
    ):
        _validate_capability_language(
            follow_up,
            label=(
                f"Follow-up question {index}"
            ),
        )

    return result