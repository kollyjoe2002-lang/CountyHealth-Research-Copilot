from __future__ import annotations

from ai.classifier import classify_question
from ai.executor import execute_plan
from ai.interpreter import build_interpretation_input
from ai.interpretation_validator import (
    InterpretationValidationError,
    validate_interpretation_result,
)
from ai.models import (
    GroundedAnswer,
    InterpretationResult,
    InterpretationStatement,
)
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan


QUESTION = (
    "Show the trend in ischemic heart disease in Albany County, "
    "Wyoming from 2000 to 2019."
)


def build_input():
    classified = classify_question(
        QUESTION
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

    return build_interpretation_input(
        bundle
    )


def main() -> None:
    print("=" * 80)
    print("AI Statement-Level Grounding Validation")
    print("=" * 80)

    interpretation_input = build_input()

    valid_result = InterpretationResult(
        direct_answer=GroundedAnswer(
            text=(
                "The estimated YLL rate declined over "
                "the observed period."
            ),
            supporting_claim_ids=[
                "trend.absolute_change",
            ],
        ),
        interpretation=[
            InterpretationStatement(
                text=(
                    "The validated trend shows a decrease "
                    "between 2000 and 2019."
                ),
                supporting_claim_ids=[
                    "trend.context",
                    "trend.absolute_change",
                ],
            )
        ],
        limitations=list(
            interpretation_input.limitations
        ),
        follow_up_questions=[
            "Which counties had the highest rates in 2019?"
        ],
    )

    validate_interpretation_result(
        interpretation_input,
        valid_result,
    )

    print("Valid statement-level grounding: PASS")

    unknown_claim_result = InterpretationResult(
        direct_answer=GroundedAnswer(
            text="The trend declined.",
            supporting_claim_ids=[
                "trend.nonexistent_claim",
            ],
        ),
        interpretation=[
            InterpretationStatement(
                text=(
                    "The validated evidence shows a decline."
                ),
                supporting_claim_ids=[
                    "trend.absolute_change",
                ],
            )
        ],
        limitations=list(
            interpretation_input.limitations
        ),
        follow_up_questions=[],
    )

    try:
        validate_interpretation_result(
            interpretation_input,
            unknown_claim_result,
        )
    except InterpretationValidationError as exc:
        print("Unknown direct-answer claim correctly rejected:")
        print(f"  {exc}")
    else:
        raise AssertionError(
            "Unknown direct-answer evidence claim "
            "was not rejected."
        )

    unknown_statement_claim_result = InterpretationResult(
        direct_answer=GroundedAnswer(
            text="The trend declined.",
            supporting_claim_ids=[
                "trend.absolute_change",
            ],
        ),
        interpretation=[
            InterpretationStatement(
                text=(
                    "The validated evidence shows a decline."
                ),
                supporting_claim_ids=[
                    "trend.nonexistent_claim",
                ],
            )
        ],
        limitations=list(
            interpretation_input.limitations
        ),
        follow_up_questions=[],
    )

    try:
        validate_interpretation_result(
            interpretation_input,
            unknown_statement_claim_result,
        )
    except InterpretationValidationError as exc:
        print("Unknown statement claim correctly rejected:")
        print(f"  {exc}")
    else:
        raise AssertionError(
            "Unknown statement evidence claim "
            "was not rejected."
        )

    ungrounded_result = InterpretationResult(
        direct_answer=GroundedAnswer(
            text="The trend declined.",
            supporting_claim_ids=[
                "trend.absolute_change",
            ],
        ),
        interpretation=[
            InterpretationStatement(
                text=(
                    "The decline was caused by improved "
                    "access to care."
                ),
                supporting_claim_ids=[],
            )
        ],
        limitations=list(
            interpretation_input.limitations
        ),
        follow_up_questions=[],
    )

    try:
        validate_interpretation_result(
            interpretation_input,
            ungrounded_result,
        )
    except InterpretationValidationError as exc:
        print("Ungrounded statement correctly rejected:")
        print(f"  {exc}")
    else:
        raise AssertionError(
            "Ungrounded narrative statement was not rejected."
        )

    missing_limitations = InterpretationResult(
        direct_answer=GroundedAnswer(
            text="The trend declined.",
            supporting_claim_ids=[
                "trend.absolute_change",
            ],
        ),
        interpretation=[
            InterpretationStatement(
                text=(
                    "The validated evidence shows a decline."
                ),
                supporting_claim_ids=[
                    "trend.absolute_change",
                ],
            )
        ],
        limitations=[],
        follow_up_questions=[],
    )

    try:
        validate_interpretation_result(
            interpretation_input,
            missing_limitations,
        )
    except InterpretationValidationError as exc:
        print("Missing limitations correctly rejected:")
        print(f"  {exc}")
    else:
        raise AssertionError(
            "Missing analytical limitations were not rejected."
        )

    print("\n" + "=" * 80)
    print(
        "AI statement-level grounding validation "
        "completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()