"""
CountyHealth Research Copilot

Database schema definitions
"""

TABLE_NAME = "ihme.burden"

COLUMN_TYPES = {
    "measure_id": "BIGINT",
    "measure_name": "VARCHAR",
    "location_id": "BIGINT",
    "location_name": "VARCHAR",
    "fips": "VARCHAR",
    "race_id": "BIGINT",
    "race_name": "VARCHAR",
    "sex_id": "BIGINT",
    "sex_name": "VARCHAR",
    "age_group_id": "BIGINT",
    "age_name": "VARCHAR",
    "cause_id": "BIGINT",
    "cause_name": "VARCHAR",
    "year": "INTEGER",
    "metric_id": "BIGINT",
    "metric_name": "VARCHAR",
    "val": "DOUBLE",
    "upper": "DOUBLE",
    "lower": "DOUBLE",
}