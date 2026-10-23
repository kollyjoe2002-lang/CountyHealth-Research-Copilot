from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.data_access import (
    get_places_ihme_rurality_comparison,
    get_places_rural_metro_comparison,
    get_places_rucc_comparison,
)


st.set_page_config(
    page_title="Rural Health",
    page_icon="??",
    layout="wide",
)

st.title("Rural Health")

st.caption(
    "Compare county health patterns across metropolitan and "
    "nonmetropolitan settings using USDA RUCC 2023 classifications."
)

analysis = st.selectbox(
    "Analysis",
    [
        "Metro vs nonmetro prevalence",
        "Detailed RUCC comparison",
        "PLACES + IHME rurality comparison",
    ],
)

if analysis in {
    "Metro vs nonmetro prevalence",
    "Detailed RUCC comparison",
}:
    measure_id = st.text_input(
        "CDC PLACES measure ID",
        value="DIABETES",
        help="Examples: DIABETES, STROKE, CHD, OBESITY, CASTHMA",
    ).strip().upper()

    measurement_year = st.selectbox(
        "PLACES measurement year",
        [2023, 2022, 2021, 2020, 2019, 2018],
        index=4,
    )

    if analysis == "Metro vs nonmetro prevalence":
        if st.button(
            "Run rural comparison",
            type="primary",
        ):
            df = get_places_rural_metro_comparison(
                measure_id,
                int(measurement_year),
            )

            if df.empty:
                st.warning("No matching rurality comparison was found.")
            else:
                st.subheader(
                    f"{df.iloc[0]['measure_name']} - "
                    f"{measurement_year}"
                )

                chart = (
                    df[
                        [
                            "metro_status",
                            "median_prevalence",
                        ]
                    ]
                    .set_index("metro_status")
                )

                st.bar_chart(chart)

                st.dataframe(
                    df[
                        [
                            "metro_status",
                            "counties_with_estimate",
                            "mean_prevalence",
                            "median_prevalence",
                            "minimum_prevalence",
                            "maximum_prevalence",
                        ]
                    ],
                    width="stretch",
                    hide_index=True,
                )

    else:
        if st.button(
            "Run RUCC comparison",
            type="primary",
        ):
            df = get_places_rucc_comparison(
                measure_id,
                int(measurement_year),
            )

            if df.empty:
                st.warning("No matching RUCC comparison was found.")
            else:
                st.subheader(
                    f"{df.iloc[0]['measure_name']} by RUCC category"
                )

                chart = (
                    df[
                        [
                            "rucc_code",
                            "median_prevalence",
                        ]
                    ]
                    .set_index("rucc_code")
                )

                st.bar_chart(chart)

                st.dataframe(
                    df[
                        [
                            "rucc_code",
                            "rucc_description",
                            "metro_status",
                            "adjacency_status",
                            "counties_with_estimate",
                            "mean_prevalence",
                            "median_prevalence",
                        ]
                    ],
                    width="stretch",
                    hide_index=True,
                )

else:
    validated_pairs = {
        "Diabetes prevalence + type 2 diabetes burden": (
            "DIABETES",
            976,
        ),
        "Stroke prevalence + stroke burden": (
            "STROKE",
            494,
        ),
        "Current asthma prevalence + asthma burden": (
            "CASTHMA",
            515,
        ),
    }

    selected_pair = st.selectbox(
        "Validated cross-source pair",
        list(validated_pairs),
    )

    places_measure_id, ihme_cause_id = (
        validated_pairs[selected_pair]
    )

    places_year = st.selectbox(
        "PLACES measurement year",
        [2019],
        help=(
            "Current validated matched-year cross-source rurality "
            "analysis uses 2019."
        ),
    )

    ihme_year = st.selectbox(
        "IHME year",
        [2019],
    )

    st.info(
        "CDC PLACES prevalence and IHME YLL rates are displayed as "
        "separate outcomes. They are not combined into one measure."
    )

    if st.button(
        "Run cross-source rurality comparison",
        type="primary",
    ):
        df = get_places_ihme_rurality_comparison(
            places_measure_id,
            int(places_year),
            int(ihme_cause_id),
            int(ihme_year),
        )

        if df.empty:
            st.warning(
                "No matching cross-source rurality comparison was found."
            )
        else:
            st.subheader(selected_pair)

            left, right = st.columns(2)

            with left:
                st.markdown("#### CDC PLACES prevalence")

                places_chart = (
                    df[
                        [
                            "rurality_group",
                            "median_places_prevalence",
                        ]
                    ]
                    .set_index("rurality_group")
                )

                st.bar_chart(places_chart)

            with right:
                st.markdown("#### IHME YLL rate")

                ihme_chart = (
                    df[
                        [
                            "rurality_group",
                            "median_ihme_yll_rate",
                        ]
                    ]
                    .set_index("rurality_group")
                )

                st.bar_chart(ihme_chart)

            st.dataframe(
                df[
                    [
                        "rurality_group",
                        "counties",
                        "mean_places_prevalence",
                        "median_places_prevalence",
                        "mean_ihme_yll_rate",
                        "median_ihme_yll_rate",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

            st.caption(
                "This is a descriptive comparison. Differences across "
                "rurality groups do not establish causation."
            )

st.divider()

st.caption(
    "Rurality source: USDA Rural-Urban Continuum Codes (RUCC), 2023."
)
