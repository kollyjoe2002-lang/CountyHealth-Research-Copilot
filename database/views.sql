CREATE SCHEMA IF NOT EXISTS analytics;

DROP VIEW IF EXISTS analytics.vw_geography;

CREATE TABLE IF NOT EXISTS analytics.dim_geography (
    location_id BIGINT,
    location_name VARCHAR,
    fips VARCHAR,
    geography_level VARCHAR,
    state_fips VARCHAR,
    county_fips VARCHAR,
    is_dc_county_equivalent BOOLEAN
);

DELETE FROM analytics.dim_geography;

INSERT INTO analytics.dim_geography
SELECT
    location_id,
    location_name,
    fips,

    CASE
        WHEN fips IS NULL THEN 'UNCLASSIFIED'
        WHEN LEFT(fips, 3) = '000' THEN 'STATE'
        ELSE 'COUNTY'
    END AS geography_level,

    CASE
        WHEN fips IS NULL THEN NULL
        WHEN LEFT(fips, 3) = '000' THEN RIGHT(fips, 2)
        ELSE LEFT(fips, 2)
    END AS state_fips,

    CASE
        WHEN fips IS NULL THEN NULL
        WHEN LEFT(fips, 3) = '000' THEN NULL
        ELSE RIGHT(fips, 3)
    END AS county_fips,

    fips = '11001' AS is_dc_county_equivalent

FROM (
    SELECT DISTINCT
        location_id,
        location_name,
        fips
    FROM ihme.burden
);

CREATE OR REPLACE VIEW analytics.vw_geography AS
SELECT
    location_id,
    location_name,
    fips,
    geography_level,
    state_fips,
    county_fips,
    is_dc_county_equivalent
FROM analytics.dim_geography;

CREATE TABLE IF NOT EXISTS analytics.county_bmi_trends (
    location_id BIGINT,
    location_name VARCHAR,
    fips VARCHAR,
    state_fips VARCHAR,
    county_fips VARCHAR,
    year INTEGER,
    sex_id INTEGER,
    sex_name VARCHAR,
    race_id INTEGER,
    race_name VARCHAR,
    age_group_id INTEGER,
    age_name VARCHAR,
    metric VARCHAR,
    value DOUBLE,
    lower DOUBLE,
    upper DOUBLE
);

DELETE FROM analytics.county_bmi_trends;

INSERT INTO analytics.county_bmi_trends
SELECT
    b.location_id,
    b.location_name,
    b.fips,
    g.state_fips,
    g.county_fips,
    b.year,
    b.sex_id,
    b.sex_name,
    b.race_id,
    b.race_name,
    b.age_group_id,
    b.age_name,
    b.metric,
    b.val AS value,
    b.lower,
    b.upper
FROM ihme.bmi AS b
JOIN analytics.dim_geography AS g
    ON b.location_id = g.location_id
   AND (
        b.fips = g.fips
        OR (b.fips IS NULL AND g.fips IS NULL)
   )
WHERE g.geography_level = 'COUNTY';

CREATE OR REPLACE VIEW analytics.vw_county_bmi_summary AS
SELECT
    location_id,
    location_name,
    fips,
    state_fips,
    county_fips,
    year,
    metric,
    value,
    lower,
    upper
FROM analytics.county_bmi_trends
WHERE sex_name = 'Both'
  AND race_name = 'Total'
  AND age_name = '20 plus, age standardized';

-- =====================================================
-- County Burden Summary
-- Both sexes, total race, age-standardized YLL rate
-- =====================================================

CREATE TABLE IF NOT EXISTS analytics.county_burden_summary (
    location_id BIGINT,
    location_name VARCHAR,
    fips VARCHAR,
    state_fips VARCHAR,
    county_fips VARCHAR,
    year INTEGER,
    cause_id BIGINT,
    cause_name VARCHAR,
    value DOUBLE,
    lower DOUBLE,
    upper DOUBLE
);

DELETE FROM analytics.county_burden_summary;

INSERT INTO analytics.county_burden_summary
SELECT
    b.location_id,
    b.location_name,
    b.fips,
    g.state_fips,
    g.county_fips,
    b.year,
    b.cause_id,
    b.cause_name,
    b.val AS value,
    b.lower,
    b.upper
FROM ihme.burden AS b
JOIN analytics.dim_geography AS g
    ON b.fips = g.fips
WHERE g.geography_level = 'COUNTY'
  AND b.sex_name = 'Both'
  AND b.race_name = 'Total'
  AND b.age_name = '20 plus, age standardized'
  AND b.measure_name = 'YLLs (Years of Life Lost)'
  AND b.metric_name = 'Rate';

CREATE OR REPLACE VIEW analytics.vw_county_burden_summary AS
SELECT *
FROM analytics.county_burden_summary;

-- =====================================================
-- County PAF Summary
-- Both sexes, total race, age-standardized YLL percent
-- =====================================================

CREATE TABLE IF NOT EXISTS analytics.county_paf_summary (
    location_id BIGINT,
    location_name VARCHAR,
    fips VARCHAR,
    state_fips VARCHAR,
    county_fips VARCHAR,
    year INTEGER,
    cause_id BIGINT,
    cause_name VARCHAR,
    value DOUBLE,
    lower DOUBLE,
    upper DOUBLE
);

DELETE FROM analytics.county_paf_summary;

INSERT INTO analytics.county_paf_summary
SELECT
    p.location_id,
    p.location_name,
    p.fips,
    g.state_fips,
    g.county_fips,
    p.year,
    p.cause_id,
    p.cause_name,
    p.val AS value,
    p.lower,
    p.upper
FROM ihme.paf AS p
JOIN analytics.dim_geography AS g
    ON p.fips = g.fips
WHERE g.geography_level = 'COUNTY'
  AND p.sex_name = 'Both'
  AND p.race_name = 'Total'
  AND p.age_name = '20 plus, age standardized'
  AND p.measure_name = 'YLLs (Years of Life Lost)'
  AND p.metric_name = 'Percent';

CREATE OR REPLACE VIEW analytics.vw_county_paf_summary AS
SELECT *
FROM analytics.county_paf_summary;