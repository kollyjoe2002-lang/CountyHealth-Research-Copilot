from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"


class DatabaseError(RuntimeError):
    """Raised when the CountyHealth database cannot be queried."""


def _validate_database() -> None:
    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"DuckDB database not found at: {DB_FILE}"
        )


def run_query(
    sql: str,
    parameters: list[Any] | tuple[Any, ...] | None = None,
) -> pd.DataFrame:
    """
    Execute a read-only DuckDB query and return a pandas DataFrame.

    Parameters must be supplied separately rather than interpolated into
    SQL strings.
    """
    _validate_database()

    connection = None

    try:
        connection = duckdb.connect(
            database=str(DB_FILE),
            read_only=True,
        )

        if parameters is None:
            return connection.execute(sql).fetchdf()

        return connection.execute(sql, parameters).fetchdf()

    except duckdb.Error as exc:
        raise DatabaseError(
            f"Database query failed: {exc}"
        ) from exc

    finally:
        if connection is not None:
            connection.close()


@st.cache_data(show_spinner=False)
def get_counties() -> pd.DataFrame:
    """
    Return counties available for current-county analysis.
    """
    return run_query(
        """
        SELECT
            location_id,
            location_name,
            display_name,
            fips,
            state_fips,
            county_fips,
            has_burden_estimates,
            is_rankable

        FROM analytics.vw_county_display_lookup

        WHERE is_rankable = TRUE

        ORDER BY location_name, fips
        """
    )


@st.cache_data(show_spinner=False)
def get_available_years() -> list[int]:
    """
    Return available analytical years in descending order.
    """
    result = run_query(
        """
        SELECT DISTINCT year
        FROM analytics.vw_county_rankings_display
        ORDER BY year DESC
        """
    )

    return result["year"].astype(int).tolist()


@st.cache_data(show_spinner=False)
def get_causes() -> pd.DataFrame:
    """
    Return causes included in the current ranking layer.
    """
    return run_query(
        """
        SELECT DISTINCT
            cause_id,
            cause_name

        FROM analytics.vw_county_rankings_display

        ORDER BY cause_name
        """
    )


@st.cache_data(show_spinner=False)
def get_top_causes(
    fips: str,
    year: int,
    limit: int = 10,
) -> pd.DataFrame:
    """
    Return the leading causes for one county and year.
    """
    if limit < 1 or limit > 30:
        raise ValueError("limit must be between 1 and 30")

    return run_query(
        """
        SELECT
            county_display_order,
            county_cause_rank,
            cause_id,
            cause_name,
            yll_rate,
            lower,
            upper,
            national_county_rank,
            national_display_order,
            counties_with_estimate,
            burden_percentile

        FROM analytics.vw_county_rankings_display

        WHERE fips = ?
          AND year = ?

        ORDER BY county_display_order

        LIMIT ?
        """,
        [fips, year, limit],
    )


@st.cache_data(show_spinner=False)
def get_cause_trend(
    fips: str,
    cause_id: int,
) -> pd.DataFrame:
    """
    Return the complete annual trend for a county and cause.
    """
    return run_query(
        """
        SELECT
            year,
            cause_id,
            cause_name,
            yll_rate,
            lower,
            upper,
            county_cause_rank,
            national_county_rank,
            national_display_order,
            counties_with_estimate,
            burden_percentile

        FROM analytics.vw_county_rankings_display

        WHERE fips = ?
          AND cause_id = ?

        ORDER BY year
        """,
        [fips, cause_id],
    )


@st.cache_data(show_spinner=False)
def get_county_cause_record(
    fips: str,
    year: int,
    cause_id: int,
) -> pd.DataFrame:
    """
    Return one county-year-cause observation.
    """
    return run_query(
        """
        SELECT
            location_id,
            location_name,
            fips,
            year,
            cause_id,
            cause_name,
            yll_rate,
            lower,
            upper,
            county_cause_rank,
            national_county_rank,
            national_display_order,
            counties_with_estimate,
            burden_percentile

        FROM analytics.vw_county_rankings_display

        WHERE fips = ?
          AND year = ?
          AND cause_id = ?
        """,
        [fips, year, cause_id],
    )


@st.cache_data(show_spinner=False)
def get_long_term_change(
    fips: str,
) -> pd.DataFrame:
    """
    Return cause-specific change between 2000 and 2019.
    """
    return run_query(
        """
        SELECT
            cause_id,
            cause_name,
            yll_rate_2000,
            yll_rate_2019,
            absolute_change_2000_2019,
            percent_change_2000_2019,
            trend_direction

        FROM analytics.vw_current_county_cause_change_2000_2019

        WHERE fips = ?

        ORDER BY percent_change_2000_2019 DESC NULLS LAST
        """,
        [fips],
    )


@st.cache_data(show_spinner=False)
def get_bmi_summary(
    fips: str,
    year: int,
) -> pd.DataFrame:
    """
    Return all available BMI indicators for one county and year.

    SELECT * is temporary because the exact BMI summary columns should
    be inspected before the County Profile interface formats them.
    """
    return run_query(
        """
        SELECT *
        FROM analytics.vw_county_bmi_summary
        WHERE fips = ?
          AND year = ?
        """,
        [fips, year],
    )


