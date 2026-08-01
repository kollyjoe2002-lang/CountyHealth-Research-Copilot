CREATE SCHEMA IF NOT EXISTS analytics;

-- =====================================================================
-- LOCATION ALIAS DIMENSION
--
-- Maps confirmed historical county identifiers to the preferred modern
-- county identifier used by dashboards and current-county comparisons.
--
-- Raw IHME identifiers remain unchanged.
-- =====================================================================

CREATE OR REPLACE TABLE analytics.dim_location_alias (
    source_fips VARCHAR PRIMARY KEY,
    canonical_fips VARCHAR NOT NULL,
    relationship_type VARCHAR NOT NULL,
    effective_year INTEGER,
    source_note VARCHAR,
    is_confirmed BOOLEAN NOT NULL
);

INSERT INTO analytics.dim_location_alias VALUES

(
    '46113',
    '46102',
    'renamed_and_recoded',
    2015,
    'Shannon County renamed Oglala Lakota County; county code changed from 113 to 102.',
    TRUE
),

(
    '02270',
    '02158',
    'renamed_and_recoded',
    2015,
    'Wade Hampton Census Area renamed Kusilvak Census Area; county code changed from 270 to 158.',
    TRUE
),

(
    '12025',
    '12086',
    'renamed_and_recoded',
    1997,
    'Dade County renamed Miami-Dade County; county code changed from 025 to 086.',
    TRUE
);


-- =====================================================================
-- COUNTY STATUS DIMENSION
--
-- One row for every source county geography.
--
-- source_*:
--     Original IHME geography.
--
-- canonical_*:
--     Preferred geography for current display.
--
-- has_burden_estimates:
--     At least one non-null value in county_burden_summary.
--
-- is_rankable:
--     Has at least one eligible non-null cause estimate.
--
-- county_status:
--     current
--     historical_alias
--     estimate_unavailable
-- =====================================================================

CREATE OR REPLACE TABLE analytics.dim_county_status AS

WITH burden_coverage AS (
    SELECT
        fips,

        COUNT(*) AS burden_rows,

        COUNT(value) AS non_null_burden_rows,

        COUNT(DISTINCT CASE
            WHEN value IS NOT NULL THEN year
        END) AS years_with_burden_estimate,

        COUNT(DISTINCT CASE
            WHEN value IS NOT NULL THEN cause_id
        END) AS causes_with_burden_estimate

    FROM analytics.county_burden_summary

    GROUP BY fips
),

ranking_coverage AS (
    SELECT
        fips,
        COUNT(*) AS ranking_rows,
        COUNT(DISTINCT year) AS ranking_years,
        COUNT(DISTINCT cause_id) AS ranking_causes

    FROM analytics.county_cause_rankings

    GROUP BY fips
),

county_geography AS (
    SELECT
        g.location_id,
        g.location_name AS source_location_name,
        g.fips AS source_fips,
        g.state_fips AS source_state_fips,
        g.county_fips AS source_county_fips,

        COALESCE(
            a.canonical_fips,
            g.fips
        ) AS canonical_fips,

        a.relationship_type,
        a.effective_year,
        a.source_note,
        COALESCE(a.is_confirmed, FALSE) AS is_confirmed_alias

    FROM analytics.dim_geography AS g

    LEFT JOIN analytics.dim_location_alias AS a
        ON g.fips = a.source_fips

    WHERE g.geography_level = 'COUNTY'
),

canonical_geography AS (
    SELECT
        c.*,

        COALESCE(
            canonical.location_id,
            c.location_id
        ) AS canonical_location_id,

        COALESCE(
            canonical.location_name,
            c.source_location_name
        ) AS canonical_location_name,

        COALESCE(
            canonical.state_fips,
            c.source_state_fips
        ) AS canonical_state_fips,

        COALESCE(
            canonical.county_fips,
            c.source_county_fips
        ) AS canonical_county_fips

    FROM county_geography AS c

    LEFT JOIN analytics.dim_geography AS canonical
        ON c.canonical_fips = canonical.fips
       AND canonical.geography_level = 'COUNTY'
)

