from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except ImportError:
    px = None


# ============================================================================
# PATHS AND IMPORTS
# ============================================================================

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from data_access import (  # noqa: E402
    get_county_disparity_ranking,
    get_county_disparity_trend,
    get_disparity_causes,
    get_disparity_groups,
    get_disparity_years,
)


COUNTY_GEOJSON_CANDIDATES = [
    APP_DIR / "assets" / "geojson" / "counties.geojson",
    APP_DIR / "assets" / "counties.geojson",
    PROJECT_ROOT / "data" / "geojson" / "counties.geojson",
    PROJECT_ROOT / "data" / "counties.geojson",
]


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Disparity Finder",
    page_icon="⚖️",
    layout="wide",
)

st.title("Disparity Finder")

st.caption(
    "Compare county-level demographic differences in "
    "high-BMI-attributable years-of-life-lost rates."
)


# ============================================================================
# HELPERS
# ============================================================================

def normalize_fips(value: Any) -> str | None:
    """
    Convert a FIPS value into a five-character county FIPS code.

    Handles values such as:
        1001
        01001
        1001.0
        '01001'
    """
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    # Handle values accidentally represented as floating point strings.
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", maxsplit=1)[0]

    digits = re.sub(r"\D", "", text)

    if not digits:
        return None

    return digits.zfill(5)[-5:]


def format_number(
    value: float | int | None,
    decimal_places: int = 2,
) -> str:
    if value is None or pd.isna(value):
        return "Not available"

    return f"{float(value):,.{decimal_places}f}"


def format_percent(
    value: float | int | None,
    decimal_places: int = 1,
) -> str:
    if value is None or pd.isna(value):
        return "Not available"

    return f"{float(value):,.{decimal_places}f}%"


def safe_filename_component(value: str) -> str:
    cleaned = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        value.strip(),
    )

    return cleaned.strip("_").lower()


def extract_selected_map_fips(
    selection_event: Any,
) -> str | None:
    """
    Extract a five-digit county FIPS code from a Streamlit Plotly
    selection event.

    Returns None when no county has been selected.
    """
    if selection_event is None:
        return None

    try:
        selection = selection_event.selection
    except (AttributeError, KeyError):
        try:
            selection = selection_event.get(
                "selection",
                {},
            )
        except AttributeError:
            return None

    try:
        points = selection.points
    except AttributeError:
        try:
            points = selection.get(
                "points",
                [],
            )
        except AttributeError:
            return None

    if not points:
        return None

    point = points[0]

    if hasattr(point, "to_dict"):
        point = point.to_dict()

    if not isinstance(point, dict):
        return None

    possible_values = [
        point.get("location"),
        point.get("id"),
    ]

    customdata = point.get("customdata")

    if isinstance(customdata, (list, tuple)):
        if customdata:
            possible_values.append(customdata[0])
    elif customdata is not None:
        possible_values.append(customdata)

    for value in possible_values:
        normalized = normalize_fips(value)

        if normalized is not None:
            return normalized

    return None


@st.cache_data(show_spinner=False)
def dataframe_to_csv(dataframe: pd.DataFrame) -> bytes:
    return dataframe.to_csv(index=False).encode("utf-8")


@st.cache_data(show_spinner=False)
def load_county_geojson() -> dict[str, Any] | None:
    """
    Load a local U.S. county GeoJSON file.

    The application checks several likely locations. The page continues
    working even when no map file is available.
    """
    geojson_path = next(
        (
            candidate
            for candidate in COUNTY_GEOJSON_CANDIDATES
            if candidate.exists()
        ),
        None,
    )

    if geojson_path is None:
        return None

    try:
        with geojson_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            geojson = json.load(file)

    except (OSError, json.JSONDecodeError):
        return None

    features = geojson.get("features", [])

    for feature in features:
        properties = feature.setdefault(
            "properties",
            {},
        )

        possible_values = [
            feature.get("id"),
            properties.get("GEOID"),
            properties.get("GEOID10"),
            properties.get("GEOID20"),
            properties.get("FIPS"),
            properties.get("fips"),
            properties.get("geoid"),
        ]

        normalized = next(
            (
                normalize_fips(value)
                for value in possible_values
                if normalize_fips(value) is not None
            ),
            None,
        )

        properties["__fips__"] = normalized

    return geojson


