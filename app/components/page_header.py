import streamlit as st


def page_header(title: str, description: str) -> None:
    st.title(title)
    st.write(description)
    st.divider()