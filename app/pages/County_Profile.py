from pathlib import Path
import sys

import altair as alt
import streamlit as st


APP_DIR = Path(__file__).resolve().parents[1]

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from data_access import (  # noqa: E402
    get_bmi_summary,
    get_cause_trend,
    get_long_term_change,
    get_top_causes,
)

from components.lookups import (  # noqa: E402
    county_lookup,
    year_lookup,
)


st.set_page_config(
    page_title="County Profile",
    page_icon="📍",
    layout="wide",
)


st.title("📍 County Profile")

st.write(
    """
    Explore county-level obesity prevalence and high-BMI-attributable
    disease burden for an individual county.
    """
)

st.divider()


# --------------------------------------------------
# Sidebar
# --------------------------------------------------

counties = county_lookup()

if counties.empty:
    st.error("No county records are available.")
    st.stop()

county_names = counties["display_name"].tolist()

selected_county = st.sidebar.selectbox(
    label="County",
    options=county_names,
)

years = year_lookup()

if not years:
    st.error("No analysis years are available.")
    st.stop()

selected_year = st.sidebar.selectbox(
    label="Year",
    options=years,
)


# --------------------------------------------------
# Selected county
# --------------------------------------------------

selected_record = counties.loc[
    counties["display_name"] == selected_county
].iloc[0]

fips = str(selected_record["fips"]).zfill(5)

st.subheader("Selected County")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="County",
        value=selected_county,
    )

with col2:
    st.metric(
        label="FIPS",
        value=fips,
    )

with col3:
    st.metric(
        label="Year",
        value=int(selected_year),
    )


# --------------------------------------------------
# BMI Summary
# --------------------------------------------------

st.divider()

st.subheader("BMI Summary")

bmi = get_bmi_summary(
    fips=fips,
    year=int(selected_year),
)

if bmi.empty:
    st.warning(
        "No BMI estimates are available for the selected county and year."
    )
else:
    bmi_lookup = {
        str(row.metric).strip().lower(): row
        for row in bmi.itertuples(index=False)
    }

    mean_bmi = bmi_lookup.get("mean bmi")
    obesity = bmi_lookup.get("obesity")
    overweight = bmi_lookup.get("overweight")

    bmi_col1, bmi_col2, bmi_col3 = st.columns(3)

    with bmi_col1:
        if mean_bmi is not None:
            st.metric(
                label="Mean BMI",
                value=f"{mean_bmi.value:.2f}",
            )

            st.caption(
                f"95% uncertainty interval: "
                f"{mean_bmi.lower:.2f}–{mean_bmi.upper:.2f}"
            )
        else:
            st.metric(
                label="Mean BMI",
                value="Not available",
            )

    with bmi_col2:
        if obesity is not None:
            st.metric(
                label="Obesity prevalence",
                value=f"{obesity.value * 100:.1f}%",
            )

            st.caption(
                f"95% uncertainty interval: "
                f"{obesity.lower * 100:.1f}%–"
                f"{obesity.upper * 100:.1f}%"
            )
        else:
            st.metric(
                label="Obesity prevalence",
                value="Not available",
            )

    with bmi_col3:
        if overweight is not None:
            st.metric(
                label="Overweight prevalence",
                value=f"{overweight.value * 100:.1f}%",
            )

            st.caption(
                f"95% uncertainty interval: "
                f"{overweight.lower * 100:.1f}%–"
                f"{overweight.upper * 100:.1f}%"
            )
        else:
            st.metric(
                label="Overweight prevalence",
                value="Not available",
            )


# --------------------------------------------------
# Leading causes
# --------------------------------------------------

st.divider()

st.subheader("Leading High-BMI-Attributable Causes")

st.caption(
    "Top causes ranked by years-of-life-lost rate for the selected "
    "county and year."
)

top_causes = get_top_causes(
    fips=fips,
    year=int(selected_year),
    limit=10,
)

if top_causes.empty:
    st.warning(
        "No cause-burden estimates are available for the selected "
        "county and year."
    )
