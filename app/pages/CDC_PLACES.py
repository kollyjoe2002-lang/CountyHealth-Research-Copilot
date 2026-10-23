from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.data_access import (
    get_places_county_snapshot,
    get_places_county_measure_ranking,
    get_places_county_measure_trend,
)


st.set_page_config(
    page_title="CDC PLACES",
    page_icon="??",
    layout="wide",
)

st.title("CDC PLACES")

st.caption(
    "Explore county-level CDC PLACES modeled prevalence estimates. "
    "Measurement year and release year are shown separately."
)

st.info(
    "CDC PLACES estimates are modeled prevalence estimates based on BRFSS "
    "and related data. Age-adjusted prevalence is used where available."
)

analysis = st.selectbox(
    "Analysis",
    [
        "County snapshot",
        "County measure trend",
        "National county ranking",
    ],
)

if analysis == "County snapshot":
    fips = st.text_input(
        "County FIPS",
        value="55079",
        help="Example: Milwaukee County, Wisconsin = 55079",
    )

    release_year = st.selectbox(
        "PLACES release year",
        [2025, 2024, 2023, 2022, 2021, 2020],
    )

    if st.button(
        "Run snapshot",
        type="primary",
    ):
        df = get_places_county_snapshot(
            fips.strip(),
            int(release_year),
        )

        if df.empty:
            st.warning("No matching PLACES estimates were found.")
        else:
            county = df.iloc[0]

            st.subheader(
                f"{county['geography_name']} County, "
                f"{county['state_abbr']}"
            )

            st.caption(
                f"PLACES release {int(county['release_year'])} | "
                f"Measurement year {int(county['measurement_year'])}"
            )

            display = df[
                [
                    "measure_id",
                    "measure_name",
                    "category",
                    "crude_prevalence",
                    "crude_ci_lower",
                    "crude_ci_upper",
                    "age_adjusted_prevalence",
                    "age_adjusted_ci_lower",
                    "age_adjusted_ci_upper",
                ]
            ].copy()

            st.dataframe(
                display,
                width="stretch",
                hide_index=True,
            )

elif analysis == "County measure trend":
    fips = st.text_input(
        "County FIPS",
        value="55079",
    )

    measure_id = st.text_input(
        "PLACES measure ID",
        value="DIABETES",
        help="Examples: DIABETES, STROKE, CHD, OBESITY, CASTHMA",
    ).strip().upper()

    if st.button(
        "Run trend",
        type="primary",
    ):
        df = get_places_county_measure_trend(
            fips.strip(),
            measure_id,
        )

        if df.empty:
            st.warning("No matching PLACES trend was found.")
        else:
            county = df.iloc[0]

            st.subheader(
                f"{county['measure_name']} - "
                f"{county['geography_name']} County, "
                f"{county['state_abbr']}"
            )

            chart = (
                df[
                    [
                        "measurement_year",
                        "age_adjusted_prevalence",
                    ]
                ]
                .dropna()
                .set_index("measurement_year")
            )

            st.line_chart(chart)

            st.dataframe(
                df[
                    [
                        "release_year",
                        "measurement_year",
                        "age_adjusted_prevalence",
                        "age_adjusted_ci_lower",
                        "age_adjusted_ci_upper",
                        "carry_forward",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

elif analysis == "National county ranking":
    measure_id = st.text_input(
        "PLACES measure ID",
        value="DIABETES",
        help="Examples: DIABETES, STROKE, CHD, OBESITY, CASTHMA",
    ).strip().upper()

    measurement_year = st.selectbox(
        "Measurement year",
        [2023, 2022, 2021, 2020, 2019, 2018],
        index=4,
    )

    limit = st.slider(
        "Number of counties",
        min_value=5,
        max_value=100,
        value=25,
        step=5,
    )

    if st.button(
        "Run ranking",
        type="primary",
    ):
        df = get_places_county_measure_ranking(
            measure_id,
            int(measurement_year),
            int(limit),
        )

        if df.empty:
            st.warning("No matching county ranking was found.")
        else:
            st.subheader(
                f"{df.iloc[0]['measure_name']} - "
                f"{measurement_year}"
            )

            st.dataframe(
                df[
                    [
                        "national_rank",
                        "geography_name",
                        "state_abbr",
                        "age_adjusted_prevalence",
                        "age_adjusted_ci_lower",
                        "age_adjusted_ci_upper",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

st.divider()

st.caption(
    "Source: CDC PLACES. Release year is not necessarily the same as "
    "the BRFSS measurement year."
)
