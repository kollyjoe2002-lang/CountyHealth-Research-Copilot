from pathlib import Path
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


st.set_page_config(
    page_title="CountyHealth Research Copilot",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    st.title("🏥 CountyHealth Research Copilot")

    st.markdown(
        """
        Welcome to the **CountyHealth Research Copilot**.

        This research application allows investigators to explore
        county-level obesity prevalence and high-BMI-attributable
        disease burden across the United States using validated
        IHME county estimates (2000–2019).
        """
    )

    st.divider()

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            label="Current Counties",
            value="3,124",
        )

    with c2:
        st.metric(
            label="Years",
            value="20",
        )

    with c3:
        st.metric(
            label="Causes",
            value="30",
        )

    st.divider()

    st.subheader("Available Pages")

    st.markdown(
        """
        - **County Profile**
        - **Trend Finder**
        - **Disparity Finder**
        - **Research Report**
        """
    )

    st.info(
        "Select a page from the left navigation once additional pages are added."
    )

    st.divider()

    st.caption(
        "Version 0.1 • Built with DuckDB, Streamlit and IHME county-level data."
    )


if __name__ == "__main__":
    main()