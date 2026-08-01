CREATE SCHEMA IF NOT EXISTS analytics;

-- =====================================================================
-- COUNTY CAUSE RANKINGS
--
-- One row per county, year, and ranking-eligible cause.
--
-- county_cause_rank:
--     Rank of the cause within a county and year.
--
-- national_county_rank:
--     Rank of the county among all counties for that cause and year.
--     Rank 1 means the highest YLL rate.
--
-- burden_percentile:
--     Percentile of the county's YLL rate among counties.
--     Higher values indicate higher burden.
-- =====================================================================

CREATE OR REPLACE TABLE analytics.county_cause_rankings AS

WITH eligible_causes AS (
    SELECT
        cause_id,
        cause_name
    FROM analytics.dim_cause
    WHERE include_in_default_ranking = TRUE
),

eligible_estimates AS (
    SELECT
        b.location_id,
        b.location_name,
        b.fips,
        b.state_fips,
        b.county_fips,
        b.year,
        b.cause_id,
        b.cause_name,
        b.value AS yll_rate,
        b.lower,
        b.upper
    FROM analytics.county_burden_summary AS b

    INNER JOIN eligible_causes AS c
        ON b.cause_id = c.cause_id

    WHERE b.value IS NOT NULL
),

ranked AS (
    SELECT
        location_id,
        location_name,
        fips,
        state_fips,
        county_fips,
        year,
        cause_id,
        cause_name,
        yll_rate,
        lower,
        upper,

        RANK() OVER (
            PARTITION BY fips, year
            ORDER BY yll_rate DESC
        ) AS county_cause_rank,

        ROW_NUMBER() OVER (
            PARTITION BY fips, year
            ORDER BY yll_rate DESC, cause_name, cause_id
        ) AS county_display_order,

        RANK() OVER (
            PARTITION BY cause_id, year
            ORDER BY yll_rate DESC
        ) AS national_county_rank,

        COUNT(*) OVER (
            PARTITION BY cause_id, year
        ) AS counties_with_estimate,

        ROUND(
            100.0 * PERCENT_RANK() OVER (
                PARTITION BY cause_id, year
                ORDER BY yll_rate
            ),
            2
        ) AS burden_percentile

    FROM eligible_estimates
)

SELECT *
FROM ranked;


-- =====================================================================
-- TOP 10 CAUSES BY COUNTY AND YEAR
-- =====================================================================

CREATE OR REPLACE VIEW analytics.vw_county_top_causes AS

SELECT
    location_id,
    location_name,
    fips,
    state_fips,
    county_fips,
    year,
    cause_id,
    cause_name,
    yll_rate,
    lower,
    upper,
    county_cause_rank,
    county_display_order,
    national_county_rank,
    counties_with_estimate,
    burden_percentile

FROM analytics.county_cause_rankings

WHERE county_display_order <= 10;


-- =====================================================================
-- ANNUAL COUNTY-CAUSE TRENDS
--
-- LAG is calculated before rows are exposed to the application.
-- The first available year for each county-cause combination will have
-- null previous-year and change values.
-- =====================================================================

CREATE OR REPLACE VIEW analytics.vw_county_cause_trends AS

SELECT
    location_id,
    location_name,
    fips,
    state_fips,
    county_fips,
    year,
    cause_id,
    cause_name,
    yll_rate,
    lower,
    upper,
    county_cause_rank,
    national_county_rank,
    burden_percentile,

    LAG(yll_rate) OVER (
        PARTITION BY fips, cause_id
        ORDER BY year
    ) AS previous_year_rate,

    yll_rate
        - LAG(yll_rate) OVER (
            PARTITION BY fips, cause_id
            ORDER BY year
        ) AS annual_absolute_change,

    CASE
        WHEN LAG(yll_rate) OVER (
            PARTITION BY fips, cause_id
            ORDER BY year
        ) IS NULL
        THEN NULL

        WHEN LAG(yll_rate) OVER (
            PARTITION BY fips, cause_id
            ORDER BY year
        ) = 0
        THEN NULL

        ELSE ROUND(
            100.0 * (
                yll_rate
                - LAG(yll_rate) OVER (
                    PARTITION BY fips, cause_id
                    ORDER BY year
                )
            )
            / LAG(yll_rate) OVER (
                PARTITION BY fips, cause_id
                ORDER BY year
            ),
            2
        )
    END AS annual_percent_change

FROM analytics.county_cause_rankings;


-- =====================================================================
-- LONG-TERM CHANGE: 2000 TO 2019
-- =====================================================================

CREATE OR REPLACE VIEW analytics.vw_county_cause_change_2000_2019 AS

WITH endpoints AS (
    SELECT
        location_id,
        location_name,
        fips,
        state_fips,
        county_fips,
        cause_id,
        cause_name,

        MAX(CASE
            WHEN year = 2000 THEN yll_rate
        END) AS yll_rate_2000,

        MAX(CASE
            WHEN year = 2019 THEN yll_rate
        END) AS yll_rate_2019

    FROM analytics.county_cause_rankings

    WHERE year IN (2000, 2019)

    GROUP BY
        location_id,
        location_name,
        fips,
        state_fips,
        county_fips,
        cause_id,
        cause_name
)

SELECT
    location_id,
    location_name,
    fips,
    state_fips,
    county_fips,
    cause_id,
    cause_name,
    yll_rate_2000,
    yll_rate_2019,

    yll_rate_2019 - yll_rate_2000
        AS absolute_change_2000_2019,

    CASE
        WHEN yll_rate_2000 IS NULL
          OR yll_rate_2019 IS NULL
          OR yll_rate_2000 = 0
        THEN NULL

        ELSE ROUND(
            100.0
            * (yll_rate_2019 - yll_rate_2000)
            / yll_rate_2000,
            2
        )
    END AS percent_change_2000_2019,

    CASE
        WHEN yll_rate_2000 IS NULL
          OR yll_rate_2019 IS NULL
        THEN 'Incomplete data'

        WHEN yll_rate_2019 > yll_rate_2000
        THEN 'Increased'

        WHEN yll_rate_2019 < yll_rate_2000
        THEN 'Decreased'

        ELSE 'No change'
    END AS trend_direction

FROM endpoints;

ANALYZE analytics.county_cause_rankings;