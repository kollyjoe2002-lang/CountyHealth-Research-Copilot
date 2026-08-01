from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

con = duckdb.connect(str(DB_FILE), read_only=True)

print("=" * 70)
print("County PAF Structure Check")
print("=" * 70)

# --------------------------------------------------------------------
# Row count
# --------------------------------------------------------------------
print("\nRow count")
print(
    con.execute("""
        SELECT COUNT(*) AS rows
        FROM ihme.paf
    """).fetchdf()
)

# --------------------------------------------------------------------
# Year coverage
# --------------------------------------------------------------------
print("\nYear coverage")
print(
    con.execute("""
        SELECT
            MIN(year) AS first_year,
            MAX(year) AS last_year,
            COUNT(DISTINCT year) AS years
        FROM ihme.paf
    """).fetchdf()
)

# --------------------------------------------------------------------
# Causes
# --------------------------------------------------------------------
print("\nCauses")
print(
    con.execute("""
        SELECT
            COUNT(DISTINCT cause_name) AS distinct_causes
        FROM ihme.paf
    """).fetchdf()
)

print(
    con.execute("""
        SELECT DISTINCT cause_name
        FROM ihme.paf
        ORDER BY cause_name
    """).fetchdf()
)

# --------------------------------------------------------------------
# Measures
# --------------------------------------------------------------------
print("\nMeasures")
print(
    con.execute("""
        SELECT DISTINCT measure_name
        FROM ihme.paf
        ORDER BY measure_name
    """).fetchdf()
)

# --------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------
print("\nMetrics")
print(
    con.execute("""
        SELECT DISTINCT metric_name
        FROM ihme.paf
        ORDER BY metric_name
    """).fetchdf()
)

# --------------------------------------------------------------------
# Sexes
# --------------------------------------------------------------------
print("\nSexes")
print(
    con.execute("""
        SELECT DISTINCT sex_name
        FROM ihme.paf
        ORDER BY sex_name
    """).fetchdf()
)

# --------------------------------------------------------------------
# Races
# --------------------------------------------------------------------
print("\nRaces")
print(
    con.execute("""
        SELECT DISTINCT race_name
        FROM ihme.paf
        ORDER BY race_name
    """).fetchdf()
)

# --------------------------------------------------------------------
# Age groups
# --------------------------------------------------------------------
print("\nAge groups")
print(
    con.execute("""
        SELECT DISTINCT age_name
        FROM ihme.paf
        ORDER BY age_name
    """).fetchdf()
)

# --------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------
print("\nDistinct locations")
print(
    con.execute("""
        SELECT
            COUNT(DISTINCT location_id) AS locations,
            COUNT(DISTINCT fips) AS fips_codes
        FROM ihme.paf
    """).fetchdf()
)

# --------------------------------------------------------------------
# Null FIPS
# --------------------------------------------------------------------
print("\nNull FIPS")
print(
    con.execute("""
        SELECT COUNT(*) AS rows
        FROM ihme.paf
        WHERE fips IS NULL
    """).fetchdf()
)

# --------------------------------------------------------------------
# Column structure
# --------------------------------------------------------------------
print("\nPAF table columns")
print(
    con.execute("""
        DESCRIBE ihme.paf
    """).fetchdf()
)

con.close()