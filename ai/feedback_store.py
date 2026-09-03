from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FEEDBACK_DB_FILE = (
    PROJECT_ROOT
    / "database"
    / "epicounty_feedback.duckdb"
)


@dataclass(frozen=True)
class ResearchFeedback:
    """
    Privacy-conscious feedback for one completed EpiCounty result.

    Raw research-question text is intentionally excluded.
    """

    feedback_id: str
    timestamp_utc: str

    anonymous_session_id: str
    beta_cohort: str

    helpfulness: str
    clarity: str
    perceived_accuracy: str

    intent: str
    optional_comment: str | None = None


CREATE_FEEDBACK_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS research_feedback (
    feedback_id VARCHAR PRIMARY KEY,
    timestamp_utc TIMESTAMP,

    anonymous_session_id VARCHAR NOT NULL,
    beta_cohort VARCHAR NOT NULL,

    helpfulness VARCHAR NOT NULL,
    clarity VARCHAR NOT NULL,
    perceived_accuracy VARCHAR NOT NULL,

    intent VARCHAR NOT NULL,

    optional_comment VARCHAR
)
"""


def initialize_feedback_store(
    db_file: Path = DEFAULT_FEEDBACK_DB_FILE,
) -> None:
    db_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = duckdb.connect(
        str(db_file)
    )

    try:
        connection.execute(
            CREATE_FEEDBACK_TABLE_SQL
        )
    finally:
        connection.close()


def build_research_feedback(
    *,
    anonymous_session_id: str,
    beta_cohort: str,
    helpfulness: str,
    clarity: str,
    perceived_accuracy: str,
    intent: str,
    optional_comment: str | None = None,
) -> ResearchFeedback:
    return ResearchFeedback(
        feedback_id=str(uuid4()),
        timestamp_utc=datetime.now(
            timezone.utc
        ).isoformat(),
        anonymous_session_id=anonymous_session_id,
        beta_cohort=beta_cohort,
        helpfulness=helpfulness,
        clarity=clarity,
        perceived_accuracy=perceived_accuracy,
        intent=intent,
        optional_comment=(
            optional_comment.strip()
            if optional_comment
            and optional_comment.strip()
            else None
        ),
    )


def append_research_feedback(
    feedback: ResearchFeedback,
    db_file: Path = DEFAULT_FEEDBACK_DB_FILE,
) -> None:
    initialize_feedback_store(
        db_file
    )

    connection = duckdb.connect(
        str(db_file)
    )

    try:
        connection.execute(
            """
            INSERT INTO research_feedback VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                feedback.feedback_id,
                feedback.timestamp_utc,
                feedback.anonymous_session_id,
                feedback.beta_cohort,
                feedback.helpfulness,
                feedback.clarity,
                feedback.perceived_accuracy,
                feedback.intent,
                feedback.optional_comment,
            ],
        )

    finally:
        connection.close()