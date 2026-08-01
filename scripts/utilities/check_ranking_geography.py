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
        print("Ranking Geography and Missing-County Diagnostics")
        print("=" * 80)

        # -------------------------------------------------------------
        # Counties absent from ranking layer
        # -------------------------------------------------------------
        heading("Counties absent from county_cause_rankings")

        print(
            con.execute("""
                SELECT
                    g.fips,
                    g.location_id,
                    g.location_name,
                    g.state_fips,
                    g.county_fips
                FROM analytics.dim_geography AS g

                LEFT JOIN (
                    SELECT DISTINCT fips
                    FROM analytics.county_cause_rankings
                ) AS r
                    ON g.fips = r.fips

                WHERE g.geography_level = 'COUNTY'
                  AND r.fips IS NULL

                ORDER BY g.state_fips, g.fips
            """).fetchdf().to_string(index=False)
        )

        # -------------------------------------------------------------
        # Raw burden coverage for counties absent from rankings
        # -------------------------------------------------------------
        heading("BURDEN coverage for counties absent from rankings")

        print(
            con.execute("""
                WITH missing_counties AS (
                    SELECT
                        g.fips,
                        g.location_name
                    FROM analytics.dim_geography AS g

                    LEFT JOIN (
                        SELECT DISTINCT fips
                        FROM analytics.county_cause_rankings
                    ) AS r
                        ON g.fips = r.fips

                    WHERE g.geography_level = 'COUNTY'
                      AND r.fips IS NULL
                )

                SELECT
                    m.fips,
                    m.location_name,
                    COUNT(b.*) AS burden_rows,

                    SUM(
                        CASE
                            WHEN b.value IS NULL THEN 1
                            ELSE 0
                        END
                    ) AS null_value_rows,

                    SUM(
                        CASE
                            WHEN b.value IS NOT NULL THEN 1
                            ELSE 0
                        END
                    ) AS non_null_value_rows,

                    COUNT(DISTINCT b.year) AS years,
                    COUNT(DISTINCT b.cause_id) AS causes

                FROM missing_counties AS m

                LEFT JOIN analytics.county_burden_summary AS b
                    ON m.fips = b.fips

                GROUP BY
                    m.fips,
                    m.location_name

                ORDER BY
                    non_null_value_rows,
                    m.fips
            """).fetchdf().to_string(index=False)
        )

        # -------------------------------------------------------------
        # Missing counties by state
        # -------------------------------------------------------------
        heading("Ranking exclusions summarized by state")

        print(
            con.execute("""
                WITH missing_counties AS (
                    SELECT
                        g.fips,
                        g.state_fips
                    FROM analytics.dim_geography AS g

                    LEFT JOIN (
                        SELECT DISTINCT fips
                        FROM analytics.county_cause_rankings
                    ) AS r
                        ON g.fips = r.fips

                    WHERE g.geography_level = 'COUNTY'
                      AND r.fips IS NULL
                )

                SELECT
                    state_fips,
                    COUNT(*) AS excluded_counties
                FROM missing_counties
                GROUP BY state_fips
                ORDER BY excluded_counties DESC, state_fips
            """).fetchdf().to_string(index=False)
        )

        # -------------------------------------------------------------
        # Similar or duplicate county names
        # -------------------------------------------------------------
        heading("County names associated with multiple FIPS codes")

        print(
            con.execute("""
                SELECT
                    location_name,
                    COUNT(DISTINCT fips) AS fips_count,
                    STRING_AGG(
                        DISTINCT fips,
                        ', '
                        ORDER BY fips
                    ) AS fips_codes

                FROM analytics.dim_geography

                WHERE geography_level = 'COUNTY'

                GROUP BY location_name

                HAVING COUNT(DISTINCT fips) > 1

                ORDER BY fips_count DESC, location_name
            """).fetchdf().to_string(index=False)
        )

        # -------------------------------------------------------------
        # South Dakota geography inspection
        # -------------------------------------------------------------
        heading("South Dakota county geography records")

        print(
            con.execute("""
                SELECT
                    location_id,
                    location_name,
                    fips,
                    state_fips,
                    county_fips
                FROM analytics.dim_geography
                WHERE geography_level = 'COUNTY'
                  AND state_fips = '46'
                ORDER BY fips, location_name
            """).fetchdf().to_string(index=False)
        )

        # -------------------------------------------------------------
        # Shannon and Oglala Lakota comparison
        # -------------------------------------------------------------
        heading("Shannon and Oglala Lakota BURDEN comparison")

        print(
            con.execute("""
                SELECT
                    location_name,
                    fips,
                    year,
                    cause_id,
                    cause_name,
                    value,
                    lower,
                    upper
                FROM analytics.county_burden_summary
                WHERE fips IN ('46102', '46113')
                  AND cause_name = 'Diabetes mellitus type 2'
                ORDER BY year, fips
            """).fetchdf().to_string(index=False)
        )

        # -------------------------------------------------------------
        # Check whether all values match between the two FIPS codes
        # -------------------------------------------------------------
        heading("Full estimate comparison between FIPS 46102 and 46113")

        print(
            con.execute("""
                WITH oglala AS (
                    SELECT
                        year,
                        cause_id,
                        value,
                        lower,
                        upper
                    FROM analytics.county_burden_summary
                    WHERE fips = '46102'
                ),

                shannon AS (
                    SELECT
                        year,
                        cause_id,
                        value,
                        lower,
                        upper
                    FROM analytics.county_burden_summary
                    WHERE fips = '46113'
                )

                SELECT
                    COUNT(*) AS matched_rows,

                    SUM(
                        CASE
                            WHEN o.value = s.value
                              OR (
                                  o.value IS NULL
                                  AND s.value IS NULL
                              )
                            THEN 1
                            ELSE 0
                        END
                    ) AS equal_value_rows,

                    SUM(
                        CASE
                            WHEN o.lower = s.lower
                              OR (
                                  o.lower IS NULL
                                  AND s.lower IS NULL
                              )
                            THEN 1
                            ELSE 0
                        END
                    ) AS equal_lower_rows,

                    SUM(
                        CASE
                            WHEN o.upper = s.upper
                              OR (
                                  o.upper IS NULL
                                  AND s.upper IS NULL
                              )
                            THEN 1
                            ELSE 0
                        END
                    ) AS equal_upper_rows,

                    MAX(
                        ABS(o.value - s.value)
                    ) AS maximum_value_difference

                FROM oglala AS o

                INNER JOIN shannon AS s
                    ON o.year = s.year
                   AND o.cause_id = s.cause_id
            """).fetchdf()
        )

        # -------------------------------------------------------------
        # Check for other county pairs with identical annual profiles
        # -------------------------------------------------------------
        heading("Potential duplicate county profiles in 2019")

        print(
            con.execute("""
                WITH profiles AS (
                    SELECT
                        fips,
                        location_name,
                        year,
                        HASH(
                            STRING_AGG(
                                cause_id::VARCHAR
                                || ':'
                                || COALESCE(
                                    ROUND(value, 8)::VARCHAR,
                                    'NULL'
                                ),
                                '|'
                                ORDER BY cause_id
                            )
                        ) AS profile_hash

                    FROM analytics.county_burden_summary

                    WHERE year = 2019

                    GROUP BY
                        fips,
                        location_name,
                        year
                )

                SELECT
                    profile_hash,
                    COUNT(*) AS matching_counties,

                    STRING_AGG(
                        fips || ' — ' || location_name,
                        ' | '
                        ORDER BY fips
                    ) AS matching_locations

                FROM profiles

                GROUP BY profile_hash

                HAVING COUNT(*) > 1

                ORDER BY matching_counties DESC, profile_hash
            """).fetchdf().to_string(index=False)
        )

    finally:
        con.close()


if __name__ == "__main__":
    main()