def prepare_ranking_dataframe(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    prepared = dataframe.copy()

    prepared["fips"] = prepared["fips"].apply(
        normalize_fips
    )

    numeric_columns = [
        "group_a_value",
        "group_a_lower",
        "group_a_upper",
        "group_b_value",
        "group_b_lower",
        "group_b_upper",
        "absolute_gap",
        "absolute_gap_magnitude",
        "relative_gap_percent",
    ]

    for column in numeric_columns:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(
                prepared[column],
                errors="coerce",
            )

    prepared = prepared.dropna(
        subset=[
            "fips",
            "group_a_value",
            "group_b_value",
            "absolute_gap",
        ]
    )

    prepared["disparity_direction"] = "No difference"

    prepared.loc[
        prepared["absolute_gap"] > 0,
        "disparity_direction",
    ] = "Group A higher"

    prepared.loc[
        prepared["absolute_gap"] < 0,
        "disparity_direction",
    ] = "Group B higher"

    return prepared


def display_ranking_table(
    dataframe: pd.DataFrame,
    group_a_name: str,
    group_b_name: str,
) -> None:
    if dataframe.empty:
        st.info("No counties met the selected criteria.")
        return

    display = dataframe.rename(
        columns={
            "location_name": "County",
            "fips": "FIPS",
            "group_a_value": group_a_name,
            "group_b_value": group_b_name,
            "absolute_gap": "Signed gap",
            "absolute_gap_magnitude": "Gap magnitude",
            "relative_gap_percent": "Relative gap (%)",
            "disparity_direction": "Direction",
        }
    )

    requested_columns = [
        "County",
        "Signed gap",
        "Relative gap (%)",
        group_a_name,
        group_b_name,
        "Gap magnitude",
        "Direction",
        "FIPS",
    ]

    available_columns = [
        column
        for column in requested_columns
        if column in display.columns
    ]

    st.dataframe(
        display[available_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "County": st.column_config.TextColumn(width="large"),
            "FIPS": st.column_config.TextColumn(width="small"),
            group_a_name: st.column_config.NumberColumn(format="%.2f"),
            group_b_name: st.column_config.NumberColumn(format="%.2f"),
            "Signed gap": st.column_config.NumberColumn(format="%.2f"),
            "Gap magnitude": st.column_config.NumberColumn(format="%.2f"),
            "Relative gap (%)": st.column_config.NumberColumn(
                format="%.1f%%"
            ),
        },
    )


# ============================================================================
# LOAD FILTER OPTIONS
# ============================================================================

try:
    causes = get_disparity_causes()
    years = get_disparity_years()

except Exception as exc:
    st.error(
        "The application could not load disparity-filter options "
        f"from the warehouse.\n\n{exc}"
    )
    st.stop()


if causes.empty:
    st.error(
        "No causes were found in the IHME burden table."
    )
    st.stop()


if not years:
    st.error(
        "No analysis years were found in the IHME burden table."
    )
    st.stop()


# ============================================================================
# SIDEBAR FILTERS
# ============================================================================

with st.sidebar:
    st.header("Analysis settings")

    dimension = st.selectbox(
        "Comparison dimension",
        options=[
            "Race / ethnicity",
            "Sex",
            "Age group",
        ],
        help=(
            "Choose the demographic dimension used to compare "
            "Group A with Group B."
        ),
    )

    cause_names = causes["cause_name"].astype(str).tolist()

    cause_lookup = {
        str(row.cause_name): int(row.cause_id)
        for row in causes.itertuples(index=False)
    }

    preferred_cause_names = [
        "Diabetes mellitus type 2",
        "Type 2 diabetes mellitus",
        "Diabetes mellitus",
    ]

    default_cause_index = 0

    for preferred_name in preferred_cause_names:
        matching_indices = [
            index
            for index, cause_name in enumerate(cause_names)
            if preferred_name.lower() in cause_name.lower()
        ]

        if matching_indices:
            default_cause_index = matching_indices[0]
            break

    selected_cause_name = st.selectbox(
        "Cause",
        options=cause_names,
        index=default_cause_index,
    )

    selected_cause_id = cause_lookup[
        selected_cause_name
    ]

    selected_year = int(
        st.selectbox(
            "Year",
            options=years,
            index=0,
        )
    )

    try:
        groups = get_disparity_groups(dimension)

    except Exception as exc:
        st.error(
            "The demographic groups could not be loaded.\n\n"
            f"{exc}"
        )
        st.stop()

    if groups.empty or len(groups) < 2:
        st.error(
            "At least two demographic groups are required."
        )
        st.stop()

    group_names = (
        groups["group_name"]
        .astype(str)
        .tolist()
    )

    group_lookup = {
        str(row.group_name): int(row.group_id)
        for row in groups.itertuples(index=False)
    }

    group_a_default_index = 0
    group_b_default_index = 1 if len(group_names) > 1 else 0

    if dimension == "Race / ethnicity":
        for index, name in enumerate(group_names):
            if "Black" in name:
                group_a_default_index = index

            if "White" in name:
                group_b_default_index = index

    elif dimension == "Sex":
        for index, name in enumerate(group_names):
            if name == "Male":
                group_a_default_index = index

            if name == "Female":
                group_b_default_index = index

    group_a_name = st.selectbox(
        "Group A",
        options=group_names,
        index=group_a_default_index,
        help=(
            "The signed gap is calculated as Group A minus Group B."
        ),
    )

    group_b_name = st.selectbox(
        "Group B",
        options=group_names,
        index=group_b_default_index,
    )

    counties_to_show = st.slider(
        "Counties in ranking",
        min_value=10,
        max_value=100,
        value=25,
        step=5,
    )

    map_measure = st.radio(
        "Map measure",
        options=[
            "Signed gap",
            "Relative gap",
            "Gap magnitude",
            "Group A rate",
            "Group B rate",
        ],
        index=0,
        help=(
            "Signed gap preserves direction. Relative gap expresses the "
            "difference as a percentage of Group B. Gap magnitude ignores "
            "direction. Group-rate views show the burden within one group."
        ),
    )

if group_a_name == group_b_name:
    st.warning(
        "Group A and Group B must be different."
    )
    st.stop()


group_a_id = group_lookup[group_a_name]
group_b_id = group_lookup[group_b_name]


# ============================================================================
# QUERY COUNTY DISPARITIES
# ============================================================================

try:
    with st.spinner(
        "Calculating county-level disparities..."
    ):
        ranking = get_county_disparity_ranking(
            cause_id=selected_cause_id,
            year=selected_year,
            dimension=dimension,
            group_a_id=group_a_id,
            group_b_id=group_b_id,
        )

except Exception as exc:
    st.error(
        "The county disparity query failed.\n\n"
        f"{exc}"
    )
    st.stop()


if ranking.empty:
    st.warning(
        "No counties had non-null estimates for both selected groups "
        "under this exact cause, year, and demographic definition."
    )

    st.info(
        "Try a more common cause such as type 2 diabetes, ischemic "
        "heart disease, stroke, or all causes. Rare diseases frequently "
        "have suppressed county-level subgroup estimates."
    )

    st.stop()


ranking = prepare_ranking_dataframe(ranking)
stored_clicked_fips = st.session_state.get(
    "disparity_clicked_fips"
)

if stored_clicked_fips is not None:
    available_fips = {
        normalize_fips(value)
        for value in ranking["fips"].tolist()
    }

    if normalize_fips(
        stored_clicked_fips
    ) not in available_fips:
        st.session_state.pop(
            "disparity_clicked_fips",
            None,
        )

if ranking.empty:
    st.warning(
        "No valid county comparisons remained after cleaning "
        "the query results."
    )
    st.stop()


# ============================================================================
# COMPARISON DEFINITION
# ============================================================================

st.subheader("Comparison definition")

definition_col_1, definition_col_2 = st.columns(
    [3, 2]
)

with definition_col_1:
    st.markdown(
        f"""
**Outcome:** High-BMI-attributable YLL rate  
**Cause:** {selected_cause_name}  
**Year:** {selected_year}  
**Dimension:** {dimension}  
**Comparison:** {group_a_name} minus {group_b_name}
"""
    )

with definition_col_2:
    st.info(
        "A positive gap means Group A has the higher YLL rate. "
        "A negative gap means Group B has the higher YLL rate."
    )


# ============================================================================
# SUMMARY METRICS
# ============================================================================

positive = ranking.loc[
    ranking["absolute_gap"] > 0
].copy()

negative = ranking.loc[
    ranking["absolute_gap"] < 0
].copy()

largest_positive_row = (
    positive.sort_values(
        "absolute_gap",
        ascending=False,
    ).iloc[0]
    if not positive.empty
    else None
)

largest_reverse_row = (
    negative.sort_values(
        "absolute_gap",
        ascending=True,
    ).iloc[0]
    if not negative.empty
    else None
)

median_gap = ranking["absolute_gap"].median()
median_magnitude = ranking[
    "absolute_gap_magnitude"
].median()


st.subheader("Summary")

metric_1, metric_2, metric_3, metric_4 = st.columns(
    4
)

metric_1.metric(
    "Counties analyzed",
    f"{len(ranking):,}",
)

metric_2.metric(
    "Median signed gap",
    format_number(median_gap),
    help=(
        "The median of Group A minus Group B across "
        "all analyzed counties."
    ),
)

metric_3.metric(
    "Median gap magnitude",
    format_number(median_magnitude),
    help=(
        "The median absolute difference between the two groups."
    ),
)

with metric_4:
    st.metric(
        "Group A higher",
        f"{len(positive):,}",
    )

    st.caption(
        f"{len(negative):,} counties had Group B higher."
    )


summary_col_1, summary_col_2 = st.columns(2)

with summary_col_1:
    st.markdown("#### Largest positive disparity")

    if largest_positive_row is None:
        st.write(
            "No county had a positive Group A minus Group B gap."
        )
    else:
        st.metric(
            label=str(
                largest_positive_row["location_name"]
            ),
            value=format_number(
                largest_positive_row["absolute_gap"]
            ),
            delta=(
                f"{format_percent(largest_positive_row['relative_gap_percent'])} "
                "relative gap"
            ),
        )

with summary_col_2:
    st.markdown("#### Largest reverse disparity")

    if largest_reverse_row is None:
        st.write(
            "No county had a negative Group A minus Group B gap."
        )
    else:
        st.metric(
            label=str(
                largest_reverse_row["location_name"]
            ),
            value=format_number(
                largest_reverse_row["absolute_gap"]
            ),
            delta=(
                f"{format_percent(largest_reverse_row['relative_gap_percent'])} "
                "relative gap"
            ),
            delta_color="inverse",
        )


# ============================================================================
# COUNTY MAP
# ============================================================================

st.subheader("Geographic distribution")

county_geojson = load_county_geojson()

if px is None:
    st.warning(
        "Plotly is not installed, so the county map cannot be displayed. "
        "Install it with: pip install plotly"
    )

elif county_geojson is None:
    st.info(
        "The disparity calculations are working, but the local county "
        "GeoJSON file has not yet been added. The rankings and trend "
        "sections below remain fully available."
    )

    with st.expander(
        "Expected GeoJSON file location"
    ):
        st.code(
            str(
                APP_DIR
                / "assets"
                / "geojson"
                / "counties.geojson"
            ),
            language="text",
        )

else:
    map_column_lookup = {
        "Signed gap": "absolute_gap",
        "Relative gap": "relative_gap_percent",
        "Gap magnitude": "absolute_gap_magnitude",
        "Group A rate": "group_a_value",
        "Group B rate": "group_b_value",
    }

    map_column = map_column_lookup[
        map_measure
    ]

    map_data = ranking[
        [
            "fips",
            "location_name",
            "group_a_value",
            "group_b_value",
            "absolute_gap",
            "absolute_gap_magnitude",
            "relative_gap_percent",
        ]
    ].copy()

    map_data["fips"] = (
        map_data["fips"]
        .astype(str)
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
        .str.zfill(5)
    )

    map_data = map_data.dropna(
        subset=[
            "fips",
            map_column,
        ]
    )

    # --------------------------------------------------------------
    # Map visual design
    # --------------------------------------------------------------

    if map_measure == "Signed gap":
        color_scale = "RdBu_r"
        color_midpoint = 0
        colorbar_title = "Signed gap"

        map_explanation = (
            f"Red counties indicate a higher YLL rate for "
            f"{group_a_name}. Blue counties indicate a higher rate "
            f"for {group_b_name}. Counties near white have smaller "
            "signed differences."
        )

    elif map_measure == "Relative gap":
        color_scale = "RdBu_r"
        color_midpoint = 0
        colorbar_title = "Relative gap (%)"

        map_explanation = (
            f"Red counties indicate a higher relative burden for "
            f"{group_a_name}; blue counties indicate a higher burden "
            f"for {group_b_name}. Group B is the percentage reference."
        )

    elif map_measure == "Gap magnitude":
        color_scale = "Blues"
        color_midpoint = None
        colorbar_title = "Gap magnitude"

        map_explanation = (
            "Darker counties have larger differences between the two "
            "groups, regardless of which group has the higher rate."
        )

    elif map_measure == "Group A rate":
        color_scale = "Reds"
        color_midpoint = None
        colorbar_title = f"{group_a_name} rate"

        map_explanation = (
            f"Darker counties have a higher estimated YLL rate for "
            f"{group_a_name}."
        )

    else:
        color_scale = "Blues"
        color_midpoint = None
        colorbar_title = f"{group_b_name} rate"

        map_explanation = (
            f"Darker counties have a higher estimated YLL rate for "
            f"{group_b_name}."
        )

    map_title = (
        f"{map_measure}: {group_a_name} versus {group_b_name}"
        f"<br><sup>{selected_cause_name}, {selected_year}</sup>"
    )

    choropleth_arguments = {
        "data_frame": map_data,
        "geojson": county_geojson,
        "locations": "fips",
        "featureidkey": "id",
        "color": map_column,
        "color_continuous_scale": color_scale,
        "hover_name": "location_name",
        "custom_data": ["fips"],
        "hover_data": {
            "fips": True,
            "group_a_value": ":,.2f",
            "group_b_value": ":,.2f",
            "absolute_gap": ":,.2f",
            "absolute_gap_magnitude": ":,.2f",
            "relative_gap_percent": ":,.1f",
        },
        "labels": {
            "fips": "FIPS",
            "group_a_value": f"{group_a_name} YLL rate",
            "group_b_value": f"{group_b_name} YLL rate",
            "absolute_gap": "Signed gap",
            "absolute_gap_magnitude": "Gap magnitude",
            "relative_gap_percent": "Relative gap (%)",
        },
        "title": map_title,
    }

    if color_midpoint is not None:
        choropleth_arguments[
            "color_continuous_midpoint"
        ] = color_midpoint

    figure = px.choropleth(
        **choropleth_arguments
    )

    figure.update_traces(
        marker_line_width=0.15,
        marker_line_color="white",
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "FIPS: %{location}<br>"
            f"{group_a_name}: "
            "%{customdata[1]:,.2f}<br>"
            f"{group_b_name}: "
            "%{customdata[2]:,.2f}<br>"
            "Signed gap: "
            "%{customdata[3]:,.2f}<br>"
            "Gap magnitude: "
            "%{customdata[4]:,.2f}<br>"
            "Relative gap: "
            "%{customdata[5]:,.1f}%"
            "<extra></extra>"
        ),
        customdata=map_data[
            [
                "fips",
                "group_a_value",
                "group_b_value",
                "absolute_gap",
                "absolute_gap_magnitude",
                "relative_gap_percent",
            ]
        ].to_numpy(),
    )

    figure.update_geos(
        scope="usa",
        projection_type="albers usa",
        visible=False,
        showland=True,
        landcolor="rgb(238, 238, 238)",
        showcountries=False,
        showsubunits=True,
        subunitcolor="rgb(90, 90, 90)",
        subunitwidth=0.8,
        showlakes=True,
        lakecolor="white",
    )

    figure.update_layout(
        height=680,
        margin={
            "r": 0,
            "t": 75,
            "l": 0,
            "b": 0,
        },
        title={
            "x": 0.01,
            "xanchor": "left",
        },
        coloraxis_colorbar={
            "title": colorbar_title,
            "thickness": 16,
            "len": 0.72,
        },
        clickmode="event+select",
        dragmode="zoom",
    )

    st.caption(
        map_explanation
    )

    map_event = st.plotly_chart(
        figure,
        use_container_width=True,
        key="disparity_county_map",
        on_select="rerun",
        selection_mode="points",
        config={
            "displaylogo": False,
            "scrollZoom": True,
            "responsive": True,
            "toImageButtonOptions": {
                "format": "png",
                "filename": (
                    f"{safe_filename_component(map_measure)}_"
                    f"{safe_filename_component(selected_cause_name)}_"
                    f"{selected_year}"
                ),
                "height": 900,
                "width": 1500,
                "scale": 2,
            },
            "modeBarButtonsToRemove": [
                "lasso2d",
                "select2d",
            ],
        },
    )

    clicked_map_fips = extract_selected_map_fips(
        map_event
    )

    if clicked_map_fips is not None:
        st.session_state[
            "disparity_clicked_fips"
        ] = clicked_map_fips

        clicked_record = ranking.loc[
            ranking["fips"].astype(str).str.zfill(5)
            == clicked_map_fips
        ]

        if not clicked_record.empty:
            clicked_county_name = str(
                clicked_record.iloc[0][
                    "location_name"
                ]
            )

            st.success(
                f"Selected from map: {clicked_county_name} "
                f"({clicked_map_fips}). The trend section below "
                "has been updated."
            )


