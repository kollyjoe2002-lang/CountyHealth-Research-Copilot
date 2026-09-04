from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path

import duckdb

from ai.telemetry_store import DEFAULT_TELEMETRY_DB_FILE

from enum import Enum

class TelemetryTrafficScope(str, Enum):
    """
    Supported provenance scopes for deterministic telemetry aggregation.
    """

    ALL = "all"
    EXTERNAL_BETA = "external_beta"
    INTERNAL = "internal"

@dataclass(frozen=True)
class TelemetrySummary:
    """
    Deterministic aggregate metrics for EpiCounty beta telemetry.

    This summary operates only on structured operational metadata.
    It does not access or reconstruct raw research-question text.
    """

    total_requests: int

    answer_count: int
    clarify_count: int
    reject_count: int

    answer_rate: float
    clarification_rate: float
    rejection_rate: float

    interpretation_success_count: int
    interpretation_failure_count: int
    interpretation_success_rate: float

    median_latency_ms: float | None
    p95_latency_ms: float | None

    evidence_warning_event_count: int

    intent_counts: dict[str, int] = field(
        default_factory=dict
    )

    policy_decision_counts: dict[str, int] = field(
        default_factory=dict
    )


def _safe_rate(
    numerator: int,
    denominator: int,
) -> float:
    """
    Return a deterministic proportion in the range 0.0-1.0.

    Empty denominators return 0.0 rather than raising.
    """

    if denominator <= 0:
        return 0.0

    return numerator / denominator


def _build_scope_filter(
    traffic_scope: TelemetryTrafficScope,
) -> tuple[str, list[str]]:
    """
    Return a trusted SQL predicate and parameters for one supported
    telemetry provenance scope.

    Legacy rows with empty metadata are treated as internal traffic.
    """

    if traffic_scope == TelemetryTrafficScope.ALL:
        return "TRUE", []

    if traffic_scope == TelemetryTrafficScope.EXTERNAL_BETA:
        launch_utc = os.getenv(
            "EPICOUNTY_BETA_LAUNCH_UTC"
        )

        where_sql = """
            COALESCE(
                json_extract_string(
                    metadata_json,
                    '$.environment'
                ),
                ''
            ) = ?
            AND COALESCE(
                json_extract_string(
                    metadata_json,
                    '$.traffic_source'
                ),
                ''
            ) = ?
        """

        parameters = [
            "beta",
            "external_researcher",
        ]

        if launch_utc:
            where_sql += """
                AND timestamp_utc >= CAST(? AS TIMESTAMP)
            """
            parameters.append(launch_utc)

        return where_sql, parameters

    if traffic_scope == TelemetryTrafficScope.INTERNAL:
        return (
            """
            NOT (
                COALESCE(
                    json_extract_string(
                        metadata_json,
                        '$.environment'
                    ),
                    ''
                ) = ?
                AND COALESCE(
                    json_extract_string(
                        metadata_json,
                        '$.traffic_source'
                    ),
                    ''
                ) = ?
            )
            """,
            [
                "beta",
                "external_researcher",
            ],
        )

    raise ValueError(
        f"Unsupported telemetry traffic scope: {traffic_scope}"
    )


def _fetch_count_map(
    connection: duckdb.DuckDBPyConnection,
    *,
    column_name: str,
    where_sql: str = "TRUE",
    parameters: list[str] | None = None,
) -> dict[str, int]:
    """
    Return counts grouped by one trusted telemetry column.

    column_name must be one of the explicitly supported columns below.
    """

    allowed_columns = {
        "intent",
        "policy_decision",
    }

    if column_name not in allowed_columns:
        raise ValueError(
            f"Unsupported telemetry grouping column: {column_name}"
        )

    rows = connection.execute(
        f"""
        SELECT
            {column_name},
            COUNT(*) AS event_count
        FROM research_telemetry
        WHERE {where_sql}
        GROUP BY {column_name}
        ORDER BY {column_name}
        """,
        parameters or [],
    ).fetchall()

    return {
        str(name): int(count)
        for name, count in rows
    }


