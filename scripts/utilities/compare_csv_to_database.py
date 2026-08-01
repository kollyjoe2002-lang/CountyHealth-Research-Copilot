"""
Compare original CSV row counts with rows stored in DuckDB.

For every successfully imported file, this script:

1. Counts rows directly from the source CSV.
2. Counts rows stored in the destination DuckDB table.
3. Reports any mismatch.

This is an end-to-end completeness check.
"""

from pathlib import Path
import sys

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"


def sql_quote(value: str) -> str:
    """
    Escape single quotes for use inside a SQL string literal.
    """

    return value.replace("'", "''")


def main() -> None:
    con = duckdb.connect(str(DB_FILE))

    try:
        records = con.execute(
            """
            SELECT
                file_name,
                file_path,
                dataset_type,
                rows_imported
            FROM ihme.import_log
            WHERE status = 'SUCCESS'
            ORDER BY dataset_type, file_name
            """
        ).fetchall()

        print("=" * 70)
        print("CSV-to-Database Row Count Verification")
        print("=" * 70)
        print(f"Files scheduled for checking: {len(records):,}")

        checked = 0
        mismatches = 0
        missing_files = 0
        errors = 0

        for index, (
            file_name,
            file_path_text,
            dataset_type,
            logged_rows,
        ) in enumerate(records, start=1):

            file_path = Path(file_path_text)
            table_name = dataset_type.lower()

            print(
                f"[{index:,}/{len(records):,}] "
                f"{dataset_type:<7} {file_name}"
            )

            if not file_path.exists():
                missing_files += 1

                print("  MISSING SOURCE FILE")
                print(f"  Path: {file_path}")
                continue

            try:
                escaped_path = sql_quote(file_path.as_posix())

                csv_rows = con.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM read_csv_auto(
                        '{escaped_path}',
                        header = true
                    )
                    """
                ).fetchone()[0]

                database_rows = con.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM ihme.{table_name}
                    WHERE source_file = ?
                    """,
                    [file_name],
                ).fetchone()[0]

                checked += 1

                if (
                    csv_rows != database_rows
                    or database_rows != logged_rows
                ):
                    mismatches += 1

                    print("  MISMATCH")
                    print(f"  CSV rows      : {csv_rows:,}")
                    print(f"  Database rows : {database_rows:,}")
                    print(f"  Logged rows   : {logged_rows:,}")

                else:
                    print(f"  OK: {csv_rows:,} rows")

            except Exception as exc:
                errors += 1

                print("  ERROR")
                print(f"  {exc}")

        print("\n" + "=" * 70)
        print("Verification Summary")
        print("=" * 70)
        print(f"Successful imports found : {len(records):,}")
        print(f"Files checked            : {checked:,}")
        print(f"Mismatches               : {mismatches:,}")
        print(f"Missing source files     : {missing_files:,}")
        print(f"Errors                    : {errors:,}")

        if (
            mismatches == 0
            and missing_files == 0
            and errors == 0
        ):
            print(
                "\n✓ Every checked CSV matches both "
                "the database and import log."
            )
            return

        print(
            "\nVerification failed. Do not start the full import "
            "until the reported issues are resolved."
        )
        raise SystemExit(1)

    finally:
        con.close()


if __name__ == "__main__":
    main()