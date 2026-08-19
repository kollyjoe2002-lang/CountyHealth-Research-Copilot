from __future__ import annotations

from ai.classifier import classify_question
from ai.executor import execute_plan
from ai.interpreter import build_interpretation_input
from ai.models import (
    GroundedAnswer,
    InterpretationResult,
    InterpretationStatement,
)
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan
from ai.semantic_entailment import (
    SemanticEntailmentError,
    validate_semantic_entailment,
)


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


def expect_rejection(
    interpretation_input,
    result: InterpretationResult,
    label: str,
) -> None:
    try:
        validate_semantic_entailment(
            interpretation_input,
            result,
        )
    except SemanticEntailmentError as exc:
        print(f"{label}: correctly rejected")
        print(f"  {exc}")
    else:
        raise AssertionError(
            f"{label} was not rejected."
        )


def main() -> None:
    print("=" * 80)
    print("AI Semantic Entailment Validation")
    print("=" * 80)

    interpretation_input = build_input()

    valid_result = InterpretationResult(
        direct_answer=GroundedAnswer(
            text=(
                "The YLL rate declined from 606.45 in 2000 "
                "to 412.66 in 2019."
            ), 
    supporting_claim_ids=[
        "trend.observation_count",
        "trend.absolute_change",
    ],
),
        interpretation=[
            InterpretationStatement(
                text=(
                    "The observed YLL rate declined by 193.79 "
                    "over the period."
                ),
                supporting_claim_ids=[
                    "trend.absolute_change",
                ],
            ),
            InterpretationStatement(
                text=(
                    "This represents a 32.0% relative decrease."
                ),
                supporting_claim_ids=[
                    "trend.relative_change",
                ],
            ),
        ],
        limitations=list(
            interpretation_input.limitations
        ),
        follow_up_questions=[],
        warnings=list(
            interpretation_input.warnings
        ),
    )

    validate_semantic_entailment(
        interpretation_input,
        valid_result,
    )

    print("Valid evidence-supported paraphrase: PASS")

    wrong_number = InterpretationResult(
        direct_answer=GroundedAnswer(
            text="The trend declined.",
            supporting_claim_ids=[
                "trend.absolute_change",
            ],
        ),
        interpretation=[
            InterpretationStatement(
                text=(
                    "The YLL rate declined by 40.0%."
                ),
                supporting_claim_ids=[
                    "trend.relative_change",
                ],
            ),
        ],
        limitations=list(
            interpretation_input.limitations
        ),
        follow_up_questions=[],
    )

    expect_rejection(
        interpretation_input,
        wrong_number,
        "Wrong numeric value",
    )

    causal_claim = InterpretationResult(
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
                    "healthcare access."
                ),
                supporting_claim_ids=[
                    "trend.absolute_change",
                ],
            ),
        ],
        limitations=list(
            interpretation_input.limitations
        ),
        follow_up_questions=[],
    )

    expect_rejection(
        interpretation_input,
        causal_claim,
        "Unsupported causal explanation",
    )

    unsupported_capability = InterpretationResult(
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
            ),
        ],
        limitations=list(
            interpretation_input.limitations
        ),
        follow_up_questions=[
            (
                "Would you like formal statistical testing "
                "of the trend?"
            ),
        ],
    )

    expect_rejection(
        interpretation_input,
        unsupported_capability,
        "Unsupported analytical capability",
    )

    print("\n" + "=" * 80)
    print(
        "AI semantic entailment validation "
        "completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()