# ============================================================================
# RANKINGS
# ============================================================================

st.subheader("County rankings")

positive_tab, reverse_tab, all_tab = st.tabs(
    [
        "Largest positive disparities",
        "Largest reverse disparities",
        "All counties",
    ]
)


with positive_tab:
    st.caption(
        f"Counties where {group_a_name} had a higher "
        f"YLL rate than {group_b_name}."
    )

    positive_ranking = (
        positive.sort_values(
            "absolute_gap",
            ascending=False,
        )
        .head(counties_to_show)
        .copy()
    )

    if not positive_ranking.empty:
        positive_chart_data = (
            positive_ranking[
                [
                    "location_name",
                    "absolute_gap",
                    "relative_gap_percent",
                ]
            ]
            .sort_values(
                "absolute_gap",
                ascending=True,
            )
            .copy()
        )

        positive_chart = (
            alt.Chart(positive_chart_data)
            .mark_bar()
            .encode(
                x=alt.X(
                    "absolute_gap:Q",
                    title="Signed YLL-rate gap",
                ),
                y=alt.Y(
                    "location_name:N",
                    title=None,
                    sort=None,
                    axis=alt.Axis(
                        labelLimit=320,
                    ),
                ),
                tooltip=[
                    alt.Tooltip(
                        "location_name:N",
                        title="County",
                    ),
                    alt.Tooltip(
                        "absolute_gap:Q",
                        title="Signed gap",
                        format=",.2f",
                    ),
                    alt.Tooltip(
                        "relative_gap_percent:Q",
                        title="Relative gap",
                        format=",.1f",
                    ),
                ],
            )
            .properties(
                height=max(
                    350,
                    len(positive_chart_data) * 25,
                )
            )
        )

        st.altair_chart(
            positive_chart,
            width="stretch",
        )

        display_ranking_table(
            positive_ranking,
            group_a_name,
            group_b_name,
        )