SELECT
    g.location_id AS source_location_id,
    g.source_location_name,
    g.source_fips,
    g.source_state_fips,
    g.source_county_fips,

    g.canonical_location_id,
    g.canonical_location_name,
    g.canonical_fips,
    g.canonical_state_fips,
    g.canonical_county_fips,

    g.relationship_type,
    g.effective_year,
    g.source_note,
    g.is_confirmed_alias,

    COALESCE(b.burden_rows, 0) AS burden_rows,
    COALESCE(b.non_null_burden_rows, 0) AS non_null_burden_rows,
    COALESCE(b.years_with_burden_estimate, 0)
        AS years_with_burden_estimate,
    COALESCE(b.causes_with_burden_estimate, 0)
        AS causes_with_burden_estimate,

    COALESCE(r.ranking_rows, 0) AS ranking_rows,
    COALESCE(r.ranking_years, 0) AS ranking_years,
    COALESCE(r.ranking_causes, 0) AS ranking_causes,

    COALESCE(b.non_null_burden_rows, 0) > 0
        AS has_burden_estimates,

    COALESCE(r.ranking_rows, 0) > 0
        AS is_rankable,

    CASE
        WHEN g.is_confirmed_alias
            THEN 'historical_alias'

        WHEN COALESCE(b.non_null_burden_rows, 0) = 0
            THEN 'estimate_unavailable'

        ELSE 'current'
    END AS county_status,

    CASE
        WHEN g.is_confirmed_alias
            THEN FALSE

        WHEN COALESCE(r.ranking_rows, 0) = 0
            THEN FALSE

        ELSE TRUE
    END AS include_in_current_county_selector,

    CASE
        WHEN g.is_confirmed_alias
            THEN
                g.source_location_name
                || ' — historical name for '
                || g.canonical_location_name

        WHEN COALESCE(b.non_null_burden_rows, 0) = 0
            THEN
                g.source_location_name
                || ' — estimate unavailable'

        ELSE g.canonical_location_name
    END AS display_name

FROM canonical_geography AS g

LEFT JOIN burden_coverage AS b
    ON g.source_fips = b.fips

LEFT JOIN ranking_coverage AS r
    ON g.source_fips = r.fips;


-- =====================================================================
-- CURRENT COUNTY LOOKUP
--
-- Default county selector for dashboards.
--
-- Historical aliases and counties without usable ranking estimates are
-- excluded.
-- =====================================================================

CREATE OR REPLACE VIEW analytics.vw_current_county_lookup AS

SELECT
    canonical_location_id AS location_id,
    canonical_location_name AS location_name,
    canonical_fips AS fips,
    canonical_state_fips AS state_fips,
    canonical_county_fips AS county_fips,
    display_name,
    has_burden_estimates,
    is_rankable

FROM analytics.dim_county_status

WHERE include_in_current_county_selector = TRUE;


-- =====================================================================
-- COMPLETE COUNTY LOOKUP
--
-- Includes current counties, historical aliases, and counties whose
-- estimates are unavailable.
-- =====================================================================

CREATE OR REPLACE VIEW analytics.vw_all_county_lookup AS

SELECT
    source_location_id,
    source_location_name,
    source_fips,
    source_state_fips,
    source_county_fips,

    canonical_location_id,
    canonical_location_name,
    canonical_fips,
    canonical_state_fips,
    canonical_county_fips,

    county_status,
    relationship_type,
    effective_year,
    has_burden_estimates,
    is_rankable,
    include_in_current_county_selector,
    display_name

FROM analytics.dim_county_status;


-- =====================================================================
-- CANONICALIZED RANKINGS VIEW
--
-- Historical aliases are excluded from current cross-county rankings.
--
-- No estimates are aggregated or rewritten.
-- =====================================================================

CREATE OR REPLACE VIEW analytics.vw_current_county_cause_rankings AS

SELECT
    r.location_id,
    r.location_name,
    r.fips,
    r.state_fips,
    r.county_fips,
    r.year,
    r.cause_id,
    r.cause_name,
    r.yll_rate,
    r.lower,
    r.upper,
    r.county_cause_rank,
    r.county_display_order,
    r.national_county_rank,
    r.counties_with_estimate,
    r.burden_percentile

FROM analytics.county_cause_rankings AS r

INNER JOIN analytics.dim_county_status AS s
    ON r.fips = s.source_fips

WHERE s.include_in_current_county_selector = TRUE;


ANALYZE analytics.dim_county_status;