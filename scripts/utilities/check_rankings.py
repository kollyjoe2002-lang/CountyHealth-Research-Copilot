from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"


def print_heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> None:
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    con = duckdb.connect(str(DB_FILE), read_only=True)

    try:
        print("=" * 80)
        print("County Cause-Ranking Validation")
        print("=" * 80)

        print_heading("Object row counts")
        print(
            con.execute("""
                SELECT
                    'county_cause_rankings' AS object_name,
                    COUNT(*) AS rows
                FROM analytics.county_cause_rankings

                UNION ALL

                SELECT
                    'vw_county_top_causes',
                    COUNT(*)
                FROM analytics.vw_county_top_causes

                UNION ALL

                SELECT
                    'vw_county_cause_change_2000_2019',
                    COUNT(*)
                FROM analytics.vw_county_cause_change_2000_2019
            """).fetchdf()
        )

        print_heading("Coverage")
        print(
            con.execute("""
                SELECT
                    COUNT(DISTINCT fips) AS counties,
                    MIN(year) AS first_year,
                    MAX(year) AS last_year,
                    COUNT(DISTINCT cause_id) AS causes,
                    COUNT(DISTINCT year) AS years
                FROM analytics.county_cause_rankings
            """).fetchdf()
        )

        print_heading("Duplicate county-year-cause keys")
        print(
            con.execute("""
                SELECT COUNT(*) AS duplicate_groups
                FROM (
                    SELECT
                        fips,
                        year,
                        cause_id,
                        COUNT(*) AS records
                    FROM analytics.county_cause_rankings
                    GROUP BY fips, year, cause_id
                    HAVING COUNT(*) > 1
                )
            """).fetchdf()
        )

        print_heading("Null and invalid ranking checks")
        print(
            con.execute("""
                SELECT
                    SUM(CASE
                        WHEN yll_rate IS NULL THEN 1 ELSE 0
                    END) AS null_yll_rate,

                    SUM(CASE
                        WHEN county_cause_rank IS NULL THEN 1 ELSE 0
                    END) AS null_county_rank,

                    SUM(CASE
                        WHEN national_county_rank IS NULL THEN 1 ELSE 0
                    END) AS null_national_rank,

                    SUM(CASE
                        WHEN burden_percentile IS NULL THEN 1 ELSE 0
                    END) AS null_percentile,

                    SUM(CASE
                        WHEN burden_percentile < 0
                          OR burden_percentile > 100
                        THEN 1 ELSE 0
                    END) AS invalid_percentile
                FROM analytics.county_cause_rankings
            """).fetchdf()
        )

        print_heading("Broad-group exclusion check")
        print(
            con.execute("""
                SELECT COUNT(*) AS broad_group_rows
                FROM analytics.county_cause_rankings AS r

                INNER JOIN analytics.dim_cause AS c
                    ON r.cause_id = c.cause_id

                WHERE c.is_broad_group = TRUE
                   OR c.include_in_default_ranking = FALSE
            """).fetchdf()
        )

        print_heading("County-year ranking continuity")
        print(
            con.execute("""
                SELECT
                    COUNT(*) AS county_years,
                    MIN(cause_rows) AS minimum_causes,
                    MAX(cause_rows) AS maximum_causes,
                    MIN(maximum_display_order) AS minimum_max_order,
                    MAX(maximum_display_order) AS maximum_max_order
                FROM (
                    SELECT
                        fips,
                        year,
                        COUNT(*) AS cause_rows,
                        MAX(county_display_order) AS maximum_display_order
                    FROM analytics.county_cause_rankings
                    GROUP BY fips, year
                )
            """).fetchdf()
        )

        print_heading("Top causes — Albany County, Wyoming, 2019")
        print(
            con.execute("""
                SELECT
                    county_display_order,
                    county_cause_rank,
                    cause_name,
                    ROUND(yll_rate, 2) AS yll_rate,
                    ROUND(lower, 2) AS lower,
                    ROUND(upper, 2) AS upper,
                    national_county_rank,
                    counties_with_estimate,
                    burden_percentile
                FROM analytics.vw_county_top_causes
                WHERE fips = '56001'
                  AND year = 2019
                ORDER BY county_display_order
            """).fetchdf().to_string(index=False)
        )

        print_heading(
            "Highest-burden counties for type 2 diabetes — 2019"
        )
        print(
            con.execute("""
                SELECT
                    national_county_rank,
                    location_name,
                    fips,
                    ROUND(yll_rate, 2) AS yll_rate,
                    burden_percentile
                FROM analytics.county_cause_rankings
                WHERE cause_name = 'Diabetes mellitus type 2'
                  AND year = 2019
                ORDER BY national_county_rank, fips
                LIMIT 15
            """).fetchdf().to_string(index=False)
        )

        print_heading(
            "Albany County type 2 diabetes trend — 2000 to 2019"
        )
        print(
            con.execute("""
                SELECT
                    year,
                    ROUND(yll_rate, 2) AS yll_rate,
                    county_cause_rank,
                    national_county_rank,
                    burden_percentile,
                    ROUND(previous_year_rate, 2) AS previous_year_rate,
                    ROUND(annual_absolute_change, 2)
                        AS annual_absolute_change,
                    annual_percent_change
                FROM analytics.vw_county_cause_trends
                WHERE fips = '56001'
                  AND cause_name = 'Diabetes mellitus type 2'
                ORDER BY year
            """).fetchdf().to_string(index=False)
        )

        print_heading(
            "Albany County long-term cause changes — 2000 to 2019"
        )
        print(
            con.execute("""
                SELECT
                    cause_name,
                    ROUND(yll_rate_2000, 2) AS yll_rate_2000,
                    ROUND(yll_rate_2019, 2) AS yll_rate_2019,
                    ROUND(
                        absolute_change_2000_2019,
                        2
                    ) AS absolute_change,
                    percent_change_2000_2019,
                    trend_direction
                FROM analytics.vw_county_cause_change_2000_2019
                WHERE fips = '56001'
                ORDER BY ABS(absolute_change_2000_2019) DESC NULLS LAST
                LIMIT 15
            """).fetchdf().to_string(index=False)
        )

    finally:
        con.close()


if __name__ == "__main__":
    main()