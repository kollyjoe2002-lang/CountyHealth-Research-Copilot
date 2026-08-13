from __future__ import annotations

from io import BytesIO
from typing import Callable

import matplotlib.pyplot as plt
import pandas as pd

from ai.models import AnalysisIntent, EvidenceBundle


class FigureGenerationError(RuntimeError):
    """Raised when a validated evidence figure cannot be created safely."""


def _find_dataframe(
    bundle: EvidenceBundle,
    source_function: str,
) -> pd.DataFrame:
    """
    Retrieve a DataFrame evidence item by source function.
    """
    for item in bundle.items:
        if item.source_function == source_function:
            if not isinstance(
                item.data,
                pd.DataFrame,
            ):
                raise FigureGenerationError(
                    f"Evidence from '{source_function}' "
                    "is not a pandas DataFrame."
                )

            return item.data.copy()

    raise FigureGenerationError(
        f"Evidence item from '{source_function}' was not found."
    )


def _require_columns(
    dataframe: pd.DataFrame,
    required: set[str],
    *,
    figure_name: str,
) -> None:
    """
    Confirm required analytical columns exist.
    """
    missing = required.difference(
        dataframe.columns
    )

    if missing:
        raise FigureGenerationError(
            f"{figure_name} is missing required columns: "
            f"{sorted(missing)}."
        )


