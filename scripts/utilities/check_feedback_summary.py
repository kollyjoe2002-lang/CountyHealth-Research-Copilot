from __future__ import annotations

import tempfile
from pathlib import Path

from ai.feedback_store import (
    append_research_feedback,
    build_research_feedback,
)
from ai.feedback_summary import build_feedback_summary


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_file = (
            Path(temp_dir)
            / "feedback_summary_test.duckdb"
        )

        feedback_rows = [
            build_research_feedback(
                anonymous_session_id="session-1",
                beta_cohort="beta_2026_01",
                helpfulness="Yes",
                clarity="Clear",
                perceived_accuracy="Accurate",
                intent="county_profile",
            ),
            build_research_feedback(
                anonymous_session_id="session-2",
                beta_cohort="beta_2026_01",
                helpfulness="Yes",
                clarity="Somewhat clear",
                perceived_accuracy="Accurate",
                intent="trend_comparison",
            ),
            build_research_feedback(
                anonymous_session_id="session-3",
                beta_cohort="beta_2026_01",
                helpfulness="Partly",
                clarity="Clear",
                perceived_accuracy="Unsure",
                intent="county_profile",
            ),
            build_research_feedback(
                anonymous_session_id="session-4",
                beta_cohort="other_cohort",
                helpfulness="No",
                clarity="Unclear",
                perceived_accuracy="Inaccurate",
                intent="county_ranking",
            ),
        ]

        for feedback in feedback_rows:
            append_research_feedback(
                feedback,
                db_file=db_file,
            )

        summary = build_feedback_summary(
            db_file,
            beta_cohort="beta_2026_01",
        )

        assert summary.total_feedback == 3

        assert summary.helpful_count == 2
        assert summary.partly_helpful_count == 1
        assert summary.not_helpful_count == 0
        assert summary.helpful_rate == (2 / 3)

        assert summary.clear_count == 2
        assert summary.somewhat_clear_count == 1
        assert summary.unclear_count == 0
        assert summary.clear_rate == (2 / 3)

        assert summary.accurate_count == 2
        assert summary.unsure_accuracy_count == 1
        assert summary.inaccurate_count == 0
        assert summary.accurate_rate == (2 / 3)

        assert summary.intent_feedback_counts == {
            "county_profile": 2,
            "trend_comparison": 1,
        }

        print("PASS: cohort filtering")
        print("PASS: helpfulness aggregation")
        print("PASS: clarity aggregation")
        print("PASS: perceived-accuracy aggregation")
        print("PASS: intent feedback aggregation")

        print()
        print(
            "FEEDBACK SUMMARY VALIDATION: "
            "ALL CHECKS PASSED"
        )


if __name__ == "__main__":
    main()