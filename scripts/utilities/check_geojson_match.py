import json
import duckdb

# Load GeoJSON
with open(
    r"app\assets\geojson\counties.geojson",
    encoding="utf-8",
) as f:
    geo = json.load(f)

geo_fips = {
    str(feature["id"]).zfill(5)
    for feature in geo["features"]
}

# Load database
con = duckdb.connect(
    r"database\countyhealth.duckdb",
    read_only=True,
)

db_fips = {
    str(row[0]).zfill(5)
    for row in con.execute("""
        SELECT DISTINCT fips
        FROM analytics.vw_current_county_lookup
        WHERE fips IS NOT NULL
    """).fetchall()
}

con.close()

matches = geo_fips & db_fips

print("=" * 60)
print("GeoJSON counties :", len(geo_fips))
print("Database counties:", len(db_fips))
print("Matching counties:", len(matches))
print("=" * 60)

print("\nFirst 20 matching FIPS:")
print(sorted(matches)[:20])

print("\nFirst 20 GeoJSON-only FIPS:")
print(sorted(geo_fips - db_fips)[:20])

print("\nFirst 20 Database-only FIPS:")
print(sorted(db_fips - geo_fips)[:20])