else:
    leading_causes = top_causes[
        [
            "county_cause_rank",
            "cause_name",
            "yll_rate",
            "lower",
            "upper",
            "national_county_rank",
            "burden_percentile",
        ]
    ].copy()

    leading_causes = leading_causes.rename(
        columns={
            "county_cause_rank": "County rank",
            "cause_name": "Cause",
            "yll_rate": "YLL rate",
            "lower": "Lower",
            "upper": "Upper",
            "national_county_rank": "National rank",
            "burden_percentile": "Burden percentile",
        }
    )

    leading_causes["YLL rate"] = leading_causes[
        "YLL rate"
    ].round(1)

    leading_causes["Lower"] = leading_causes[
        "Lower"
    ].round(1)

    leading_causes["Upper"] = leading_causes[
        "Upper"
    ].round(1)

    leading_causes["Burden percentile"] = leading_causes[
        "Burden percentile"
    ].round(1)

    st.dataframe(
        leading_causes,
        width="stretch",
        hide_index=True,
        column_config={
            "County rank": st.column_config.NumberColumn(
                "County rank",
                format="%d",
                help=(
                    "Rank among the causes available for the selected county."
                ),
            ),
            "Cause": st.column_config.TextColumn(
                "Cause",
                width="large",
            ),
            "YLL rate": st.column_config.NumberColumn(
                "YLL rate",
                format="%.1f",
                help=(
                    "Estimated years of life lost attributable to high BMI."
                ),
            ),
            "Lower": st.column_config.NumberColumn(
                "Lower",
                format="%.1f",
                help="Lower bound of the 95% uncertainty interval.",
            ),
            "Upper": st.column_config.NumberColumn(
                "Upper",
                format="%.1f",
                help="Upper bound of the 95% uncertainty interval.",
            ),
            "National rank": st.column_config.NumberColumn(
                "National rank",
                format="%d",
                help=(
                    "County position among all counties with an estimate."
                ),
            ),
            "Burden percentile": st.column_config.NumberColumn(
                "Burden percentile",
                format="%.1f",
                help=(
                    "Relative position of the county among counties "
                    "with an estimate."
                ),
            ),
        },
    )

    leading_causes_csv = leading_causes.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="Download leading causes as CSV",
        data=leading_causes_csv,
        file_name=(
            f"{fips}_{int(selected_year)}_leading_causes.csv"
        ),
        mime="text/csv",
    )


# --------------------------------------------------
# Cause trend
# --------------------------------------------------

st.divider()

st.subheader("Cause Trend")

st.caption(
    "Annual high-BMI-attributable years-of-life-lost rate, "
    "including the 95% uncertainty interval."
)

if top_causes.empty:
    st.warning(
        "A trend cannot be displayed because no cause estimates "
        "are available."
    )
