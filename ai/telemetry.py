from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from ai.models import (
    ResearchAssistantOutcome,
    ResearchTelemetryEvent,
    TelemetryOutcome,
)


def build_research_telemetry_event(
    outcome: ResearchAssistantOutcome,
    *,
    latency_ms: float | None = None,
) -> ResearchTelemetryEvent:
    """
    Build a privacy-conscious telemetry event from a completed
    ResearchAssistantOutcome.

    This function performs no persistence and stores no raw research
    question text.
    """

    try:
        telemetry_outcome = TelemetryOutcome(
            outcome.status
        )
    except ValueError:
        telemetry_outcome = TelemetryOutcome.ERROR

    resolved_plan = outcome.resolved_plan
    evidence = outcome.evidence_bundle

    resolved_context = (
        resolved_plan.resolved_context
        if resolved_plan is not None
        else {}
    )

    assumptions_count = len(
        resolved_plan.assumptions
        if resolved_plan is not None
        else outcome.policy_result.assumptions
    )

    unresolved_items_count = len(
        resolved_plan.unresolved_items
        if resolved_plan is not None
        else []
    )

    evidence_item_count = (
        len(evidence.items)
        if evidence is not None
        else 0
    )

    evidence_warning_count = (
        len(evidence.warnings)
        if evidence is not None
        else 0
    )

    county_resolved = any(
        key in resolved_context
        for key in (
            "county",
            "county_name",
            "county_fips",
            "location_id",
        )
    )

    cause_resolved = any(
        key in resolved_context
        for key in (
            "cause",
            "cause_name",
            "cause_id",
        )
    )

    semantic_request = outcome.semantic_request

    return ResearchTelemetryEvent(
        event_id=str(uuid4()),
        timestamp_utc=datetime.now(
            timezone.utc
        ).isoformat(),
        outcome=telemetry_outcome,
        intent=semantic_request.intent.value,
        semantic_confidence=semantic_request.confidence,
        policy_decision=outcome.policy_result.decision.value,
        assumptions_count=assumptions_count,
        unresolved_items_count=unresolved_items_count,
        evidence_item_count=evidence_item_count,
        evidence_warning_count=evidence_warning_count,
        interpretation_succeeded=(
            outcome.interpretation_result is not None
        ),
        ai_error_present=(
            outcome.ai_error is not None
        ),
        latency_ms=latency_ms,
        county_resolved=county_resolved,
        cause_resolved=cause_resolved,
        demographic_dimension_present=(
            semantic_request.demographic_dimension
            is not None
        ),
        clarification_present=(
            outcome.clarification_question
            is not None
        ),
        rejection_present=(
            outcome.rejection_reason
            is not None
        ),
    )


class ResearchTelemetryTimer:
    """
    Small utility for measuring one research-assistant execution.
    """

    def __init__(self) -> None:
        self._started_at: float | None = None

    def start(self) -> None:
        self._started_at = perf_counter()

    def elapsed_ms(self) -> float | None:
        if self._started_at is None:
            return None

        return (
            perf_counter() - self._started_at
        ) * 1000.0