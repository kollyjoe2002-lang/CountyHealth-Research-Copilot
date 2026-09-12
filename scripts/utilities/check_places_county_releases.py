from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_DIR = PROJECT_ROOT / "database" / "places"


EXPECTED = {
    2020: {
        "db": "places_2020_test.duckdb",
        "counties": 3142,
        "measures": 28,
        "rows": 87976,
        "measurement_years": {
            2017: 4,
            2018: 24,
        },
    },
    2021: {
        "db": "places_2021_test.duckdb",
        "counties": 3142,
        "measures": 30,
        "rows": 94260,
        "measurement_years": {
            2018: 8,
            2019: 22,
        },
    },
    2022: {
        "db": "places_2022_test.duckdb",
        "counties": 3143,
        "measures": 30,
        "rows": 94290,
        "measurement_years": {
            2019: 4,
            2020: 26,
        },
    },
    2023: {
        "db": "places_2023_test.duckdb",
        "counties": 3143,
        "measures": 37,
        "rows": 116291,
        "measurement_years": {
            2020: 8,
            2021: 29,
        },
    },
    2024: {
        "db": "places_2024_test.duckdb",
        "counties": 3144,
        "measures": 40,
        "rows": 125760,
        "measurement_years": {
            2021: 4,
            2022: 36,
        },
    },
    2025: {
        "db": "places_2025_test.duckdb",
        "counties": 3143,
        "measures": 40,
        "rows": 125720,
        "measurement_years": {
            2022: 5,
            2023: 35,
        },
    },
}


EXPECTED_2025_CARRY_FORWARD = {
    "COLON_SCREEN",
    "DENTAL",
    "MAMMOUSE",
    "SLEEP",
    "TEETHLOST",
}


def validate_release(
    release_year: int,
    config: dict,
) -> None:
    db_path = DB_DIR / config["db"]

    if not db_path.exists():
        raise FileNotFoundError(
            f"Missing test database: {db_path}"
        )

    con = duckdb.connect(str(db_path))

    try:
        row_count = con.execute(
            """
            SELECT COUNT(*)
            FROM places.estimates
            WHERE release_year = ?
            """,
            [release_year],
        ).fetchone()[0]

        county_count = con.execute(
            """
            SELECT COUNT(DISTINCT geoid)
            FROM places.estimates
            WHERE release_year = ?
            """,
            [release_year],
        ).fetchone()[0]

        measure_count = con.execute(
            """
            SELECT COUNT(DISTINCT measure_id)
            FROM places.estimates
            WHERE release_year = ?
            """,
            [release_year],
        ).fetchone()[0]

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

        duplicate_rows = con.execute(
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
                WHERE release_year = ?
                GROUP BY
                    release_year,
                    geography_level,
                    geoid,
                    measure_id
                HAVING COUNT(*) > 1
            )
            """,
            [release_year],
        ).fetchone()[0]

        bad_fips = con.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT geoid
                FROM places.estimates
                WHERE release_year = ?
            )
            WHERE length(geoid) <> 5
               OR regexp_matches(geoid, '[^0-9]')
            """,
            [release_year],
        ).fetchone()[0]

        assert row_count == config["rows"], (
            release_year,
            row_count,
        )

        assert county_count == config["counties"], (
            release_year,
            county_count,
        )

        assert measure_count == config["measures"], (
            release_year,
            measure_count,
        )

        assert measurement_years == config[
            "measurement_years"
        ], (
            release_year,
            measurement_years,
        )

        assert duplicate_rows == 0, (
            release_year,
            duplicate_rows,
        )

        assert bad_fips == 0, (
            release_year,
            bad_fips,
        )

    finally:
        con.close()


