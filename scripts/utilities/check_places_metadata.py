from pathlib import Path

import duckdb

from app import data_access


DB_PATH = Path(data_access.DB_FILE).resolve()

EXPECTED_COUNTS = {
    2020: 28,
    2021: 30,
    2022: 30,
    2023: 37,
    2024: 40,
    2025: 40,
}

CARRY_FORWARD_2025 = {
    "COLON_SCREEN",
    "DENTAL",
    "MAMMOUSE",
    "SLEEP",
    "TEETHLOST",
}


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Qualification warehouse not found: {DB_PATH}"
        )

    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        # ---------------------------------------------------------
        # Canonical catalog
        # ---------------------------------------------------------
        measure_count = con.execute(
            "SELECT COUNT(*) FROM places.measures"
        ).fetchone()[0]

        assert measure_count == 45, (
            f"Expected 45 canonical measures, got {measure_count}"
        )

        unique_measure_count = con.execute(
            """
            SELECT COUNT(DISTINCT measure_id)
            FROM places.measures
            """
        ).fetchone()[0]

        assert unique_measure_count == measure_count, (
            "Canonical measure IDs are not unique"
        )

        # ---------------------------------------------------------
        # Releases
        # ---------------------------------------------------------
        releases = [
            row[0]
            for row in con.execute(
                """
                SELECT release_year
                FROM places.releases
                ORDER BY release_year
                """
            ).fetchall()
        ]

        assert releases == list(range(2020, 2026)), (
            f"Unexpected releases: {releases}"
        )

        # ---------------------------------------------------------
        # Measure versions
        # ---------------------------------------------------------
        counts = dict(
            con.execute(
                """
                SELECT release_year, COUNT(*)
                FROM places.measure_versions
                GROUP BY release_year
                ORDER BY release_year
                """
            ).fetchall()
        )

        assert counts == EXPECTED_COUNTS, (
            f"Unexpected release counts: {counts}"
        )

        duplicate_versions = con.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    release_year,
                    measure_id,
                    COUNT(*) AS n
                FROM places.measure_versions
                GROUP BY release_year, measure_id
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

        assert duplicate_versions == 0, (
            "Duplicate release-year / measure-id rows found"
        )

        # ---------------------------------------------------------
        # 2025 carry-forward validation
        # ---------------------------------------------------------
        carry_forward_rows = con.execute(
            """
            SELECT measure_id, measurement_year
            FROM places.measure_versions
            WHERE release_year = 2025
              AND carry_forward
            ORDER BY measure_id
            """
        ).fetchall()

        actual_carry_forward = {
            measure_id for measure_id, _ in carry_forward_rows
        }

        assert actual_carry_forward == CARRY_FORWARD_2025, (
            f"Unexpected 2025 carry-forward set: "
            f"{sorted(actual_carry_forward)}"
        )

        carry_forward_years = {
            measurement_year
            for _, measurement_year in carry_forward_rows
        }

        assert carry_forward_years == {2022}, (
            f"Unexpected carry-forward measurement years: "
            f"{sorted(carry_forward_years)}"
        )

        current_years = {
            row[0]
            for row in con.execute(
                """
                SELECT DISTINCT measurement_year
                FROM places.measure_versions
                WHERE release_year = 2025
                  AND NOT carry_forward
                """
            ).fetchall()
        }

        assert current_years == {2023}, (
            f"Unexpected current 2025 measurement years: "
            f"{sorted(current_years)}"
        )

        # ---------------------------------------------------------
        # ISOLATION / LONELINESS boundary
        # ---------------------------------------------------------
        isolation_years = {
            row[0]
            for row in con.execute(
                """
                SELECT release_year
                FROM places.measure_versions
                WHERE measure_id = 'ISOLATION'
                """
            ).fetchall()
        }

        loneliness_years = {
            row[0]
            for row in con.execute(
                """
                SELECT release_year
                FROM places.measure_versions
                WHERE measure_id = 'LONELINESS'
                """
            ).fetchall()
        }

        assert isolation_years == {2024}
        assert loneliness_years == {2025}

        # ---------------------------------------------------------
        # Measurement-year sanity
        # ---------------------------------------------------------
        bad_measurement_years = con.execute(
            """
            SELECT COUNT(*)
            FROM places.measure_versions
            WHERE measurement_year IS NULL
               OR measurement_year > release_year
            """
        ).fetchone()[0]

        assert bad_measurement_years == 0, (
            f"Invalid measurement-year rows: {bad_measurement_years}"
        )

    finally:
        con.close()

    print("=" * 70)
    print("PLACES metadata validation: PASS")
    print("=" * 70)
    print(f"Canonical measures : {measure_count}")
    print(f"Measure versions   : {sum(counts.values())}")
    print(f"Releases           : {len(releases)}")
    print()
    print("Release counts:")
    for year, count in EXPECTED_COUNTS.items():
        print(f"{year}: {count}")
    print()
    print(
        "2025 carry-forward:",
        ", ".join(sorted(CARRY_FORWARD_2025)),
    )
    print("ISOLATION releases :", sorted(isolation_years))
    print("LONELINESS releases:", sorted(loneliness_years))


if __name__ == "__main__":
    main()
