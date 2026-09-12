from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "database" / "countyhealth.duckdb"

EXPECTED = {
    2020: 87_976,
    2021: 94_260,
    2022: 94_290,
    2023: 116_291,
    2024: 125_760,
    2025: 125_720,
}


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        rows = con.execute(
            """
            SELECT
                release_year,
                rows_imported,
                status,
                started_at,
                completed_at,
                error_message
            FROM places.import_log
            WHERE geography_level = 'county'
            ORDER BY release_year
            """
        ).fetchall()

        assert len(rows) == 6, (
            f"Expected 6 historical import-log rows, got {len(rows)}"
        )

        for (
            release_year,
            rows_imported,
            status,
            started_at,
            completed_at,
            error_message,
        ) in rows:
            assert release_year in EXPECTED
            assert rows_imported == EXPECTED[release_year]
            assert status == "success_backfilled"
            assert started_at is None
            assert completed_at is not None
            assert error_message is None

        print("PLACES import-log validation: PASS")

        for row in rows:
            print(row)

    finally:
        con.close()


if __name__ == "__main__":
    main()
