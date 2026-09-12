from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "database" / "places" / "countyhealth_places_integration_test.duckdb"

EXPECTED_IHME_BURDEN_ROWS = 689_763_368
EXPECTED_PLACES_ROWS = 644_297

EXPECTED_AUTAUGA_OBESITY = [
    (2020, 2018, 35.5),
    (2021, 2019, 35.3),
    (2022, 2020, 37.3),
    (2023, 2021, 38.9),
    (2024, 2022, 38.4),
    (2025, 2023, 39.5),
]


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Integration test database not found: {DB_PATH}"
        )

    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        ihme_rows = con.execute(
            "SELECT COUNT(*) FROM ihme.burden"
        ).fetchone()[0]

        assert ihme_rows == EXPECTED_IHME_BURDEN_ROWS, (
            f"IHME burden row count mismatch: "
            f"expected {EXPECTED_IHME_BURDEN_ROWS:,}, got {ihme_rows:,}"
        )

        places_rows = con.execute(
            "SELECT COUNT(*) FROM places.estimates"
        ).fetchone()[0]

        assert places_rows == EXPECTED_PLACES_ROWS, (
            f"PLACES row count mismatch: "
            f"expected {EXPECTED_PLACES_ROWS:,}, got {places_rows:,}"
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

        assert duplicate_keys == 0, (
            f"PLACES duplicate keys found: {duplicate_keys}"
        )

        ihme_autauga_rows = con.execute(
            """
            SELECT COUNT(*)
            FROM ihme.burden
            WHERE fips = '01001'
            """
        ).fetchone()[0]

        assert ihme_autauga_rows > 0, (
            "Autauga County FIPS 01001 not found in IHME burden data"
        )

        places_autauga_rows = con.execute(
            """
            SELECT COUNT(*)
            FROM places.estimates
            WHERE geoid = '01001'
            """
        ).fetchone()[0]

        assert places_autauga_rows > 0, (
            "Autauga County FIPS 01001 not found in PLACES data"
        )

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

        assert autauga_obesity == EXPECTED_AUTAUGA_OBESITY, (
            "Autauga obesity sequence mismatch:\n"
            f"expected: {EXPECTED_AUTAUGA_OBESITY}\n"
            f"actual:   {autauga_obesity}"
        )

        print("PLACES + IHME coexistence validation: PASS")
        print(f"IHME burden rows      : {ihme_rows:,}")
        print(f"PLACES rows           : {places_rows:,}")
        print(f"PLACES duplicate keys : {duplicate_keys}")
        print(f"Autauga IHME rows     : {ihme_autauga_rows:,}")
        print(f"Autauga PLACES rows   : {places_autauga_rows:,}")
        print("Autauga obesity trend : verified")

    finally:
        con.close()


if __name__ == "__main__":
    main()