else:
    cause_options = (
        top_causes[
            [
                "cause_id",
                "cause_name",
            ]
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    selected_cause_name = st.selectbox(
        label="Select a cause",
        options=cause_options["cause_name"].tolist(),
        key="county_profile_cause",
    )

    selected_cause_record = cause_options.loc[
        cause_options["cause_name"] == selected_cause_name
    ].iloc[0]

    selected_cause_id = int(
        selected_cause_record["cause_id"]
    )

    trend = get_cause_trend(
        fips=fips,
        cause_id=selected_cause_id,
    )

    if trend.empty:
        st.warning(
            "No historical trend is available for the selected cause."
        )
    else:
        trend_chart_data = trend[
            [
                "year",
                "yll_rate",
                "lower",
                "upper",
            ]
        ].copy()

        trend_chart_data["year"] = trend_chart_data[
            "year"
        ].astype(int)

        uncertainty_band = (
            alt.Chart(trend_chart_data)
            .mark_area(opacity=0.20)
            .encode(
                x=alt.X(
                    "year:O",
                    title="Year",
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y(
                    "lower:Q",
                    title="YLL rate",
                ),
                y2="upper:Q",
                tooltip=[
                    alt.Tooltip(
                        "year:O",
                        title="Year",
                    ),
                    alt.Tooltip(
                        "lower:Q",
                        title="Lower",
                        format=".1f",
                    ),
                    alt.Tooltip(
                        "upper:Q",
                        title="Upper",
                        format=".1f",
                    ),
                ],
            )
        )

        trend_line = (
            alt.Chart(trend_chart_data)
            .mark_line(
                point=True,
                strokeWidth=3,
            )
            .encode(
                x=alt.X(
                    "year:O",
                    title="Year",
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y(
                    "yll_rate:Q",
                    title="YLL rate",
                ),
                tooltip=[
                    alt.Tooltip(
                        "year:O",
                        title="Year",
                    ),
                    alt.Tooltip(
                        "yll_rate:Q",
                        title="YLL rate",
                        format=".1f",
                    ),
                    alt.Tooltip(
                        "lower:Q",
                        title="Lower",
                        format=".1f",
                    ),
                    alt.Tooltip(
                        "upper:Q",
                        title="Upper",
                        format=".1f",
                    ),
                ],
            )
        )

        combined_chart = (
            uncertainty_band
            + trend_line
        ).properties(
            height=420,
            title=(
                f"{selected_cause_name}: "
                f"{selected_county}, 2000–2019"
            ),
        )

        st.altair_chart(
            combined_chart,
            width="stretch",
        )

        ordered_trend = trend.sort_values(
            "year"
        )

        first_record = ordered_trend.iloc[0]
        latest_record = ordered_trend.iloc[-1]

        absolute_change = (
            float(latest_record["yll_rate"])
            - float(first_record["yll_rate"])
        )

        if float(first_record["yll_rate"]) != 0:
            percent_change = (
                absolute_change
                / float(first_record["yll_rate"])
                * 100
            )
        else:
            percent_change = None

        summary_col1, summary_col2, summary_col3 = st.columns(3)

        with summary_col1:
            st.metric(
                label=f"{int(first_record['year'])} YLL rate",
                value=f"{first_record['yll_rate']:.1f}",
            )

        with summary_col2:
            st.metric(
                label=f"{int(latest_record['year'])} YLL rate",
                value=f"{latest_record['yll_rate']:.1f}",
            )

        with summary_col3:
            if percent_change is None:
                st.metric(
                    label="Long-term change",
                    value="Not calculable",
                )
            else:
                st.metric(
                    label="Long-term change",
                    value=f"{percent_change:+.1f}%",
                    delta=f"{absolute_change:+.1f} YLL rate",
                )

        trend_csv = trend_chart_data.to_csv(
            index=False
        ).encode("utf-8")

        safe_cause_name = (
            selected_cause_name.lower()
            .replace(" ", "_")
            .replace("/", "_")
            .replace("'", "")
        )

        st.download_button(
            label="Download trend data as CSV",
            data=trend_csv,
            file_name=(
                f"{fips}_{safe_cause_name}_trend.csv"
            ),
            mime="text/csv",
        )


# --------------------------------------------------
# Long-term cause change
# --------------------------------------------------

st.divider()

st.subheader("Long-Term Cause Change")

st.caption(
    "Change in high-BMI-attributable years-of-life-lost rates "
    "between 2000 and 2019."
)

long_term = get_long_term_change(fips)

if long_term.empty:
    st.warning(
        "No long-term change estimates are available for the selected county."
    )
else:
    increases = (
        long_term.loc[
            long_term["percent_change_2000_2019"] > 0
        ]
        .sort_values(
            "percent_change_2000_2019",
            ascending=False,
        )
        .head(10)
        .copy()
    )

    decreases = (
        long_term.loc[
            long_term["percent_change_2000_2019"] < 0
        ]
        .sort_values(
            "percent_change_2000_2019",
            ascending=True,
        )
        .head(10)
        .copy()
    )

    display_columns = [
        "cause_name",
        "yll_rate_2000",
        "yll_rate_2019",
        "absolute_change_2000_2019",
        "percent_change_2000_2019",
        "trend_direction",
    ]

    rename_columns = {
        "cause_name": "Cause",
        "yll_rate_2000": "2000 YLL rate",
        "yll_rate_2019": "2019 YLL rate",
        "absolute_change_2000_2019": "Absolute change",
        "percent_change_2000_2019": "Percent change",
        "trend_direction": "Direction",
    }

    increases_tab, decreases_tab = st.tabs(
        [
            "Largest increases",
            "Largest decreases",
        ]
    )

    with increases_tab:
        if increases.empty:
            st.info(
                "No causes increased between 2000 and 2019."
            )
        else:
            increases_display = increases[
                display_columns
            ].rename(
                columns=rename_columns
            )

            st.dataframe(
                increases_display,
                width="stretch",
                hide_index=True,
                column_config={
                    "Cause": st.column_config.TextColumn(
                        "Cause",
                        width="large",
                    ),
                    "2000 YLL rate": st.column_config.NumberColumn(
                        "2000 YLL rate",
                        format="%.1f",
                    ),
                    "2019 YLL rate": st.column_config.NumberColumn(
                        "2019 YLL rate",
                        format="%.1f",
                    ),
                    "Absolute change": st.column_config.NumberColumn(
                        "Absolute change",
                        format="%+.1f",
                    ),
                    "Percent change": st.column_config.NumberColumn(
                        "Percent change",
                        format="%+.1f%%",
                    ),
                    "Direction": st.column_config.TextColumn(
                        "Direction",
                    ),
                },
            )

    with decreases_tab:
        if decreases.empty:
            st.info(
                "No causes decreased between 2000 and 2019."
            )
        else:
            decreases_display = decreases[
                display_columns
            ].rename(
                columns=rename_columns
            )

            st.dataframe(
                decreases_display,
                width="stretch",
                hide_index=True,
                column_config={
                    "Cause": st.column_config.TextColumn(
                        "Cause",
                        width="large",
                    ),
                    "2000 YLL rate": st.column_config.NumberColumn(
                        "2000 YLL rate",
                        format="%.1f",
                    ),
                    "2019 YLL rate": st.column_config.NumberColumn(
                        "2019 YLL rate",
                        format="%.1f",
                    ),
                    "Absolute change": st.column_config.NumberColumn(
                        "Absolute change",
                        format="%+.1f",
                    ),
                    "Percent change": st.column_config.NumberColumn(
                        "Percent change",
                        format="%+.1f%%",
                    ),
                    "Direction": st.column_config.TextColumn(
                        "Direction",
                    ),
                },
            )

    long_term_csv = long_term.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="Download long-term change data as CSV",
        data=long_term_csv,
        file_name=f"{fips}_long_term_change.csv",
        mime="text/csv",
    )


st.divider()

st.caption(
    "YLL rate represents estimated years of life lost attributable "
    "to high BMI. Estimates include uncertainty and are intended "
    "for population-health research."
)