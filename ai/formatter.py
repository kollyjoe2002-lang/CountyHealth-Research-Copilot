from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd


class EvidenceFormattingError(RuntimeError):
    """Raised when analytical evidence cannot be formatted safely."""


@dataclass(frozen=True)
class TableFormatRule:
    columns: tuple[str, ...]
    rename: dict[str, str]
    formatter: Callable[[pd.DataFrame], pd.DataFrame] | None = None


def _numeric(
    series: pd.Series,
) -> pd.Series:
    return pd.to_numeric(
        series,
        errors="coerce",
    )


def _format_decimal(
    value: object,
    decimals: int = 2,
) -> str:
    if value is None or pd.isna(value):
        return ""

    return f"{float(value):,.{decimals}f}"


def _format_integer(
    value: object,
) -> str:
    if value is None or pd.isna(value):
        return ""

    return f"{int(float(value)):,}"


def _format_percent(
    value: object,
    decimals: int = 1,
    *,
    proportion: bool = False,
) -> str:
    if value is None or pd.isna(value):
        return ""

    numeric = float(value)

    if proportion:
        numeric *= 100

    return f"{numeric:,.{decimals}f}%"


def _format_fips(
    value: object,
) -> str:
    if value is None or pd.isna(value):
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text.zfill(5)


def _require_columns(
    dataframe: pd.DataFrame,
    required_columns: tuple[str, ...],
    *,
    source_function: str,
) -> None:
    missing = set(required_columns).difference(
        dataframe.columns
    )

    if missing:
        raise EvidenceFormattingError(
            f"Evidence from '{source_function}' is missing "
            f"required columns: {sorted(missing)}."
        )