with reverse_tab:
    st.caption(
        f"Counties where {group_b_name} had a higher "
        f"YLL rate than {group_a_name}."
    )

    reverse_ranking = (
        negative.sort_values(
            "absolute_gap",
            ascending=True,
        )
        .head(counties_to_show)
        .copy()
    )

    if not reverse_ranking.empty:
        reverse_chart_data = (
            reverse_ranking[
                [
                    "location_name",
                    "absolute_gap",
                    "absolute_gap_magnitude",
                    "relative_gap_percent",
                ]
            ]
            .sort_values(
                "absolute_gap_magnitude",
                ascending=True,
            )
            .copy()
        )

        reverse_chart = (
            alt.Chart(reverse_chart_data)
            .mark_bar()
            .encode(
                x=alt.X(
                    "absolute_gap_magnitude:Q",
                    title="Gap magnitude",
                ),
                y=alt.Y(
                    "location_name:N",
                    title=None,
                    sort=None,
                    axis=alt.Axis(
                        labelLimit=320,
                    ),
                ),
                tooltip=[
                    alt.Tooltip(
                        "location_name:N",
                        title="County",
                    ),
                    alt.Tooltip(
                        "absolute_gap:Q",
                        title="Signed gap",
                        format=",.2f",
                    ),
                    alt.Tooltip(
                        "absolute_gap_magnitude:Q",
                        title="Gap magnitude",
                        format=",.2f",
                    ),
                    alt.Tooltip(
                        "relative_gap_percent:Q",
                        title="Relative gap",
                        format=",.1f",
                    ),
                ],
            )
            .properties(
                height=max(
                    350,
                    len(reverse_chart_data) * 25,
                )
            )
        )

        st.altair_chart(
            reverse_chart,
            width="stretch",
        )

        display_ranking_table(
            reverse_ranking,
            group_a_name,
            group_b_name,
        )


