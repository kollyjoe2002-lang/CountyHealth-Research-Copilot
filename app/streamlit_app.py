from pathlib import Path
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


st.set_page_config(
    page_title="EpiCounty",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    st.title("EpiCounty")

    st.markdown(
        """
        **EpiCounty** is a county-level public health research platform for
        exploring disease burden, prevalence, demographic disparities,
        rural-urban differences, and validated cross-source patterns across
        the United States.

        The platform integrates **IHME county disease-burden estimates**,
        **CDC PLACES prevalence estimates**, and **USDA Rural-Urban Continuum
        Codes (RUCC)** within a validated analytical workflow.
        """
    )

    st.divider()

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            label="IHME Coverage",
            value="2000-2019",
        )

    with c2:
        st.metric(
            label="CDC PLACES",
            value="Through 2023",
        )

    with c3:
        st.metric(
            label="Rurality",
            value="RUCC 2023",
        )

    st.divider()

    st.subheader("Research Capabilities")

    left, right = st.columns(2)

    with left:
        st.markdown(
            """
            **County and disease analysis**
            - County health profiles
            - Disease-burden trends
            - County rankings
            - Race, ethnicity, sex, and age disparities

            **CDC PLACES**
            - County prevalence snapshots
            - Prevalence trends
            - County rankings
            """
        )

    with right:
        st.markdown(
            """
            **Rural Health**
            - Metropolitan vs nonmetropolitan comparisons
            - RUCC rurality analysis
            - Adjacent vs non-adjacent rural comparisons

            **PLACES + IHME**
            - Validated county trend comparisons
            - Rurality comparisons
            - Demographic disparity context
            """
        )

    st.info(
        "Use the AI Research Assistant to ask supported natural-language "
        "research questions. EpiCounty keeps CDC PLACES prevalence and IHME "
        "disease-burden measures distinct and does not treat descriptive "
        "cross-source associations as causal."
    )

    st.divider()

    st.subheader("Available Pages")

    st.markdown(
        """
        - **County Profile**
        - **Trend Finder**
        - **Disparity Finder**
        - **Research Report / AI Research Assistant**
        - **Beta Health**
        """
    )

    st.divider()

    st.caption(
        "EpiCounty V1.2 ? DuckDB ? Streamlit ? IHME ? CDC PLACES ? USDA RUCC"
    )

if __name__ == "__main__":
    main()