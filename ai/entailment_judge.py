from __future__ import annotations

import json

from ai.models import (
    EntailmentJudgment,
    EntailmentLabel,
    InterpretationInput,
    InterpretationResult,
)

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover
    OpenAI = None


class EntailmentJudgeError(RuntimeError):
    """Raised when semantic entailment cannot be established safely."""


class OpenAIEntailmentJudge:
    """
    Judge whether generated narrative is semantically entailed by
    the deterministic evidence claims it cites.

    The judge receives only cited evidence and generated text.
    It must not use outside knowledge.
    """

    def __init__(
        self,
        *,
        model: str = "gpt-5.6",
    ) -> None:
        if OpenAI is None:
            raise EntailmentJudgeError(
                "The openai package is not installed."
            )

        self.model = model
        self.client = OpenAI()

    def judge(
        self,
        *,
        statement_text: str,
        evidence_text: str,
    ) -> EntailmentJudgment:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "label": {
                    "type": "string",
                    "enum": [
                        "ENTAILED",
                        "UNSUPPORTED",
                        "CONTRADICTED",
                    ],
                },
                "rationale": {
                    "type": "string",
                },
            },
            "required": [
                "label",
                "rationale",
            ],
        }

        instructions = """
You are a strict semantic entailment judge for a public-health
research system.

You will receive:
1. VALIDATED EVIDENCE
2. GENERATED STATEMENT

Use ONLY the validated evidence.

Return:

ENTAILED:
Every factual assertion in the generated statement follows from
the supplied evidence. Normal paraphrase, rounding, and expressing
a negative change as a decline of the corresponding magnitude are
allowed.

UNSUPPORTED:
The statement adds a factual assertion, explanation, mechanism,
cause, interpretation, generalization, or detail that is not
established by the supplied evidence.

CONTRADICTED:
The statement conflicts with the supplied evidence, including
wrong direction, wrong entity, wrong time period, or incompatible
numeric information.

Rules:
- Do not use outside knowledge.
- Do not assume causal explanations.
- Do not give the statement credit merely because it cites evidence.
- Every material factual component must be supported.
- If uncertain between ENTAILED and UNSUPPORTED, choose UNSUPPORTED.
"""

        payload = json.dumps(
            {
                "validated_evidence": evidence_text,
                "generated_statement": statement_text,
            },
            ensure_ascii=False,
            indent=2,
        )

        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=payload,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "countyhealth_entailment_judgment",
                        "strict": True,
                        "schema": schema,
                    }
                },
            )
        except Exception as exc:
            raise EntailmentJudgeError(
                f"Entailment judge request failed: {exc}"
            ) from exc

        try:
            parsed = json.loads(
                response.output_text
            )

            label = EntailmentLabel(
                parsed["label"]
            )

            rationale = str(
                parsed["rationale"]
            ).strip()

        except Exception as exc:
            raise EntailmentJudgeError(
                "Entailment judge returned an invalid response."
            ) from exc

        return EntailmentJudgment(
            label=label,
            rationale=rationale,
        )


def _evidence_for_claims(
    interpretation_input: InterpretationInput,
    claim_ids: list[str],
) -> str:
    claim_map = {
        claim.claim_id: claim.text
        for claim in interpretation_input.claims
    }

    missing = [
        claim_id
        for claim_id in claim_ids
        if claim_id not in claim_map
    ]

    if missing:
        raise EntailmentJudgeError(
            "Cannot judge semantic entailment because "
            f"evidence claims are missing: {missing}."
        )

    return "\n".join(
        f"{claim_id}: {claim_map[claim_id]}"
        for claim_id in claim_ids
    )


def validate_model_entailment(
    interpretation_input: InterpretationInput,
    result: InterpretationResult,
    *,
    judge: OpenAIEntailmentJudge,
) -> InterpretationResult:
    """
    Require the direct answer and every interpretation statement
    to be semantically entailed by their cited evidence.
    """

    direct_evidence = _evidence_for_claims(
        interpretation_input,
        result.direct_answer.supporting_claim_ids,
    )

    direct_judgment = judge.judge(
        statement_text=result.direct_answer.text,
        evidence_text=direct_evidence,
    )

    if direct_judgment.label is not EntailmentLabel.ENTAILED:
        raise EntailmentJudgeError(
            "Direct answer failed semantic entailment: "
            f"{direct_judgment.label.value} — "
            f"{direct_judgment.rationale}"
        )

    for index, statement in enumerate(
        result.interpretation,
        start=1,
    ):
        evidence_text = _evidence_for_claims(
            interpretation_input,
            statement.supporting_claim_ids,
        )

        judgment = judge.judge(
            statement_text=statement.text,
            evidence_text=evidence_text,
        )

        if judgment.label is not EntailmentLabel.ENTAILED:
            raise EntailmentJudgeError(
                f"Interpretation statement {index} failed "
                "semantic entailment: "
                f"{judgment.label.value} — "
                f"{judgment.rationale}"
            )

    return result