-- ============================================================
-- EpiCounty
-- CDC PLACES Evidence Schema
-- ============================================================

CREATE SCHEMA IF NOT EXISTS places;


-- ------------------------------------------------------------
-- Import log
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS places.import_log (
    source_file         VARCHAR PRIMARY KEY,
    file_path           VARCHAR,
    release_year        INTEGER,
    geography_level     VARCHAR,
    file_size_bytes     BIGINT,
    rows_imported       BIGINT,
    status              VARCHAR,
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP,
    error_message       VARCHAR
);


-- ------------------------------------------------------------
-- CDC PLACES releases
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS places.releases (
    release_year        INTEGER PRIMARY KEY,
    release_label       VARCHAR,
    release_date        DATE,
    source_name         VARCHAR DEFAULT 'CDC PLACES',
    methodology         VARCHAR,
    notes               VARCHAR
);


-- ------------------------------------------------------------
-- Canonical measure catalog
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS places.measures (
    measure_id                  VARCHAR PRIMARY KEY,
    canonical_name              VARCHAR,
    category                    VARCHAR,
    frequency                   VARCHAR,
    unit                        VARCHAR DEFAULT 'Percent',
    age_adjusted_available      BOOLEAN,
    first_release_year          INTEGER,
    last_release_year           INTEGER,
    notes                       VARCHAR
);


-- ------------------------------------------------------------
-- Release-specific measure definitions
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS places.measure_versions (
    release_year        INTEGER,
    measure_id          VARCHAR,
    measure_name        VARCHAR,
    measure_definition  VARCHAR,
    data_source         VARCHAR,
    measurement_year    INTEGER,
    frequency           VARCHAR,
    carry_forward       BOOLEAN DEFAULT FALSE,
    definition_version  VARCHAR,
    notes               VARCHAR,

    PRIMARY KEY (release_year, measure_id)
);


-- ------------------------------------------------------------
-- PLACES small-area estimates
--
-- One row represents one:
-- release × geography × measure
--
-- Crude and age-adjusted estimates are retained separately.
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS places.estimates (
    release_year            INTEGER,
    measurement_year        INTEGER,

    geography_level         VARCHAR,
    geoid                   VARCHAR,
    geography_name          VARCHAR,

    state_abbr              VARCHAR,
    state_name              VARCHAR,

    total_population        BIGINT,
    total_pop_18plus        BIGINT,

    measure_id              VARCHAR,

    crude_prevalence        DOUBLE,
    crude_ci_lower          DOUBLE,
    crude_ci_upper          DOUBLE,

    age_adjusted_prevalence DOUBLE,
    age_adjusted_ci_lower   DOUBLE,
    age_adjusted_ci_upper   DOUBLE,

    carry_forward           BOOLEAN DEFAULT FALSE,
    missing_reason          VARCHAR,

    source_file             VARCHAR,
    imported_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        release_year,
        geography_level,
        geoid,
        measure_id
    )
);