@st.cache_data(show_spinner=False)
def get_county_status(fips: str) -> pd.DataFrame:
    """
    Return geography and analytical status for one source FIPS code.
    """
    return run_query(
        """
        SELECT
            source_location_id,
            source_location_name,
            source_fips,
            canonical_location_id,
            canonical_location_name,
            canonical_fips,
            county_status,
            has_burden_estimates,
            is_rankable,
            include_in_current_county_selector,
            display_name

        FROM analytics.dim_county_status

        WHERE source_fips = ?
        """,
        [fips],
    )


def clear_data_cache() -> None:
    """
    Clear cached query results after rebuilding database objects.
    """
    st.cache_data.clear()

# ============================================================================
# DISPARITY FINDER
# ============================================================================

DISPARITY_DIMENSIONS = {
    "Race / ethnicity": {
        "id_column": "race_id",
        "name_column": "race_name",
        "fixed_filters": {
            "sex_id": 3,         # Both sexes
            "age_group_id": 38,  # Age 20+, age standardized
        },
    },
    "Sex": {
        "id_column": "sex_id",
        "name_column": "sex_name",
        "fixed_filters": {
            "race_id": 1,        # Total population
            "age_group_id": 38,  # Age 20+, age standardized
        },
    },
    "Age group": {
        "id_column": "age_group_id",
        "name_column": "age_name",
        "fixed_filters": {
            "race_id": 1,  # Total population
            "sex_id": 3,   # Both sexes
        },
    },
}


@st.cache_data(show_spinner=False)
def get_disparity_causes() -> pd.DataFrame:
    """
    Return all causes available for disparity analysis.

    The burden table contains high-BMI-attributable YLL rates.
    """
    sql = """
        SELECT DISTINCT
            cause_id,
            cause_name
        FROM ihme.burden
        WHERE cause_id IS NOT NULL
          AND cause_name IS NOT NULL
          AND measure_id = 4
          AND metric_id = 3
        ORDER BY cause_name
    """

    return run_query(sql)


@st.cache_data(show_spinner=False)
def get_disparity_years() -> list[int]:
    """
    Return available burden years in descending order.
    """
    sql = """
        SELECT DISTINCT
            year
        FROM ihme.burden
        WHERE year IS NOT NULL
          AND measure_id = 4
          AND metric_id = 3
        ORDER BY year DESC
    """

    dataframe = run_query(sql)

    if dataframe.empty:
        return []

    return dataframe["year"].astype(int).tolist()


@st.cache_data(show_spinner=False)
def get_disparity_groups(
    dimension: str,
) -> pd.DataFrame:
    """
    Return valid demographic groups for a selected comparison dimension.

    The total population category is excluded from race/ethnicity
    comparisons because it overlaps with every race/ethnicity subgroup.
    """
    if dimension not in DISPARITY_DIMENSIONS:
        raise ValueError(
            f"Unsupported disparity dimension: {dimension}"
        )

    definition = DISPARITY_DIMENSIONS[dimension]

    id_column = definition["id_column"]
    name_column = definition["name_column"]

    additional_condition = ""

    if dimension == "Race / ethnicity":
        additional_condition = "AND race_id <> 1"

    sql = f"""
        SELECT DISTINCT
            {id_column} AS group_id,
            {name_column} AS group_name
        FROM ihme.burden
        WHERE {id_column} IS NOT NULL
          AND {name_column} IS NOT NULL
          AND measure_id = 4
          AND metric_id = 3
          {additional_condition}
        ORDER BY group_id
    """

    return run_query(sql)

