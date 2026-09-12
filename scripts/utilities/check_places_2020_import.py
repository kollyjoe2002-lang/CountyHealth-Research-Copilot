from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]

TEST_DB = (
    PROJECT_ROOT
    / "database"
    / "places"
    / "places_2020_test.duckdb"
)


def main() -> None:
    if not TEST_DB.exists():
        raise FileNotFoundError(
            f"Test database not found: {TEST_DB}"
        )

    con = duckdb.connect(str(TEST_DB))

    try:
        row_count = con.execute(
            """
            SELECT COUNT(*)
            FROM places.estimates
            WHERE release_year = 2020
            """
        ).fetchone()[0]

        assert row_count == 87976, row_count

        county_count = con.execute(
            """
            SELECT COUNT(DISTINCT geoid)
            FROM places.estimates
            WHERE release_year = 2020
            """
        ).fetchone()[0]

        assert county_count == 3142, county_count

        measure_count = con.execute(
            """
            SELECT COUNT(DISTINCT measure_id)
            FROM places.estimates
            WHERE release_year = 2020
            """
        ).fetchone()[0]

        assert measure_count == 28, measure_count

        autauga = con.execute(
            """
            SELECT
                measurement_year,
                crude_prevalence,
                crude_ci_lower,
                crude_ci_upper,
                age_adjusted_prevalence,
                age_adjusted_ci_lower,
                age_adjusted_ci_upper
            FROM places.estimates
            WHERE release_year = 2020
              AND geoid = '01001'
              AND measure_id = 'OBESITY'
            """
        ).fetchone()

        assert autauga == (
            2018,
            35.8,
            34.2,
            37.3,
            35.5,
            33.9,
            37.0,
        ), autauga

        measurement_years = dict(
            con.execute(
                """
                SELECT
                    measurement_year,
                    COUNT(DISTINCT measure_id)
                FROM places.estimates
                WHERE release_year = 2020
                GROUP BY measurement_year
                ORDER BY measurement_year
                """
            ).fetchall()
        )

        assert measurement_years == {
            2017: 4,
            2018: 24,
        }, measurement_years

        bad_fips = con.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT geoid
                FROM places.estimates
                WHERE release_year = 2020
            )
            WHERE length(geoid) <> 5
               OR regexp_matches(geoid, '[^0-9]')
            """
        ).fetchone()[0]

        assert bad_fips == 0, bad_fips

    finally:
        con.close()

    print("=" * 70)
    print("PLACES 2020 county import validation: PASS")
    print("=" * 70)
    print("Rows             : 87,976")
    print("Counties         : 3,142")
    print("Measures         : 28")
    print("Measurement years: 2017=4, 2018=24")
    print("Autauga obesity  : verified")
    print("County FIPS      : verified")


if __name__ == "__main__":
    main()