def validate_geography_transitions() -> None:
    con_2021 = duckdb.connect(
        str(DB_DIR / "places_2021_test.duckdb")
    )
    con_2022 = duckdb.connect(
        str(DB_DIR / "places_2022_test.duckdb")
    )
    con_2023 = duckdb.connect(
        str(DB_DIR / "places_2023_test.duckdb")
    )
    con_2024 = duckdb.connect(
        str(DB_DIR / "places_2024_test.duckdb")
    )

    try:
        fips_2021 = {
            row[0]
            for row in con_2021.execute(
                """
                SELECT DISTINCT geoid
                FROM places.estimates
                WHERE release_year = 2021
                """
            ).fetchall()
        }

        fips_2022 = {
            row[0]
            for row in con_2022.execute(
                """
                SELECT DISTINCT geoid
                FROM places.estimates
                WHERE release_year = 2022
                """
            ).fetchall()
        }

        assert fips_2022 - fips_2021 == {
            "02063",
            "02066",
        }

        assert fips_2021 - fips_2022 == {
            "02261",
        }

        fips_2023 = {
            row[0]
            for row in con_2023.execute(
                """
                SELECT DISTINCT geoid
                FROM places.estimates
                WHERE release_year = 2023
                """
            ).fetchall()
        }

        fips_2024 = {
            row[0]
            for row in con_2024.execute(
                """
                SELECT DISTINCT geoid
                FROM places.estimates
                WHERE release_year = 2024
                """
            ).fetchall()
        }

        assert fips_2024 - fips_2023 == {
            "09110",
            "09120",
            "09130",
            "09140",
            "09150",
            "09160",
            "09170",
            "09180",
            "09190",
        }

        assert fips_2023 - fips_2024 == {
            "09001",
            "09003",
            "09005",
            "09007",
            "09009",
            "09011",
            "09013",
            "09015",
        }

    finally:
        con_2021.close()
        con_2022.close()
        con_2023.close()
        con_2024.close()


def validate_2025_special_cases() -> None:
    db_path = DB_DIR / "places_2025_test.duckdb"
    con = duckdb.connect(str(db_path))

    try:
        carry_forward = {
            row[0]
            for row in con.execute(
                """
                SELECT DISTINCT measure_id
                FROM places.estimates
                WHERE release_year = 2025
                  AND carry_forward = TRUE
                """
            ).fetchall()
        }

        assert carry_forward == (
            EXPECTED_2025_CARRY_FORWARD
        )

        carry_years = {
            row[0]
            for row in con.execute(
                """
                SELECT DISTINCT measurement_year
                FROM places.estimates
                WHERE release_year = 2025
                  AND carry_forward = TRUE
                """
            ).fetchall()
        }

        assert carry_years == {2022}

        current_years = {
            row[0]
            for row in con.execute(
                """
                SELECT DISTINCT measurement_year
                FROM places.estimates
                WHERE release_year = 2025
                  AND carry_forward = FALSE
                """
            ).fetchall()
        }

        assert current_years == {2023}

        kentucky = dict(
            con.execute(
                """
                SELECT
                    measure_id,
                    age_adjusted_prevalence
                FROM places.estimates
                WHERE release_year = 2025
                  AND geoid = '21221'
                  AND measure_id IN (
                      'COLON_SCREEN',
                      'DENTAL',
                      'MAMMOUSE',
                      'SLEEP',
                      'TEETHLOST',
                      'DIABETES',
                      'OBESITY'
                  )
                """
            ).fetchall()
        )

        for measure_id in EXPECTED_2025_CARRY_FORWARD:
            assert kentucky[measure_id] is not None, (
                measure_id,
                kentucky[measure_id],
            )

        assert kentucky["DIABETES"] is None
        assert kentucky["OBESITY"] is None

    finally:
        con.close()


def main() -> None:
    for release_year, config in EXPECTED.items():
        validate_release(
            release_year,
            config,
        )

    validate_geography_transitions()
    validate_2025_special_cases()

    print("=" * 70)
    print(
        "PLACES county releases 2020-2025 "
        "validation: PASS"
    )
    print("=" * 70)

    for release_year, config in EXPECTED.items():
        print(
            f"{release_year}: "
            f"{config['counties']:,} counties | "
            f"{config['measures']} measures | "
            f"{config['rows']:,} rows"
        )

    print()
    print(
        "Alaska geography transition 2021->2022: "
        "verified"
    )
    print(
        "Connecticut geography transition 2023->2024: "
        "verified"
    )
    print(
        "2025 carry-forward and Kentucky missingness: "
        "verified"
    )


if __name__ == "__main__":
    main()