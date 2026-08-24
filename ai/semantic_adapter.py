from __future__ import annotations

from ai.models import (
    ClassifiedQuestion,
    SemanticAnalysisRequest,
)


def semantic_request_to_classified(
    request: SemanticAnalysisRequest,
) -> ClassifiedQuestion:
    """
    Convert a validated semantic interpretation into the existing
    ClassifiedQuestion contract used by the deterministic planner.

    This adapter performs no analytics and does not access the database.
    """

    entities: dict[str, object] = {}

    years: list[int] = []

    if request.year is not None:
        years.append(int(request.year))

    if request.start_year is not None:
        years.append(int(request.start_year))

    if request.end_year is not None:
        years.append(int(request.end_year))

    entities["years"] = sorted(
        set(years)
    )

    if request.county_name:
        entities[
            "semantic_county_name"
        ] = request.county_name

    if request.cause_name:
        entities[
            "semantic_cause_name"
        ] = request.cause_name

    if request.demographic_dimension:
        entities[
            "dimension"
        ] = request.demographic_dimension

    if request.demographic_groups:
        entities[
            "demographic_groups"
        ] = list(
            request.demographic_groups
        )

    if request.direction:
        entities[
            "direction"
        ] = request.direction

    if request.geographic_scope:
        entities[
            "geographic_scope"
        ] = request.geographic_scope

    return ClassifiedQuestion(
        question=request.question,
        intent=request.intent,
        confidence=request.confidence,
        extracted_entities=entities,
        explanation=(
            "LLM semantic routing: "
            + request.explanation
        ),
    )