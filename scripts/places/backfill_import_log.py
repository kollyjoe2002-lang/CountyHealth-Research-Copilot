from pathlib import Path
import sys

import duckdb


EXPECTED_ROWS = {
    2020: 87_976,
    2021: 94_260,
    2022: 94_290,
    2023: 116_291,
    2024: 125_760,
    2025: 125_720,
}


def backfill_import_log(
    db_path: Path,
    places_dir: Path,
) -> None:
    db_path = db_path.resolve()
    places_dir = places_dir.resolve()

    files = {
        year: places_dir
        / (
            "PLACES__County_Data_(GIS_Friendly_Format),_"
            f"{year}_release_20260911.csv"
        )
        for year in EXPECTED_ROWS
    }

    con = duckdb.connect(str(db_path))

    try:
        for year, path in files.items():
            if not path.exists():
                raise FileNotFoundError(path)

            rows = con.execute(
                """
                SELECT COUNT(*)
                FROM places.estimates
                WHERE release_year = ?
                  AND geography_level = 'county'
                """,
                [year],
            ).fetchone()[0]

            expected = EXPECTED_ROWS[year]

            if rows != expected:
                raise AssertionError(
                    f"{year}: expected {expected:,} rows, got {rows:,}"
                )

            con.execute(
                """
                DELETE FROM places.import_log
                WHERE source_file = ?
                """,
                [path.name],
            )

            con.execute(
                """
                INSERT INTO places.import_log (
                    source_file,
                    file_path,
                    release_year,
                    geography_level,
                    file_size_bytes,
                    rows_imported,
                    status,
                    started_at,
                    completed_at,
                    error_message
                )
                VALUES (
                    ?, ?, ?, 'county', ?, ?,
                    'success_backfilled',
                    NULL,
                    CURRENT_TIMESTAMP,
                    NULL
                )
                """,
                [
                    path.name,
                    str(path),
                    year,
                    path.stat().st_size,
                    rows,
                ],
            )

    finally:
        con.close()

    print("PLACES historical import-log backfill: SUCCESS")


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Usage:\n"
            "python scripts\\places\\backfill_import_log.py "
            "\"database.duckdb\" "
            "\"D:\\CDC places data\""
        )
        raise SystemExit(1)

    backfill_import_log(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
    )


if __name__ == "__main__":
    main()