with all_tab:
    all_counties = ranking.sort_values(
        "absolute_gap_magnitude",
        ascending=False,
    ).copy()

    display_ranking_table(
        all_counties,
        group_a_name,
        group_b_name,
    )


# ============================================================================
# SELECTED COUNTY TREND
# ============================================================================

st.subheader("Selected county trend")

county_options = (
    ranking[
        [
            "fips",
            "location_name",
        ]
    ]
    .drop_duplicates()
    .sort_values(
        [
            "location_name",
            "fips",
        ]
    )
)

county_label_to_fips = {
    f"{row.location_name} ({row.fips})": str(row.fips)
    for row in county_options.itertuples(index=False)
}

default_county_label = next(
    iter(county_label_to_fips)
)

clicked_fips = st.session_state.get(
    "disparity_clicked_fips"
)

if clicked_fips is not None:
    clicked_label = next(
        (
            label
            for label, fips_value
            in county_label_to_fips.items()
            if normalize_fips(fips_value)
            == normalize_fips(clicked_fips)
        ),
        None,
    )

    if clicked_label is not None:
        default_county_label = clicked_label
        st.session_state[
            "disparity_county_selector"
        ] = clicked_label

elif largest_positive_row is not None:
    candidate_label = (
        f"{largest_positive_row['location_name']} "
        f"({largest_positive_row['fips']})"
    )

    if candidate_label in county_label_to_fips:
        default_county_label = candidate_label

