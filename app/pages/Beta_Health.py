from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.telemetry_summary import build_telemetry_summary


st.set_page_config(
    page_title="Beta Health",
    page_icon="📊",
    layout="wide",
)


def _format_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def _format_latency(value: float | None) -> str:
    if value is None:
        return "—"

    if value >= 1000:
        return f"{value / 1000:.2f} s"

    return f"{value:.0f} ms"


def _dict_to_frame(
    values: dict[str, int],
    *,
    category_label: str,
) -> pd.DataFrame:
    if not values:
        return pd.DataFrame(
            columns=[
                category_label,
                "Requests",
            ]
        )

    return pd.DataFrame(
        [
            {
                category_label: key,
                "Requests": count,
            }
            for key, count in values.items()
        ]
    ).sort_values(
        by="Requests",
        ascending=False,
    )


st.title("EpiCounty Beta Health")

st.caption(
    "Internal operational view of privacy-conscious beta telemetry. "
    "Raw researcher questions are not stored in this telemetry system."
)

summary = build_telemetry_summary()

if summary.total_requests == 0:
    st.info(
        "No beta telemetry events are currently available. "
        "This page will populate automatically after researchers "
        "begin using the Research Assistant."
    )

    st.stop()


st.markdown("## Request Outcomes")

metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)

with metric_col_1:
    st.metric(
        "Total requests",
        f"{summary.total_requests:,}",
    )

with metric_col_2:
    st.metric(
        "Answer rate",
        _format_rate(
            summary.answer_rate
        ),
        help=(
            f"{summary.answer_count:,} requests produced "
            "validated analytical answers."
        ),
    )

with metric_col_3:
    st.metric(
        "Clarification rate",
        _format_rate(
            summary.clarification_rate
        ),
        help=(
            f"{summary.clarify_count:,} requests required "
            "additional information."
        ),
    )

with metric_col_4:
    st.metric(
        "Rejection rate",
        _format_rate(
            summary.rejection_rate
        ),
        help=(
            f"{summary.reject_count:,} requests were outside "
            "the currently validated analytical capability."
        ),
    )


st.markdown("## AI Interpretation Reliability")

ai_col_1, ai_col_2, ai_col_3 = st.columns(3)

with ai_col_1:
    st.metric(
        "Interpretation success rate",
        _format_rate(
            summary.interpretation_success_rate
        ),
    )

with ai_col_2:
    st.metric(
        "Validated interpretations",
        f"{summary.interpretation_success_count:,}",
    )

with ai_col_3:
    st.metric(
        "Interpretation failures",
        f"{summary.interpretation_failure_count:,}",
    )

st.caption(
    "Interpretation success is calculated only among requests "
    "that successfully produced deterministic analytical answers."
)


st.markdown("## Performance")

performance_col_1, performance_col_2, performance_col_3 = st.columns(3)

with performance_col_1:
    st.metric(
        "Median latency",
        _format_latency(
            summary.median_latency_ms
        ),
    )

with performance_col_2:
    st.metric(
        "P95 latency",
        _format_latency(
            summary.p95_latency_ms
        ),
    )

with performance_col_3:
    st.metric(
        "Events with evidence warnings",
        f"{summary.evidence_warning_event_count:,}",
    )


st.markdown("## Analytical Demand")

intent_frame = _dict_to_frame(
    summary.intent_counts,
    category_label="Intent",
)

if intent_frame.empty:
    st.info(
        "No analytical-intent telemetry is currently available."
    )
else:
    st.dataframe(
        intent_frame,
        width="stretch",
        hide_index=True,
    )

    st.bar_chart(
        intent_frame.set_index(
            "Intent"
        )["Requests"]
    )


st.markdown("## Policy Decisions")

policy_frame = _dict_to_frame(
    summary.policy_decision_counts,
    category_label="Decision",
)

if policy_frame.empty:
    st.info(
        "No request-policy telemetry is currently available."
    )
else:
    st.dataframe(
        policy_frame,
        width="stretch",
        hide_index=True,
    )

    st.bar_chart(
        policy_frame.set_index(
            "Decision"
        )["Requests"]
    )


with st.expander(
    "How to interpret these beta metrics"
):
    st.markdown(
        """
- **Answer rate** measures how often the current validated engine can
  successfully execute a research request.
- **Clarification rate** measures how often EpiCounty understands the
  analytical direction but needs more information before safe execution.
- **Rejection rate** measures requests outside the currently validated
  analytical capability.
- **Interpretation success rate** measures how often answered requests
  also receive an AI interpretation that passes EpiCounty's grounding
  and entailment validation layers.
- **Median latency** represents the typical recorded response time.
- **P95 latency** represents a slower-end response time and is useful
  for detecting performance deterioration during beta testing.
- **Evidence-warning events** identify analytical responses carrying
  deterministic data warnings that may merit inspection.
        """
    )


st.markdown("---")

st.caption(
    "Internal beta operations page. Telemetry is intended for "
    "product reliability and research-beta evaluation."
)