def _numeric(
    dataframe: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """
    Convert selected columns to numeric values.
    """
    result = dataframe.copy()

    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(
                result[column],
                errors="coerce",
            )

    return result


def _figure_to_png_bytes(
    figure,
    *,
    dpi: int = 180,
) -> bytes:
    """
    Serialize a Matplotlib figure to PNG bytes.
    """
    buffer = BytesIO()

    figure.savefig(
        buffer,
        format="png",
        dpi=dpi,
        bbox_inches="tight",
    )

    buffer.seek(0)

    png_bytes = buffer.getvalue()

    plt.close(
        figure
    )

    return png_bytes


def _build_trend_figure(
    bundle: EvidenceBundle,
):
    """
    Build an annual YLL-rate trend figure.
    """
    try:
        dataframe = _find_dataframe(
            bundle,
            "filter_dataframe",
        )
    except FigureGenerationError:
        dataframe = _find_dataframe(
            bundle,
            "get_cause_trend",
        )

    _require_columns(
        dataframe,
        {
            "year",
            "yll_rate",
        },
        figure_name="Trend figure",
    )

    dataframe = _numeric(
        dataframe,
        [
            "year",
            "yll_rate",
            "lower",
            "upper",
        ],
    )

    dataframe = (
        dataframe.dropna(
            subset=[
                "year",
                "yll_rate",
            ]
        )
        .sort_values("year")
        .copy()
    )

    if dataframe.empty:
        raise FigureGenerationError(
            "No usable trend observations were available."
        )

    figure, axis = plt.subplots(
        figsize=(8.5, 4.8)
    )

    axis.plot(
        dataframe["year"],
        dataframe["yll_rate"],
        marker="o",
        linewidth=2,
    )

    if {
        "lower",
        "upper",
    }.issubset(
        dataframe.columns
    ):
        uncertainty = dataframe.dropna(
            subset=[
                "lower",
                "upper",
            ]
        )

        if not uncertainty.empty:
            axis.fill_between(
                uncertainty["year"],
                uncertainty["lower"],
                uncertainty["upper"],
                alpha=0.2,
            )

    axis.set_title(
        "Annual High-BMI-Attributable YLL Rate"
    )

    years = (
        dataframe["year"]
        .astype(int)
        .tolist()
    )

    tick_years = years[::2]

    axis.set_xticks(
        tick_years
    )

    axis.set_xticklabels(
        [
            str(year)
            for year in tick_years
        ]
    )
    
    axis.set_xlabel(
        "Year"
    )

    axis.set_ylabel(
        "YLL Rate"
    )

    axis.grid(
        axis="y",
        alpha=0.25,
    )

    figure.tight_layout()

    return figure


def _build_ranking_figure(
    bundle: EvidenceBundle,
):
    """
    Build a horizontal bar chart of the highest-ranked counties.
    """
    dataframe = _find_dataframe(
        bundle,
        "get_county_ranking",
    )

    _require_columns(
        dataframe,
        {
            "location_name",
            "yll_rate",
            "national_display_order",
        },
        figure_name="County ranking figure",
    )

    dataframe = _numeric(
        dataframe,
        [
            "yll_rate",
            "national_display_order",
        ],
    )

    display = (
        dataframe.dropna(
            subset=[
                "location_name",
                "yll_rate",
                "national_display_order",
            ]
        )
        .sort_values(
            "national_display_order"
        )
        .head(10)
        .copy()
    )

    if display.empty:
        raise FigureGenerationError(
            "No usable county-ranking observations were available."
        )

    display = display.sort_values(
        "yll_rate",
        ascending=True,
    )

    figure, axis = plt.subplots(
        figsize=(9, 5.8)
    )

    axis.barh(
        display["location_name"],
        display["yll_rate"],
    )

    axis.set_title(
        "Highest County YLL Rates"
    )

    axis.set_xlabel(
        "YLL Rate"
    )

    axis.set_ylabel(
        "County"
    )

    axis.grid(
        axis="x",
        alpha=0.25,
    )

    figure.tight_layout()

    return figure


def _build_disparity_figure(
    bundle: EvidenceBundle,
):
    """
    Build a horizontal chart of the largest positive
    county demographic disparity gaps.
    """
    dataframe = _find_dataframe(
        bundle,
        "get_county_disparity_ranking",
    )

    _require_columns(
        dataframe,
        {
            "location_name",
            "absolute_gap",
        },
        figure_name="Disparity figure",
    )

    dataframe = _numeric(
        dataframe,
        [
            "absolute_gap",
        ],
    )

    display = (
        dataframe.dropna(
            subset=[
                "location_name",
                "absolute_gap",
            ]
        )
        .sort_values(
            "absolute_gap",
            ascending=False,
        )
        .head(10)
        .copy()
    )

    if display.empty:
        raise FigureGenerationError(
            "No usable disparity observations were available."
        )

    display = display.sort_values(
        "absolute_gap",
        ascending=True,
    )

    group_a_name = str(
        bundle.context.get(
            "group_a_name",
            "Comparison group",
        )
    )

    group_b_name = str(
        bundle.context.get(
            "group_b_name",
            "Reference group",
        )
    )

    figure, axis = plt.subplots(
        figsize=(9, 5.8)
    )

    axis.barh(
        display["location_name"],
        display["absolute_gap"],
    )

    axis.set_title(
        "Largest County Demographic Disparities"
    )

    axis.set_xlabel(
        f"Signed Gap: {group_a_name} minus {group_b_name}"
    )

    axis.set_ylabel(
        "County"
    )

    axis.axvline(
        0,
        linewidth=1,
    )

    axis.grid(
        axis="x",
        alpha=0.25,
    )

    figure.tight_layout()

    return figure


def _build_county_profile_figure(
    bundle: EvidenceBundle,
):
    """
    Build a horizontal bar chart of leading attributable causes
    for the selected county.
    """
    dataframe = _find_dataframe(
        bundle,
        "get_top_causes",
    )

    _require_columns(
        dataframe,
        {
            "cause_name",
            "yll_rate",
            "county_cause_rank",
        },
        figure_name="County profile figure",
    )

    dataframe = _numeric(
        dataframe,
        [
            "yll_rate",
            "county_cause_rank",
        ],
    )

    display = (
        dataframe.dropna(
            subset=[
                "cause_name",
                "yll_rate",
                "county_cause_rank",
            ]
        )
        .sort_values(
            [
                "county_cause_rank",
                "cause_name",
            ]
        )
        .head(10)
        .copy()
    )

    if display.empty:
        raise FigureGenerationError(
            "No usable leading-cause observations were available."
        )

    display = display.sort_values(
        "yll_rate",
        ascending=True,
    )

    figure, axis = plt.subplots(
        figsize=(9, 5.8)
    )

    axis.barh(
        display["cause_name"],
        display["yll_rate"],
    )

    axis.set_title(
        "Leading High-BMI-Attributable Causes"
    )

    axis.set_xlabel(
        "YLL Rate"
    )

    axis.set_ylabel(
        "Cause"
    )

    axis.grid(
        axis="x",
        alpha=0.25,
    )

    figure.tight_layout()

    return figure


FIGURE_BUILDERS: dict[
    AnalysisIntent,
    Callable[[EvidenceBundle], object],
] = {
    AnalysisIntent.TREND_COMPARISON:
        _build_trend_figure,
    AnalysisIntent.COUNTY_RANKING:
        _build_ranking_figure,
    AnalysisIntent.DEMOGRAPHIC_DISPARITY:
        _build_disparity_figure,
    AnalysisIntent.COUNTY_PROFILE:
        _build_county_profile_figure,
}


def build_evidence_figure(
    bundle: EvidenceBundle,
):
    """
    Build the primary deterministic research figure
    for an evidence bundle.

    Returns a Matplotlib Figure.
    """
    builder = FIGURE_BUILDERS.get(
        bundle.intent
    )

    if builder is None:
        raise FigureGenerationError(
            f"Figure generation is not implemented for "
            f"intent '{bundle.intent.value}'."
        )

    return builder(
        bundle
    )


def export_evidence_figure_png(
    bundle: EvidenceBundle,
    *,
    dpi: int = 180,
) -> bytes:
    """
    Build and export the primary research figure as PNG bytes.
    """
    figure = build_evidence_figure(
        bundle
    )

    return _figure_to_png_bytes(
        figure,
        dpi=dpi,
    )