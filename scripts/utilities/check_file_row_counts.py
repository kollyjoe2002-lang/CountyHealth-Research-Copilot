"""
Verify that every successful IHME import contains the expected number of rows.

For each dataset type, this validator compares:

    ihme.import_log.rows_imported

against grouped counts from the corresponding destination table:

    SELECT source_file, COUNT(*)
    FROM ihme.<dataset>
    GROUP BY source_file

This preserves per-file import verification while scanning each dataset table
only once rather than once per imported file.
"""

from pathlib import Path

import duckdb

from app import data_access


DB_FILE = Path(data_access.DB_FILE).resolve()

SUPPORTED_DATASETS = {
    "BMI": "bmi",
    "BURDEN": "burden",
    "PAF": "paf",
}


def main() -> None:
    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"Qualification warehouse not found: {DB_FILE}"
        )

    con = duckdb.connect(str(DB_FILE), read_only=True)

    try:
        records = con.execute(
            """
            SELECT
                file_name,
                dataset_type,
                rows_imported
            FROM ihme.import_log
            WHERE status = 'SUCCESS'
            ORDER BY dataset_type, file_name
            """
        ).fetchall()

        print("=" * 70)
        print("IHME Import Verification")
        print("=" * 70)

        expected_by_dataset = {}

        for file_name, dataset_type, expected_rows in records:
            if dataset_type not in SUPPORTED_DATASETS:
                raise AssertionError(
                    f"Unsupported successful dataset type: {dataset_type}"
                )

            expected_by_dataset.setdefault(
                dataset_type, {}
            )[file_name] = expected_rows

        checked = 0
        mismatches = 0

        for dataset_type, table in SUPPORTED_DATASETS.items():
            expected = expected_by_dataset.get(dataset_type, {})

            if not expected:
                continue

            print(
                f"\nScanning ihme.{table} once for "
                f"{len(expected):,} successful imports..."
            )

            actual = dict(
                con.execute(
                    f"""
                    SELECT
                        source_file,
                        COUNT(*) AS rows
                    FROM ihme.{table}
                    GROUP BY source_file
                    """
                ).fetchall()
            )

            for file_name, expected_rows in expected.items():
                actual_rows = actual.get(file_name, 0)
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

        assert checked == len(records), (
            f"Expected to check {len(records):,} successful imports, "
            f"checked {checked:,}"
        )

        assert mismatches == 0, (
            f"{mismatches:,} imported files do not match ihme.import_log"
        )

        print("\nAll imported files match the import log.")

    finally:
        con.close()


if __name__ == "__main__":
    main()
