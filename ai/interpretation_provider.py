from __future__ import annotations

from abc import ABC, abstractmethod

from ai.models import (
    InterpretationInput,
    InterpretationResult,
)


class InterpretationProviderError(RuntimeError):
    """
    Raised when a narrative interpretation provider cannot
    produce a valid structured response.
    """


class InterpretationProvider(ABC):
    """
    Abstract interface for narrative interpretation providers.

    Providers receive only validated InterpretationInput.
    They must not execute analytics or access the CountyHealth
    database directly.
    """

    @abstractmethod
    def interpret(
        self,
        interpretation_input: InterpretationInput,
    ) -> InterpretationResult:
        """
        Produce a structured narrative interpretation from
        validated evidence claims.
        """
        raise NotImplementedError
    

class DeterministicInterpretationProvider(
    InterpretationProvider
):
    """
    Test provider that converts validated evidence claims directly
    into an InterpretationResult without calling an external model.

    This provider exists for architecture and regression testing.
    """

    def interpret(
        self,
        interpretation_input: InterpretationInput,
    ) -> InterpretationResult:
        from ai.models import InterpretationStatement

        if not interpretation_input.claims:
            raise InterpretationProviderError(
                "Interpretation input contains no evidence claims."
            )

        statements = [
            InterpretationStatement(
                text=claim.text,
                supporting_claim_ids=[
                    claim.claim_id
                ],
            )
            for claim in interpretation_input.claims
        ]

        direct_answer = " ".join(
            claim.text
            for claim in interpretation_input.claims[:2]
        )

        return InterpretationResult(
            direct_answer=direct_answer,
            interpretation=statements,
            limitations=list(
                interpretation_input.limitations
            ),
            follow_up_questions=[],
            warnings=list(
                interpretation_input.warnings
            ),
        )    