def _format_bmi_summary(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    display = dataframe.copy()

    display["metric_key"] = (
        display["metric"]
        .astype(str)
        .str.strip()
        .str.casefold()
    )

    metric_order = {
        "mean bmi": 1,
        "obesity": 2,
        "overweight": 3,
    }

    metric_labels = {
        "mean bmi": "Mean BMI",
        "obesity": "Obesity prevalence",
        "overweight": "Overweight prevalence",
    }

    display["sort_order"] = (
        display["metric_key"]
        .map(metric_order)
        .fillna(999)
    )

    display["Metric"] = (
        display["metric_key"]
        .map(metric_labels)
        .fillna(display["metric"])
    )

    for column in [
        "value",
        "lower",
        "upper",
    ]:
        display[column] = _numeric(
            display[column]
        )

    def format_bmi_value(
        row: pd.Series,
        column: str,
    ) -> str:
        value = row[column]

        if row["metric_key"] in {
            "obesity",
            "overweight",
        }:
            return _format_percent(
                value,
                decimals=1,
                proportion=True,
            )

        return _format_decimal(
            value,
            decimals=2,
        )

    display["Estimate"] = display.apply(
        lambda row: format_bmi_value(
            row,
            "value",
        ),
        axis=1,
    )

    display["Lower"] = display.apply(
        lambda row: format_bmi_value(
            row,
            "lower",
        ),
        axis=1,
    )

    display["Upper"] = display.apply(
        lambda row: format_bmi_value(
            row,
            "upper",
        ),
        axis=1,
    )

    return (
        display.sort_values(
            "sort_order"
        )[
            [
                "Metric",
                "Estimate",
                "Lower",
                "Upper",
            ]
        ]
        .reset_index(drop=True)
    )


def _format_year(
    value: object,
) -> str:
    """
    Format a calendar year without thousands separators.
    """
    if pd.isna(value):
        return ""

    try:
        return str(
            int(float(value))
        )
    except (
        TypeError,
        ValueError,
    ):
        return str(value)
    
    
def _format_top_causes(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    display = dataframe.copy()

    for column in [
        "county_cause_rank",
        "yll_rate",
        "lower",
        "upper",
        "national_county_rank",
        "burden_percentile",
    ]:
        if column in display.columns:
            display[column] = _numeric(
                display[column]
            )

    display = display.sort_values(
        [
            "county_cause_rank",
            "cause_name",
        ]
    )

    formatted = pd.DataFrame(
        {
            "County Rank": display[
                "county_cause_rank"
            ].map(_format_integer),
            "Cause": display[
                "cause_name"
            ].astype(str),
            "YLL Rate": display[
                "yll_rate"
            ].map(_format_decimal),
            "Lower": display[
                "lower"
            ].map(_format_decimal),
            "Upper": display[
                "upper"
            ].map(_format_decimal),
            "National Rank": display[
                "national_county_rank"
            ].map(_format_integer),
            "Percentile": display[
                "burden_percentile"
            ].map(
                lambda value: _format_percent(
                    value,
                    decimals=1,
                    proportion=False,
                )
            ),
        }
    )

    return formatted.reset_index(
        drop=True
    )


def _format_long_term_change(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    display = dataframe.copy()

    for column in [
        "yll_rate_2000",
        "yll_rate_2019",
        "absolute_change_2000_2019",
        "percent_change_2000_2019",
    ]:
        if column in display.columns:
            display[column] = _numeric(
                display[column]
            )

    display = display.sort_values(
        "absolute_change_2000_2019",
        ascending=False,
    )

    formatted = pd.DataFrame(
        {
            "Cause": display[
                "cause_name"
            ].astype(str),
            "2000 Rate": display[
                "yll_rate_2000"
            ].map(_format_decimal),
            "2019 Rate": display[
                "yll_rate_2019"
            ].map(_format_decimal),
            "Absolute Change": display[
                "absolute_change_2000_2019"
            ].map(_format_decimal),
            "Percent Change": display[
                "percent_change_2000_2019"
            ].map(
                lambda value: _format_percent(
                    value,
                    decimals=1,
                    proportion=False,
                )
            ),
            "Direction": display[
                "trend_direction"
            ].astype(str),
        }
    )

    return formatted.reset_index(
        drop=True
    )


def _format_county_ranking(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    display = dataframe.copy()

    for column in [
        "national_display_order",
        "yll_rate",
        "lower",
        "upper",
        "burden_percentile",
    ]:
        if column in display.columns:
            display[column] = _numeric(
                display[column]
            )

    display = display.sort_values(
        "national_display_order"
    )

    formatted = pd.DataFrame(
        {
            "Rank": display[
                "national_display_order"
            ].map(_format_integer),
            "County": display[
                "location_name"
            ].astype(str),
            "FIPS": display[
                "fips"
            ].map(_format_fips),
            "YLL Rate": display[
                "yll_rate"
            ].map(_format_decimal),
            "Lower": display[
                "lower"
            ].map(_format_decimal),
            "Upper": display[
                "upper"
            ].map(_format_decimal),
            "Percentile": display[
                "burden_percentile"
            ].map(
                lambda value: _format_percent(
                    value,
                    decimals=1,
                    proportion=False,
                )
            ),
        }
    )

    return formatted.reset_index(
        drop=True
    )


def _format_cause_trend(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    display = dataframe.copy()

    for column in [
        "year",
        "yll_rate",
        "lower",
        "upper",
    ]:
        if column in display.columns:
            display[column] = _numeric(
                display[column]
            )

    display = display.sort_values(
        "year"
    )

    formatted = pd.DataFrame(
        {
           "Year": display[
               "year"
            ].map(_format_year),
            "YLL Rate": display[
                "yll_rate"
            ].map(_format_decimal),
            "Lower": display[
                "lower"
            ].map(_format_decimal),
            "Upper": display[
                "upper"
            ].map(_format_decimal),
        }
    )

    return formatted.reset_index(
        drop=True
    )


def _format_disparity_ranking(
    dataframe: pd.DataFrame,
    *,
    context: dict[str, object] | None = None,
) -> pd.DataFrame:
    """
    Format county demographic disparity evidence using
    resolved demographic labels when available.
    """
    display = dataframe.copy()

    context = context or {}

    group_a_name = str(
        context.get(
            "group_a_name",
            "Comparison Group",
        )
    )

    group_b_name = str(
        context.get(
            "group_b_name",
            "Reference Group",
        )
    )

    for column in [
        "group_a_value",
        "group_b_value",
        "absolute_gap",
        "absolute_gap_magnitude",
        "relative_gap_percent",
    ]:
        if column in display.columns:
            display[column] = _numeric(
                display[column]
            )

    display = display.sort_values(
        "absolute_gap",
        ascending=False,
    )

    formatted = pd.DataFrame(
        {
            "County": display[
                "location_name"
            ].astype(str),
            "FIPS": display[
                "fips"
            ].map(_format_fips),
            f"{group_a_name} Rate": display[
                "group_a_value"
            ].map(_format_decimal),
            f"{group_b_name} Rate": display[
                "group_b_value"
            ].map(_format_decimal),
            "Signed Gap": display[
                "absolute_gap"
            ].map(_format_decimal),
            "Gap Magnitude": display[
                "absolute_gap_magnitude"
            ].map(_format_decimal),
            "Relative Gap": display[
                "relative_gap_percent"
            ].map(
                lambda value: _format_percent(
                    value,
                    decimals=1,
                    proportion=False,
                )
            ),
        }
    )

    return formatted.reset_index(
        drop=True
    )


FORMAT_RULES: dict[
    str,
    TableFormatRule,
] = {
    "get_bmi_summary": TableFormatRule(
        columns=(
            "metric",
            "value",
            "lower",
            "upper",
        ),
        rename={},
        formatter=_format_bmi_summary,
    ),
    "get_top_causes": TableFormatRule(
        columns=(
            "county_cause_rank",
            "cause_name",
            "yll_rate",
            "lower",
            "upper",
            "national_county_rank",
            "burden_percentile",
        ),
        rename={},
        formatter=_format_top_causes,
    ),
    "get_long_term_change": TableFormatRule(
        columns=(
            "cause_name",
            "yll_rate_2000",
            "yll_rate_2019",
            "absolute_change_2000_2019",
            "percent_change_2000_2019",
            "trend_direction",
        ),
        rename={},
        formatter=_format_long_term_change,
    ),
    "get_county_ranking": TableFormatRule(
        columns=(
            "national_display_order",
            "location_name",
            "fips",
            "yll_rate",
            "lower",
            "upper",
            "burden_percentile",
        ),
        rename={},
        formatter=_format_county_ranking,
    ),
    "get_cause_trend": TableFormatRule(
        columns=(
            "year",
            "yll_rate",
            "lower",
            "upper",
        ),
        rename={},
        formatter=_format_cause_trend,
    ),
    "filter_dataframe": TableFormatRule(
        columns=(
            "year",
            "yll_rate",
            "lower",
            "upper",
        ),
        rename={},
        formatter=_format_cause_trend,
    ),
    "get_county_disparity_ranking": TableFormatRule(
        columns=(
            "location_name",
            "fips",
            "group_a_value",
            "group_b_value",
            "absolute_gap",
            "absolute_gap_magnitude",
            "relative_gap_percent",
        ),
        rename={},
        formatter=_format_disparity_ranking,
    ),
}


def format_evidence_table(
    source_function: str,
    dataframe: pd.DataFrame,
    *,
    context: dict[str, object] | None = None,
) -> pd.DataFrame:
    """
    Convert a raw analytical DataFrame into a compact,
    publication-ready table.

    Context may contain resolved analytical metadata such as
    demographic group names.

    Unknown evidence types are returned as a copy of the original
    DataFrame so the exporter remains forward-compatible.
    """
    if not isinstance(
        dataframe,
        pd.DataFrame,
    ):
        raise EvidenceFormattingError(
            "Evidence data must be a pandas DataFrame."
        )

    if dataframe.empty:
        return dataframe.copy()

    rule = FORMAT_RULES.get(
        source_function
    )

    if rule is None:
        return dataframe.copy()

    _require_columns(
        dataframe,
        rule.columns,
        source_function=source_function,
    )

    if (
        source_function
        == "get_county_disparity_ranking"
    ):
        return _format_disparity_ranking(
            dataframe.copy(),
            context=context,
        )

    if rule.formatter is not None:
        return rule.formatter(
            dataframe.copy()
        )

    display = dataframe.loc[
        :,
        list(rule.columns),
    ].copy()

    if rule.rename:
        display = display.rename(
            columns=rule.rename
        )

    return display.reset_index(
        drop=True
    )


def table_caption(
    source_function: str,
    fallback_title: str,
) -> str:
    captions = {
        "get_bmi_summary":
            "County BMI Summary",
        "get_top_causes":
            "Leading High-BMI-Attributable Causes",
        "get_long_term_change":
            "Long-Term Cause Change, 2000–2019",
        "get_county_ranking":
            "National County Ranking",
        "get_cause_trend":
            "Annual Disease-Burden Trend",
        "filter_dataframe":
            "Requested-Period Disease-Burden Trend",
        "get_county_disparity_ranking":
            "County Demographic Disparity Ranking",
    }

    return captions.get(
        source_function,
        fallback_title,
    )