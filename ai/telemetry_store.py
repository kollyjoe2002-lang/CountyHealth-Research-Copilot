from __future__ import annotations

import json
from pathlib import Path

import duckdb

from ai.models import ResearchTelemetryEvent


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TELEMETRY_DB_FILE = (
    PROJECT_ROOT
    / "database"
    / "epicounty_telemetry.duckdb"
)


CREATE_TELEMETRY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS research_telemetry (
    event_id VARCHAR PRIMARY KEY,
    timestamp_utc TIMESTAMP,

    outcome VARCHAR NOT NULL,
    intent VARCHAR NOT NULL,

    semantic_confidence DOUBLE NOT NULL,
    policy_decision VARCHAR NOT NULL,

    assumptions_count INTEGER NOT NULL,
    unresolved_items_count INTEGER NOT NULL,

    evidence_item_count INTEGER NOT NULL,
    evidence_warning_count INTEGER NOT NULL,

    interpretation_succeeded BOOLEAN NOT NULL,
    ai_error_present BOOLEAN NOT NULL,

    latency_ms DOUBLE,

    county_resolved BOOLEAN NOT NULL,
    cause_resolved BOOLEAN NOT NULL,
    demographic_dimension_present BOOLEAN NOT NULL,

    clarification_present BOOLEAN NOT NULL,
    rejection_present BOOLEAN NOT NULL,

    metadata_json VARCHAR
)
"""


def initialize_telemetry_store(
    db_file: Path = DEFAULT_TELEMETRY_DB_FILE,
) -> None:
    """
    Create the telemetry database and table if they do not already exist.
    """

    db_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = duckdb.connect(
        str(db_file)
    )

    try:
        connection.execute(
            CREATE_TELEMETRY_TABLE_SQL
        )
    finally:
        connection.close()


def append_telemetry_event(
    event: ResearchTelemetryEvent,
    db_file: Path = DEFAULT_TELEMETRY_DB_FILE,
) -> None:
    """
    Append one structured telemetry event.

    No raw research-question text is persisted.
    """

    initialize_telemetry_store(
        db_file
    )

    connection = duckdb.connect(
        str(db_file)
    )

    try:
        connection.execute(
            """
            INSERT INTO research_telemetry VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                event.event_id,
                event.timestamp_utc,
                event.outcome.value,
                event.intent,
                event.semantic_confidence,
                event.policy_decision,
                event.assumptions_count,
                event.unresolved_items_count,
                event.evidence_item_count,
                event.evidence_warning_count,
                event.interpretation_succeeded,
                event.ai_error_present,
                event.latency_ms,
                event.county_resolved,
                event.cause_resolved,
                event.demographic_dimension_present,
                event.clarification_present,
                event.rejection_present,
                json.dumps(
                    event.metadata,
                    sort_keys=True,
                ),
            ],
        )

    finally:
        connection.close()