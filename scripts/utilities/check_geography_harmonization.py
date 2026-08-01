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
        print("Geographic Harmonization Validation")
        print("=" * 80)

        heading("Object row counts")

        print(
            con.execute("""
                SELECT
                    'dim_location_alias' AS object_name,
                    COUNT(*) AS rows
                FROM analytics.dim_location_alias

                UNION ALL

                SELECT
                    'dim_county_status',
                    COUNT(*)
                FROM analytics.dim_county_status

                UNION ALL

                SELECT
                    'vw_current_county_lookup',
                    COUNT(*)
                FROM analytics.vw_current_county_lookup

                UNION ALL

                SELECT
                    'vw_all_county_lookup',
                    COUNT(*)
                FROM analytics.vw_all_county_lookup

                UNION ALL

                SELECT
                    'vw_current_county_cause_rankings',
                    COUNT(*)
                FROM analytics.vw_current_county_cause_rankings
            """).fetchdf()
        )

        heading("County status totals")

        print(
            con.execute("""
                SELECT
                    county_status,
                    COUNT(*) AS counties
                FROM analytics.dim_county_status
                GROUP BY county_status
                ORDER BY county_status
            """).fetchdf().to_string(index=False)
        )

        heading("Confirmed aliases")

        print(
            con.execute("""
                SELECT
                    source_fips,
                    source_location_name,
                    canonical_fips,
                    canonical_location_name,
                    relationship_type,
                    effective_year,
                    include_in_current_county_selector
                FROM analytics.dim_county_status
                WHERE is_confirmed_alias = TRUE
                ORDER BY source_fips
            """).fetchdf().to_string(index=False)
        )

        heading("Counties with unavailable estimates")

        print(
            con.execute("""
                SELECT
                    source_fips AS fips,
                    source_location_name AS location_name,
                    burden_rows,
                    non_null_burden_rows,
                    county_status,
                    display_name
                FROM analytics.dim_county_status
                WHERE county_status = 'estimate_unavailable'
                ORDER BY source_fips
            """).fetchdf().to_string(index=False)
        )

        heading("Selector uniqueness checks")

        print(
            con.execute("""
                SELECT
                    COUNT(*) AS selector_rows,
                    COUNT(DISTINCT fips) AS distinct_fips,
                    COUNT(DISTINCT location_id) AS distinct_location_ids,
                    COUNT(DISTINCT display_name) AS distinct_display_names
                FROM analytics.vw_current_county_lookup
            """).fetchdf()
        )

        heading("Duplicate selector FIPS")

        print(
            con.execute("""
                SELECT COUNT(*) AS duplicate_fips_groups
                FROM (
                    SELECT
                        fips,
                        COUNT(*) AS records
                    FROM analytics.vw_current_county_lookup
                    GROUP BY fips
                    HAVING COUNT(*) > 1
                )
            """).fetchdf()
        )

        heading("Historical aliases incorrectly included in selector")

        print(
            con.execute("""
                SELECT COUNT(*) AS historical_aliases_in_selector
                FROM analytics.dim_county_status
                WHERE county_status = 'historical_alias'
                  AND include_in_current_county_selector = TRUE
            """).fetchdf()
        )

        heading("Unavailable counties incorrectly marked rankable")

        print(
            con.execute("""
                SELECT COUNT(*) AS invalid_counties
                FROM analytics.dim_county_status
                WHERE county_status = 'estimate_unavailable'
                  AND is_rankable = TRUE
            """).fetchdf()
        )

        heading("South Dakota alias check")

        print(
            con.execute("""
                SELECT
                    source_fips,
                    source_location_name,
                    canonical_fips,
                    canonical_location_name,
                    county_status,
                    include_in_current_county_selector
                FROM analytics.dim_county_status
                WHERE source_fips IN ('46102', '46113')
                ORDER BY source_fips
            """).fetchdf().to_string(index=False)
        )

        heading("Florida alias check")

        print(
            con.execute("""
                SELECT
                    source_fips,
                    source_location_name,
                    canonical_fips,
                    canonical_location_name,
                    county_status,
                    include_in_current_county_selector
                FROM analytics.dim_county_status
                WHERE source_fips IN ('12025', '12086')
                ORDER BY source_fips
            """).fetchdf().to_string(index=False)
        )

        heading("Alaska alias check")

        print(
            con.execute("""
                SELECT
                    source_fips,
                    source_location_name,
                    canonical_fips,
                    canonical_location_name,
                    county_status,
                    include_in_current_county_selector
                FROM analytics.dim_county_status
                WHERE source_fips IN ('02158', '02270')
                ORDER BY source_fips
            """).fetchdf().to_string(index=False)
        )

        heading("Current 2019 type 2 diabetes ranking")

        print(
            con.execute("""
                SELECT
                    national_county_rank,
                    location_name,
                    fips,
                    ROUND(yll_rate, 2) AS yll_rate,
                    burden_percentile
                FROM analytics.vw_current_county_cause_rankings
                WHERE cause_name = 'Diabetes mellitus type 2'
                  AND year = 2019
                ORDER BY national_county_rank, fips
                LIMIT 15
            """).fetchdf().to_string(index=False)
        )

    finally:
        con.close()


if __name__ == "__main__":
    main()