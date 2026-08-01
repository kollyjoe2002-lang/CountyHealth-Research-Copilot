CREATE SCHEMA IF NOT EXISTS analytics;

-- =====================================================================
-- DISPLAY LABEL OVERRIDES
--
-- Source values are preserved in all warehouse and analytical tables.
-- This dimension supplies clean human-readable labels for dashboards,
-- reports, exports, and AI-generated narratives.
-- =====================================================================

CREATE OR REPLACE TABLE analytics.dim_display_label_override (
    entity_type VARCHAR NOT NULL,
    entity_key VARCHAR NOT NULL,
    source_label VARCHAR NOT NULL,
    display_label VARCHAR NOT NULL,
    correction_reason VARCHAR NOT NULL,

    PRIMARY KEY (entity_type, entity_key)
);


-- =====================================================================
-- COUNTY LABEL OVERRIDES
-- =====================================================================

INSERT INTO analytics.dim_display_label_override VALUES

(
    'county',
    '46102',
    'Oglala Lakota County (SouthDakota)',
    'Oglala Lakota County (South Dakota)',
    'Missing space in state name'
),

(
    'county',
    '38079',
    'Rolette County (NorthDakota)',
    'Rolette County (North Dakota)',
    'Missing space in state name'
);


-- =====================================================================
-- CAUSE LABEL OVERRIDES
--
-- The cause IDs below should be verified from dim_cause before relying
-- on these records. The INSERT statements use cause names to retrieve
-- the correct IDs from the database.
-- =====================================================================

INSERT INTO analytics.dim_display_label_override

SELECT
    'cause' AS entity_type,
    cause_id::VARCHAR AS entity_key,
    cause_name AS source_label,
    'Diabetes mellitus type 2' AS display_label,
    'Missing space in cause name' AS correction_reason

FROM analytics.dim_cause

WHERE REPLACE(LOWER(cause_name), ' ', '')
    = 'diabetesmellitustype2'

ON CONFLICT DO NOTHING;


INSERT INTO analytics.dim_display_label_override

SELECT
    'cause' AS entity_type,
    cause_id::VARCHAR AS entity_key,
    cause_name AS source_label,
    'Colon and rectum cancer' AS display_label,
    'Missing space in cause name' AS correction_reason

FROM analytics.dim_cause

WHERE REPLACE(LOWER(cause_name), ' ', '')
    = 'colonandrectumcancer'

ON CONFLICT DO NOTHING;


-- =====================================================================
-- CLEAN COUNTY LOOKUP
-- =====================================================================

CREATE OR REPLACE VIEW analytics.vw_county_display_lookup AS

SELECT
    c.location_id,
    c.location_name AS source_location_name,

    COALESCE(
        o.display_label,
        c.location_name
    ) AS location_name,

    c.fips,
    c.state_fips,
    c.county_fips,

    COALESCE(
        o.display_label,
        c.display_name
    ) AS display_name,

    c.has_burden_estimates,
    c.is_rankable

FROM analytics.vw_current_county_lookup AS c

LEFT JOIN analytics.dim_display_label_override AS o
    ON o.entity_type = 'county'
   AND o.entity_key = c.fips;


-- =====================================================================
-- CLEAN CURRENT RANKINGS
-- =====================================================================

CREATE OR REPLACE VIEW analytics.vw_county_rankings_display AS

SELECT
    r.location_id,

    r.location_name AS source_location_name,

    COALESCE(
        county_label.display_label,
        r.location_name
    ) AS location_name,

    r.fips,
    r.state_fips,
    r.county_fips,
    r.year,
    r.cause_id,

    r.cause_name AS source_cause_name,

    COALESCE(
        cause_label.display_label,
        r.cause_name
    ) AS cause_name,

    r.yll_rate,
    r.lower,
    r.upper,
    r.county_cause_rank,
    r.county_display_order,
    r.national_county_rank,
    r.national_display_order,
    r.counties_with_estimate,
    r.burden_percentile

FROM analytics.current_county_cause_rankings AS r

LEFT JOIN analytics.dim_display_label_override AS county_label
    ON county_label.entity_type = 'county'
   AND county_label.entity_key = r.fips

LEFT JOIN analytics.dim_display_label_override AS cause_label
    ON cause_label.entity_type = 'cause'
   AND cause_label.entity_key = r.cause_id::VARCHAR;


-- =====================================================================
-- CLEAN TOP-CAUSE VIEW
-- =====================================================================

CREATE OR REPLACE VIEW analytics.vw_county_top_causes_display AS

SELECT *
FROM analytics.vw_county_rankings_display

WHERE county_display_order <= 10;


-- =====================================================================
-- CLEAN CAUSE DIMENSION
-- =====================================================================

CREATE OR REPLACE VIEW analytics.vw_cause_display_lookup AS

SELECT
    c.*,

    COALESCE(
        o.display_label,
        c.cause_name
    ) AS display_cause_name

FROM analytics.dim_cause AS c

LEFT JOIN analytics.dim_display_label_override AS o
    ON o.entity_type = 'cause'
   AND o.entity_key = c.cause_id::VARCHAR;


ANALYZE analytics.dim_display_label_override;