import streamlit as st

from data_access import (
    get_available_years,
    get_causes,
    get_counties,
)


@st.cache_data
def county_lookup():
    """Return the current county lookup table."""
    return get_counties()


@st.cache_data
def cause_lookup():
    """Return the available cause lookup table."""
    return get_causes()


@st.cache_data
def year_lookup():
    """Return the available analysis years."""
    return get_available_years()


def clear_lookup_cache() -> None:
    """Clear cached lookup tables."""
    county_lookup.clear()
    cause_lookup.clear()
    year_lookup.clear()