from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from ai.feedback_store import DEFAULT_FEEDBACK_DB_FILE


@dataclass(frozen=True)
class FeedbackSummary:
    """
    Deterministic aggregate metrics for EpiCounty researcher feedback.
    """

    total_feedback: int

    helpful_count: int
    partly_helpful_count: int
    not_helpful_count: int

    helpful_rate: float

    clear_count: int
    somewhat_clear_count: int
    unclear_count: int

    clear_rate: float

    accurate_count: int
    unsure_accuracy_count: int
    inaccurate_count: int

    accurate_rate: float

    intent_feedback_counts: dict[str, int] = field(
        default_factory=dict
    )


def _safe_rate(
    numerator: int,
    denominator: int,
) -> float:
    if denominator <= 0:
        return 0.0

    return numerator / denominator


def _empty_summary() -> FeedbackSummary:
    return FeedbackSummary(
        total_feedback=0,
        helpful_count=0,
        partly_helpful_count=0,
        not_helpful_count=0,
        helpful_rate=0.0,
        clear_count=0,
        somewhat_clear_count=0,
        unclear_count=0,
        clear_rate=0.0,
        accurate_count=0,
        unsure_accuracy_count=0,
        inaccurate_count=0,
        accurate_rate=0.0,
        intent_feedback_counts={},
    )


def build_feedback_summary(
    db_file: Path = DEFAULT_FEEDBACK_DB_FILE,
    *,
    beta_cohort: str | None = None,
) -> FeedbackSummary:
    """
    Build aggregate researcher-feedback metrics.

    When beta_cohort is provided, only feedback belonging to that
    cohort is included.
    """

    if not db_file.exists():
        return _empty_summary()

    connection = duckdb.connect(
        str(db_file),
        read_only=True,
    )

    if beta_cohort is None:
        where_sql = "TRUE"
        parameters: list[str] = []

    else:
        where_sql = "beta_cohort = ?"
        parameters = [
            beta_cohort
        ]

    try:
        total_row = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM research_feedback
            WHERE {where_sql}
            """,
            parameters,
        ).fetchone()

        total_feedback = int(
            total_row[0]
            if total_row is not None
            else 0
        )

        helpful_row = connection.execute(
            f"""
            SELECT
                SUM(CASE WHEN helpfulness = 'Yes' THEN 1 ELSE 0 END),
                SUM(CASE WHEN helpfulness = 'Partly' THEN 1 ELSE 0 END),
                SUM(CASE WHEN helpfulness = 'No' THEN 1 ELSE 0 END)
            FROM research_feedback
            WHERE {where_sql}
            """,
            parameters,
        ).fetchone()

        helpful_count = int(
            helpful_row[0] or 0
        )

        partly_helpful_count = int(
            helpful_row[1] or 0
        )

        not_helpful_count = int(
            helpful_row[2] or 0
        )

        clarity_row = connection.execute(
            f"""
            SELECT
                SUM(CASE WHEN clarity = 'Clear' THEN 1 ELSE 0 END),
                SUM(
                    CASE
                        WHEN clarity = 'Somewhat clear'
                        THEN 1
                        ELSE 0
                    END
                ),
                SUM(CASE WHEN clarity = 'Unclear' THEN 1 ELSE 0 END)
            FROM research_feedback
            WHERE {where_sql}
            """,
            parameters,
        ).fetchone()

        clear_count = int(
            clarity_row[0] or 0
        )

        somewhat_clear_count = int(
            clarity_row[1] or 0
        )

        unclear_count = int(
            clarity_row[2] or 0
        )

        accuracy_row = connection.execute(
            f"""
            SELECT
                SUM(
                    CASE
                        WHEN perceived_accuracy = 'Accurate'
                        THEN 1
                        ELSE 0
                    END
                ),
                SUM(
                    CASE
                        WHEN perceived_accuracy = 'Unsure'
                        THEN 1
                        ELSE 0
                    END
                ),
                SUM(
                    CASE
                        WHEN perceived_accuracy = 'Inaccurate'
                        THEN 1
                        ELSE 0
                    END
                )
            FROM research_feedback
            WHERE {where_sql}
            """,
            parameters,
        ).fetchone()

        accurate_count = int(
            accuracy_row[0] or 0
        )

        unsure_accuracy_count = int(
            accuracy_row[1] or 0
        )

        inaccurate_count = int(
            accuracy_row[2] or 0
        )

        intent_rows = connection.execute(
            f"""
            SELECT
                intent,
                COUNT(*) AS feedback_count
            FROM research_feedback
            WHERE {where_sql}
            GROUP BY intent
            ORDER BY intent
            """,
            parameters,
        ).fetchall()

        intent_feedback_counts = {
            str(intent): int(count)
            for intent, count in intent_rows
        }

    finally:
        connection.close()

    return FeedbackSummary(
        total_feedback=total_feedback,
        helpful_count=helpful_count,
        partly_helpful_count=partly_helpful_count,
        not_helpful_count=not_helpful_count,
        helpful_rate=_safe_rate(
            helpful_count,
            total_feedback,
        ),
        clear_count=clear_count,
        somewhat_clear_count=somewhat_clear_count,
        unclear_count=unclear_count,
        clear_rate=_safe_rate(
            clear_count,
            total_feedback,
        ),
        accurate_count=accurate_count,
        unsure_accuracy_count=unsure_accuracy_count,
        inaccurate_count=inaccurate_count,
        accurate_rate=_safe_rate(
            accurate_count,
            total_feedback,
        ),
        intent_feedback_counts=(
            intent_feedback_counts
        ),
    )