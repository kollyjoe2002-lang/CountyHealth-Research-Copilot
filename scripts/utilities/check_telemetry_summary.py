from __future__ import annotations

import tempfile
from pathlib import Path

from ai.models import (
    ResearchTelemetryEvent,
    TelemetryOutcome,
)
from ai.telemetry_store import append_telemetry_event
from ai.telemetry_summary import build_telemetry_summary


def _make_event(
    *,
    event_id: str,
    outcome: TelemetryOutcome,
    intent: str,
    policy_decision: str,
    interpretation_succeeded: bool,
    latency_ms: float,
    evidence_warning_count: int = 0,
) -> ResearchTelemetryEvent:
    return ResearchTelemetryEvent(
        event_id=event_id,
        timestamp_utc="2026-08-26T12:00:00+00:00",
        outcome=outcome,
        intent=intent,
        semantic_confidence=0.95,
        policy_decision=policy_decision,
        assumptions_count=0,
        unresolved_items_count=0,
        evidence_item_count=(
            2
            if outcome is TelemetryOutcome.ANSWER
            else 0
        ),
        evidence_warning_count=evidence_warning_count,
        interpretation_succeeded=(
            interpretation_succeeded
        ),
        ai_error_present=(
            outcome is TelemetryOutcome.ANSWER
            and not interpretation_succeeded
        ),
        latency_ms=latency_ms,
        county_resolved=False,
        cause_resolved=False,
        demographic_dimension_present=False,
        clarification_present=(
            outcome is TelemetryOutcome.CLARIFY
        ),
        rejection_present=(
            outcome is TelemetryOutcome.REJECT
        ),
        metadata={},
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_file = (
            Path(temp_dir)
            / "telemetry_summary_test.duckdb"
        )

        events = [
            _make_event(
                event_id="event-1",
                outcome=TelemetryOutcome.ANSWER,
                intent="county_cause_snapshot",
                policy_decision="execute",
                interpretation_succeeded=True,
                latency_ms=100.0,
            ),
            _make_event(
                event_id="event-2",
                outcome=TelemetryOutcome.ANSWER,
                intent="trend_comparison",
                policy_decision="execute",
                interpretation_succeeded=False,
                latency_ms=200.0,
                evidence_warning_count=1,
            ),
            _make_event(
                event_id="event-3",
                outcome=TelemetryOutcome.CLARIFY,
                intent="trend_comparison",
                policy_decision="clarify",
                interpretation_succeeded=False,
                latency_ms=50.0,
            ),
            _make_event(
                event_id="event-4",
                outcome=TelemetryOutcome.REJECT,
                intent="unknown",
                policy_decision="reject",
                interpretation_succeeded=False,
                latency_ms=25.0,
            ),
        ]

        for event in events:
            append_telemetry_event(
                event,
                db_file=db_file,
            )

        summary = build_telemetry_summary(
            db_file
        )

        assert summary.total_requests == 4

        assert summary.answer_count == 2
        assert summary.clarify_count == 1
        assert summary.reject_count == 1

        assert summary.answer_rate == 0.5
        assert summary.clarification_rate == 0.25
        assert summary.rejection_rate == 0.25

        assert (
            summary.interpretation_success_count
            == 1
        )

        assert (
            summary.interpretation_failure_count
            == 1
        )

        assert (
            summary.interpretation_success_rate
            == 0.5
        )

        assert summary.median_latency_ms == 75.0

        assert summary.p95_latency_ms is not None
        assert summary.p95_latency_ms > 100.0

        assert (
            summary.evidence_warning_event_count
            == 1
        )

        assert summary.intent_counts == {
            "county_cause_snapshot": 1,
            "trend_comparison": 2,
            "unknown": 1,
        }

        assert summary.policy_decision_counts == {
            "clarify": 1,
            "execute": 2,
            "reject": 1,
        }

        print(
            "PASS: request outcome metrics"
        )

        print(
            "PASS: interpretation success metrics"
        )

        print(
            "PASS: latency aggregation"
        )

        print(
            "PASS: warning-event aggregation"
        )

        print(
            "PASS: intent and policy distributions"
        )

        empty_db = (
            Path(temp_dir)
            / "does_not_exist.duckdb"
        )

        empty_summary = build_telemetry_summary(
            empty_db
        )

        assert empty_summary.total_requests == 0
        assert empty_summary.answer_rate == 0.0
        assert empty_summary.median_latency_ms is None
        assert empty_summary.intent_counts == {}

        print(
            "PASS: missing-store behavior"
        )

        print()
        print(
            "TELEMETRY SUMMARY VALIDATION: "
            "ALL CHECKS PASSED"
        )


if __name__ == "__main__":
    main()