from __future__ import annotations

from typing import Any

import pandas as pd

from ai.models import (
    AnalysisIntent,
    EvidenceBundle,
    EvidenceClaim,
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

    dimension = str(
        bundle.context.get(
            "dimension",
            "demographic group",
        )
    ).strip()

    findings = [
        (
            f"{len(ranking):,} current counties had complete estimates "
            f"for both selected groups ({group_a_name} and {group_b_name}) "
            f"in the {dimension} comparison."
        ),
        (
            f"The median signed disparity gap, defined as "
            f"{group_a_name} minus {group_b_name}, was "
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


def _interpret_places_ihme_trend(
    bundle: EvidenceBundle,
) -> list[str]:
    """
    Interpret a county cross-source CDC PLACES and IHME trend.

    PLACES prevalence and IHME YLL rates are interpreted as
    separate measures. They are never combined into a composite
    metric and no causal relationship is inferred.
    """
    trend = _find_item(
        bundle,
        "get_places_ihme_county_trend_context",
    )

    if trend.empty:
        return [
            "No cross-source trend observations were available."
        ]

    _require_columns(
        trend,
        {
            "analysis_year",
            "places_age_adjusted_prevalence",
            "ihme_yll_rate",
            "places_available",
            "ihme_available",
            "same_year_overlap",
        },
        evidence_name="CDC PLACES and IHME county trend",
    )

    trend = trend.copy()

    trend["analysis_year"] = pd.to_numeric(
        trend["analysis_year"],
        errors="coerce",
    )

    trend["places_age_adjusted_prevalence"] = pd.to_numeric(
        trend["places_age_adjusted_prevalence"],
        errors="coerce",
    )

    trend["ihme_yll_rate"] = pd.to_numeric(
        trend["ihme_yll_rate"],
        errors="coerce",
    )

    trend = (
        trend.dropna(
            subset=["analysis_year"]
        )
        .sort_values("analysis_year")
        .drop_duplicates(
            subset=["analysis_year"],
            keep="last",
        )
        .copy()
    )

    if trend.empty:
        return [
            "No usable cross-source trend observations were available."
        ]

    first_year = int(
        trend["analysis_year"].min()
    )

    last_year = int(
        trend["analysis_year"].max()
    )

    findings = [
        (
            f"The cross-source trend contained "
            f"{len(trend):,} analysis-year observations "
            f"from {first_year} through {last_year}."
        )
    ]

    places = (
        trend.dropna(
            subset=[
                "places_age_adjusted_prevalence"
            ]
        )
        .sort_values("analysis_year")
        .copy()
    )

    if not places.empty:
        places_first = places.iloc[0]
        places_last = places.iloc[-1]

        places_first_year = int(
            places_first["analysis_year"]
        )

        places_last_year = int(
            places_last["analysis_year"]
        )

        places_first_value = float(
            places_first[
                "places_age_adjusted_prevalence"
            ]
        )

        places_last_value = float(
            places_last[
                "places_age_adjusted_prevalence"
            ]
        )

        places_change = (
            places_last_value
            - places_first_value
        )

        if places_change > 0:
            places_direction = "increased"
        elif places_change < 0:
            places_direction = "decreased"
        else:
            places_direction = "did not change"

        findings.append(
            (
                "CDC PLACES age-adjusted prevalence "
                f"{places_direction} from "
                f"{_format_number(places_first_value)}% "
                f"in {places_first_year} to "
                f"{_format_number(places_last_value)}% "
                f"in {places_last_year}, an absolute change of "
                f"{_format_number(places_change)} "
                "percentage points."
            )
        )

    ihme = (
        trend.dropna(
            subset=["ihme_yll_rate"]
        )
        .sort_values("analysis_year")
        .copy()
    )

    if not ihme.empty:
        ihme_first = ihme.iloc[0]
        ihme_last = ihme.iloc[-1]

        ihme_first_year = int(
            ihme_first["analysis_year"]
        )

        ihme_last_year = int(
            ihme_last["analysis_year"]
        )

        ihme_first_value = float(
            ihme_first["ihme_yll_rate"]
        )

        ihme_last_value = float(
            ihme_last["ihme_yll_rate"]
        )

        ihme_change = (
            ihme_last_value
            - ihme_first_value
        )

        if ihme_change > 0:
            ihme_direction = "increased"
        elif ihme_change < 0:
            ihme_direction = "decreased"
        else:
            ihme_direction = "did not change"

        findings.append(
            (
                f"The IHME YLL rate {ihme_direction} from "
                f"{_format_number(ihme_first_value)} "
                f"in {ihme_first_year} to "
                f"{_format_number(ihme_last_value)} "
                f"in {ihme_last_year}, an absolute change of "
                f"{_format_number(ihme_change)} "
                "YLL-rate units."
            )
        )

    overlap = trend.loc[
        trend["same_year_overlap"].fillna(False).astype(bool)
    ].copy()

    if overlap.empty:
        findings.append(
            (
                "CDC PLACES and IHME had no same-year "
                "observations in the requested period."
            )
        )
    else:
        overlap_years = sorted(
            overlap["analysis_year"]
            .astype(int)
            .tolist()
        )

        findings.append(
            (
                f"Both sources had estimates for "
                f"{len(overlap_years):,} same-year "
                f"observation"
                f"{'' if len(overlap_years) == 1 else 's'}: "
                + ", ".join(
                    str(year)
                    for year in overlap_years
                )
                + "."
            )
        )

    findings.append(
        (
            "CDC PLACES prevalence and IHME YLL rates represent "
            "different measures and are reported separately; "
            "these descriptive trends do not by themselves "
            "establish a causal relationship."
        )
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


def _interpret_places_county_snapshot(
    bundle: EvidenceBundle,
) -> list[str]:
    """
    Interpret one validated CDC PLACES county-measure observation.
    """
    snapshot = _find_item(
        bundle,
        "get_places_county_measure_trend",
    )

    if snapshot.empty:
        return [
            "No CDC PLACES prevalence estimate was available "
            "for the selected county, measure, and measurement year."
        ]

    _require_columns(
        snapshot,
        {
            "geography_name",
            "state_name",
            "release_year",
            "measurement_year",
            "measure_id",
            "measure_name",
            "unit",
            "data_source",
            "age_adjusted_prevalence",
            "age_adjusted_ci_lower",
            "age_adjusted_ci_upper",
            "carry_forward",
            "dataset",
        },
        evidence_name="CDC PLACES county prevalence snapshot",
    )

    if len(snapshot) != 1:
        raise EvidenceInterpretationError(
            "CDC PLACES county prevalence snapshot must contain "
            "exactly one observation."
        )

    row = snapshot.iloc[0]

    geography_name = str(
        row["geography_name"]
    )

    state_name = str(
        row["state_name"]
    )

    measure_name = str(
        row["measure_name"]
    )

    measurement_year = int(
        row["measurement_year"]
    )

    release_year = int(
        row["release_year"]
    )

    prevalence = _safe_float(
        row["age_adjusted_prevalence"]
    )

    lower = _safe_float(
        row["age_adjusted_ci_lower"]
    )

    upper = _safe_float(
        row["age_adjusted_ci_upper"]
    )

    findings: list[str] = []

    if prevalence is not None:
        findings.append(
            f"The CDC PLACES age-adjusted prevalence for "
            f"{measure_name} in {geography_name}, {state_name} "
            f"in BRFSS measurement year {measurement_year} was "
            f"{_format_number(prevalence)}%."
        )

    if (
        lower is not None
        and upper is not None
    ):
        findings.append(
            "The 95% confidence interval was "
            f"{_format_number(lower)}% to "
            f"{_format_number(upper)}%."
        )

    findings.append(
        f"The estimate appears in the {release_year} CDC PLACES "
        "release; the analytical time point is the underlying "
        f"BRFSS measurement year {measurement_year}."
    )

    if bool(row["carry_forward"]):
        findings.append(
            "This PLACES observation was marked as carry-forward "
            "rather than a new measurement-year estimate."
        )
    else:
        findings.append(
            "This PLACES observation was not marked as carry-forward."
        )

    return findings


def _interpret_county_cause_snapshot(
    bundle: EvidenceBundle,
) -> list[str]:
    """
    Interpret one validated county-year-cause burden observation.
    """
    snapshot = _find_item(
        bundle,
        "get_county_cause_record",
    )

    if snapshot.empty:
        return [
            "No county disease-burden estimate was available "
            "for the selected county, cause, and year."
        ]

    _require_columns(
        snapshot,
        {
            "location_name",
            "year",
            "cause_name",
            "yll_rate",
            "lower",
            "upper",
            "national_county_rank",
            "counties_with_estimate",
            "burden_percentile",
        },
        evidence_name="County disease-burden snapshot",
    )

    if len(snapshot) != 1:
        raise EvidenceInterpretationError(
            "County disease-burden snapshot must contain "
            "exactly one observation."
        )

    row = snapshot.iloc[0]

    location_name = str(
        row["location_name"]
    )

    cause_name = str(
        row["cause_name"]
    )

    year = int(
        row["year"]
    )

    yll_rate = _safe_float(
        row["yll_rate"]
    )

    lower = _safe_float(
        row["lower"]
    )

    upper = _safe_float(
        row["upper"]
    )

    national_rank = _safe_float(
        row["national_county_rank"]
    )

    counties_with_estimate = _safe_float(
        row["counties_with_estimate"]
    )

    burden_percentile = _safe_float(
        row["burden_percentile"]
    )

    findings: list[str] = []

    if yll_rate is not None:
        findings.append(
            f"The estimated {cause_name} YLL rate in "
            f"{location_name} in {year} was "
            f"{_format_number(yll_rate)}."
        )

    if (
        lower is not None
        and upper is not None
    ):
        findings.append(
            f"The reported uncertainty interval ranged from "
            f"{_format_number(lower)} to "
            f"{_format_number(upper)}."
        )

    if (
        national_rank is not None
        and counties_with_estimate is not None
    ):
        findings.append(
            f"{location_name} ranked "
            f"{int(national_rank):,} of "
            f"{int(counties_with_estimate):,} counties "
            f"nationally for {cause_name} burden."
        )

    if burden_percentile is not None:
        findings.append(
            f"The county's burden percentile was "
            f"{_format_number(burden_percentile, 1)}."
        )

    if not findings:
        findings.append(
            "No interpretable county disease-burden "
            "estimate was available."
        )

    return findings


def _interpret_places_ihme_rurality(
    bundle: EvidenceBundle,
) -> list[str]:
    """
    Interpret validated CDC PLACES + IHME evidence summarized
    across USDA RUCC rurality groups.
    """
    comparison = _find_item(
        bundle,
        "get_places_ihme_rurality_comparison",
    )

    if comparison.empty:
        return [
            "No matched CDC PLACES and IHME rurality evidence "
            "was available for the requested measure and year."
        ]

    _require_columns(
        comparison,
        {
            "rurality_group",
            "counties",
            "mean_places_prevalence",
            "median_places_prevalence",
            "mean_ihme_yll_rate",
            "median_ihme_yll_rate",
            "places_measure_id",
            "places_measurement_year",
            "ihme_cause_id",
            "ihme_year",
            "dataset",
        },
        evidence_name=(
            "CDC PLACES and IHME rurality comparison"
        ),
    )

    findings: list[str] = []

    total_counties = int(
        comparison["counties"].sum()
    )

    findings.append(
        "The rurality comparison included "
        f"{total_counties:,} matched counties across "
        f"{len(comparison)} USDA RUCC rurality groups."
    )

    for _, row in comparison.iterrows():
        group = str(
            row["rurality_group"]
        )

        counties = int(
            row["counties"]
        )

        median_places = _safe_float(
            row["median_places_prevalence"]
        )

        median_ihme = _safe_float(
            row["median_ihme_yll_rate"]
        )

        if (
            median_places is not None
            and median_ihme is not None
        ):
            findings.append(
                f"{group} counties (n={counties:,}) had a "
                "median CDC PLACES age-adjusted prevalence of "
                f"{_format_number(median_places)}% and a median "
                "IHME YLL rate of "
                f"{_format_number(median_ihme)}."
            )

    findings.append(
        "CDC PLACES prevalence and IHME YLL rate are distinct "
        "measures; differences across rurality groups are "
        "descriptive and do not establish a causal relationship."
    )

    return findings


def interpret_evidence(
    bundle: EvidenceBundle,
) -> list[str]:
    """
    Convert validated analytical evidence into deterministic findings.
    """
    if bundle.intent == AnalysisIntent.RURALITY_COMPARISON:
        return _interpret_places_ihme_rurality(
            bundle
        )

    if bundle.intent == AnalysisIntent.DEMOGRAPHIC_DISPARITY:
        return _interpret_disparity(bundle)

    if bundle.intent == AnalysisIntent.COUNTY_CAUSE_SNAPSHOT:
        if (
            bundle.context.get("evidence_domain")
            == "PLACES"
        ):
            return _interpret_places_county_snapshot(
                bundle
            )

        return _interpret_county_cause_snapshot(
            bundle
        )

    if bundle.intent == AnalysisIntent.TREND_COMPARISON:
        if (
            bundle.context.get("evidence_domain")
            == "PLACES_IHME"
        ):
            return _interpret_places_ihme_trend(
                bundle
            )

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


def build_evidence_claims(
    bundle: EvidenceBundle,
) -> list[EvidenceClaim]:
    """
    Build structured deterministic claims from validated evidence.

    Existing deterministic interpretation remains the factual source.
    Validated resolved context is promoted into an explicit context
    claim so downstream narrative interpretation can cite county,
    cause, year, and demographic context directly.

    Semantic claim identifiers are assigned according to the meaning
    of each deterministic finding rather than its list position.
    """
    findings = interpret_evidence(bundle)

    context_claims: list[EvidenceClaim] = []

    if bundle.intent == AnalysisIntent.COUNTY_CAUSE_SNAPSHOT:
        evidence_domain = bundle.context.get(
            "evidence_domain"
        )

        location_name = str(
            bundle.context.get(
                "location_name",
                "the selected county",
            )
        )

        if evidence_domain == "PLACES":
            measure_name = str(
                bundle.context.get(
                    "places_measure_name",
                    "the selected CDC PLACES measure",
                )
            )

            measurement_year = bundle.context.get(
                "measurement_year"
            )

            context_text = (
                "The CDC PLACES county prevalence snapshot "
                f"concerns {measure_name} in {location_name}"
            )

            if measurement_year is not None:
                context_text += (
                    " for BRFSS measurement year "
                    f"{measurement_year}."
                )
            else:
                context_text += "."

            context_claims.append(
                EvidenceClaim(
                    claim_id="snapshot.context",
                    text=context_text,
                    source_function="resolved_context",
                    metadata={
                        "intent": bundle.intent.value,
                        "evidence_domain": evidence_domain,
                        "fips": bundle.context.get(
                            "fips"
                        ),
                        "location_name": location_name,
                        "places_measure_id": bundle.context.get(
                            "places_measure_id"
                        ),
                        "places_measure_name": measure_name,
                        "measurement_year": measurement_year,
                        "measure": "Age-adjusted prevalence",
                        "units": "Percent",
                    },
                )
            )

        else:
            cause_name = str(
                bundle.context.get(
                    "cause_name",
                    "the selected cause",
                )
            )

            year = bundle.context.get(
                "year"
            )

            context_text = (
                "The county disease-burden snapshot concerns "
                f"{cause_name} in {location_name}"
            )

            if year is not None:
                context_text += (
                    f" in {year}."
                )
            else:
                context_text += "."

            context_claims.append(
                EvidenceClaim(
                    claim_id="snapshot.context",
                    text=context_text,
                    source_function="resolved_context",
                    metadata={
                        "intent": bundle.intent.value,
                        "fips": bundle.context.get(
                            "fips"
                        ),
                        "location_name": location_name,
                        "cause_id": bundle.context.get(
                            "cause_id"
                        ),
                        "cause_name": cause_name,
                        "year": year,
                        "measure": "YLL rate",
                        "units": "YLL-rate units",
                    },
                )
            )

    elif bundle.intent == AnalysisIntent.COUNTY_PROFILE:
        location_name = str(
            bundle.context.get(
                "location_name",
                "the selected county",
            )
        )

        year = bundle.context.get(
            "year"
        )

        context_text = (
            f"The county profile concerns {location_name}"
        )

        if year is not None:
            context_text += (
                f" using {year} profile indicators."
            )
        else:
            context_text += "."

        context_claims.append(
            EvidenceClaim(
                claim_id="profile.context",
                text=context_text,
                source_function="resolved_context",
                metadata={
                    "intent": bundle.intent.value,
                    "fips": bundle.context.get(
                        "fips"
                    ),
                    "location_name": location_name,
                    "year": year,
                },
            )
        )

    elif bundle.intent == AnalysisIntent.TREND_COMPARISON:
        location_name = str(
            bundle.context.get(
                "location_name",
                "the selected county",
            )
        )

        cause_name = str(
            bundle.context.get(
                "cause_name",
                "the selected cause",
            )
        )

        first_year = bundle.context.get(
            "first_year"
        )

        last_year = bundle.context.get(
            "last_year"
        )

        context_text = (
            f"The trend analysis concerns {cause_name} "
            f"in {location_name}"
        )

        if (
            first_year is not None
            and last_year is not None
        ):
            context_text += (
                f" from {first_year} through {last_year}."
            )
        else:
            context_text += "."

        context_claims.append(
            EvidenceClaim(
                claim_id="trend.context",
                text=context_text,
                source_function="resolved_context",
                metadata={
                    "intent": bundle.intent.value,
                    "cause_id": bundle.context.get(
                        "cause_id"
                    ),
                    "cause_name": cause_name,
                    "fips": bundle.context.get(
                        "fips"
                    ),
                    "location_name": location_name,
                    "first_year": first_year,
                    "last_year": last_year,
                },
            )
        )

    elif bundle.intent == AnalysisIntent.COUNTY_RANKING:
        cause_name = str(
            bundle.context.get(
                "cause_name",
                "the selected cause",
            )
        )

        year = bundle.context.get(
            "year"
        )

        context_text = (
            "The national county ranking concerns "
            f"{cause_name}"
        )

        if year is not None:
            context_text += (
                f" in {year}."
            )
        else:
            context_text += "."

        context_claims.append(
            EvidenceClaim(
                claim_id="ranking.context",
                text=context_text,
                source_function="resolved_context",
                metadata={
                    "intent": bundle.intent.value,
                    "cause_id": bundle.context.get(
                        "cause_id"
                    ),
                    "cause_name": cause_name,
                    "year": year,
                },
            )
        )

    elif bundle.intent == AnalysisIntent.DEMOGRAPHIC_DISPARITY:
        cause_name = str(
            bundle.context.get(
                "cause_name",
                "the selected cause",
            )
        )

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

        dimension = str(
            bundle.context.get(
                "dimension",
                "demographic group",
            )
        )

        year = bundle.context.get(
            "year"
        )

        context_text = (
            f"The disparity analysis compares {group_a_name} "
            f"with {group_b_name} for {cause_name} "
            f"by {dimension}, using county-level YLL rates"
        )

        if year is not None:
            context_text += (
                f" in {year}."
            )
        else:
            context_text += "."

        context_claims.append(
            EvidenceClaim(
                claim_id="disparity.context",
                text=context_text,
                source_function="resolved_context",
                metadata={
                    "intent": bundle.intent.value,
                    "cause_id": bundle.context.get(
                        "cause_id"
                    ),
                    "cause_name": cause_name,
                    "dimension": dimension,
                    "group_a_id": bundle.context.get(
                        "group_a_id"
                    ),
                    "group_a_name": group_a_name,
                    "group_b_id": bundle.context.get(
                        "group_b_id"
                    ),
                    "group_b_name": group_b_name,
                    "year": year,
                    "measure": "YLL rate",
                    "units": "YLL-rate units",
                    "signed_gap_definition": (
                        f"{group_a_name} minus {group_b_name}"
                    ),
                    "signed_gap_group_a": group_a_name,
                    "signed_gap_group_b": group_b_name,
                },
            )
        )

    claims: list[EvidenceClaim] = list(
        context_claims
    )

    for index, finding in enumerate(
        findings,
        start=1,
    ):
        lowered = finding.casefold()

        claim_id: str

        if bundle.intent == AnalysisIntent.RURALITY_COMPARISON:
            if "matched counties" in lowered:
                claim_id = (
                    "rurality.counties_compared"
                )

            elif (
                "median cdc places age-adjusted prevalence"
                in lowered
                and "median ihme yll rate" in lowered
            ):
                claim_id = (
                    f"rurality.group_summary.{index}"
                )

            elif (
                "distinct measures" in lowered
                and "causal relationship" in lowered
            ):
                claim_id = (
                    "rurality.interpretation_guardrail"
                )

            else:
                claim_id = (
                    f"rurality_comparison.finding.{index}"
                )

        elif bundle.intent == AnalysisIntent.DEMOGRAPHIC_DISPARITY:
            if "complete estimates" in lowered:
                claim_id = "disparity.counties_compared"

            elif "median signed disparity gap" in lowered:
                claim_id = "disparity.median_gap"

            elif "had the higher estimated rate" in lowered:
                claim_id = "disparity.direction_counts"

            elif "equal estimated rates" in lowered:
                claim_id = "disparity.equal_count"

            elif "largest positive disparity" in lowered:
                claim_id = "disparity.largest_positive_gap"

            elif "largest reverse disparity" in lowered:
                claim_id = "disparity.largest_reverse_gap"

            else:
                claim_id = (
                    f"demographic_disparity.finding.{index}"
                )

        elif bundle.intent == AnalysisIntent.RURALITY_COMPARISON:
            if "cross-source trend contained" in lowered:
                claim_id = "trend.cross_source_observation_count"

            elif (
                "cdc places age-adjusted prevalence" in lowered
                and "absolute change" in lowered
            ):
                claim_id = "trend.places_prevalence_change"

            elif (
                "ihme yll rate" in lowered
                and "absolute change" in lowered
            ):
                claim_id = "trend.ihme_yll_change"

            elif "same-year observation" in lowered:
                claim_id = "trend.same_year_overlap"

            elif (
                "different measures" in lowered
                and "causal relationship" in lowered
            ):
                claim_id = "trend.cross_source_interpretation_guardrail"

            elif "annual observations" in lowered:
                claim_id = "trend.observation_count"

            elif "absolute change" in lowered:
                claim_id = "trend.absolute_change"

            elif "relative change" in lowered:
                claim_id = "trend.relative_change"

            elif "highest observed rate" in lowered:
                claim_id = "trend.maximum"

            elif "lowest observed rate" in lowered:
                claim_id = "trend.minimum"

            else:
                claim_id = (
                    f"trend_comparison.finding.{index}"
                )

        elif bundle.intent == AnalysisIntent.COUNTY_RANKING:
            if "ranking included" in lowered:
                claim_id = "ranking.county_count"

            elif "ranked first nationally" in lowered:
                claim_id = "ranking.highest"

            elif "ranked last nationally" in lowered:
                claim_id = "ranking.lowest"

            elif "national range" in lowered:
                claim_id = "ranking.range"

            else:
                claim_id = (
                    f"county_ranking.finding.{index}"
                )

        elif bundle.intent == AnalysisIntent.COUNTY_CAUSE_SNAPSHOT:
            if (
                bundle.context.get("evidence_domain")
                == "PLACES"
            ):
                if "age-adjusted prevalence" in lowered:
                    claim_id = "snapshot.places_prevalence"

                elif "95% confidence interval" in lowered:
                    claim_id = (
                        "snapshot.places_confidence_interval"
                    )

                elif "cdc places release" in lowered:
                    claim_id = (
                        "snapshot.places_release_provenance"
                    )

                elif "carry-forward" in lowered:
                    claim_id = (
                        "snapshot.places_carry_forward"
                    )

                else:
                    claim_id = (
                        f"county_cause_snapshot.finding.{index}"
                    )

            else:
                if (
                    "yll rate" in lowered
                    and "estimated" in lowered
                ):
                    claim_id = "snapshot.yll_rate"

                elif "uncertainty interval" in lowered:
                    claim_id = "snapshot.uncertainty_interval"

                elif (
                    "ranked" in lowered
                    and "nationally" in lowered
                ):
                    claim_id = "snapshot.national_rank"

                elif "burden percentile" in lowered:
                    claim_id = "snapshot.burden_percentile"

                else:
                    claim_id = (
                        f"county_cause_snapshot.finding.{index}"
                    )

        elif bundle.intent == AnalysisIntent.COUNTY_PROFILE:
            if lowered.startswith("obesity prevalence"):
                claim_id = "profile.obesity_prevalence"

            elif lowered.startswith("mean bmi"):
                claim_id = "profile.mean_bmi"

            elif lowered.startswith("overweight prevalence"):
                claim_id = "profile.overweight_prevalence"

            elif "leading high-bmi-attributable cause" in lowered:
                claim_id = "profile.leading_cause"

            elif "largest long-term increase" in lowered:
                claim_id = "profile.largest_increase"

            elif "largest long-term decrease" in lowered:
                claim_id = "profile.largest_decrease"

            else:
                claim_id = (
                    f"county_profile.finding.{index}"
                )

        else:
            claim_id = (
                f"{bundle.intent.value}.finding.{index}"
            )

        claims.append(
            EvidenceClaim(
                claim_id=claim_id,
                text=finding,
                source_function="deterministic_interpretation",
                metadata={
                    "intent": bundle.intent.value,
                    "finding_index": index,
                },
            )
        )

    return claims