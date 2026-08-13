CREATE SCHEMA IF NOT EXISTS analytics;

-- =====================================================
-- Cause Dimension
-- =====================================================

CREATE OR REPLACE TABLE analytics.dim_cause AS
SELECT DISTINCT
    cause_id,
    cause_name,

    CASE
        WHEN cause_name IN (
            'All causes',
            'Non-communicable diseases',
            'Cardiovascular diseases',
            'Neoplasms',
            'Digestive diseases',
            'Neurological disorders',
            'Chronic respiratory diseases'
        )
        THEN TRUE
        ELSE FALSE
    END AS is_broad_group,

    CASE
        WHEN cause_name IN (
            'All causes',
            'Non-communicable diseases',
            'Cardiovascular diseases',
            'Neoplasms',
            'Digestive diseases',
            'Neurological disorders',
            'Chronic respiratory diseases'
        )
        THEN FALSE
        ELSE TRUE
    END AS include_in_default_ranking,

    CASE
        WHEN cause_name = 'All causes'
            THEN 'Overall burden category'

        WHEN cause_name = 'Non-communicable diseases'
            THEN 'Broad disease category'

        WHEN cause_name IN (
            'Cardiovascular diseases',
            'Neoplasms',
            'Digestive diseases',
            'Neurological disorders',
            'Chronic respiratory diseases'
        )
            THEN 'Broad cause group'

        ELSE 'Cause available for default rankings'
    END AS cause_type,

    CASE
        -- Broad aggregate categories should not appear
        -- in a leading-cause presentation list.
        WHEN cause_name IN (
            'All causes',
            'Non-communicable diseases',
            'Cardiovascular diseases',
            'Neoplasms',
            'Digestive diseases',
            'Neurological disorders',
            'Chronic respiratory diseases'
        )
            THEN FALSE

        -- Use Diabetes mellitus as the display-level
        -- diabetes cause rather than showing overlapping
        -- broader and subtype categories together.
        WHEN cause_name IN (
            'Diabetes and kidney diseases',
            'Diabetes mellitus type 2'
        )
            THEN FALSE

        -- Use Stroke as the display-level cerebrovascular
        -- cause in the leading-cause list.
        WHEN cause_name IN (
            'Ischemic stroke',
            'Intracerebral hemorrhage'
        )
            THEN FALSE

        -- Use Leukemia rather than simultaneously displaying
        -- leukemia and represented subtypes.
        WHEN cause_name IN (
            'Acute myeloid leukemia',
            'Chronic lymphoid leukemia',
            'Chronic myeloid leukemia',
            'Other leukemia'
        )
            THEN FALSE

        -- Use Non-Hodgkin lymphoma rather than simultaneously
        -- displaying represented subtypes.
        WHEN cause_name IN (
            'Burkitt lymphoma',
            'Other non-Hodgkin lymphoma'
        )
            THEN FALSE

        ELSE TRUE
    END AS include_in_top_cause_ranking

FROM (
    SELECT
        cause_id,
        cause_name
    FROM ihme.burden

    UNION

    SELECT
        cause_id,
        cause_name
    FROM ihme.paf
)

ORDER BY cause_name;

-- =====================================================
-- Sex Dimension
-- =====================================================

CREATE OR REPLACE TABLE analytics.dim_sex AS
SELECT DISTINCT
    sex_id,
    sex_name,

    CASE sex_name
        WHEN 'Both' THEN 1
        WHEN 'Female' THEN 2
        WHEN 'Male' THEN 3
        ELSE 99
    END AS display_order,

    sex_name = 'Both' AS is_default

FROM ihme.burden
ORDER BY display_order;


-- =====================================================
-- Race Dimension
-- =====================================================

CREATE OR REPLACE TABLE analytics.dim_race AS
SELECT DISTINCT
    race_id,
    race_name,

    CASE race_name
        WHEN 'Total' THEN 1
        WHEN 'Non-Latino, White' THEN 2
        WHEN 'Non-Latino, Black' THEN 3
        WHEN 'Latino, Any race' THEN 4
        WHEN 'Non-Latino, Asian or Pacific Islander' THEN 5
        WHEN 'Non-Latino, American Indian or Alaska Native' THEN 6
        ELSE 99
    END AS display_order,

    race_name = 'Total' AS is_default

FROM ihme.burden
ORDER BY display_order;


