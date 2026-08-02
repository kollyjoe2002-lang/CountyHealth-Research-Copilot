from __future__ import annotations

from ai.models import (
    AnalysisIntent,
    AnalysisPlan,
    AnalysisStep,
    ClassifiedQuestion,
)


def _default_year(
    entities: dict[str, object],
) -> int:
    years = entities.get("years", [])

    if isinstance(years, list) and years:
        return int(max(years))

    return 2019


def _year_range(
    entities: dict[str, object],
) -> tuple[int, int]:
    years = entities.get("years", [])

    if isinstance(years, list):
        cleaned = sorted(
            {
                int(year)
                for year in years
            }
        )

        if len(cleaned) >= 2:
            return cleaned[0], cleaned[-1]

        if len(cleaned) == 1:
            return cleaned[0], 2019

    return 2000, 2019


def _demographic_groups(
    entities: dict[str, object],
) -> list[str]:
    groups = entities.get(
        "demographic_groups",
        [],
    )

    if not isinstance(groups, list):
        return []

    return [
        str(group)
        for group in groups
    ]


def build_analysis_plan(
    classified: ClassifiedQuestion,
) -> AnalysisPlan:
    """
    Convert a classified research question into a transparent
    sequence of approved analytical operations.
    """
    intent = classified.intent
    entities = classified.extracted_entities

    steps: list[AnalysisStep] = []
    assumptions: list[str] = []
    unresolved_items: list[str] = []

    if intent == AnalysisIntent.DEMOGRAPHIC_DISPARITY:
        groups = _demographic_groups(entities)
        dimension = entities.get("dimension")
        year = _default_year(entities)

        if dimension is None:
            if any(
                group in {
                    "Non-Latino, Black",
                    "Non-Latino, White",
                }
                for group in groups
            ):
                dimension = "Race / ethnicity"
                assumptions.append(
                    "Race / ethnicity was inferred from the named groups."
                )

        if len(groups) < 2:
            unresolved_items.append(
                "Two demographic groups must be identified."
            )

        if dimension is None:
            unresolved_items.append(
                "The demographic comparison dimension is unresolved."
            )

        steps.extend(
            [
                AnalysisStep(
                    step_number=1,
                    operation="resolve_cause",
                    function_name="get_disparity_causes",
                    parameters={},
                    purpose=(
                        "Resolve the requested disease or cause "
                        "against the validated cause lookup."
                    ),
                ),
                AnalysisStep(
                    step_number=2,
                    operation="resolve_groups",
                    function_name="get_disparity_groups",
                    parameters={
                        "dimension": dimension,
                    },
                    purpose=(
                        "Resolve the requested demographic groups "
                        "against the validated group lookup."
                    ),
                ),
                AnalysisStep(
                    step_number=3,
                    operation="county_disparity_ranking",
                    function_name="get_county_disparity_ranking",
                    parameters={
                        "cause_id": None,
                        "year": year,
                        "dimension": dimension,
                        "group_a_id": None,
                        "group_b_id": None,
                    },
                    purpose=(
                        "Calculate county-level signed and relative "
                        "disparity estimates."
                    ),
                ),
            ]
        )

    elif intent == AnalysisIntent.TREND_COMPARISON:
        first_year, last_year = _year_range(
            entities
        )

        steps.extend(
            [
                AnalysisStep(
                    step_number=1,
                    operation="resolve_counties",
                    function_name="get_counties",
                    parameters={},
                    purpose=(
                        "Resolve requested county names and FIPS codes."
                    ),
                ),
                AnalysisStep(
                    step_number=2,
                    operation="resolve_cause",
                    function_name="get_causes",
                    parameters={},
                    purpose=(
                        "Resolve the requested cause against "
                        "the validated cause lookup."
                    ),
                ),
                AnalysisStep(
                    step_number=3,
                    operation="cause_trend",
                    function_name="get_cause_trend",
                    parameters={
                        "fips": None,
                        "cause_id": None,
                    },
                    purpose=(
                        "Retrieve the annual county cause trend."
                    ),
                ),
                AnalysisStep(
                    step_number=4,
                    operation="restrict_year_range",
                    function_name="filter_dataframe",
                    parameters={
                        "first_year": first_year,
                        "last_year": last_year,
                    },
                    purpose=(
                        "Restrict the evidence to the requested period."
                    ),
                ),
            ]
        )

    elif intent == AnalysisIntent.COUNTY_RANKING:
        year = _default_year(entities)

        steps.extend(
            [
                AnalysisStep(
                    step_number=1,
                    operation="resolve_cause",
                    function_name="get_causes",
                    parameters={},
                    purpose=(
                        "Resolve the requested cause."
                    ),
                ),
                AnalysisStep(
                    step_number=2,
                    operation="national_county_ranking",
                    function_name="get_county_ranking",
                    parameters={
                        "cause_id": None,
                        "year": year,
                    },
                    purpose=(
                        "Retrieve current-county national rankings."
                    ),
                ),
            ]
        )


    elif intent == AnalysisIntent.COUNTY_PROFILE:
        year = _default_year(entities)

        steps.extend(
            [
                AnalysisStep(
                    step_number=1,
                    operation="resolve_county",
                    function_name="get_counties",
                    parameters={},
                    purpose=(
                        "Resolve the requested county and FIPS code."
                    ),
                ),
                AnalysisStep(
                    step_number=2,
                    operation="bmi_summary",
                    function_name="get_bmi_summary",
                    parameters={
                        "fips": None,
                        "year": year,
                    },
                    purpose=(
                        "Retrieve mean BMI, overweight prevalence, "
                        "and obesity prevalence."
                    ),
                ),
                AnalysisStep(
                    step_number=3,
                    operation="top_causes",
                    function_name="get_top_causes",
                    parameters={
                        "fips": None,
                        "year": year,
                        "limit": 10,
                    },
                    purpose=(
                        "Retrieve the leading high-BMI-attributable causes."
                    ),
                ),
                AnalysisStep(
                    step_number=4,
                    operation="long_term_change",
                    function_name="get_long_term_change",
                    parameters={
                        "fips": None,
                    },
                    purpose=(
                        "Retrieve cause-specific long-term change."
                    ),
                ),
            ]
        )

    elif intent == AnalysisIntent.LONG_TERM_CHANGE:
        first_year, last_year = _year_range(
            entities
        )

        steps.extend(
            [
                AnalysisStep(
                    step_number=1,
                    operation="resolve_counties",
                    function_name="get_counties",
                    parameters={},
                    purpose=(
                        "Resolve the relevant county universe."
                    ),
                ),
                AnalysisStep(
                    step_number=2,
                    operation="long_term_change",
                    function_name="get_long_term_change",
                    parameters={
                        "fips": None,
                    },
                    purpose=(
                        "Retrieve long-term cause change for each county."
                    ),
                ),
                AnalysisStep(
                    step_number=3,
                    operation="compare_change",
                    function_name="aggregate_long_term_change",
                    parameters={
                        "first_year": first_year,
                        "last_year": last_year,
                    },
                    purpose=(
                        "Compare changes and identify improvement "
                        "or worsening."
                    ),
                ),
            ]
        )

    else:
        unresolved_items.append(
            "The question does not map to a supported analysis intent."
        )

    return AnalysisPlan(
        question=classified.question,
        intent=intent,
        steps=steps,
        assumptions=assumptions,
        unresolved_items=unresolved_items,
    )