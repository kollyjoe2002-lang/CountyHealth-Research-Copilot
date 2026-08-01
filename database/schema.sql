-- ============================================================
-- CountyHealth Research Copilot
-- Database Schema
-- ============================================================

CREATE SCHEMA IF NOT EXISTS ihme;

-- ------------------------------------------------------------
-- Import log
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ihme.import_log (
    file_name          VARCHAR PRIMARY KEY,
    file_path          VARCHAR,
    dataset_type       VARCHAR,
    file_size_bytes    BIGINT,
    rows_imported      BIGINT,
    status             VARCHAR,
    started_at         TIMESTAMP,
    completed_at       TIMESTAMP,
    error_message      VARCHAR
);

-- ------------------------------------------------------------
-- BURDEN
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ihme.burden (
    measure_id         BIGINT,
    measure_name       VARCHAR,

    location_id        BIGINT,
    location_name      VARCHAR,

    fips               VARCHAR,

    race_id            BIGINT,
    race_name          VARCHAR,

    sex_id             BIGINT,
    sex_name           VARCHAR,

    age_group_id       BIGINT,
    age_name           VARCHAR,

    cause_id           BIGINT,
    cause_name         VARCHAR,

    year               INTEGER,

    metric_id          BIGINT,
    metric_name        VARCHAR,

    val                DOUBLE,
    upper              DOUBLE,
    lower              DOUBLE,

    source_file        VARCHAR,
    imported_at        TIMESTAMP
);

-- ------------------------------------------------------------
-- PAF
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ihme.paf (
    measure_id         BIGINT,
    measure_name       VARCHAR,

    location_id        BIGINT,
    location_name      VARCHAR,

    fips               VARCHAR,

    race_id            BIGINT,
    race_name          VARCHAR,

    sex_id             BIGINT,
    sex_name           VARCHAR,

    age_group_id       BIGINT,
    age_name           VARCHAR,

    cause_id           BIGINT,
    cause_name         VARCHAR,

    year               INTEGER,

    metric_id          BIGINT,
    metric_name        VARCHAR,

    val                DOUBLE,
    upper              DOUBLE,
    lower              DOUBLE,

    source_file        VARCHAR,
    imported_at        TIMESTAMP
);

-- ------------------------------------------------------------
-- BMI
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ihme.bmi (
    measure_id         BIGINT,
    measure_name       VARCHAR,

    location_id        BIGINT,
    location_name      VARCHAR,

    fips               VARCHAR,

    race_id            BIGINT,
    race_name          VARCHAR,

    sex_id             BIGINT,
    sex_name           VARCHAR,

    age_group_id       BIGINT,
    age_name           VARCHAR,

    year               INTEGER,

    metric_id          BIGINT,
    metric_name        VARCHAR,
    metric             VARCHAR,

    val                DOUBLE,
    upper              DOUBLE,
    lower              DOUBLE,

    source_file        VARCHAR,
    imported_at        TIMESTAMP
);