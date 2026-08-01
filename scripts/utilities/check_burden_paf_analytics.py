from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

con = duckdb.connect(str(DB_FILE), read_only=True)

print("=" * 70)
print("BURDEN and PAF Analytics Check")
print("=" * 70)

print("\nRow counts")
print(
    con.execute("""
        SELECT
            'county_burden_summary' AS object_name,
            COUNT(*) AS rows
        FROM analytics.county_burden_summary

        UNION ALL

        SELECT
            'county_paf_summary',
            COUNT(*)
        FROM analytics.county_paf_summary
    """).fetchdf()
)

print("\nExpected dimensions")
print(
    con.execute("""
        SELECT
            'BURDEN' AS dataset,
            COUNT(DISTINCT fips) AS counties,
            MIN(year) AS first_year,
            MAX(year) AS last_year,
            COUNT(DISTINCT cause_name) AS causes
        FROM analytics.vw_county_burden_summary

        UNION ALL

        SELECT
            'PAF',
            COUNT(DISTINCT fips),
            MIN(year),
            MAX(year),
            COUNT(DISTINCT cause_name)
        FROM analytics.vw_county_paf_summary
    """).fetchdf()
)

print("\nDuplicate-key check")
print(
    con.execute("""
        SELECT
            'BURDEN' AS dataset,
            COUNT(*) AS duplicate_groups
        FROM (
            SELECT fips, year, cause_id, COUNT(*) AS n
            FROM analytics.county_burden_summary
            GROUP BY fips, year, cause_id
            HAVING COUNT(*) > 1
        )

        UNION ALL

        SELECT
            'PAF',
            COUNT(*)
        FROM (
            SELECT fips, year, cause_id, COUNT(*) AS n
            FROM analytics.county_paf_summary
            GROUP BY fips, year, cause_id
            HAVING COUNT(*) > 1
        )
    """).fetchdf()
)

print("\nAlbany County, Wyoming — top YLL rates in 2019")
print(
    con.execute("""
        SELECT
            cause_name,
            ROUND(value, 2) AS yll_rate,
            ROUND(lower, 2) AS lower,
            ROUND(upper, 2) AS upper
        FROM analytics.vw_county_burden_summary
        WHERE fips = '56001'
          AND year = 2019
        ORDER BY value DESC
        LIMIT 15
    """).fetchdf()
)

print("\nAlbany County, Wyoming — PAF values in 2019")
print(
    con.execute("""
        SELECT
            cause_name,
            ROUND(value, 4) AS paf_value,
            ROUND(lower, 4) AS lower,
            ROUND(upper, 4) AS upper
        FROM analytics.vw_county_paf_summary
        WHERE fips = '56001'
          AND year = 2019
        ORDER BY value DESC
        LIMIT 15
    """).fetchdf()
)

print("\nPAF value range")
print(
    con.execute("""
        SELECT
            MIN(value) AS minimum,
            MAX(value) AS maximum,
            AVG(value) AS mean
        FROM analytics.vw_county_paf_summary
    """).fetchdf()
)

print("\nNull checks")
print(
    con.execute("""
        SELECT
            'BURDEN' AS dataset,
            SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) AS null_value,
            SUM(CASE WHEN lower IS NULL THEN 1 ELSE 0 END) AS null_lower,
            SUM(CASE WHEN upper IS NULL THEN 1 ELSE 0 END) AS null_upper
        FROM analytics.county_burden_summary

        UNION ALL

        SELECT
            'PAF',
            SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN lower IS NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN upper IS NULL THEN 1 ELSE 0 END)
        FROM analytics.county_paf_summary
    """).fetchdf()
)

con.close()