def build_telemetry_summary(
    db_file: Path = DEFAULT_TELEMETRY_DB_FILE,
    *,
    traffic_scope: TelemetryTrafficScope = (
        TelemetryTrafficScope.ALL
    ),
) -> TelemetrySummary:
    """
    Build deterministic aggregate beta-health metrics from the
    telemetry DuckDB store.

    The function is read-only and does not modify telemetry data.
    """

    if not db_file.exists():
        return TelemetrySummary(
            total_requests=0,
            answer_count=0,
            clarify_count=0,
            reject_count=0,
            answer_rate=0.0,
            clarification_rate=0.0,
            rejection_rate=0.0,
            interpretation_success_count=0,
            interpretation_failure_count=0,
            interpretation_success_rate=0.0,
            median_latency_ms=None,
            p95_latency_ms=None,
            evidence_warning_event_count=0,
            intent_counts={},
            policy_decision_counts={},
        )

    connection = duckdb.connect(
        str(db_file),
        read_only=True,
    )
    where_sql, parameters = _build_scope_filter(
        traffic_scope
    )
    try:
        total_requests_row = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM research_telemetry
            WHERE {where_sql}
            """,
            parameters,
        ).fetchone()

        total_requests = int(
            total_requests_row[0]
            if total_requests_row is not None
            else 0
        )

        answer_count = int(
            connection.execute(
                f"""
                SELECT COUNT(*)
                FROM research_telemetry
                WHERE
                    ({where_sql})
                    AND outcome = 'answer'
                """,
                parameters,
            ).fetchone()[0]
        )
        clarify_count = int(
            connection.execute(
                f"""
                SELECT COUNT(*)
                FROM research_telemetry
                WHERE
                    ({where_sql})
                    AND outcome = 'clarify'
                """,
                parameters,
            ).fetchone()[0]
        )

        reject_row = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM research_telemetry
            WHERE
                ({where_sql})
                AND outcome = 'reject'
            """,
            parameters,
        ).fetchone()
        reject_count = int(reject_row[0] if reject_row is not None else 0)

        interpretation_success_row = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM research_telemetry
            WHERE
                ({where_sql})
                AND outcome = 'answer'
                AND interpretation_succeeded = TRUE
            """,
            parameters,
        ).fetchone()
        interpretation_success_count = int(
            interpretation_success_row[0]
            if interpretation_success_row is not None
            else 0
        )

        interpretation_failure_row = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM research_telemetry
            WHERE
                ({where_sql})
                AND outcome = 'answer'
                AND interpretation_succeeded = FALSE
            """,
            parameters,
        ).fetchone()

        interpretation_failure_count = int(
            interpretation_failure_row[0]
            if interpretation_failure_row is not None
            else 0
        )
        latency_row = connection.execute(
            f"""
            SELECT
                median(latency_ms),
                quantile_cont(latency_ms, 0.95)
            FROM research_telemetry
            WHERE
                ({where_sql})
                AND latency_ms IS NOT NULL
            """,
            parameters,
        ).fetchone()

        median_latency_ms = (
            float(latency_row[0])
            if latency_row is not None
            and latency_row[0] is not None
            else None
        )

        p95_latency_ms = (
            float(latency_row[1])
            if latency_row is not None
            and latency_row[1] is not None
            else None
        )

        evidence_warning_row = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM research_telemetry
            WHERE
                ({where_sql})
                AND evidence_warning_count > 0
            """,
            parameters,
        ).fetchone()
        evidence_warning_event_count = int(
            evidence_warning_row[0]
            if evidence_warning_row is not None
            and evidence_warning_row[0] is not None
            else 0
        )

        intent_counts = _fetch_count_map(
            connection,
            column_name="intent",
            where_sql=where_sql,
            parameters=parameters,
        )

        policy_decision_counts = _fetch_count_map(
            connection,
            column_name="policy_decision",
            where_sql=where_sql,
            parameters=parameters,
        )

    finally:
        connection.close()

    return TelemetrySummary(
        total_requests=total_requests,
        answer_count=answer_count,
        clarify_count=clarify_count,
        reject_count=reject_count,
        answer_rate=_safe_rate(
            answer_count,
            total_requests,
        ),
        clarification_rate=_safe_rate(
            clarify_count,
            total_requests,
        ),
        rejection_rate=_safe_rate(
            reject_count,
            total_requests,
        ),
        interpretation_success_count=(
            interpretation_success_count
        ),
        interpretation_failure_count=(
            interpretation_failure_count
        ),
        interpretation_success_rate=_safe_rate(
            interpretation_success_count,
            answer_count,
        ),
        median_latency_ms=median_latency_ms,
        p95_latency_ms=p95_latency_ms,
        evidence_warning_event_count=(
            evidence_warning_event_count
        ),
        intent_counts=intent_counts,
        policy_decision_counts=policy_decision_counts,
    )