@st.cache_data(show_spinner=False)
def get_county_disparity_ranking(
    cause_id: int,
    year: int,
    dimension: str,
    group_a_id: int,
    group_b_id: int,
) -> pd.DataFrame:
    """
    Compare two demographic groups across current U.S. counties.

    The signed gap is calculated as:

        Group A YLL rate - Group B YLL rate

    Only current counties in analytics.vw_current_county_lookup are
    included. Historical aliases, state-level rows, national rows, and
    counties without current analytical eligibility are excluded.

    Only counties with non-null estimates for both groups are returned.
    """
    if dimension not in DISPARITY_DIMENSIONS:
        raise ValueError(
            f"Unsupported disparity dimension: {dimension}"
        )

    if int(group_a_id) == int(group_b_id):
        raise ValueError(
            "Group A and Group B must be different."
        )

    definition = DISPARITY_DIMENSIONS[dimension]

    id_column = definition["id_column"]
    fixed_filters = definition["fixed_filters"]

    fixed_conditions: list[str] = []
    fixed_parameters: list[int] = []

    for column, value in fixed_filters.items():
        fixed_conditions.append(
            f"b.{column} = ?"
        )
        fixed_parameters.append(
            int(value)
        )

    fixed_where = "\n              AND ".join(
        fixed_conditions
    )

    sql = f"""
        WITH county_values AS (
            SELECT
                g.fips,
                g.location_name,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.val
                    END
                ) AS group_a_value,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.lower
                    END
                ) AS group_a_lower,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.upper
                    END
                ) AS group_a_upper,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.val
                    END
                ) AS group_b_value,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.lower
                    END
                ) AS group_b_lower,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.upper
                    END
                ) AS group_b_upper

            FROM ihme.burden AS b

            INNER JOIN analytics.vw_current_county_lookup AS g
                ON CAST(b.fips AS VARCHAR) = g.fips

            WHERE b.measure_id = 4
              AND b.metric_id = 3
              AND b.cause_id = ?
              AND b.year = ?
              AND {fixed_where}
              AND b.{id_column} IN (?, ?)
              AND b.val IS NOT NULL

            GROUP BY
                g.fips,
                g.location_name
        )

        SELECT
            fips,
            location_name,

            group_a_value,
            group_a_lower,
            group_a_upper,

            group_b_value,
            group_b_lower,
            group_b_upper,

            group_a_value - group_b_value
                AS absolute_gap,

            ABS(group_a_value - group_b_value)
                AS absolute_gap_magnitude,

            CASE
                WHEN group_b_value IS NULL
                  OR group_b_value = 0
                THEN NULL

                ELSE (
                    (
                        group_a_value - group_b_value
                    ) / group_b_value
                ) * 100
            END AS relative_gap_percent

        FROM county_values

        WHERE group_a_value IS NOT NULL
          AND group_b_value IS NOT NULL

        ORDER BY
            absolute_gap DESC,
            location_name
    """

    parameters: list[Any] = [
        int(group_a_id),
        int(group_a_id),
        int(group_a_id),

        int(group_b_id),
        int(group_b_id),
        int(group_b_id),

        int(cause_id),
        int(year),

        *fixed_parameters,

        int(group_a_id),
        int(group_b_id),
    ]

    return run_query(
        sql,
        parameters,
    )


@st.cache_data(show_spinner=False)
def get_county_disparity_trend(
    fips: str,
    cause_id: int,
    dimension: str,
    group_a_id: int,
    group_b_id: int,
) -> pd.DataFrame:
    """
    Return an annual disparity trend for one current U.S. county.

    The county must exist in analytics.vw_current_county_lookup.
    Historical aliases, state rows, national rows, and non-current
    geographies are excluded.
    """
    if dimension not in DISPARITY_DIMENSIONS:
        raise ValueError(
            f"Unsupported disparity dimension: {dimension}"
        )

    if int(group_a_id) == int(group_b_id):
        raise ValueError(
            "Group A and Group B must be different."
        )

    definition = DISPARITY_DIMENSIONS[dimension]

    id_column = definition["id_column"]
    fixed_filters = definition["fixed_filters"]

    fixed_conditions: list[str] = []
    fixed_parameters: list[int] = []

    for column, value in fixed_filters.items():
        fixed_conditions.append(
            f"b.{column} = ?"
        )
        fixed_parameters.append(
            int(value)
        )

    fixed_where = "\n              AND ".join(
        fixed_conditions
    )

    normalized_fips = str(fips).zfill(5)

    sql = f"""
        WITH annual_values AS (
            SELECT
                b.year,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.val
                    END
                ) AS group_a_value,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.lower
                    END
                ) AS group_a_lower,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.upper
                    END
                ) AS group_a_upper,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.val
                    END
                ) AS group_b_value,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.lower
                    END
                ) AS group_b_lower,

                MAX(
                    CASE
                        WHEN b.{id_column} = ?
                        THEN b.upper
                    END
                ) AS group_b_upper

            FROM ihme.burden AS b

            INNER JOIN analytics.vw_current_county_lookup AS g
                ON CAST(b.fips AS VARCHAR) = g.fips

            WHERE b.measure_id = 4
              AND b.metric_id = 3
              AND b.cause_id = ?
              AND g.fips = ?
              AND {fixed_where}
              AND b.{id_column} IN (?, ?)
              AND b.val IS NOT NULL

            GROUP BY
                b.year
        )

        SELECT
            year,

            group_a_value,
            group_a_lower,
            group_a_upper,

            group_b_value,
            group_b_lower,
            group_b_upper,

            group_a_value - group_b_value
                AS absolute_gap,

            ABS(group_a_value - group_b_value)
                AS absolute_gap_magnitude,

            CASE
                WHEN group_b_value IS NULL
                  OR group_b_value = 0
                THEN NULL

                ELSE (
                    (
                        group_a_value - group_b_value
                    ) / group_b_value
                ) * 100
            END AS relative_gap_percent

        FROM annual_values

        WHERE group_a_value IS NOT NULL
          AND group_b_value IS NOT NULL

        ORDER BY year
    """

    parameters: list[Any] = [
        int(group_a_id),
        int(group_a_id),
        int(group_a_id),

        int(group_b_id),
        int(group_b_id),
        int(group_b_id),

        int(cause_id),
        normalized_fips,

        *fixed_parameters,

        int(group_a_id),
        int(group_b_id),
    ]

    return run_query(
        sql,
        parameters,
    )