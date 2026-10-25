import streamlit as st

from data_access import (
    get_available_years,
    get_causes,
    get_counties,
)


@st.cache_data
def county_lookup():
    """Return the current county lookup table."""
    return _read_lookup(get_counties)


@st.cache_data
def cause_lookup():
    """Return the available cause lookup table."""
    return _read_lookup(get_causes)


@st.cache_data
def year_lookup():
    """Return the available analysis years."""
    return _read_lookup(get_available_years)


def clear_lookup_cache() -> None:
    """Clear cached lookup tables."""
    county_lookup.clear()
    cause_lookup.clear()
    year_lookup.clear()

def _read_lookup(reader):
    try:
        return reader()
    except Exception:
        st.error("A required analytical database/service is unavailable. This infrastructure problem does not establish scientific data absence.")
        st.stop()
