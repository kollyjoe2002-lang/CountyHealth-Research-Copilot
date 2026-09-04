from __future__ import annotations

import tempfile
from pathlib import Path

from ai.models import (
    ResearchTelemetryEvent,
    TelemetryOutcome,
)
from ai.telemetry_store import append_telemetry_event
from ai.telemetry_summary import (
    TelemetryTrafficScope,
    build_telemetry_summary,
)


def _event(
    *,
    event_id: str,
    metadata: dict,
    timestamp_utc: str = "2026-09-05T20:00:00+00:00",
) -> ResearchTelemetryEvent:
    return ResearchTelemetryEvent(
        event_id=event_id,
        timestamp_utc=timestamp_utc,
        outcome=TelemetryOutcome.ANSWER,
        intent="county_profile",
        semantic_confidence=0.95,
        policy_decision="execute",
        assumptions_count=0,
        unresolved_items_count=0,
        evidence_item_count=2,
        evidence_warning_count=0,
        interpretation_succeeded=True,
        ai_error_present=False,
        latency_ms=100.0,
        county_resolved=True,
        cause_resolved=False,
        demographic_dimension_present=False,
        clarification_present=False,
        rejection_present=False,
        metadata=metadata,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_file = (
            Path(temp_dir)
            / "telemetry_scope_test.duckdb"
        )

        events = [
            _event(
                event_id="legacy",
                metadata={},
            ),
            _event(
                event_id="development",
                metadata={
                    "environment": "development",
                    "traffic_source": "internal_manual",
                },
            ),
            _event(
                event_id="beta-pre-launch",
                timestamp_utc="2026-09-03T20:00:00+00:00",
                metadata={
                    "environment": "beta",
                    "traffic_source": "external_researcher",
                    "beta_cohort": "beta_2026_01",
                    "anonymous_session_id": "session-pre-launch",
                },
            ),
            _event(
                event_id="beta-1",
                metadata={
                    "environment": "beta",
                    "traffic_source": "external_researcher",
                    "beta_cohort": "beta_2026_01",
                    "anonymous_session_id": "session-1",
                },
            ),
            _event(
                event_id="beta-2",
                metadata={
                    "environment": "beta",
                    "traffic_source": "external_researcher",
                    "beta_cohort": "beta_2026_01",
                    "anonymous_session_id": "session-2",
                },
            ),
        ]

        for event in events:
            append_telemetry_event(
                event,
                db_file=db_file,
            )

        all_summary = build_telemetry_summary(
            db_file,
            traffic_scope=TelemetryTrafficScope.ALL,
        )

        external_summary = build_telemetry_summary(
            db_file,
            traffic_scope=(
                TelemetryTrafficScope.EXTERNAL_BETA
            ),
        )

        internal_summary = build_telemetry_summary(
            db_file,
            traffic_scope=(
                TelemetryTrafficScope.INTERNAL
            ),
        )

        assert all_summary.total_requests == 5
        assert external_summary.total_requests == 2
        assert internal_summary.total_requests == 2

        assert (
            all_summary.total_requests
            - external_summary.total_requests
            - internal_summary.total_requests
            == 1
        )

        print("PASS: all traffic count = 5")
        print("PASS: post-launch external beta count = 2")
        print("PASS: internal traffic count = 2")
        print("PASS: pre-launch external beta excluded = 1")

        print()
        print(
            "TELEMETRY SCOPE FILTER VALIDATION: "
            "ALL CHECKS PASSED"
        )


if __name__ == "__main__":
    main()