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
        print("Display-Label Validation")
        print("=" * 80)

        heading("Configured overrides")

        print(
            con.execute("""
                SELECT
                    entity_type,
                    entity_key,
                    source_label,
                    display_label,
                    correction_reason
                FROM analytics.dim_display_label_override
                ORDER BY entity_type, entity_key
            """).fetchdf().to_string(index=False)
        )

        heading("County display corrections")

        print(
            con.execute("""
                SELECT
                    source_location_name,
                    location_name,
                    fips
                FROM analytics.vw_county_display_lookup
                WHERE fips IN ('46102', '38079')
                ORDER BY fips
            """).fetchdf().to_string(index=False)
        )

        heading("Cause display corrections")

        print(
            con.execute("""
                SELECT
                    cause_id,
                    cause_name AS source_cause_name,
                    display_cause_name
                FROM analytics.vw_cause_display_lookup
                WHERE display_cause_name IN (
                    'Diabetes mellitus type 2',
                    'Colon and rectum cancer'
                )
                ORDER BY cause_id
            """).fetchdf().to_string(index=False)
        )

        heading("Corrected diabetes ranking labels")

        print(
            con.execute("""
                SELECT
                    national_display_order,
                    location_name,
                    fips,
                    cause_name,
                    ROUND(yll_rate, 2) AS yll_rate
                FROM analytics.vw_county_rankings_display
                WHERE cause_name = 'Diabetes mellitus type 2'
                  AND year = 2019
                ORDER BY national_display_order
                LIMIT 12
            """).fetchdf().to_string(index=False)
        )

        heading("Source values remain unchanged")

        print(
            con.execute("""
                SELECT
                    r.location_name AS original_location_name,
                    d.location_name AS display_location_name,
                    r.cause_name AS original_cause_name,
                    d.cause_name AS display_cause_name
                FROM analytics.current_county_cause_rankings AS r

                INNER JOIN analytics.vw_county_rankings_display AS d
                    ON r.fips = d.fips
                   AND r.year = d.year
                   AND r.cause_id = d.cause_id

                WHERE r.fips = '46102'
                  AND r.year = 2019
                  AND d.cause_name =
                      'Diabetes mellitus type 2'

                LIMIT 1
            """).fetchdf().to_string(index=False)
        )

        heading("Duplicate county display names")

        print(
            con.execute("""
                SELECT COUNT(*) AS duplicate_display_name_groups
                FROM (
                    SELECT
                        display_name,
                        COUNT(*) AS records
                    FROM analytics.vw_county_display_lookup
                    GROUP BY display_name
                    HAVING COUNT(*) > 1
                )
            """).fetchdf()
        )

    finally:
        con.close()


if __name__ == "__main__":
    main()