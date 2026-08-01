from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"


def heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> None:
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    con = duckdb.connect(str(DB_FILE), read_only=True)

    try:
        print("=" * 80)
        print("Current-Geography Ranking Validation")
        print("=" * 80)

        heading("Object row counts")

        print(
            con.execute("""
                SELECT
                    'current_county_cause_rankings'
                        AS object_name,
                    COUNT(*) AS rows
                FROM analytics.current_county_cause_rankings

                UNION ALL

                SELECT
                    'vw_current_county_top_causes',
                    COUNT(*)
                FROM analytics.vw_current_county_top_causes

                UNION ALL

                SELECT
                    'vw_current_county_cause_change_2000_2019',
                    COUNT(*)
                FROM
                    analytics
                    .vw_current_county_cause_change_2000_2019
            """).fetchdf()
        )

        heading("Coverage")

        print(
            con.execute("""
                SELECT
                    COUNT(DISTINCT fips) AS counties,
                    COUNT(DISTINCT year) AS years,
                    COUNT(DISTINCT cause_id) AS causes,
                    MIN(year) AS first_year,
                    MAX(year) AS last_year
                FROM analytics.current_county_cause_rankings
            """).fetchdf()
        )

        heading("Expected row-count calculation")

        print(
            con.execute("""
                SELECT
                    COUNT(DISTINCT fips) AS counties,
                    COUNT(DISTINCT year) AS years,
                    COUNT(DISTINCT cause_id) AS causes,

                    COUNT(DISTINCT fips)
                    * COUNT(DISTINCT year)
                    * COUNT(DISTINCT cause_id)
                        AS expected_rows,

                    COUNT(*) AS actual_rows

                FROM analytics.current_county_cause_rankings
            """).fetchdf()
        )

        heading("Historical alias exclusion")

        print(
            con.execute("""
                SELECT COUNT(*) AS historical_alias_rows
                FROM analytics.current_county_cause_rankings
                WHERE fips IN ('02270', '12025', '46113')
            """).fetchdf()
        )

        heading("Unavailable-county exclusion")

        print(
            con.execute("""
                SELECT COUNT(*) AS unavailable_county_rows

                FROM analytics.current_county_cause_rankings AS r

                INNER JOIN analytics.dim_county_status AS s
                    ON r.fips = s.source_fips

                WHERE s.county_status = 'estimate_unavailable'
            """).fetchdf()
        )

        heading("Duplicate county-year-cause keys")

        print(
            con.execute("""
                SELECT COUNT(*) AS duplicate_groups
                FROM (
                    SELECT
                        fips,
                        year,
                        cause_id,
                        COUNT(*) AS records
                    FROM analytics.current_county_cause_rankings
                    GROUP BY fips, year, cause_id
                    HAVING COUNT(*) > 1
                )
            """).fetchdf()
        )

        heading("Ranking integrity")

        print(
            con.execute("""
                SELECT
                    SUM(
                        CASE
                            WHEN national_county_rank < 1
                            THEN 1 ELSE 0
                        END
                    ) AS invalid_national_rank,

                    SUM(
                        CASE
                            WHEN national_display_order < 1
                            THEN 1 ELSE 0
                        END
                    ) AS invalid_display_order,

                    SUM(
                        CASE
                            WHEN burden_percentile < 0
                              OR burden_percentile > 100
                            THEN 1 ELSE 0
                        END
                    ) AS invalid_percentile,

                    MIN(counties_with_estimate)
                        AS minimum_county_count,

                    MAX(counties_with_estimate)
                        AS maximum_county_count

                FROM analytics.current_county_cause_rankings
            """).fetchdf()
        )

        heading("Display-order continuity by cause-year")

        print(
            con.execute("""
                SELECT COUNT(*) AS invalid_cause_year_groups
                FROM (
                    SELECT
                        cause_id,
                        year,
                        COUNT(*) AS row_count,
                        MIN(national_display_order) AS min_order,
                        MAX(national_display_order) AS max_order,
                        COUNT(DISTINCT national_display_order)
                            AS distinct_orders

                    FROM analytics.current_county_cause_rankings

                    GROUP BY cause_id, year

                    HAVING min_order <> 1
                        OR max_order <> row_count
                        OR distinct_orders <> row_count
                )
            """).fetchdf()
        )

        heading("Current 2019 type 2 diabetes ranking")

        print(
            con.execute("""
                SELECT
                    national_display_order,
                    national_county_rank,
                    location_name,
                    fips,
                    ROUND(yll_rate, 2) AS yll_rate,
                    counties_with_estimate,
                    burden_percentile

                FROM analytics.current_county_cause_rankings

                WHERE cause_name = 'Diabetes mellitus type 2'
                  AND year = 2019

                ORDER BY national_display_order

                LIMIT 15
            """).fetchdf().to_string(index=False)
        )

        heading("Rank and percentile endpoints")

        print(
            con.execute("""
                WITH diabetes AS (
                    SELECT
                        location_name,
                        fips,
                        national_county_rank,
                        national_display_order,
                        counties_with_estimate,
                        burden_percentile,
                        yll_rate,

                        ROW_NUMBER() OVER (
                            ORDER BY national_display_order
                        ) AS highest_order,

                        ROW_NUMBER() OVER (
                            ORDER BY national_display_order DESC
                        ) AS lowest_order

                    FROM analytics.current_county_cause_rankings

                    WHERE cause_name = 'Diabetes mellitus type 2'
                      AND year = 2019
                )

                SELECT
                    CASE
                        WHEN highest_order = 1 THEN 'highest'
                        WHEN lowest_order = 1 THEN 'lowest'
                    END AS endpoint,

                    location_name,
                    fips,
                    national_county_rank,
                    national_display_order,
                    counties_with_estimate,
                    burden_percentile,
                    ROUND(yll_rate, 2) AS yll_rate

                FROM diabetes

                WHERE highest_order = 1
                   OR lowest_order = 1

                ORDER BY
                    CASE
                        WHEN highest_order = 1 THEN 1
                        ELSE 2
                    END
            """).fetchdf().to_string(index=False)
        )

        heading("Albany County current-ranking check")

        print(
            con.execute("""
                SELECT
                    year,
                    cause_name,
                    ROUND(yll_rate, 2) AS yll_rate,
                    county_cause_rank,
                    national_county_rank,
                    national_display_order,
                    counties_with_estimate,
                    burden_percentile

                FROM analytics.current_county_cause_rankings

                WHERE fips = '56001'
                  AND year = 2019

                ORDER BY county_display_order

                LIMIT 10
            """).fetchdf().to_string(index=False)
        )

    finally:
        con.close()


if __name__ == "__main__":
    main()