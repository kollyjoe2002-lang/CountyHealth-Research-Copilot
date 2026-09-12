from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = (
    PROJECT_ROOT
    / "database"
    / "places"
    / "places_integrated_test.duckdb"
)


EXPECTED_RELEASES = {
    2020: {
        "rows": 87976,
        "counties": 3142,
        "measures": 28,
        "measurement_years": {
            2017: 4,
            2018: 24,
        },
    },
    2021: {
        "rows": 94260,
        "counties": 3142,
        "measures": 30,
        "measurement_years": {
            2018: 8,
            2019: 22,
        },
    },
    2022: {
        "rows": 94290,
        "counties": 3143,
        "measures": 30,
        "measurement_years": {
            2019: 4,
            2020: 26,
        },
    },
    2023: {
        "rows": 116291,
        "counties": 3143,
        "measures": 37,
        "measurement_years": {
            2020: 8,
            2021: 29,
        },
    },
    2024: {
        "rows": 125760,
        "counties": 3144,
        "measures": 40,
        "measurement_years": {
            2021: 4,
            2022: 36,
        },
    },
    2025: {
        "rows": 125720,
        "counties": 3143,
        "measures": 40,
        "measurement_years": {
            2022: 5,
            2023: 35,
        },
    },
}


EXPECTED_TOTAL_ROWS = 644297

EXPECTED_AUTAUGA_OBESITY = [
    (2020, 2018, 35.5),
    (2021, 2019, 35.3),
    (2022, 2020, 37.3),
    (2023, 2021, 38.9),
    (2024, 2022, 38.4),
    (2025, 2023, 39.5),
]


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Integrated PLACES test database not found: {DB_PATH}"
        )

    con = duckdb.connect(str(DB_PATH))

    try:
        total_rows = con.execute(
            """
            SELECT COUNT(*)
            FROM places.estimates
            """
        ).fetchone()[0]

        assert total_rows == EXPECTED_TOTAL_ROWS, total_rows

        for release_year, expected in EXPECTED_RELEASES.items():
            result = con.execute(
                """
                SELECT
                    COUNT(*) AS rows,
                    COUNT(DISTINCT geoid) AS counties,
                    COUNT(DISTINCT measure_id) AS measures
                FROM places.estimates
                WHERE release_year = ?
                """,
                [release_year],
            ).fetchone()

            assert result == (
                expected["rows"],
                expected["counties"],
                expected["measures"],
            ), (
                release_year,
                result,
            )

            measurement_years = dict(
                con.execute(
                    """
                    SELECT
                        measurement_year,
                        COUNT(DISTINCT measure_id)
                    FROM places.estimates
                    WHERE release_year = ?
                    GROUP BY measurement_year
                    ORDER BY measurement_year
                    """,
                    [release_year],
                ).fetchall()
            )

            assert measurement_years == (
                expected["measurement_years"]
            ), (
                release_year,
                measurement_years,
            )

        duplicate_keys = con.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    release_year,
                    geography_level,
                    geoid,
                    measure_id,
                    COUNT(*) AS n
                FROM places.estimates
                GROUP BY
                    release_year,
                    geography_level,
                    geoid,
                    measure_id
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

        assert duplicate_keys == 0, duplicate_keys

        autauga_obesity = con.execute(
            """
            SELECT
                release_year,
                measurement_year,
                age_adjusted_prevalence
            FROM places.estimates
            WHERE geoid = '01001'
              AND measure_id = 'OBESITY'
            ORDER BY release_year
            """
        ).fetchall()

        assert autauga_obesity == (
            EXPECTED_AUTAUGA_OBESITY
        ), autauga_obesity

        bad_measurement_years = con.execute(
            """
            SELECT COUNT(*)
            FROM places.estimates
            WHERE measurement_year > release_year
            """
        ).fetchone()[0]

        assert bad_measurement_years == 0, (
            bad_measurement_years
        )

    finally:
        con.close()

    print("=" * 70)
    print("PLACES integrated county database validation: PASS")
    print("=" * 70)
    print(f"Total rows        : {EXPECTED_TOTAL_ROWS:,}")
    print("Releases          : 2020-2025")
    print("Duplicate keys    : 0")
    print("Measurement years : verified")
    print("Autauga obesity   : verified across all releases")


if __name__ == "__main__":
    main()