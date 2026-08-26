from __future__ import annotations

import tempfile
from pathlib import Path

import duckdb

from ai.research_assistant import run_research_assistant
from ai.telemetry import build_research_telemetry_event
from ai.telemetry_store import append_telemetry_event


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_file = (
            Path(temp_dir)
            / "test_telemetry.duckdb"
        )

        outcome = run_research_assistant(
            "Breast cancer in Milwaukee County, Wisconsin"
        )

        event = build_research_telemetry_event(
            outcome,
            latency_ms=125.5,
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
                SELECT
                    event_id,
                    outcome,
                    intent,
                    policy_decision,
                    evidence_item_count,
                    interpretation_succeeded,
                    latency_ms
                FROM research_telemetry
                """
            ).fetchone()

            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM research_telemetry
                """
            ).fetchone()[0]

        finally:
            connection.close()

        assert count == 1
        assert row is not None

        assert row[0] == event.event_id
        assert row[1] == "answer"
        assert row[2] == "county_cause_snapshot"
        assert row[3] == "execute"
        assert row[4] > 0
        assert row[5] is True
        assert row[6] == 125.5

        print(
            "PASS: telemetry event persisted "
            "and retrieved successfully"
        )

        print(
            "PASS: test used isolated temporary "
            "DuckDB database"
        )

        print()
        print(
            "TELEMETRY STORE VALIDATION: "
            "ALL CHECKS PASSED"
        )


if __name__ == "__main__":
    main()