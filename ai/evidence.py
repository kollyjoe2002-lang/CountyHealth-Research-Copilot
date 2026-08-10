from __future__ import annotations

from typing import Any

import pandas as pd

from ai.models import (
    AnalysisIntent,
    EvidenceBundle,
)


class EvidenceInterpretationError(RuntimeError):
    """Raised when an evidence bundle cannot be interpreted safely."""


def _safe_float(
    value: Any,
) -> float | None:
    """
    Convert a value to float when possible.

    Returns None for missing, non-numeric, or non-finite values.
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if not pd.notna(numeric):
        return None

    return numeric


def _format_number(
    value: Any,
    decimals: int = 2,
) -> str:
    """
    Format a numeric value with commas and a fixed number of decimals.
    """
    numeric = _safe_float(value)

    if numeric is None:
        return "not available"

    return f"{numeric:,.{decimals}f}"


def _require_columns(
    dataframe: pd.DataFrame,
    required_columns: set[str],
    *,
    evidence_name: str,
) -> None:
    """
    Confirm that an analytical DataFrame contains required columns.
    """
    missing_columns = required_columns.difference(
        dataframe.columns
    )

    if missing_columns:
        raise EvidenceInterpretationError(
            f"{evidence_name} is missing required columns: "
            f"{sorted(missing_columns)}."
        )


def _find_item(
    bundle: EvidenceBundle,
    source_function: str,
) -> pd.DataFrame:
    """
    Retrieve a DataFrame evidence item by its source function.
    """
    for item in bundle.items:
        if item.source_function == source_function:
            if not isinstance(
                item.data,
                pd.DataFrame,
            ):
                raise EvidenceInterpretationError(
                    f"Evidence from '{source_function}' "
                    "is not a pandas DataFrame."
                )

            return item.data.copy()

    raise EvidenceInterpretationError(
        f"Evidence item from '{source_function}' was not found."
    )


def _interpret_disparity(
    bundle: EvidenceBundle,
) -> list[str]:
    """
    Interpret a county demographic disparity ranking.
    """
    ranking = _find_item(
        bundle,
        "get_county_disparity_ranking",
    )

    if ranking.empty:
        return [
            "No counties had complete estimates for both selected groups."
        ]

    _require_columns(
        ranking,
        {
            "location_name",
            "absolute_gap",
            "relative_gap_percent",
        },
        evidence_name="County disparity ranking",
    )

    ranking["absolute_gap"] = pd.to_numeric(
        ranking["absolute_gap"],
        errors="coerce",
    )

    ranking["relative_gap_percent"] = pd.to_numeric(
        ranking["relative_gap_percent"],
        errors="coerce",
    )

    ranking = ranking.dropna(
        subset=[
            "location_name",
            "absolute_gap",
        ]
    )

    if ranking.empty:
        return [
            "No counties had usable disparity estimates after validation."
        ]

    positive = ranking.loc[
        ranking["absolute_gap"] > 0
    ].copy()

    negative = ranking.loc[
        ranking["absolute_gap"] < 0
    ].copy()

    equal = ranking.loc[
        ranking["absolute_gap"] == 0
    ].copy()

    group_a_name = str(
        bundle.context.get(
            "group_a_name",
            "Group A",
        )
    )

    group_b_name = str(
        bundle.context.get(
            "group_b_name",
            "Group B",
        )
    )
    
    findings = [
        (
            f"{len(ranking):,} current counties had complete estimates "
            "for both demographic groups."
        ),
        (
            f"The median signed disparity gap was "
            f"{_format_number(ranking['absolute_gap'].median())} "
            "YLL-rate units."
        ),
        (
            f"{group_a_name} had the higher estimated rate in "
            f"{len(positive):,} counties, while {group_b_name} had the "
            f"higher estimated rate in {len(negative):,} counties."
        ),
    ]

    if not equal.empty:
        findings.append(
            f"{group_a_name} and {group_b_name} had equal estimated "
            f"rates in {len(equal):,} counties."
        )

    if not positive.empty:
        largest = positive.loc[
            positive["absolute_gap"].idxmax()
        ]

        relative_gap = _safe_float(
            largest.get(
                "relative_gap_percent"
            )
        )

        relative_text = (
            f" and a relative gap of "
            f"{_format_number(relative_gap, 1)}%"
            if relative_gap is not None
            else ""
        )

        findings.append(
            f"The largest positive disparity occurred in "
            f"{largest['location_name']}, with a signed gap of "
            f"{_format_number(largest['absolute_gap'])}"
            f"{relative_text}."
        )

    if not negative.empty:
        reverse = negative.loc[
            negative["absolute_gap"].idxmin()
        ]

        relative_gap = _safe_float(
            reverse.get(
                "relative_gap_percent"
            )
        )

        relative_text = (
            f" and a relative gap of "
            f"{_format_number(relative_gap, 1)}%"
            if relative_gap is not None
            else ""
        )

        findings.append(
            f"The largest reverse disparity occurred in "
            f"{reverse['location_name']}, with a signed gap of "
            f"{_format_number(reverse['absolute_gap'])}"
            f"{relative_text}."
        )

    return findings


def _interpret_trend(
    bundle: EvidenceBundle,
) -> list[str]:
    """
    Interpret a county cause trend.
    """
    try:
        trend = _find_item(
            bundle,
            "filter_dataframe",
        )
    except EvidenceInterpretationError:
        trend = _find_item(
            bundle,
            "get_cause_trend",
        )

    if trend.empty:
        return [
            "No annual trend observations were available."
        ]

    _require_columns(
        trend,
        {
            "year",
            "yll_rate",
        },
        evidence_name="County cause trend",
    )

    trend["year"] = pd.to_numeric(
        trend["year"],
        errors="coerce",
    )

    trend["yll_rate"] = pd.to_numeric(
        trend["yll_rate"],
        errors="coerce",
    )

    trend = (
        trend.dropna(
            subset=[
                "year",
                "yll_rate",
            ]
        )
        .sort_values("year")
        .drop_duplicates(
            subset=["year"],
            keep="last",
        )
        .copy()
    )

    if trend.empty:
        return [
            "No usable annual trend observations were available."
        ]

    first = trend.iloc[0]
    last = trend.iloc[-1]

    first_year = int(first["year"])
    last_year = int(last["year"])

    first_value = _safe_float(
        first["yll_rate"]
    )

    last_value = _safe_float(
        last["yll_rate"]
    )

    findings = [
        (
            f"The trend contained {len(trend):,} annual observations "
            f"from {first_year} through {last_year}."
        )
    ]

    if (
        first_value is not None
        and last_value is not None
    ):
        absolute_change = (
            last_value - first_value
        )

        percent_change = (
            absolute_change
            / first_value
            * 100
            if first_value != 0
            else None
        )

        if absolute_change > 0:
            direction = "increased"
        elif absolute_change < 0:
            direction = "decreased"
        else:
            direction = "did not change"

        findings.append(
            (
                f"The YLL rate {direction} from "
                f"{_format_number(first_value)} to "
                f"{_format_number(last_value)}, an absolute change of "
                f"{_format_number(absolute_change)}."
            )
        )

        if percent_change is not None:
            findings.append(
                (
                    f"This corresponds to a relative change of "
                    f"{_format_number(percent_change, 1)}%."
                )
            )

    peak = trend.loc[
        trend["yll_rate"].idxmax()
    ]

    low = trend.loc[
        trend["yll_rate"].idxmin()
    ]

    findings.extend(
        [
            (
                f"The highest observed rate was "
                f"{_format_number(peak['yll_rate'])} in "
                f"{int(peak['year'])}."
            ),
            (
                f"The lowest observed rate was "
                f"{_format_number(low['yll_rate'])} in "
                f"{int(low['year'])}."
            ),
        ]
    )

    return findings


def _interpret_ranking(
    bundle: EvidenceBundle,
) -> list[str]:
    """
    Interpret a national current-county ranking.
    """
    ranking = _find_item(
        bundle,
        "get_county_ranking",
    )

    if ranking.empty:
        return [
            "No county-ranking records were available."
        ]

    _require_columns(
        ranking,
        {
            "national_display_order",
            "location_name",
            "yll_rate",
        },
        evidence_name="National county ranking",
    )

    ranking["national_display_order"] = pd.to_numeric(
        ranking["national_display_order"],
        errors="coerce",
    )

    ranking["yll_rate"] = pd.to_numeric(
        ranking["yll_rate"],
        errors="coerce",
    )

    ranking = (
        ranking.dropna(
            subset=[
                "national_display_order",
                "location_name",
                "yll_rate",
            ]
        )
        .sort_values(
            "national_display_order"
        )
        .copy()
    )

    if ranking.empty:
        return [
            "No usable county-ranking records were available."
        ]

    top = ranking.iloc[0]
    bottom = ranking.iloc[-1]

    national_range = (
        float(top["yll_rate"])
        - float(bottom["yll_rate"])
    )

    return [
        (
            f"The ranking included {len(ranking):,} current counties."
        ),
        (
            f"{top['location_name']} ranked first nationally, with a "
            f"YLL rate of {_format_number(top['yll_rate'])}."
        ),
        (
            f"{bottom['location_name']} ranked last nationally, with a "
            f"YLL rate of {_format_number(bottom['yll_rate'])}."
        ),
        (
            f"The national range was "
            f"{_format_number(national_range)} "
            "YLL-rate units."
        ),
    ]


def _interpret_county_profile(
    bundle: EvidenceBundle,
) -> list[str]:
    """
    Interpret BMI, leading-cause, and long-term-change evidence
    for a selected county.
    """
    bmi = _find_item(
        bundle,
        "get_bmi_summary",
    )

    top_causes = _find_item(
        bundle,
        "get_top_causes",
    )

    long_term = _find_item(
        bundle,
        "get_long_term_change",
    )

    findings: list[str] = []

    if not bmi.empty:
        _require_columns(
            bmi,
            {
                "metric",
                "value",
            },
            evidence_name="County BMI summary",
        )

        metric_display_names = {
            "mean bmi": "Mean BMI",
            "obesity": "Obesity",
            "overweight": "Overweight",
        }

        for row in bmi.itertuples(
            index=False
        ):
            metric_name = str(
                getattr(
                    row,
                    "metric",
                )
            ).strip()

            metric_key = (
                metric_name.casefold()
            )

            display_metric_name = (
                metric_display_names.get(
                    metric_key,
                    metric_name,
                )
            )

            value = _safe_float(
                getattr(
                    row,
                    "value",
                    None,
                )
            )

            if value is None:
                findings.append(
                    (
                        f"{display_metric_name} was "
                        "not available."
                    )
                )
                continue

            if metric_key in {
                "obesity",
                "overweight",
            }:
                findings.append(
                    (
                        f"{display_metric_name} prevalence was "
                        f"{_format_number(value * 100, 1)}%."
                    )
                )

            else:
                findings.append(
                    (
                        f"{display_metric_name} was "
                        f"{_format_number(value)}."
                    )
                )

    if not top_causes.empty:
        _require_columns(
            top_causes,
            {
                "county_cause_rank",
                "cause_name",
                "yll_rate",
            },
            evidence_name="County leading causes",
        )

        top_causes["county_cause_rank"] = pd.to_numeric(
            top_causes["county_cause_rank"],
            errors="coerce",
        )

        top_causes["yll_rate"] = pd.to_numeric(
            top_causes["yll_rate"],
            errors="coerce",
        )

        valid_top_causes = (
            top_causes.dropna(
                subset=[
                    "county_cause_rank",
                    "cause_name",
                    "yll_rate",
                ]
            )
            .sort_values(
                [
                    "county_cause_rank",
                    "cause_name",
                ]
            )
            .copy()
        )

        if not valid_top_causes.empty:
            leading = valid_top_causes.iloc[0]

            findings.append(
                (
                    f"The leading high-BMI-attributable cause was "
                    f"{leading['cause_name']}, with a YLL rate of "
                    f"{_format_number(leading['yll_rate'])}."
                )
            )

    if not long_term.empty:
        _require_columns(
            long_term,
            {
                "cause_name",
            },
            evidence_name="County long-term change",
        )

        change_column = next(
            (
                column
                for column in [
                    "absolute_change_2000_2019",
                    "absolute_change",
                    "yll_rate_change",
                    "change",
                ]
                if column in long_term.columns
            ),
            None,
        )

        if change_column is not None:
            long_term[change_column] = (
                pd.to_numeric(
                    long_term[change_column],
                    errors="coerce",
                )
            )

            valid_change = long_term.dropna(
                subset=[
                    "cause_name",
                    change_column,
                ]
            ).copy()

            if not valid_change.empty:
                largest_increase = valid_change.loc[
                    valid_change[
                        change_column
                    ].idxmax()
                ]

                largest_decrease = valid_change.loc[
                    valid_change[
                        change_column
                    ].idxmin()
                ]

                findings.extend(
                    [
                        (
                            "The largest long-term increase was observed "
                            f"for {largest_increase['cause_name']} "
                            f"({_format_number(largest_increase[change_column])})."
                        ),
                        (
                            "The largest long-term decrease was observed "
                            f"for {largest_decrease['cause_name']} "
                            f"({_format_number(largest_decrease[change_column])})."
                        ),
                    ]
                )

    if not findings:
        findings.append(
            "No interpretable county-profile evidence was available."
        )

    return findings


def interpret_evidence(
    bundle: EvidenceBundle,
) -> list[str]:
    """
    Convert validated analytical evidence into deterministic findings.
    """
    if bundle.intent == AnalysisIntent.DEMOGRAPHIC_DISPARITY:
        return _interpret_disparity(
            bundle
        )

    if bundle.intent == AnalysisIntent.TREND_COMPARISON:
        return _interpret_trend(
            bundle
        )

    if bundle.intent == AnalysisIntent.COUNTY_RANKING:
        return _interpret_ranking(
            bundle
        )

    if bundle.intent == AnalysisIntent.COUNTY_PROFILE:
        return _interpret_county_profile(
            bundle
        )

    raise EvidenceInterpretationError(
        f"Interpretation is not implemented for "
        f"intent '{bundle.intent.value}'."
    )