-- =====================================================
-- Age Group Dimension
-- =====================================================

CREATE OR REPLACE TABLE analytics.dim_age_group AS
SELECT DISTINCT
    age_group_id,
    age_name,

    CASE age_name
        WHEN '20 to 24' THEN 20
        WHEN '25 to 29' THEN 25
        WHEN '30 to 34' THEN 30
        WHEN '35 to 39' THEN 35
        WHEN '40 to 44' THEN 40
        WHEN '45 to 49' THEN 45
        WHEN '50 to 54' THEN 50
        WHEN '55 to 59' THEN 55
        WHEN '60 to 64' THEN 60
        WHEN '65 to 69' THEN 65
        WHEN '70 to 74' THEN 70
        WHEN '75 to 79' THEN 75
        WHEN '80 to 84' THEN 80
        WHEN '85 plus' THEN 85
        WHEN '20 plus' THEN 20
        WHEN '20 plus, age standardized' THEN 20
        ELSE NULL
    END AS age_start,

    CASE age_name
        WHEN '20 to 24' THEN 24
        WHEN '25 to 29' THEN 29
        WHEN '30 to 34' THEN 34
        WHEN '35 to 39' THEN 39
        WHEN '40 to 44' THEN 44
        WHEN '45 to 49' THEN 49
        WHEN '50 to 54' THEN 54
        WHEN '55 to 59' THEN 59
        WHEN '60 to 64' THEN 64
        WHEN '65 to 69' THEN 69
        WHEN '70 to 74' THEN 74
        WHEN '75 to 79' THEN 79
        WHEN '80 to 84' THEN 84
        ELSE NULL
    END AS age_end,

    age_name = '20 plus, age standardized'
        AS is_age_standardized,

    age_name = '20 plus'
        AS is_all_adults,

    age_name = '20 plus, age standardized'
        AS is_default,

    CASE age_name
        WHEN '20 plus, age standardized' THEN 1
        WHEN '20 plus' THEN 2
        WHEN '20 to 24' THEN 3
        WHEN '25 to 29' THEN 4
        WHEN '30 to 34' THEN 5
        WHEN '35 to 39' THEN 6
        WHEN '40 to 44' THEN 7
        WHEN '45 to 49' THEN 8
        WHEN '50 to 54' THEN 9
        WHEN '55 to 59' THEN 10
        WHEN '60 to 64' THEN 11
        WHEN '65 to 69' THEN 12
        WHEN '70 to 74' THEN 13
        WHEN '75 to 79' THEN 14
        WHEN '80 to 84' THEN 15
        WHEN '85 plus' THEN 16
        ELSE 99
    END AS display_order

FROM ihme.burden
ORDER BY display_order;


-- =====================================================
-- Measure Dimension
-- =====================================================

CREATE OR REPLACE TABLE analytics.dim_measure AS
SELECT
    ROW_NUMBER() OVER (ORDER BY measure_name) AS measure_key,
    measure_name
FROM (
    SELECT DISTINCT measure_name
    FROM ihme.bmi
    WHERE measure_name IS NOT NULL

    UNION

    SELECT DISTINCT measure_name
    FROM ihme.burden
    WHERE measure_name IS NOT NULL

    UNION

    SELECT DISTINCT measure_name
    FROM ihme.paf
    WHERE measure_name IS NOT NULL
)
ORDER BY measure_name;


-- =====================================================
-- Metric Dimension
-- =====================================================

CREATE OR REPLACE TABLE analytics.dim_metric AS
SELECT
    ROW_NUMBER() OVER (ORDER BY metric_name) AS metric_key,
    metric_name,

    CASE metric_name
        WHEN 'Percent' THEN 'proportion'
        WHEN 'Rate' THEN 'rate'
        WHEN 'Number' THEN 'count'
        ELSE 'other'
    END AS value_type,

    CASE
        WHEN metric_name = 'Percent' THEN TRUE
        ELSE FALSE
    END AS multiply_by_100_for_display

FROM (
    SELECT DISTINCT metric_name
    FROM ihme.bmi
    WHERE metric_name IS NOT NULL

    UNION

    SELECT DISTINCT metric_name
    FROM ihme.burden
    WHERE metric_name IS NOT NULL

    UNION

    SELECT DISTINCT metric_name
    FROM ihme.paf
    WHERE metric_name IS NOT NULL
)
ORDER BY metric_name;