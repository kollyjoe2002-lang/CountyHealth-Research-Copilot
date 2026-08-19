from __future__ import annotations

from ai.entailment_judge import (
    OpenAIEntailmentJudge,
)
from ai.models import EntailmentLabel


CASES = [
    {
        "name": "Supported paraphrase",
        "evidence": (
            "trend.absolute_change: The YLL rate decreased from "
            "606.45 to 412.66, an absolute change of -193.79."
        ),
        "statement": (
            "The YLL rate declined by 193.79, "
            "from 606.45 to 412.66."
        ),
        "expected": EntailmentLabel.ENTAILED,
    },
    {
        "name": "Wrong numeric value",
        "evidence": (
            "trend.relative_change: This corresponds to a "
            "relative change of -32.0%."
        ),
        "statement": (
            "The YLL rate declined by 40.0%."
        ),
        "expected": EntailmentLabel.CONTRADICTED,
    },
    {
        "name": "Unsupported causal explanation",
        "evidence": (
            "trend.relative_change: This corresponds to a "
            "relative change of -32.0%."
        ),
        "statement": (
            "The decline was caused by improved access to care."
        ),
        "expected": EntailmentLabel.UNSUPPORTED,
    },
    {
        "name": "Unsupported factual addition",
        "evidence": (
            "trend.absolute_change: The YLL rate decreased from "
            "606.45 to 412.66, an absolute change of -193.79."
        ),
        "statement": (
            "The YLL rate declined, especially among older adults."
        ),
        "expected": EntailmentLabel.UNSUPPORTED,
    },
    {
        "name": "Direction contradiction",
        "evidence": (
            "trend.absolute_change: The YLL rate decreased from "
            "606.45 to 412.66, an absolute change of -193.79."
        ),
        "statement": (
            "The YLL rate increased over the period."
        ),
        "expected": EntailmentLabel.CONTRADICTED,
    },
]


def main() -> None:
    print("=" * 80)
    print("OpenAI Semantic Entailment Judge Validation")
    print("=" * 80)

    judge = OpenAIEntailmentJudge(
        model="gpt-5.6"
    )

    for case in CASES:
        print("\n" + "-" * 80)
        print(f"Case: {case['name']}")

        judgment = judge.judge(
            statement_text=case["statement"],
            evidence_text=case["evidence"],
        )

        print(
            f"Expected: {case['expected'].value}"
        )

        print(
            f"Received: {judgment.label.value}"
        )

        print(
            f"Rationale: {judgment.rationale}"
        )

        assert (
            judgment.label
            is case["expected"]
        ), (
            f"{case['name']} returned "
            f"{judgment.label.value}; expected "
            f"{case['expected'].value}."
        )

        print("PASS")

    print("\n" + "=" * 80)
    print(
        "OpenAI semantic entailment judge "
        "validation completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()