county_labels = list(
    county_label_to_fips.keys()
)

default_county_index = county_labels.index(
    default_county_label
)

selected_county_label = st.selectbox(
    "County",
    options=county_labels,
    index=default_county_index,
    key="disparity_county_selector",
)

selected_fips = county_label_to_fips[
    selected_county_label
]


try:
    with st.spinner(
        "Loading the county disparity trend..."
    ):
        trend = get_county_disparity_trend(
            fips=selected_fips,
            cause_id=selected_cause_id,
            dimension=dimension,
            group_a_id=group_a_id,
            group_b_id=group_b_id,
        )

except Exception as exc:
    st.error(
        "The county trend query failed.\n\n"
        f"{exc}"
    )
    trend = pd.DataFrame()


if trend.empty:
    st.info(
        "No complete annual comparison was available "
        "for this county."
    )

else:
    trend = trend.copy()

    trend_numeric_columns = [
        "group_a_value",
        "group_a_lower",
        "group_a_upper",
        "group_b_value",
        "group_b_lower",
        "group_b_upper",
        "absolute_gap",
        "absolute_gap_magnitude",
        "relative_gap_percent",
    ]

    for column in trend_numeric_columns:
        if column in trend.columns:
            trend[column] = pd.to_numeric(
                trend[column],
                errors="coerce",
            )

    trend["year"] = pd.to_numeric(
        trend["year"],
        errors="coerce",
    )

    # ----------------------------------------------------------------
    # Group-specific rates chart
    # ----------------------------------------------------------------

    rates_long = trend[
        [
            "year",
            "group_a_value",
            "group_b_value",
        ]
    ].rename(
        columns={
            "group_a_value": group_a_name,
            "group_b_value": group_b_name,
        }
    ).melt(
        id_vars="year",
        var_name="Demographic group",
        value_name="YLL rate",
    )

    st.markdown("#### Group-specific YLL rates")

    rates_chart = (
        alt.Chart(rates_long)
        .mark_line(
            point=True,
            strokeWidth=3,
        )
        .encode(
            x=alt.X(
                "year:O",
                title="Year",
                sort=list(range(2000, 2020)),
                axis=alt.Axis(
                    labelAngle=0,
                    values=list(range(2000, 2020)),
                ),
            ),
            y=alt.Y(
                "YLL rate:Q",
                title="YLL rate",
                scale=alt.Scale(
                    zero=False,
                ),
            ),
            color=alt.Color(
                "Demographic group:N",
                title="Demographic group",
            ),
            tooltip=[
                alt.Tooltip(
                    "Demographic group:N",
                    title="Group",
                ),
                alt.Tooltip(
                    "year:O",
                    title="Year",
                ),
                alt.Tooltip(
                    "YLL rate:Q",
                    title="YLL rate",
                    format=",.2f",
                ),
            ],
        )
        .properties(
            height=430,
        )
    )

    st.altair_chart(
        rates_chart,
        width="stretch",
    )

    # ----------------------------------------------------------------
    # Gap charts
    # ----------------------------------------------------------------

    trend_col_1, trend_col_2 = st.columns(2)

    with trend_col_1:
        st.markdown("#### Signed disparity gap")

        signed_gap_chart = (
            alt.Chart(trend)
            .mark_line(
                point=True,
                strokeWidth=3,
            )
            .encode(
                x=alt.X(
                    "year:O",
                    title="Year",
                    sort=list(range(2000, 2020)),
                    axis=alt.Axis(
                        labelAngle=0,
                        values=list(range(2000, 2020)),
                    ),
                ),
                y=alt.Y(
                    "absolute_gap:Q",
                    title="Signed YLL-rate gap",
                    scale=alt.Scale(
                        zero=False,
                    ),
                ),
                tooltip=[
                    alt.Tooltip(
                        "year:O",
                        title="Year",
                    ),
                    alt.Tooltip(
                        "absolute_gap:Q",
                        title="Signed gap",
                        format=",.2f",
                    ),
                ],
            )
            .properties(
                height=370,
            )
        )

        zero_line = (
            alt.Chart(
                pd.DataFrame(
                    {
                        "zero": [0],
                    }
                )
            )
            .mark_rule(
                strokeDash=[5, 5],
            )
            .encode(
                y="zero:Q",
            )
        )

        st.altair_chart(
            signed_gap_chart + zero_line,
            width="stretch",
        )

    with trend_col_2:
        st.markdown("#### Relative disparity")

        relative_gap_chart = (
            alt.Chart(trend)
            .mark_line(
                point=True,
                strokeWidth=3,
            )
            .encode(
                x=alt.X(
                    "year:O",
                    title="Year",
                    sort=list(range(2000, 2020)),
                    axis=alt.Axis(
                        labelAngle=0,
                        values=list(range(2000, 2020)),
                    ),
                ),
                y=alt.Y(
                    "relative_gap_percent:Q",
                    title="Relative gap (%)",
                    scale=alt.Scale(
                        zero=False,
                    ),
                ),
                tooltip=[
                    alt.Tooltip(
                        "year:O",
                        title="Year",
                    ),
                    alt.Tooltip(
                        "relative_gap_percent:Q",
                        title="Relative gap",
                        format=",.1f",
                    ),
                ],
            )
            .properties(
                height=370,
            )
        )

        st.altair_chart(
            relative_gap_chart,
            width="stretch",
        )

    latest_trend_row = trend.sort_values(
        "year"
    ).iloc[-1]

    latest_col_1, latest_col_2, latest_col_3 = (
        st.columns(3)
    )

    latest_col_1.metric(
        f"{group_a_name} rate",
        format_number(
            latest_trend_row["group_a_value"]
        ),
    )

    latest_col_2.metric(
        f"{group_b_name} rate",
        format_number(
            latest_trend_row["group_b_value"]
        ),
    )

    latest_col_3.metric(
        "Latest signed gap",
        format_number(
            latest_trend_row["absolute_gap"]
        ),
        delta=format_percent(
            latest_trend_row[
                "relative_gap_percent"
            ]
        ),
    )


