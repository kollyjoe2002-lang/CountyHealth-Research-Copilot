from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

con = duckdb.connect(str(DB_FILE), read_only=True)

print("=" * 80)
print("Analytics Metadata Check")
print("=" * 80)

print("\nMetadata row counts")
print(
    con.execute("""
        SELECT 'dim_cause' AS table_name, COUNT(*) AS rows
        FROM analytics.dim_cause

        UNION ALL

        SELECT 'dim_sex', COUNT(*)
        FROM analytics.dim_sex

        UNION ALL

        SELECT 'dim_race', COUNT(*)
        FROM analytics.dim_race

        UNION ALL

        SELECT 'dim_age_group', COUNT(*)
        FROM analytics.dim_age_group

        UNION ALL

        SELECT 'dim_measure', COUNT(*)
        FROM analytics.dim_measure

        UNION ALL

        SELECT 'dim_metric', COUNT(*)
        FROM analytics.dim_metric
    """).fetchdf()
)

print("\nCause dimension")
print(
    con.execute("""
        SELECT
            cause_id,
            cause_name,
            is_broad_group,
            include_in_default_ranking,
            cause_type
        FROM analytics.dim_cause
        ORDER BY is_broad_group DESC, cause_name
    """).fetchdf().to_string(index=False)
)

print("\nSex dimension")
print(
    con.execute("""
        SELECT *
        FROM analytics.dim_sex
        ORDER BY display_order
    """).fetchdf().to_string(index=False)
)

print("\nRace dimension")
print(
    con.execute("""
        SELECT *
        FROM analytics.dim_race
        ORDER BY display_order
    """).fetchdf().to_string(index=False)
)

print("\nAge-group dimension")
print(
    con.execute("""
        SELECT *
        FROM analytics.dim_age_group
        ORDER BY display_order
    """).fetchdf().to_string(index=False)
)

print("\nMeasure dimension")
print(
    con.execute("""
        SELECT *
        FROM analytics.dim_measure
        ORDER BY measure_key
    """).fetchdf().to_string(index=False)
)

print("\nMetric dimension")
print(
    con.execute("""
        SELECT *
        FROM analytics.dim_metric
        ORDER BY metric_key
    """).fetchdf().to_string(index=False)
)

print("\nDefault selections")
print(
    con.execute("""
        SELECT
            (SELECT sex_name
             FROM analytics.dim_sex
             WHERE is_default) AS default_sex,

            (SELECT race_name
             FROM analytics.dim_race
             WHERE is_default) AS default_race,

            (SELECT age_name
             FROM analytics.dim_age_group
             WHERE is_default) AS default_age
    """).fetchdf()
)

print("\nDefault ranking cause count")
print(
    con.execute("""
        SELECT
            COUNT(*) AS included_causes,
            SUM(CASE WHEN is_broad_group THEN 1 ELSE 0 END)
                AS excluded_broad_groups
        FROM analytics.dim_cause
        WHERE include_in_default_ranking
           OR is_broad_group
    """).fetchdf()
)

con.close()