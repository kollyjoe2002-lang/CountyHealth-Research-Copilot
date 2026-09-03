from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.feedback_summary import build_feedback_summary
from ai.telemetry_summary import (
    TelemetryTrafficScope,
    build_telemetry_summary,
)


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


# ============================================================================
# TRAFFIC SCOPE
# ============================================================================

st.markdown("## Traffic Scope")

traffic_scope_label = st.selectbox(
    "Show telemetry for",
    options=[
        "External beta researchers",
        "All traffic",
        "Development / internal",
    ],
    index=0,
)

traffic_scope_map = {
    "External beta researchers": (
        TelemetryTrafficScope.EXTERNAL_BETA
    ),
    "All traffic": TelemetryTrafficScope.ALL,
    "Development / internal": (
        TelemetryTrafficScope.INTERNAL
    ),
}

traffic_scope = traffic_scope_map[
    traffic_scope_label
]

if traffic_scope == TelemetryTrafficScope.EXTERNAL_BETA:
    st.caption(
        "External beta metrics include only requests tagged as "
        "beta traffic from external researcher sessions."
    )

elif traffic_scope == TelemetryTrafficScope.INTERNAL:
    st.caption(
        "Internal metrics include development, testing, and legacy "
        "telemetry not classified as external beta traffic."
    )

else:
    st.caption(
        "All traffic combines external beta and internal/development "
        "telemetry."
    )


# ============================================================================
# BUILD SUMMARIES
# ============================================================================

summary = build_telemetry_summary(
    traffic_scope=traffic_scope
)

feedback_summary = build_feedback_summary(
    beta_cohort="beta_2026_01"
)


if summary.total_requests == 0:
    st.info(
        "No telemetry events are available for the selected traffic scope."
    )

    st.stop()


# ============================================================================
# REQUEST OUTCOMES
# ============================================================================

st.markdown("## Request Outcomes")

metric_col_1, metric_col_2, metric_col_3, metric_col_4 = (
    st.columns(4)
)

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


# ============================================================================
# AI INTERPRETATION RELIABILITY
# ============================================================================

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


# ============================================================================
# PERFORMANCE
# ============================================================================

st.markdown("## Performance")

performance_col_1, performance_col_2, performance_col_3 = (
    st.columns(3)
)

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


# ============================================================================
# ANALYTICAL DEMAND
# ============================================================================

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


# ============================================================================
# POLICY DECISIONS
# ============================================================================

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


# ============================================================================
# RESEARCHER FEEDBACK
# ============================================================================

st.markdown("## Researcher Feedback")

feedback_col_1, feedback_col_2, feedback_col_3, feedback_col_4 = (
    st.columns(4)
)

with feedback_col_1:
    st.metric(
        "Feedback submissions",
        f"{feedback_summary.total_feedback:,}",
    )

with feedback_col_2:
    st.metric(
        "Helpful rate",
        _format_rate(
            feedback_summary.helpful_rate
        ),
    )

with feedback_col_3:
    st.metric(
        "Clear rate",
        _format_rate(
            feedback_summary.clear_rate
        ),
    )

with feedback_col_4:
    st.metric(
        "Perceived accurate rate",
        _format_rate(
            feedback_summary.accurate_rate
        ),
    )

if feedback_summary.total_feedback == 0:
    st.info(
        "No researcher feedback has been recorded "
        "for this beta cohort."
    )

else:
    helpfulness_frame = pd.DataFrame(
        [
            {
                "Rating": "Yes",
                "Responses": (
                    feedback_summary.helpful_count
                ),
            },
            {
                "Rating": "Partly",
                "Responses": (
                    feedback_summary.partly_helpful_count
                ),
            },
            {
                "Rating": "No",
                "Responses": (
                    feedback_summary.not_helpful_count
                ),
            },
        ]
    )

    clarity_frame = pd.DataFrame(
        [
            {
                "Rating": "Clear",
                "Responses": (
                    feedback_summary.clear_count
                ),
            },
            {
                "Rating": "Somewhat clear",
                "Responses": (
                    feedback_summary.somewhat_clear_count
                ),
            },
            {
                "Rating": "Unclear",
                "Responses": (
                    feedback_summary.unclear_count
                ),
            },
        ]
    )

    accuracy_frame = pd.DataFrame(
        [
            {
                "Rating": "Accurate",
                "Responses": (
                    feedback_summary.accurate_count
                ),
            },
            {
                "Rating": "Unsure",
                "Responses": (
                    feedback_summary.unsure_accuracy_count
                ),
            },
            {
                "Rating": "Inaccurate",
                "Responses": (
                    feedback_summary.inaccurate_count
                ),
            },
        ]
    )

    feedback_tab_1, feedback_tab_2, feedback_tab_3 = (
        st.tabs(
            [
                "Helpfulness",
                "Clarity",
                "Perceived accuracy",
            ]
        )
    )

    with feedback_tab_1:
        st.dataframe(
            helpfulness_frame,
            width="stretch",
            hide_index=True,
        )

        st.bar_chart(
            helpfulness_frame.set_index(
                "Rating"
            )["Responses"]
        )

    with feedback_tab_2:
        st.dataframe(
            clarity_frame,
            width="stretch",
            hide_index=True,
        )

        st.bar_chart(
            clarity_frame.set_index(
                "Rating"
            )["Responses"]
        )

    with feedback_tab_3:
        st.dataframe(
            accuracy_frame,
            width="stretch",
            hide_index=True,
        )

        st.bar_chart(
            accuracy_frame.set_index(
                "Rating"
            )["Responses"]
        )


# ============================================================================
# METHODS NOTE
# ============================================================================

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
- **Researcher feedback** summarizes structured beta responses on
  usefulness, clarity, and perceived accuracy.
        """
    )


st.markdown("---")

st.caption(
    "Internal beta operations page. Telemetry is intended for "
    "product reliability and research-beta evaluation."
)