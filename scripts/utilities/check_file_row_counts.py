"""
Verify that every imported IHME file contains the expected number of rows.

This script compares:
    import_log.rows_imported

against

    COUNT(*) FROM destination_table
    WHERE source_file = file_name

Any mismatch indicates a failed or partial import.
"""

from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"


def main() -> None:
    con = duckdb.connect(DB_FILE)

    records = con.execute(
        """
        SELECT
            file_name,
            dataset_type,
            rows_imported,
            status
        FROM ihme.import_log
        ORDER BY dataset_type, file_name
        """
    ).fetchall()

    print("=" * 70)
    print("IHME Import Verification")
    print("=" * 70)

    checked = 0
    mismatches = 0

    for file_name, dataset_type, expected_rows, status in records:

        if status != "SUCCESS":
            continue

        table = dataset_type.lower()

        actual_rows = con.execute(
            f"""
            SELECT COUNT(*)
            FROM ihme.{table}
            WHERE source_file = ?
            """,
            [file_name],
        ).fetchone()[0]

        checked += 1

        if actual_rows != expected_rows:
            mismatches += 1

            print("\nMismatch detected")
            print("-" * 70)
            print(f"File      : {file_name}")
            print(f"Dataset   : {dataset_type}")
            print(f"Expected  : {expected_rows:,}")
            print(f"Actual    : {actual_rows:,}")

    print("\n" + "=" * 70)
    print("Verification Summary")
    print("=" * 70)
    print(f"Files checked : {checked:,}")
    print(f"Mismatches    : {mismatches:,}")

    if mismatches == 0:
        print("\n✓ All imported files match the import log.")

    con.close()


if __name__ == "__main__":
    main()