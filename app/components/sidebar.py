import streamlit as st


def sidebar() -> None:
    st.sidebar.title("CountyHealth")

    st.sidebar.success("Research Copilot")

    st.sidebar.markdown("---")

    st.sidebar.markdown(
        """
        **Dataset**

        IHME County Estimates

        **Coverage**

        2000–2019

        **Counties**

        3,124

        **Causes**

        30
        """
    )