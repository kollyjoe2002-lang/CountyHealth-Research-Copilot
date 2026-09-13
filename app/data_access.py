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
    Return the leading non-overlapping display-level causes
    for one county and year.

    Selected broad aggregate and nested subtype causes are
    suppressed from the default top-cause presentation, while
    explicit cause-specific analyses remain available elsewhere.

    Display ranks are recalculated after filtering so the
    presented ranking is sequential.
    """
    if limit < 1 or limit > 30:
        raise ValueError(
            "limit must be between 1 and 30"
        )

    return run_query(
        """
        WITH eligible AS (
            SELECT
                r.county_display_order,
                r.cause_id,
                r.cause_name,
                r.yll_rate,
                r.lower,
                r.upper,
                r.national_county_rank,
                r.national_display_order,
                r.counties_with_estimate,
                r.burden_percentile

            FROM analytics.vw_county_rankings_display AS r

            INNER JOIN analytics.dim_cause AS c
                ON r.cause_id = c.cause_id

            WHERE r.fips = ?
              AND r.year = ?
              AND c.include_in_top_cause_ranking = TRUE
        ),

        ranked AS (
            SELECT
                county_display_order,

                ROW_NUMBER() OVER (
                    ORDER BY
                        yll_rate DESC,
                        cause_name,
                        cause_id
                ) AS county_cause_rank,

                cause_id,
                cause_name,
                yll_rate,
                lower,
                upper,
                national_county_rank,
                national_display_order,
                counties_with_estimate,
                burden_percentile

            FROM eligible
        )

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

        FROM ranked

        ORDER BY county_cause_rank

        LIMIT ?
        """,
        [
            fips,
            year,
            limit,
        ],
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
@st.cache_data(show_spinner=False)
def get_county_ranking(
    cause_id: int,
    year: int,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Return current-county national rankings for one cause and year.

    Only current counties from the harmonized geography layer are
    included. Historical aliases, unavailable counties, state rows,
    and national rows are excluded.
    """
    sql = """
        SELECT
            national_display_order,
            national_county_rank,
            fips,
            location_name,
            cause_id,
            cause_name,
            year,
            yll_rate,
            lower,
            upper,
            counties_with_estimate,
            burden_percentile
        FROM analytics.vw_current_county_cause_rankings
        WHERE cause_id = ?
          AND year = ?
        ORDER BY national_display_order
    """

    parameters: list[Any] = [
        int(cause_id),
        int(year),
    ]

    dataframe = run_query(
        sql,
        parameters,
    )

    if limit is not None:
        limit_value = int(limit)

        if limit_value <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        dataframe = dataframe.head(
            limit_value
        ).copy()

    return dataframe


@st.cache_data(show_spinner=False)
def get_places_county_snapshot(
    fips: str,
    release_year: int,
) -> pd.DataFrame:
    """
    Return all CDC PLACES measures for one county and release.

    PLACES release year and underlying BRFSS measurement year are
    preserved separately. Estimates remain distinct from IHME burden
    metrics.
    """
    if len(str(fips)) != 5 or not str(fips).isdigit():
        raise ValueError(
            "fips must be a five-digit county FIPS code"
        )

    if release_year < 2020 or release_year > 2025:
        raise ValueError(
            "release_year must be between 2020 and 2025"
        )

    return run_query(
        """
        SELECT
            e.geoid AS fips,
            e.geography_name,
            e.state_abbr,
            e.state_name,
            e.release_year,
            e.measurement_year,
            e.measure_id,
            m.canonical_name AS measure_name,
            m.category,
            m.frequency,
            m.unit,
            v.measure_definition,
            v.data_source,
            e.total_population,
            e.total_pop_18plus,
            e.crude_prevalence,
            e.crude_ci_lower,
            e.crude_ci_upper,
            e.age_adjusted_prevalence,
            e.age_adjusted_ci_lower,
            e.age_adjusted_ci_upper,
            e.carry_forward,
            e.missing_reason,
            'CDC PLACES' AS dataset

        FROM places.estimates AS e

        INNER JOIN places.measures AS m
            ON e.measure_id = m.measure_id

        INNER JOIN places.measure_versions AS v
            ON e.release_year = v.release_year
           AND e.measure_id = v.measure_id

        WHERE e.geography_level = 'county'
          AND e.geoid = ?
          AND e.release_year = ?

        ORDER BY e.measure_id
        """,
        [
            str(fips),
            int(release_year),
        ],
    )


