from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

con = duckdb.connect(str(DB_FILE), read_only=True)

print("=" * 70)
print("County BMI Analytics Check")
print("=" * 70)

print("\nRow counts")
print(
    con.execute("""
        SELECT
            'county_bmi_trends' AS object_name,
            COUNT(*) AS rows
        FROM analytics.county_bmi_trends

        UNION ALL

        SELECT
            'vw_county_bmi_summary',
            COUNT(*)
        FROM analytics.vw_county_bmi_summary
    """).fetchdf()
)

print("\nAlbany County, Wyoming")
print(
    con.execute("""
        SELECT
            year,
            metric,
            ROUND(value, 4) AS value,
            ROUND(lower, 4) AS lower,
            ROUND(upper, 4) AS upper
        FROM analytics.vw_county_bmi_summary
        WHERE fips = '56001'
        ORDER BY metric, year
    """).fetchdf()
)

print("\nDistinct summary dimensions")
print(
    con.execute("""
        SELECT
            COUNT(DISTINCT fips) AS counties,
            MIN(year) AS first_year,
            MAX(year) AS last_year,
            COUNT(DISTINCT metric) AS metrics
        FROM analytics.vw_county_bmi_summary
    """).fetchdf()
)

con.close()