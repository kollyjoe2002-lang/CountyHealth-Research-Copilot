from __future__ import annotations

from ai.classifier import classify_question
from ai.entailment_judge import (
    OpenAIEntailmentJudge,
    validate_model_entailment,
)
from ai.executor import execute_plan
from ai.interpreter import build_interpretation_input
from ai.interpretation_validator import (
    validate_interpretation_result,
)
from ai.openai_interpretation_provider import (
    OpenAIInterpretationProvider,
)
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan
from ai.semantic_entailment import (
    validate_semantic_entailment,
)


QUESTIONS = [
    (
        "County profile",
        "Tell me about Albany County, Wyoming.",
    ),
    (
        "Trend comparison",
        (
            "Show the trend in ischemic heart disease in Albany County, "
            "Wyoming from 2000 to 2019."
        ),
    ),
    (
        "County ranking",
        "Which counties had the highest diabetes YLL rates in 2019?",
    ),
    (
        "Demographic disparity",
        "Compare diabetes burden among Black and White adults in 2019.",
    ),
]


def run_case(
    label: str,
    question_text: str,
    provider: OpenAIInterpretationProvider,
    judge: OpenAIEntailmentJudge,
) -> None:
    print("\n" + "=" * 80)
    print(label)
    print("=" * 80)

    print(f"\nQuestion:\n{question_text}")

    classified = classify_question(
        question_text
    )

    print(
        f"\nClassified intent: "
        f"{classified.intent.value}"
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

    interpretation_input = (
        build_interpretation_input(
            bundle
        )
    )

    print(
        f"Evidence claims: "
        f"{len(interpretation_input.claims)}"
    )

    result = provider.interpret(
        interpretation_input
    )

    print("Generation: PASS")

    validate_interpretation_result(
        interpretation_input,
        result,
    )

    print("Structural grounding: PASS")

    validate_semantic_entailment(
        interpretation_input,
        result,
    )

    print(
        "Deterministic semantic validation: PASS"
    )

    validate_model_entailment(
        interpretation_input,
        result,
        judge=judge,
    )

    print("Model semantic entailment: PASS")

    print("\nDirect answer:")
    print(result.direct_answer.text)

    print("\nDirect-answer claims:")
    for claim_id in (
        result.direct_answer.supporting_claim_ids
    ):
        print(f"  - {claim_id}")

    print("\nInterpretation statements:")

    for index, statement in enumerate(
        result.interpretation,
        start=1,
    ):
        print(
            f"\n{index}. {statement.text}"
        )

        print(
            "   Supporting claims:"
        )

        for claim_id in (
            statement.supporting_claim_ids
        ):
            print(
                f"     - {claim_id}"
            )

    print("\nLimitations:")
    for limitation in result.limitations:
        print(
            f"  - {limitation}"
        )

    if result.follow_up_questions:
        print("\nFollow-up questions:")

        for follow_up in (
            result.follow_up_questions
        ):
            print(
                f"  - {follow_up}"
            )

    if result.warnings:
        print("\nWarnings:")

        for warning in result.warnings:
            print(
                f"  - {warning}"
            )

    print(
        f"\n{label}: FULL CHAIN PASS"
    )


def main() -> None:
    print("=" * 80)
    print(
        "EpiCounty Full AI Chain Validation "
        "Across All Supported Intents"
    )
    print("=" * 80)

    provider = OpenAIInterpretationProvider(
        model="gpt-5.6"
    )

    judge = OpenAIEntailmentJudge(
        model="gpt-5.6"
    )

    passed = 0

    for label, question_text in QUESTIONS:
        run_case(
            label,
            question_text,
            provider,
            judge,
        )

        passed += 1

    print("\n" + "=" * 80)
    print(
        f"ALL SUPPORTED INTENTS PASSED: "
        f"{passed}/{len(QUESTIONS)}"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()