@st.cache_data(show_spinner=False)
def get_places_county_measure_trend(
    fips: str,
    measure_id: str,
) -> pd.DataFrame:
    """
    Return the PLACES history for one county and measure.

    The analytical time axis is the underlying BRFSS measurement year.
    Release year is retained separately for provenance. Carry-forward
    observations remain visible and are not treated as independent new
    measurement years.
    """
    normalized_fips = str(fips).strip()
    normalized_measure_id = str(measure_id).strip().upper()

    if len(normalized_fips) != 5 or not normalized_fips.isdigit():
        raise ValueError(
            "fips must be a five-digit county FIPS code"
        )

    if not normalized_measure_id:
        raise ValueError(
            "measure_id cannot be blank"
        )

    return run_query(
        """
        SELECT
            e.geoid AS fips,
            e.geography_name,
            e.state_abbr,
            e.state_name,
            e.release_year,
            e.measurement_year,
            e.measure_id,
            m.canonical_name AS measure_name,
            m.category,
            m.frequency,
            m.unit,
            v.measure_definition,
            v.data_source,
            e.crude_prevalence,
            e.crude_ci_lower,
            e.crude_ci_upper,
            e.age_adjusted_prevalence,
            e.age_adjusted_ci_lower,
            e.age_adjusted_ci_upper,
            e.carry_forward,
            e.missing_reason,
            'CDC PLACES' AS dataset

        FROM places.estimates AS e

        INNER JOIN places.measures AS m
            ON e.measure_id = m.measure_id

        INNER JOIN places.measure_versions AS v
            ON e.release_year = v.release_year
           AND e.measure_id = v.measure_id

        WHERE e.geography_level = 'county'
          AND e.geoid = ?
          AND e.measure_id = ?

        ORDER BY
            e.measurement_year,
            e.release_year
        """,
        [
            normalized_fips,
            normalized_measure_id,
        ],
    )


