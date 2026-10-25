"""Streamlit rendering primitives shared by the direct-data pages."""
import streamlit as st
from app.research_catalogs import RURALITY_LABELS


def selector(label, options, *, key, formatter=str):
    """No automatic first match, including after a dependency changes."""
    options = tuple(options)
    if st.session_state.get(key) not in options:
        st.session_state[key] = None
    return st.selectbox(label, options, index=None, format_func=formatter, key=key,
        placeholder='Search and choose…', disabled=not options)


def rural_labels(frame):
    display = frame.copy()
    for column in ('rurality_group', 'metro_status'):
        if column in display:
            display[column] = display[column].map(lambda v: RURALITY_LABELS.get(v, v))
    return display


def show_provenance(metadata):
    with st.expander('Provenance and technical identifiers'):
        st.json(metadata)


def infrastructure_message():
    st.error('The analytical database or required service is unavailable. This infrastructure problem does not establish that scientific data are absent.')
