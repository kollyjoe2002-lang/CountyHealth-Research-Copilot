from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from ai.models import (
    AnalysisPlan,
    AnalysisStep,
    EvidenceBundle,
    EvidenceItem,
)
from app.data_access import (
    get_bmi_summary,
    get_cause_trend,
    get_county_disparity_ranking,
    get_county_ranking,
    get_long_term_change,
    get_top_causes,
)


class ExecutionError(RuntimeError):
    """Raised when an approved analysis step cannot be executed."""


APPROVED_FUNCTIONS: dict[str, Callable[..., pd.DataFrame]] = {
    "get_bmi_summary": get_bmi_summary,
    "get_top_causes": get_top_causes,
    "get_long_term_change": get_long_term_change,
    "get_cause_trend": get_cause_trend,
    "get_county_disparity_ranking": get_county_disparity_ranking,
    "get_county_ranking": get_county_ranking,
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

        previous_data = result

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
    )