from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

con = duckdb.connect(str(DB_FILE), read_only=True)

print("=" * 70)
print("FIPS Length Distribution")
print("=" * 70)
print(
    con.execute("""
        SELECT
            LENGTH(fips) AS fips_length,
            COUNT(DISTINCT fips) AS distinct_fips,
            COUNT(*) AS rows
        FROM ihme.burden
        GROUP BY LENGTH(fips)
        ORDER BY fips_length
    """).fetchdf()
)

print("\n" + "=" * 70)
print("District of Columbia")
print("=" * 70)
print(
    con.execute("""
        SELECT DISTINCT
            location_id,
            location_name,
            fips
        FROM ihme.burden
        WHERE location_name = 'District of Columbia'
        ORDER BY fips
    """).fetchdf()
)

print("\n" + "=" * 70)
print("State-level FIPS")
print("=" * 70)
print(
    con.execute("""
        SELECT DISTINCT
            location_id,
            location_name,
            fips
        FROM ihme.burden
        WHERE fips LIKE '000%'
        ORDER BY fips
        LIMIT 60
    """).fetchdf()
)

print("\n" + "=" * 70)
print("Albany County Lookup")
print("=" * 70)
print(
    con.execute("""
        SELECT
            location_id,
            location_name,
            fips,
            state_fips,
            county_fips
        FROM analytics.vw_geography
        WHERE location_name LIKE 'Albany County%'
        ORDER BY location_name
    """).fetchdf()
)
con.close()