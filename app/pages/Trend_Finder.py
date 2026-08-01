from pathlib import Path
import sys

import altair as alt
import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parents[1]

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from data_access import get_cause_trend  # noqa: E402

from components.lookups import (  # noqa: E402
    cause_lookup,
    county_lookup,
)


st.set_page_config(
    page_title="Trend Finder",
    page_icon="📈",
    layout="wide",
)


st.title("📈 Trend Finder")

st.write(
    """
    Compare high-BMI-attributable years-of-life-lost trends across
    multiple United States counties from 2000 through 2019.
    """
)

st.divider()


# --------------------------------------------------
# Load lookup data
# --------------------------------------------------

counties = county_lookup()
causes = cause_lookup()

if counties.empty:
    st.error("No county records are available.")
    st.stop()

if causes.empty:
    st.error("No cause records are available.")
    st.stop()


# --------------------------------------------------
# Sidebar controls
# --------------------------------------------------

st.sidebar.header("Trend Comparison")

cause_names = causes["cause_name"].tolist()

selected_cause_name = st.sidebar.selectbox(
    label="Cause",
    options=cause_names,
)

selected_cause_record = causes.loc[
    causes["cause_name"] == selected_cause_name
].iloc[0]

selected_cause_id = int(
    selected_cause_record["cause_id"]
)

county_names = counties["display_name"].tolist()

default_counties = [
    name
    for name in [
        "Albany County (Wyoming)",
        "Abbeville County (South Carolina)",
        "Los Angeles County (California)",
    ]
    if name in county_names
]

selected_counties = st.sidebar.multiselect(
    label="Counties",
    options=county_names,
    default=default_counties,
    max_selections=8,
    help=(
        "Select up to eight counties to keep the chart readable."
    ),
)

show_uncertainty = st.sidebar.checkbox(
    label="Show uncertainty intervals",
    value=False,
)

st.sidebar.caption(
    "Coverage: 2000–2019"
)


# --------------------------------------------------
# Selection summary
# --------------------------------------------------

summary_col1, summary_col2 = st.columns(2)

with summary_col1:
    st.metric(
        label="Selected cause",
        value=selected_cause_name,
    )

with summary_col2:
    st.metric(
        label="Counties selected",
        value=len(selected_counties),
    )


if not selected_counties:
    st.info(
        "Select at least one county from the sidebar to display trends."
    )
    st.stop()


# --------------------------------------------------
# Retrieve trend data
# --------------------------------------------------

trend_frames: list[pd.DataFrame] = []

for county_name in selected_counties:
    county_record = counties.loc[
        counties["display_name"] == county_name
    ].iloc[0]

    county_fips = str(
        county_record["fips"]
    ).zfill(5)

    county_trend = get_cause_trend(
        fips=county_fips,
        cause_id=selected_cause_id,
    )

    if county_trend.empty:
        continue

    county_trend = county_trend.copy()

    county_trend["county"] = county_name
    county_trend["fips"] = county_fips
    county_trend["year"] = county_trend[
        "year"
    ].astype(int)

    trend_frames.append(county_trend)


if not trend_frames:
    st.warning(
        "No trend records were returned for the selected cause "
        "and counties."
    )
    st.stop()


trend_data = pd.concat(
    trend_frames,
    ignore_index=True,
)


missing_counties = sorted(
    set(selected_counties)
    - set(trend_data["county"].unique())
)

if missing_counties:
    st.warning(
        "No trend data were found for: "
        + ", ".join(missing_counties)
    )


# --------------------------------------------------
# Trend chart
# --------------------------------------------------

st.divider()

st.subheader("County Trend Comparison")

st.caption(
    "Annual high-BMI-attributable years-of-life-lost rate."
)

base = alt.Chart(
    trend_data
).encode(
    x=alt.X(
        "year:O",
        title="Year",
        axis=alt.Axis(
            labelAngle=0,
        ),
    ),
    color=alt.Color(
        "county:N",
        title="County",
        legend=alt.Legend(
            orient="bottom",
            columns=2,
        ),
    ),
)

