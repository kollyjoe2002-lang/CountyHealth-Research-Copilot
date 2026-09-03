from __future__ import annotations

import tempfile
from pathlib import Path

import duckdb

from ai.feedback_store import (
    append_research_feedback,
    build_research_feedback,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_file = (
            Path(temp_dir)
            / "feedback_test.duckdb"
        )

        feedback = build_research_feedback(
            anonymous_session_id="session-test-001",
            beta_cohort="beta_2026_01",
            helpfulness="Yes",
            clarity="Clear",
            perceived_accuracy="Accurate",
            intent="county_profile",
            optional_comment=(
                "Useful for understanding the county profile."
            ),
        )

        append_research_feedback(
            feedback,
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
                    anonymous_session_id,
                    beta_cohort,
                    helpfulness,
                    clarity,
                    perceived_accuracy,
                    intent,
                    optional_comment
                FROM research_feedback
                """
            ).fetchone()

        finally:
            connection.close()

        assert row is not None

        assert row[0] == "session-test-001"
        assert row[1] == "beta_2026_01"
        assert row[2] == "Yes"
        assert row[3] == "Clear"
        assert row[4] == "Accurate"
        assert row[5] == "county_profile"

        print("PASS: feedback persisted")
        print("PASS: anonymous session preserved")
        print("PASS: beta cohort preserved")
        print("PASS: structured ratings preserved")

        print()
        print(
            "FEEDBACK STORE VALIDATION: "
            "ALL CHECKS PASSED"
        )


if __name__ == "__main__":
    main()