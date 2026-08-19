from __future__ import annotations

import json
from typing import Any

from ai.interpretation_provider import (
    InterpretationProvider,
    InterpretationProviderError,
)
from ai.models import (
    GroundedAnswer,
    InterpretationInput,
    InterpretationResult,
    InterpretationStatement,
)

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover
    OpenAI = None


class OpenAIInterpretationProvider(
    InterpretationProvider
):
    """
    OpenAI-backed narrative interpretation provider.

    The provider receives only validated InterpretationInput and
    returns structured narrative output. It does not execute analytics
    or access the CountyHealth database.
    """

    def __init__(
        self,
        *,
        model: str = "gpt-5.6",
    ) -> None:
        if OpenAI is None:
            raise InterpretationProviderError(
                "The openai package is not installed."
            )

        self.model = model
        self.client = OpenAI()

    def _input_payload(
        self,
        interpretation_input: InterpretationInput,
    ) -> str:
        claims = [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "value": claim.value,
                "units": claim.units,
                "metadata": claim.metadata,
            }
            for claim in interpretation_input.claims
        ]

        payload: dict[str, Any] = {
            "question": (
                interpretation_input.question.raw_text
            ),
            "intent": (
                interpretation_input.intent.value
            ),
            "context": (
                interpretation_input.context
            ),
            "claims": claims,
            "warnings": (
                interpretation_input.warnings
            ),
            "limitations": (
                interpretation_input.limitations
            ),
        }

        return json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )

    def interpret(
        self,
        interpretation_input: InterpretationInput,
    ) -> InterpretationResult:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "direct_answer": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "text": {
                            "type": "string",
                        },
                        "supporting_claim_ids": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "string",
                            },
                        },
                    },
                    "required": [
                        "text",
                        "supporting_claim_ids",
                    ],
                },
                "interpretation": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "text": {
                                "type": "string",
                            },
                            "supporting_claim_ids": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "string",
                                },
                            },
                        },
                        "required": [
                            "text",
                            "supporting_claim_ids",
                        ],
                    },
                },
                "limitations": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
                "follow_up_questions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
                "warnings": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
            "required": [
                "direct_answer",
                "interpretation",
                "limitations",
                "follow_up_questions",
                "warnings",
            ],
        }

        instructions = """
You are the narrative interpretation layer for a public-health
research system.

Use only the supplied validated evidence claims.

Rules:
1. Do not invent numbers, causes, mechanisms, exposures, or findings.

2. Do not infer causation from descriptive results.

3. The direct answer and every interpretation statement must cite
   every supplied claim ID needed to support every factual component
   of the text.

   Before returning the response, verify each sentence against its
   cited claims.

   Every number, year, county, group, cause, direction, ranking,
   percentage, and comparison mentioned in a sentence must appear
   explicitly in at least one of that sentence's cited evidence
   claims.

   If a sentence mentions the trend years, cite the claim that
   explicitly contains those years. Do not rely on unstated context.

4. Claim citations must be complete, not merely relevant. If multiple
   claims are needed to support one sentence, cite all of them.

5. Do not introduce population qualifiers that are not explicitly
   supported by the supplied claims or context. This includes terms
   such as adults, children, older adults, women, men, patients,
   residents, or age-specific populations unless those qualifiers
   appear in the validated evidence.

6. Return at least one interpretation statement.

   The interpretation statement must add a useful evidence-grounded
   observation beyond merely repeating the direct answer.

   Select the statement from the remaining supplied evidence claims.

   For ranking analyses, suitable interpretation statements may
   describe the number of counties included, the lowest-ranked county,
   or the observed national range, provided the cited claims explicitly
   support those facts.

   For trend analyses, suitable interpretation statements may describe
   the observation count, maximum, or minimum, provided the cited claims
   explicitly support those facts.

   For disparity analyses, suitable interpretation statements may
   describe the median gap, direction counts, largest positive gap, or
   largest reverse gap, provided the cited claims explicitly support
   those facts.

   For county profiles, suitable interpretation statements may describe
   a leading cause or long-term increase or decrease, provided the cited
   claims explicitly support those facts.

   Never invent a statement merely to satisfy this requirement.

7. Preserve every supplied analytical limitation exactly.

8. Do not claim statistical significance unless explicitly supported.

9. Follow-up questions must stay within the capabilities implied by
   the supplied evidence and intent.

10. Be concise, cautious, and suitable for research use.
"""

        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=self._input_payload(
                    interpretation_input
                ),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": (
                            "countyhealth_interpretation"
                        ),
                        "strict": True,
                        "schema": schema,
                    }
                },
            )

        except Exception as exc:
            raise InterpretationProviderError(
                f"OpenAI interpretation request failed: {exc}"
            ) from exc

        try:
            parsed = json.loads(
                response.output_text
            )

        except Exception as exc:
            raise InterpretationProviderError(
                "OpenAI returned an unreadable structured response."
            ) from exc

        statements = [
            InterpretationStatement(
                text=item["text"],
                supporting_claim_ids=list(
                    item["supporting_claim_ids"]
                ),
            )
            for item in parsed["interpretation"]
        ]

        direct_answer = GroundedAnswer(
            text=parsed["direct_answer"]["text"],
            supporting_claim_ids=list(
                parsed["direct_answer"][
                    "supporting_claim_ids"
                ]
            ),
        )

        return InterpretationResult(
            direct_answer=direct_answer,
            interpretation=statements,
            limitations=list(
                parsed["limitations"]
            ),
            follow_up_questions=list(
                parsed["follow_up_questions"]
            ),
            warnings=list(
                parsed["warnings"]
            ),
        )