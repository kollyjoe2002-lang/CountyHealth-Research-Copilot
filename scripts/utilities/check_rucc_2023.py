from pathlib import Path

import duckdb

from scripts.geography.import_rucc_2023 import import_rucc


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_DB = PROJECT_ROOT / "database" / "geography" / "rucc_2023_test.duckdb"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    if TEST_DB.exists():
        TEST_DB.unlink()

    con = duckdb.connect(str(TEST_DB))
    con.close()

    import_rucc(db_path=TEST_DB)

    con = duckdb.connect(str(TEST_DB), read_only=True)

    try:
        total = con.execute(
            """
            SELECT COUNT(*)
            FROM geography.rucc_2023
            """
        ).fetchone()[0]

        classified = con.execute(
            """
            SELECT COUNT(*)
            FROM geography.rucc_2023
            WHERE rucc_code IS NOT NULL
            """
        ).fetchone()[0]

        unclassified = con.execute(
            """
            SELECT COUNT(*)
            FROM geography.rucc_2023
            WHERE rucc_code IS NULL
            """
        ).fetchone()[0]

        distribution = dict(
            con.execute(
                """
                SELECT rucc_code, COUNT(*)
                FROM geography.rucc_2023
                WHERE rucc_code IS NOT NULL
                GROUP BY rucc_code
                ORDER BY rucc_code
                """
            ).fetchall()
        )

        expected_distribution = {
            1: 483,
            2: 398,
            3: 371,
            4: 204,
            5: 81,
            6: 385,
            7: 248,
            8: 468,
            9: 595,
        }

        metro = con.execute(
            """
            SELECT COUNT(*)
            FROM geography.rucc_2023
            WHERE metro_status = 'Metro'
            """
        ).fetchone()[0]

        nonmetro = con.execute(
            """
            SELECT COUNT(*)
            FROM geography.rucc_2023
            WHERE metro_status = 'Nonmetro'
            """
        ).fetchone()[0]

        missing_rows = con.execute(
            """
            SELECT
                fips,
                state_abbr,
                county_name,
                population_2020,
                rucc_description,
                missing_reason
            FROM geography.rucc_2023
            WHERE rucc_code IS NULL
            ORDER BY fips
            """
        ).fetchall()

        assert_true(total == 3235, f"Expected 3,235 rows; got {total}.")
        assert_true(
            classified == 3233,
            f"Expected 3,233 classified rows; got {classified}.",
        )
        assert_true(
            unclassified == 2,
            f"Expected 2 unclassified rows; got {unclassified}.",
        )
        assert_true(
            distribution == expected_distribution,
            f"Unexpected RUCC distribution: {distribution}",
        )
        assert_true(
            metro == 1252,
            f"Expected 1,252 Metro counties; got {metro}.",
        )
        assert_true(
            nonmetro == 1981,
            f"Expected 1,981 Nonmetro counties; got {nonmetro}.",
        )

        expected_missing = [
            (
                "60030",
                "AS",
                "Rose Island",
                0,
                "Not Applicable",
                "RUCC classification not applicable in source",
            ),
            (
                "60040",
                "AS",
                "Swains Island",
                0,
                "Not Applicable",
                "RUCC classification not applicable in source",
            ),
        ]

        assert_true(
            missing_rows == expected_missing,
            f"Unexpected unclassified RUCC rows: {missing_rows}",
        )

        print("RUCC 2023 validation: PASS")
        print(f"Total geographies : {total:,}")
        print(f"Classified RUCC   : {classified:,}")
        print(f"Metro             : {metro:,}")
        print(f"Nonmetro          : {nonmetro:,}")
        print(f"Unclassified      : {unclassified:,}")

    finally:
        con.close()


if __name__ == "__main__":
    main()
