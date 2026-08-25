from ai.research_assistant import run_research_assistant
from ai.telemetry import build_research_telemetry_event


CASES = [
    (
        "answer",
        "Breast cancer in Milwaukee County, Wisconsin",
    ),
    (
        "clarify",
        "Show me the trend in diabetes",
    ),
    (
        "reject",
        "Predict diabetes rates in Milwaukee County in 2035",
    ),
]


def main() -> None:
    passed = 0

    for expected_status, question in CASES:
        outcome = run_research_assistant(
            question
        )

        event = build_research_telemetry_event(
            outcome
        )

        assert event.outcome.value == expected_status
        assert event.event_id
        assert event.timestamp_utc
        assert event.intent
        assert event.semantic_confidence >= 0.0
        assert event.semantic_confidence <= 1.0

        assert question not in repr(event)

        if expected_status == "answer":
            assert event.evidence_item_count > 0

        if expected_status == "clarify":
            assert event.clarification_present

        if expected_status == "reject":
            assert event.rejection_present

        print(
            f"PASS: {expected_status} -> "
            f"{event.intent}"
        )

        passed += 1

    print()
    print(
        "RESEARCH TELEMETRY VALIDATION: "
        f"ALL {passed} CASES PASSED"
    )


if __name__ == "__main__":
    main()