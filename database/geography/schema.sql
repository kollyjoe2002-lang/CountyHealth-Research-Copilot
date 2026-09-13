CREATE SCHEMA IF NOT EXISTS geography;

CREATE TABLE IF NOT EXISTS geography.rucc_2023 (
    fips TEXT PRIMARY KEY,
    state_abbr TEXT NOT NULL,
    county_name TEXT NOT NULL,
    population_2020 BIGINT,
    rucc_code INTEGER,
    rucc_description TEXT,
    metro_status TEXT,
    adjacency_status TEXT,
    source_year INTEGER NOT NULL DEFAULT 2023,
    source_name TEXT NOT NULL DEFAULT 'USDA Rural-Urban Continuum Codes',
    missing_reason TEXT
);