# ============================================================================
# DOWNLOAD
# ============================================================================

st.subheader("Download results")

download_data = ranking.rename(
    columns={
        "group_a_value": (
            f"{safe_filename_component(group_a_name)}"
            "_yll_rate"
        ),
        "group_a_lower": (
            f"{safe_filename_component(group_a_name)}"
            "_lower"
        ),
        "group_a_upper": (
            f"{safe_filename_component(group_a_name)}"
            "_upper"
        ),
        "group_b_value": (
            f"{safe_filename_component(group_b_name)}"
            "_yll_rate"
        ),
        "group_b_lower": (
            f"{safe_filename_component(group_b_name)}"
            "_lower"
        ),
        "group_b_upper": (
            f"{safe_filename_component(group_b_name)}"
            "_upper"
        ),
    }
)

download_filename = (
    f"{safe_filename_component(dimension)}_"
    f"{safe_filename_component(group_a_name)}_vs_"
    f"{safe_filename_component(group_b_name)}_"
    f"{safe_filename_component(selected_cause_name)}_"
    f"{selected_year}.csv"
)

st.download_button(
    label="Download county disparity results",
    data=dataframe_to_csv(download_data),
    file_name=download_filename,
    mime="text/csv",
    use_container_width=False,
)


# ============================================================================
# METHODS NOTE
# ============================================================================

with st.expander("Methods and interpretation"):
    st.markdown(
        f"""
### Calculation

The signed disparity gap is calculated as:

`{group_a_name} YLL rate - {group_b_name} YLL rate`

A positive value means **{group_a_name}** has the higher rate.

A negative value means **{group_b_name}** has the higher rate.

The relative gap is calculated using Group B as the reference:

`((Group A rate - Group B rate) / Group B rate) x 100`

### Standardization

Race and sex comparisons use the warehouse's age-standardized
20-plus age group.

Age-group comparisons use both sexes and the total race or ethnicity
population.

### Important limitation

This page provides descriptive disparity estimates. It does not establish
causation, statistical significance, or the causes of observed differences.
Confidence intervals should be considered when interpreting county estimates.
"""
    )