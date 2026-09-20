from __future__ import annotations

from collections.abc import Callable

try:
    import pandas as pd  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover
    pd = None  # type: ignore[assignment]

from ai.models import (
    AnalysisPlan,
    AnalysisStep,
    EvidenceBundle,
    EvidenceItem,
)
from app.data_access import (
    get_bmi_summary,
    get_cause_trend,
    get_county_cause_record,
    get_county_disparity_ranking,
    get_county_ranking,
    get_long_term_change,
    get_places_ihme_county_trend_context,
    get_top_causes,
)


class ExecutionError(RuntimeError):
    """Raised when an approved analysis step cannot be executed."""


APPROVED_FUNCTIONS: dict[str, Callable[..., pd.DataFrame]] = {
    "get_bmi_summary": get_bmi_summary,
    "get_top_causes": get_top_causes,
    "get_county_cause_record": get_county_cause_record,
    "get_long_term_change": get_long_term_change,
    "get_cause_trend": get_cause_trend,
    "get_county_disparity_ranking": get_county_disparity_ranking,
    "get_county_ranking": get_county_ranking,
    "get_places_ihme_county_trend_context": (
    get_places_ihme_county_trend_context
),
}


NON_EXECUTABLE_OPERATIONS = {
    "resolve_cause",
    "resolve_county",
    "resolve_counties",
    "resolve_groups",
}


def _validate_step_parameters(
    step: AnalysisStep,
) -> None:
    unresolved = [
        key
        for key, value in step.parameters.items()
        if value is None
    ]

    if unresolved:
        raise ExecutionError(
            f"Step '{step.operation}' has unresolved parameters: "
            f"{', '.join(unresolved)}."
        )


def _filter_dataframe(
    dataframe: pd.DataFrame,
    *,
    first_year: int,
    last_year: int,
) -> pd.DataFrame:
    if "year" not in dataframe.columns:
        raise ExecutionError(
            "Year-range filtering requires a 'year' column."
        )

    return dataframe.loc[
        dataframe["year"].between(
            int(first_year),
            int(last_year),
        )
    ].copy()


def _filter_analysis_year_dataframe(
    dataframe: pd.DataFrame,
    *,
    first_year: int,
    last_year: int,
) -> pd.DataFrame:
    if "analysis_year" not in dataframe.columns:
        raise ExecutionError(
            "Analysis-year filtering requires an "
            "'analysis_year' column."
        )

    return dataframe.loc[
        dataframe["analysis_year"].between(
            int(first_year),
            int(last_year),
        )
    ].copy()


def _execute_step(
    step: AnalysisStep,
    previous_data: pd.DataFrame | None,
) -> pd.DataFrame | None:
    if step.operation in NON_EXECUTABLE_OPERATIONS:
        return None

    if step.function_name == "filter_dataframe":
        if previous_data is None:
            raise ExecutionError(
                "filter_dataframe requires a previous DataFrame."
            )

        return _filter_dataframe(
            previous_data,
            **step.parameters,
        )
    if step.function_name == "filter_analysis_year_dataframe":
        if previous_data is None:
            raise ExecutionError(
                "filter_analysis_year_dataframe requires "
                "a previous DataFrame."
            )

        return _filter_analysis_year_dataframe(
            previous_data,
            **step.parameters,
        )

    if step.function_name == "aggregate_long_term_change":
        raise ExecutionError(
            "aggregate_long_term_change is not yet implemented."
        )

    function = APPROVED_FUNCTIONS.get(
        step.function_name
    )

    if function is None:
        raise ExecutionError(
            f"Function '{step.function_name}' is not approved."
        )

    _validate_step_parameters(step)

    return function(
        **step.parameters
    )


def _evidence_title(
    step: AnalysisStep,
) -> str:
    title_map = {
        "bmi_summary": "County BMI summary",
        "top_causes": "Leading attributable causes",
        "long_term_change": "Long-term cause change",
        "county_cause_snapshot": "County disease-burden snapshot",
        "cause_trend": "Cause trend",
        "county_disparity_ranking": (
            "County demographic disparity ranking"
        ),
        "national_county_ranking": (
            "National county ranking"
        ),
        "restrict_year_range": (
            "Requested-period trend"
        ),
        "places_ihme_county_trend": (
    "CDC PLACES and IHME county trend"
),
"restrict_analysis_year_range": (
    "Requested-period cross-source trend"
),
    }

    return title_map.get(
        step.operation,
        step.operation.replace("_", " ").title(),
    )


def execute_plan(
    plan: AnalysisPlan,
) -> EvidenceBundle:
    """
    Execute only approved, fully resolved analytics steps.

    Resolver steps are skipped because they have already populated
    the plan parameters. Every analytical result is stored as an
    EvidenceItem with its originating function and parameters.

    Filtering steps refine the immediately preceding analytical result.
    The filtered result replaces the unfiltered evidence item so downstream
    interpretation receives only the requested analytical period.
    """
    if plan.unresolved_items:
        raise ExecutionError(
            "The plan contains unresolved items: "
            + "; ".join(plan.unresolved_items)
        )

    evidence_items: list[EvidenceItem] = []
    warnings: list[str] = []

    previous_data: pd.DataFrame | None = None

    for step in plan.steps:
        try:
            result = _execute_step(
                step,
                previous_data,
            )

        except Exception as exc:
            raise ExecutionError(
                f"Step {step.step_number} "
                f"('{step.operation}') failed: {exc}"
            ) from exc

        if result is None:
            continue

        is_filter_step = (
            step.function_name
            in {
                "filter_dataframe",
                "filter_analysis_year_dataframe",
            }
            and previous_data is not None
            and bool(evidence_items)
        )

        if is_filter_step:
            previous_item = evidence_items[-1]

            evidence_items[-1] = EvidenceItem(
                evidence_type="dataframe",
                title=_evidence_title(step),
                data=result,
                source_function=previous_item.source_function,
                parameters={
                    **previous_item.parameters,
                    **step.parameters,
                },
                interpretation_note=step.purpose,
            )

            if result.equals(previous_data):
                warnings.append(
                    "The requested year filter matched the full available "
                    "trend period, so the duplicate unfiltered evidence "
                    "table was suppressed."
                )

        else:
            evidence_items.append(
                EvidenceItem(
                    evidence_type="dataframe",
                    title=_evidence_title(step),
                    data=result,
                    source_function=step.function_name,
                    parameters=dict(step.parameters),
                    interpretation_note=step.purpose,
                )
            )

        previous_data = result

        if result.empty:
            warnings.append(
                f"Step '{step.operation}' returned no rows."
            )

    if not evidence_items:
        raise ExecutionError(
            "The plan produced no analytical evidence."
        )

    return EvidenceBundle(
        question=plan.question,
        intent=plan.intent,
        items=evidence_items,
        warnings=warnings,
        context=dict(
            plan.resolved_context
        ),
    )