@st.cache_data(show_spinner=False)
def get_places_county_measure_ranking(
    measure_id: str,
    measurement_year: int,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Rank counties nationally for one CDC PLACES measure and
    underlying BRFSS measurement year.

    Rankings use age-adjusted prevalence. Release year is retained
    separately for provenance.
    """
    normalized_measure_id = str(measure_id).strip().upper()

    if not normalized_measure_id:
        raise ValueError(
            "measure_id cannot be blank"
        )

    year_value = int(measurement_year)

    if year_value < 2017 or year_value > 2023:
        raise ValueError(
            "measurement_year must be between 2017 and 2023"
        )

    sql = """
        WITH eligible AS (
            SELECT
                e.geoid AS fips,
                e.geography_name,
                e.state_abbr,
                e.state_name,
                e.release_year,
                e.measurement_year,
                e.measure_id,
                m.canonical_name AS measure_name,
                m.category,
                m.frequency,
                m.unit,
                e.crude_prevalence,
                e.crude_ci_lower,
                e.crude_ci_upper,
                e.age_adjusted_prevalence,
                e.age_adjusted_ci_lower,
                e.age_adjusted_ci_upper,
                e.carry_forward,
                e.missing_reason

            FROM places.estimates AS e

            INNER JOIN places.measures AS m
                ON e.measure_id = m.measure_id

WHERE e.geography_level = 'county'
AND e.measure_id = ?
  AND e.measurement_year = ?
  AND e.carry_forward = FALSE
  AND e.age_adjusted_prevalence IS NOT NULL
        ),

        ranked AS (
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY
                        age_adjusted_prevalence DESC,
                        geography_name,
                        fips
                ) AS national_rank,

                COUNT(*) OVER ()
                    AS counties_with_estimate,

                *

            FROM eligible
        )

        SELECT
            national_rank,
            counties_with_estimate,
            fips,
            geography_name,
            state_abbr,
            state_name,
            release_year,
            measurement_year,
            measure_id,
            measure_name,
            category,
            frequency,
            unit,
            crude_prevalence,
            crude_ci_lower,
            crude_ci_upper,
            age_adjusted_prevalence,
            age_adjusted_ci_lower,
            age_adjusted_ci_upper,
            carry_forward,
            missing_reason,
            'CDC PLACES' AS dataset

        FROM ranked

        ORDER BY national_rank
    """

    dataframe = run_query(
        sql,
        [
            normalized_measure_id,
            year_value,
        ],
    )

    if limit is not None:
        limit_value = int(limit)

        if limit_value <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        dataframe = dataframe.head(
            limit_value
        ).copy()

    return dataframe

@st.cache_data(show_spinner=False)
def get_places_rural_metro_comparison(
    measure_id: str,
    measurement_year: int,
) -> pd.DataFrame:
    """
    Compare canonical county-level CDC PLACES estimates between
    Metro and Nonmetro counties using USDA RUCC 2023.

    Analytical time is the underlying BRFSS measurement year.
    Carry-forward PLACES rows are excluded so each county contributes
    at most one canonical observation for the requested measurement year.

    Counties without a RUCC classification are excluded from the grouped
    comparison rather than assigned a rurality category.
    """

    measure_id = str(measure_id).strip().upper()

    if not measure_id:
        raise ValueError("measure_id must not be blank.")

    if not isinstance(measurement_year, int):
        raise ValueError("measurement_year must be an integer.")

    if measurement_year < 2017 or measurement_year > 2023:
        raise ValueError(
            "measurement_year must be between 2017 and 2023."
        )

    sql = """
        WITH canonical AS (
            SELECT
                e.geoid AS fips,
                e.geography_name,
                e.state_abbr,
                e.state_name,
                e.release_year,
                e.measurement_year,
                e.measure_id,
                m.canonical_name AS measure_name,
                m.category,
                m.unit,
                e.age_adjusted_prevalence,
                e.age_adjusted_ci_lower,
                e.age_adjusted_ci_upper
            FROM places.estimates AS e
            INNER JOIN places.measures AS m
                ON m.measure_id = e.measure_id
            WHERE e.geography_level = 'county'
              AND e.measure_id = ?
              AND e.measurement_year = ?
              AND e.carry_forward = FALSE
              AND e.age_adjusted_prevalence IS NOT NULL
        ),
        classified AS (
            SELECT
                c.*,
                r.rucc_code,
                r.metro_status,
                r.adjacency_status
            FROM canonical AS c
            INNER JOIN geography.rucc_2023 AS r
                ON r.fips = c.fips
            WHERE r.rucc_code IS NOT NULL
              AND r.metro_status IN ('Metro', 'Nonmetro')
        )
        SELECT
            measure_id,
            measure_name,
            category,
            unit,
            measurement_year,
            metro_status,
            COUNT(*) AS counties_with_estimate,
            AVG(age_adjusted_prevalence) AS mean_prevalence,
            MEDIAN(age_adjusted_prevalence) AS median_prevalence,
            MIN(age_adjusted_prevalence) AS minimum_prevalence,
            MAX(age_adjusted_prevalence) AS maximum_prevalence,
            'CDC PLACES + USDA RUCC 2023' AS dataset
        FROM classified
        GROUP BY
            measure_id,
            measure_name,
            category,
            unit,
            measurement_year,
            metro_status
        ORDER BY
            CASE metro_status
                WHEN 'Metro' THEN 1
                WHEN 'Nonmetro' THEN 2
                ELSE 3
            END
    """

    return run_query(
        sql,
        [measure_id, measurement_year],
    )

@st.cache_data(show_spinner=False)
def get_places_rucc_comparison(
    measure_id: str,
    measurement_year: int,
) -> pd.DataFrame:
    """
    Compare canonical county-level CDC PLACES estimates across
    USDA RUCC 2023 codes 1 through 9.

    Analytical time is the underlying BRFSS measurement year.
    Carry-forward PLACES rows are excluded so each county contributes
    at most one canonical observation for the requested measurement year.
    """

    measure_id = str(measure_id).strip().upper()

    if not measure_id:
        raise ValueError("measure_id must not be blank.")

    if not isinstance(measurement_year, int):
        raise ValueError("measurement_year must be an integer.")

    if measurement_year < 2017 or measurement_year > 2023:
        raise ValueError(
            "measurement_year must be between 2017 and 2023."
        )

    sql = """
        WITH canonical AS (
            SELECT
                e.geoid AS fips,
                e.measurement_year,
                e.measure_id,
                m.canonical_name AS measure_name,
                m.category,
                m.unit,
                e.age_adjusted_prevalence
            FROM places.estimates AS e
            INNER JOIN places.measures AS m
                ON m.measure_id = e.measure_id
            WHERE e.geography_level = 'county'
              AND e.measure_id = ?
              AND e.measurement_year = ?
              AND e.carry_forward = FALSE
              AND e.age_adjusted_prevalence IS NOT NULL
        ),
        classified AS (
            SELECT
                c.*,
                r.rucc_code,
                r.rucc_description,
                r.metro_status,
                r.adjacency_status
            FROM canonical AS c
            INNER JOIN geography.rucc_2023 AS r
                ON r.fips = c.fips
            WHERE r.rucc_code BETWEEN 1 AND 9
        )
        SELECT
            measure_id,
            measure_name,
            category,
            unit,
            measurement_year,
            rucc_code,
            rucc_description,
            metro_status,
            adjacency_status,
            COUNT(*) AS counties_with_estimate,
            AVG(age_adjusted_prevalence) AS mean_prevalence,
            MEDIAN(age_adjusted_prevalence) AS median_prevalence,
            MIN(age_adjusted_prevalence) AS minimum_prevalence,
            MAX(age_adjusted_prevalence) AS maximum_prevalence,
            'CDC PLACES + USDA RUCC 2023' AS dataset
        FROM classified
        GROUP BY
            measure_id,
            measure_name,
            category,
            unit,
            measurement_year,
            rucc_code,
            rucc_description,
            metro_status,
            adjacency_status
        ORDER BY rucc_code
    """

    return run_query(
        sql,
        [measure_id, measurement_year],
    )

@st.cache_data(show_spinner=False)
def get_places_rucc_adjacent_comparison(
    measure_id: str,
    measurement_year: int,
) -> pd.DataFrame:
    """
    Compare canonical CDC PLACES county estimates across three
    rurality groups:

    - Metro
    - Nonmetro adjacent to metro
    - Nonmetro not adjacent to metro

    Carry-forward PLACES rows are excluded so measurement-year
    analyses use only canonical observations.
    """

    measure_id = str(measure_id).strip().upper()

    if not measure_id:
        raise ValueError("measure_id must not be blank.")

    if not isinstance(measurement_year, int):
        raise ValueError("measurement_year must be an integer.")

    if measurement_year < 2017 or measurement_year > 2023:
        raise ValueError(
            "measurement_year must be between 2017 and 2023."
        )

    sql = """
        WITH canonical AS (
            SELECT
                e.geoid AS fips,
                e.measurement_year,
                e.measure_id,
                m.canonical_name AS measure_name,
                m.category,
                m.unit,
                e.age_adjusted_prevalence
            FROM places.estimates AS e
            INNER JOIN places.measures AS m
                ON m.measure_id = e.measure_id
            WHERE e.geography_level = 'county'
              AND e.measure_id = ?
              AND e.measurement_year = ?
              AND e.carry_forward = FALSE
              AND e.age_adjusted_prevalence IS NOT NULL
        ),
        classified AS (
            SELECT
                c.*,
                CASE
                    WHEN r.rucc_code BETWEEN 1 AND 3
                        THEN 'Metro'
                    WHEN r.rucc_code IN (4, 6, 8)
                        THEN 'Nonmetro adjacent'
                    WHEN r.rucc_code IN (5, 7, 9)
                        THEN 'Nonmetro not adjacent'
                    ELSE NULL
                END AS rurality_group
            FROM canonical AS c
            INNER JOIN geography.rucc_2023 AS r
                ON r.fips = c.fips
            WHERE r.rucc_code BETWEEN 1 AND 9
        )
        SELECT
            measure_id,
            measure_name,
            category,
            unit,
            measurement_year,
            rurality_group,
            COUNT(*) AS counties_with_estimate,
            AVG(age_adjusted_prevalence) AS mean_prevalence,
            MEDIAN(age_adjusted_prevalence) AS median_prevalence,
            MIN(age_adjusted_prevalence) AS minimum_prevalence,
            MAX(age_adjusted_prevalence) AS maximum_prevalence,
            'CDC PLACES + USDA RUCC 2023' AS dataset
        FROM classified
        WHERE rurality_group IS NOT NULL
        GROUP BY
            measure_id,
            measure_name,
            category,
            unit,
            measurement_year,
            rurality_group
        ORDER BY
            CASE rurality_group
                WHEN 'Metro' THEN 1
                WHEN 'Nonmetro adjacent' THEN 2
                WHEN 'Nonmetro not adjacent' THEN 3
                ELSE 4
            END
    """

    return run_query(
        sql,
        [measure_id, measurement_year],
    )
       
@st.cache_data(show_spinner=False)
def get_places_ihme_county_context(
    places_measure_id: str,
    places_measurement_year: int,
    ihme_cause_id: int,
    ihme_year: int,
) -> pd.DataFrame:
    """
    Build a county-level analytical bridge between CDC PLACES
    prevalence estimates and IHME YLL rates.

    PLACES observations use canonical measurement-year rows only
    (carry_forward = FALSE).

    IHME observations use:
      - YLLs (measure_id = 4)
      - Rate (metric_id = 3)
      - Both sexes (sex_id = 3)
      - Total race (race_id = 1)
      - Age 20+, age standardized (age_group_id = 38)

    The two evidence systems remain explicitly labeled and are joined
    only by county FIPS. No causal relationship is implied.
    """

    places_measure_id = str(places_measure_id).strip().upper()

    if not places_measure_id:
        raise ValueError("places_measure_id must not be blank.")

    if not isinstance(places_measurement_year, int):
        raise ValueError(
            "places_measurement_year must be an integer."
        )

    if not isinstance(ihme_cause_id, int):
        raise ValueError("ihme_cause_id must be an integer.")

    if not isinstance(ihme_year, int):
        raise ValueError("ihme_year must be an integer.")

    if places_measurement_year < 2017 or places_measurement_year > 2023:
        raise ValueError(
            "places_measurement_year must be between 2017 and 2023."
        )

    if ihme_year < 2000 or ihme_year > 2019:
        raise ValueError(
            "ihme_year must be between 2000 and 2019."
        )

    sql = """
        WITH places_context AS (
            SELECT
                e.geoid AS fips,
                e.measure_id AS places_measure_id,
                m.canonical_name AS places_measure_name,
                m.unit AS places_unit,
                e.measurement_year AS places_measurement_year,
                e.age_adjusted_prevalence AS places_age_adjusted_prevalence,
                e.age_adjusted_ci_lower AS places_lower,
                e.age_adjusted_ci_upper AS places_upper
            FROM places.estimates AS e
            INNER JOIN places.measures AS m
                ON m.measure_id = e.measure_id
            WHERE e.geography_level = 'county'
              AND e.measure_id = ?
              AND e.measurement_year = ?
              AND e.carry_forward = FALSE
              AND e.age_adjusted_prevalence IS NOT NULL
        ),
        ihme_context AS (
            SELECT
                fips,
                location_name AS ihme_location_name,
                cause_id AS ihme_cause_id,
                cause_name AS ihme_cause_name,
                year AS ihme_year,
                measure_name AS ihme_measure_name,
                metric_name AS ihme_metric_name,
                age_name AS ihme_age_name,
                sex_name AS ihme_sex_name,
                race_name AS ihme_race_name,
                val AS ihme_yll_rate,
                lower AS ihme_lower,
                upper AS ihme_upper
            FROM ihme.burden
            WHERE cause_id = ?
              AND year = ?
              AND measure_id = 4
              AND metric_id = 3
              AND sex_id = 3
              AND race_id = 1
              AND age_group_id = 38
              AND val IS NOT NULL
        )
        SELECT
            p.fips,

            p.places_measure_id,
            p.places_measure_name,
            p.places_unit,
            p.places_measurement_year,
            p.places_age_adjusted_prevalence,
            p.places_lower,
            p.places_upper,

            i.ihme_location_name,
            i.ihme_cause_id,
            i.ihme_cause_name,
            i.ihme_year,
            i.ihme_measure_name,
            i.ihme_metric_name,
            i.ihme_age_name,
            i.ihme_sex_name,
            i.ihme_race_name,
            i.ihme_yll_rate,
            i.ihme_lower,
            i.ihme_upper,

            r.rucc_code,
            r.metro_status,
            r.adjacency_status,

            'CDC PLACES' AS places_source,
            'IHME' AS ihme_source,
            'USDA RUCC 2023' AS rurality_source

        FROM places_context AS p
        INNER JOIN ihme_context AS i
            ON i.fips = p.fips
        LEFT JOIN geography.rucc_2023 AS r
            ON r.fips = p.fips
        ORDER BY p.fips
    """

    return run_query(
        sql,
        [
            places_measure_id,
            places_measurement_year,
            ihme_cause_id,
            ihme_year,
        ],
    )

@st.cache_data(show_spinner=False)
def get_places_ihme_rurality_comparison(
    places_measure_id: str,
    places_measurement_year: int,
    ihme_cause_id: int,
    ihme_year: int,
) -> pd.DataFrame:
    """
    Summarize matched CDC PLACES prevalence and IHME YLL-rate evidence
    across three USDA RUCC rurality groups:

    - Metro
    - Nonmetro adjacent
    - Nonmetro not adjacent

    The underlying county-level bridge preserves the two evidence systems
    separately and uses canonical PLACES measurement-year observations.
    """

    df = get_places_ihme_county_context(
        places_measure_id=places_measure_id,
        places_measurement_year=places_measurement_year,
        ihme_cause_id=ihme_cause_id,
        ihme_year=ihme_year,
    )

    df = df[df["rucc_code"].notna()].copy()

    def classify_rucc(code):
        code = int(code)

        if 1 <= code <= 3:
            return "Metro"
        if code in (4, 6, 8):
            return "Nonmetro adjacent"
        if code in (5, 7, 9):
            return "Nonmetro not adjacent"

        return None

    df["rurality_group"] = df["rucc_code"].map(classify_rucc)

    df = df[df["rurality_group"].notna()].copy()

    summary = (
        df.groupby(
            "rurality_group",
            observed=True,
        )
        .agg(
            counties=("fips", "nunique"),
            mean_places_prevalence=(
                "places_age_adjusted_prevalence",
                "mean",
            ),
            median_places_prevalence=(
                "places_age_adjusted_prevalence",
                "median",
            ),
            mean_ihme_yll_rate=(
                "ihme_yll_rate",
                "mean",
            ),
            median_ihme_yll_rate=(
                "ihme_yll_rate",
                "median",
            ),
        )
        .reset_index()
    )

    order = {
        "Metro": 1,
        "Nonmetro adjacent": 2,
        "Nonmetro not adjacent": 3,
    }

    summary["_order"] = summary["rurality_group"].map(order)

    summary = (
        summary.sort_values("_order")
        .drop(columns="_order")
        .reset_index(drop=True)
    )

    summary["places_measure_id"] = places_measure_id.upper()
    summary["places_measurement_year"] = places_measurement_year
    summary["ihme_cause_id"] = ihme_cause_id
    summary["ihme_year"] = ihme_year
    summary["dataset"] = "CDC PLACES + IHME + USDA RUCC 2023"

    return summary

@st.cache_data(show_spinner=False)
def get_places_ihme_positive_deviance(
    places_measure_id: str,
    places_measurement_year: int,
    ihme_cause_id: int,
    ihme_year: int,
    rurality_group: str | None = None,
    limit: int = 25,
) -> pd.DataFrame:
    """
    Identify counties with lower or higher IHME YLL burden than expected
    from CDC PLACES prevalence using a simple linear relationship.

    residual = observed_yll_rate - expected_yll_rate

    Negative residual:
        lower YLL burden than expected given prevalence.

    Positive residual:
        higher YLL burden than expected given prevalence.

    This is descriptive and does not imply causation.
    """

    if not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer.")

    df = get_places_ihme_county_context(
        places_measure_id=places_measure_id,
        places_measurement_year=places_measurement_year,
        ihme_cause_id=ihme_cause_id,
        ihme_year=ihme_year,
    ).copy()

    df = df[
        df["places_age_adjusted_prevalence"].notna()
        & df["ihme_yll_rate"].notna()
    ].copy()

    def classify_rucc(code):
        if pd.isna(code):
            return None

        code = int(code)

        if 1 <= code <= 3:
            return "Metro"
        if code in (4, 6, 8):
            return "Nonmetro adjacent"
        if code in (5, 7, 9):
            return "Nonmetro not adjacent"

        return None

    df["rurality_group"] = df["rucc_code"].map(classify_rucc)

    if rurality_group is not None:
        allowed = {
            "Metro",
            "Nonmetro adjacent",
            "Nonmetro not adjacent",
        }

        if rurality_group not in allowed:
            raise ValueError(
                "rurality_group must be one of: "
                "Metro, Nonmetro adjacent, "
                "Nonmetro not adjacent."
            )

        df = df[df["rurality_group"] == rurality_group].copy()

    if len(df) < 2:
        raise ValueError(
            "At least two matched counties are required."
        )

    x = df["places_age_adjusted_prevalence"].astype(float)
    y = df["ihme_yll_rate"].astype(float)

    x_mean = x.mean()
    y_mean = y.mean()

    denominator = ((x - x_mean) ** 2).sum()

    if denominator == 0:
        raise ValueError(
            "PLACES prevalence has no variation."
        )

    slope = (
        ((x - x_mean) * (y - y_mean)).sum()
        / denominator
    )

    intercept = y_mean - slope * x_mean

    df["expected_ihme_yll_rate"] = (
        intercept
        + slope * df["places_age_adjusted_prevalence"]
    )

    df["yll_residual"] = (
        df["ihme_yll_rate"]
        - df["expected_ihme_yll_rate"]
    )

    df["deviance_direction"] = df["yll_residual"].apply(
        lambda value: (
            "Lower burden than expected"
            if value < 0
            else "Higher burden than expected"
        )
    )

    df["model_slope"] = slope
    df["model_intercept"] = intercept

    columns = [
        "fips",
        "ihme_location_name",
        "places_measure_id",
        "places_measurement_year",
        "places_age_adjusted_prevalence",
        "ihme_cause_id",
        "ihme_cause_name",
        "ihme_year",
        "ihme_yll_rate",
        "expected_ihme_yll_rate",
        "yll_residual",
        "deviance_direction",
        "rucc_code",
        "rurality_group",
        "model_slope",
        "model_intercept",
    ]

    return (
        df[columns]
        .sort_values(
            "yll_residual",
            ascending=True,
        )
        .head(limit)
        .reset_index(drop=True)
    )