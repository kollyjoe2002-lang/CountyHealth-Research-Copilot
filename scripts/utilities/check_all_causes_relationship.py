from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

con = duckdb.connect(str(DB_FILE), read_only=True)

print("=" * 80)
print("All Causes vs Non-communicable Diseases")
print("=" * 80)

print("\nCause IDs")
print(
    con.execute("""
        SELECT DISTINCT cause_id, cause_name
        FROM analytics.county_burden_summary
        WHERE cause_name IN (
            'All causes',
            'Non-communicable diseases'
        )
        ORDER BY cause_name
    """).fetchdf()
)

print("\nMatched-row comparison")
print(
    con.execute("""
        WITH all_causes AS (
            SELECT
                fips,
                year,
                value,
                lower,
                upper
            FROM analytics.county_burden_summary
            WHERE cause_name = 'All causes'
        ),
        ncd AS (
            SELECT
                fips,
                year,
                value,
                lower,
                upper
            FROM analytics.county_burden_summary
            WHERE cause_name = 'Non-communicable diseases'
        )
        SELECT
            COUNT(*) AS matched_rows,

            SUM(
                CASE
                    WHEN a.value = n.value
                      OR (a.value IS NULL AND n.value IS NULL)
                    THEN 1 ELSE 0
                END
            ) AS equal_value_rows,

            SUM(
                CASE
                    WHEN a.lower = n.lower
                      OR (a.lower IS NULL AND n.lower IS NULL)
                    THEN 1 ELSE 0
                END
            ) AS equal_lower_rows,

            SUM(
                CASE
                    WHEN a.upper = n.upper
                      OR (a.upper IS NULL AND n.upper IS NULL)
                    THEN 1 ELSE 0
                END
            ) AS equal_upper_rows,

            MAX(ABS(a.value - n.value)) AS maximum_value_difference
        FROM all_causes AS a
        JOIN ncd AS n
          ON a.fips = n.fips
         AND a.year = n.year
    """).fetchdf()
)

print("\nCoverage by year")
print(
    con.execute("""
        SELECT
            year,
            COUNT(*) FILTER (
                WHERE cause_name = 'All causes'
            ) AS all_causes_rows,

            COUNT(*) FILTER (
                WHERE cause_name = 'All causes'
                  AND value IS NOT NULL
            ) AS all_causes_non_null,

            COUNT(*) FILTER (
                WHERE cause_name = 'Non-communicable diseases'
            ) AS ncd_rows,

            COUNT(*) FILTER (
                WHERE cause_name = 'Non-communicable diseases'
                  AND value IS NOT NULL
            ) AS ncd_non_null
        FROM analytics.county_burden_summary
        WHERE cause_name IN (
            'All causes',
            'Non-communicable diseases'
        )
        GROUP BY year
        ORDER BY year
    """).fetchdf().to_string(index=False)
)

print("\nCounties missing All causes but having NCD")
print(
    con.execute("""
        WITH expected AS (
            SELECT
                g.fips,
                g.location_name,
                y.year
            FROM analytics.dim_geography AS g
            CROSS JOIN (
                SELECT DISTINCT year
                FROM analytics.county_burden_summary
            ) AS y
            WHERE g.geography_level = 'COUNTY'
        ),
        all_causes AS (
            SELECT fips, year
            FROM analytics.county_burden_summary
            WHERE cause_name = 'All causes'
        ),
        ncd AS (
            SELECT fips, year, value
            FROM analytics.county_burden_summary
            WHERE cause_name = 'Non-communicable diseases'
        )
        SELECT
            COUNT(*) AS missing_all_causes_with_ncd
        FROM expected AS e
        LEFT JOIN all_causes AS a
          ON e.fips = a.fips
         AND e.year = a.year
        JOIN ncd AS n
          ON e.fips = n.fips
         AND e.year = n.year
        WHERE a.fips IS NULL
    """).fetchdf()
)

con.close()