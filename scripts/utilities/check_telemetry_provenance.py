from __future__ import annotations

import json
import tempfile
from pathlib import Path

import duckdb

from ai.models import (
    ResearchTelemetryEvent,
    TelemetryContext,
    TelemetryOutcome,
)
from ai.telemetry_store import append_telemetry_event


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_file = (
            Path(temp_dir)
            / "telemetry_provenance_test.duckdb"
        )

        context = TelemetryContext(
            environment="beta",
            traffic_source="external_researcher",
            beta_cohort="beta_2026_01",
            anonymous_session_id="session-test-001",
        )

        event = ResearchTelemetryEvent(
            event_id="provenance-test-event",
            timestamp_utc="2026-09-02T19:00:00+00:00",
            outcome=TelemetryOutcome.ANSWER,
            intent="county_profile",
            semantic_confidence=0.98,
            policy_decision="execute",
            assumptions_count=0,
            unresolved_items_count=0,
            evidence_item_count=3,
            evidence_warning_count=0,
            interpretation_succeeded=True,
            ai_error_present=False,
            latency_ms=1234.5,
            county_resolved=True,
            cause_resolved=False,
            demographic_dimension_present=False,
            clarification_present=False,
            rejection_present=False,
            metadata={
                "environment": context.environment,
                "traffic_source": context.traffic_source,
                "beta_cohort": context.beta_cohort,
                "anonymous_session_id": (
                    context.anonymous_session_id
                ),
            },
        )

        append_telemetry_event(
            event,
            db_file=db_file,
        )

        connection = duckdb.connect(
            str(db_file),
            read_only=True,
        )

        try:
            row = connection.execute(
                """
                SELECT metadata_json
                FROM research_telemetry
                WHERE event_id = ?
                """,
                [event.event_id],
            ).fetchone()

        finally:
            connection.close()

        assert row is not None

        metadata = json.loads(
            row[0]
        )

        assert metadata["environment"] == "beta"
        assert (
            metadata["traffic_source"]
            == "external_researcher"
        )
        assert metadata["beta_cohort"] == "beta_2026_01"
        assert (
            metadata["anonymous_session_id"]
            == "session-test-001"
        )

        assert "question" not in metadata
        assert "raw_text" not in metadata
        assert "email" not in metadata
        assert "name" not in metadata
        assert "ip_address" not in metadata

        print(
            "PASS: provenance metadata persisted correctly"
        )

        print(
            "PASS: beta cohort preserved"
        )

        print(
            "PASS: anonymous session identifier preserved"
        )

        print(
            "PASS: no disallowed identifying fields present"
        )

        print()
        print(
            "TELEMETRY PROVENANCE VALIDATION: "
            "ALL CHECKS PASSED"
        )


if __name__ == "__main__":
    main()