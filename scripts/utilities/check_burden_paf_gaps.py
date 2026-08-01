from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

con = duckdb.connect(str(DB_FILE), read_only=True)

print("=" * 80)
print("BURDEN and PAF Gap Diagnostics")
print("=" * 80)

# ---------------------------------------------------------------------
# Causes present in PAF but absent from BURDEN summary
# ---------------------------------------------------------------------
print("\nCauses present in PAF but absent from BURDEN summary")
print(
    con.execute("""
        SELECT DISTINCT p.cause_id, p.cause_name
        FROM analytics.county_paf_summary AS p
        LEFT JOIN analytics.county_burden_summary AS b
            ON p.cause_id = b.cause_id
        WHERE b.cause_id IS NULL
        ORDER BY p.cause_name
    """).fetchdf()
)

# ---------------------------------------------------------------------
# Cause-level coverage in BURDEN
# ---------------------------------------------------------------------
print("\nBURDEN coverage by cause")
print(
    con.execute("""
        SELECT
            cause_id,
            cause_name,
            COUNT(*) AS rows,
            COUNT(DISTINCT fips) AS counties,
            COUNT(DISTINCT year) AS years,
            SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) AS null_values
        FROM analytics.county_burden_summary
        GROUP BY cause_id, cause_name
        ORDER BY rows, cause_name
    """).fetchdf().to_string(index=False)
)

# ---------------------------------------------------------------------
# Null estimates by cause
# ---------------------------------------------------------------------
print("\nBURDEN null estimates by cause")
print(
    con.execute("""
        SELECT
            cause_id,
            cause_name,
            COUNT(*) AS null_rows,
            COUNT(DISTINCT fips) AS affected_counties,
            MIN(year) AS first_year,
            MAX(year) AS last_year
        FROM analytics.county_burden_summary
        WHERE value IS NULL
        GROUP BY cause_id, cause_name
        ORDER BY null_rows DESC, cause_name
    """).fetchdf().to_string(index=False)
)

print("\nPAF null estimates by cause")
print(
    con.execute("""
        SELECT
            cause_id,
            cause_name,
            COUNT(*) AS null_rows,
            COUNT(DISTINCT fips) AS affected_counties,
            MIN(year) AS first_year,
            MAX(year) AS last_year
        FROM analytics.county_paf_summary
        WHERE value IS NULL
        GROUP BY cause_id, cause_name
        ORDER BY null_rows DESC, cause_name
    """).fetchdf().to_string(index=False)
)

# ---------------------------------------------------------------------
# BURDEN coverage by county
# Complete coverage for 37 causes × 20 years would equal 740 rows
# ---------------------------------------------------------------------
print("\nCounties with incomplete BURDEN coverage")
print(
    con.execute("""
        SELECT
            fips,
            location_name,
            COUNT(*) AS rows,
            COUNT(DISTINCT cause_id) AS causes,
            COUNT(DISTINCT year) AS years,
            SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) AS null_values
        FROM analytics.county_burden_summary
        GROUP BY fips, location_name
        HAVING COUNT(*) <> 740
            OR COUNT(DISTINCT cause_id) <> 37
            OR COUNT(DISTINCT year) <> 20
        ORDER BY rows, fips
    """).fetchdf().to_string(index=False)
)

# ---------------------------------------------------------------------
# Missing BURDEN combinations relative to its own 37-cause universe
# ---------------------------------------------------------------------
print("\nMissing BURDEN county-year-cause combinations")
print(
    con.execute("""
        WITH counties AS (
            SELECT DISTINCT
                fips,
                location_name
            FROM analytics.county_burden_summary
        ),
        years AS (
            SELECT DISTINCT year
            FROM analytics.county_burden_summary
        ),
        causes AS (
            SELECT DISTINCT
                cause_id,
                cause_name
            FROM analytics.county_burden_summary
        ),
        expected AS (
            SELECT
                c.fips,
                c.location_name,
                y.year,
                ca.cause_id,
                ca.cause_name
            FROM counties AS c
            CROSS JOIN years AS y
            CROSS JOIN causes AS ca
        )
        SELECT
            e.cause_id,
            e.cause_name,
            COUNT(*) AS missing_rows,
            COUNT(DISTINCT e.fips) AS affected_counties,
            MIN(e.year) AS first_year,
            MAX(e.year) AS last_year
        FROM expected AS e
        LEFT JOIN analytics.county_burden_summary AS b
            ON e.fips = b.fips
           AND e.year = b.year
           AND e.cause_id = b.cause_id
        WHERE b.fips IS NULL
        GROUP BY e.cause_id, e.cause_name
        ORDER BY missing_rows DESC, e.cause_name
    """).fetchdf().to_string(index=False)
)

# ---------------------------------------------------------------------
# Verify whether null rows have all three estimates missing together
# ---------------------------------------------------------------------
print("\nEstimate null-pattern check")
print(
    con.execute("""
        SELECT
            'BURDEN' AS dataset,
            SUM(CASE
                WHEN value IS NULL
                 AND lower IS NULL
                 AND upper IS NULL
                THEN 1 ELSE 0
            END) AS all_three_null,
            SUM(CASE
                WHEN value IS NULL
                  OR lower IS NULL
                  OR upper IS NULL
                THEN 1 ELSE 0
            END) AS any_null
        FROM analytics.county_burden_summary

        UNION ALL

        SELECT
            'PAF',
            SUM(CASE
                WHEN value IS NULL
                 AND lower IS NULL
                 AND upper IS NULL
                THEN 1 ELSE 0
            END),
            SUM(CASE
                WHEN value IS NULL
                  OR lower IS NULL
                  OR upper IS NULL
                THEN 1 ELSE 0
            END)
        FROM analytics.county_paf_summary
    """).fetchdf()
)

con.close()