trend_line = base.mark_line(
    point=True,
    strokeWidth=3,
).encode(
    y=alt.Y(
        "yll_rate:Q",
        title="YLL rate",
    ),
    tooltip=[
        alt.Tooltip(
            "county:N",
            title="County",
        ),
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

if show_uncertainty:
    uncertainty_band = base.mark_area(
        opacity=0.08,
    ).encode(
        y=alt.Y(
            "lower:Q",
            title="YLL rate",
        ),
        y2="upper:Q",
    )

    chart = (
        uncertainty_band
        + trend_line
    )
else:
    chart = trend_line


chart = chart.properties(
    height=500,
    title=(
        f"{selected_cause_name}, 2000–2019"
    ),
).interactive()


st.altair_chart(
    chart,
    width="stretch",
)


# --------------------------------------------------
# Comparison summary
# --------------------------------------------------

st.divider()

st.subheader("Long-Term Comparison")

comparison_rows: list[dict[str, object]] = []

for county_name, county_group in trend_data.groupby(
    "county"
):
    ordered = county_group.sort_values(
        "year"
    )

    start_record = ordered.iloc[0]
    end_record = ordered.iloc[-1]

    start_value = float(
        start_record["yll_rate"]
    )

    end_value = float(
        end_record["yll_rate"]
    )

    absolute_change = (
        end_value - start_value
    )

    if start_value != 0:
        percent_change = (
            absolute_change
            / start_value
            * 100
        )
    else:
        percent_change = None

    if absolute_change > 0:
        direction = "Increased"
    elif absolute_change < 0:
        direction = "Decreased"
    else:
        direction = "No change"

    comparison_rows.append(
        {
            "County": county_name,
            "FIPS": str(
                start_record["fips"]
            ).zfill(5),
            "Start year": int(
                start_record["year"]
            ),
            "Start YLL rate": start_value,
            "End year": int(
                end_record["year"]
            ),
            "End YLL rate": end_value,
            "Absolute change": absolute_change,
            "Percent change": percent_change,
            "Direction": direction,
        }
    )


comparison = pd.DataFrame(
    comparison_rows
).sort_values(
    "Percent change",
    ascending=False,
    na_position="last",
)


st.dataframe(
    comparison,
    width="stretch",
    hide_index=True,
    column_config={
        "County": st.column_config.TextColumn(
            "County",
            width="large",
        ),
        "FIPS": st.column_config.TextColumn(
            "FIPS",
        ),
        "Start year": st.column_config.NumberColumn(
            "Start year",
            format="%d",
        ),
        "Start YLL rate": st.column_config.NumberColumn(
            "Start YLL rate",
            format="%.1f",
        ),
        "End year": st.column_config.NumberColumn(
            "End year",
            format="%d",
        ),
        "End YLL rate": st.column_config.NumberColumn(
            "End YLL rate",
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


# --------------------------------------------------
# Download data
# --------------------------------------------------

download_col1, download_col2 = st.columns(2)

trend_download = trend_data[
    [
        "county",
        "fips",
        "year",
        "cause_id",
        "cause_name",
        "yll_rate",
        "lower",
        "upper",
    ]
].copy()

trend_csv = trend_download.to_csv(
    index=False
).encode("utf-8")

comparison_csv = comparison.to_csv(
    index=False
).encode("utf-8")

safe_cause_name = (
    selected_cause_name.lower()
    .replace(" ", "_")
    .replace("/", "_")
    .replace("'", "")
)

with download_col1:
    st.download_button(
        label="Download trend data as CSV",
        data=trend_csv,
        file_name=(
            f"{safe_cause_name}_county_trends.csv"
        ),
        mime="text/csv",
    )

with download_col2:
    st.download_button(
        label="Download comparison summary as CSV",
        data=comparison_csv,
        file_name=(
            f"{safe_cause_name}_county_comparison.csv"
        ),
        mime="text/csv",
    )


st.divider()

st.caption(
    "YLL rate represents estimated years of life lost attributable "
    "to high BMI. Estimates include uncertainty and are intended for "
    "population-health research."
)