"""
Import one IHME CSV file into the correct DuckDB table.
"""

from datetime import datetime
from pathlib import Path
import sys

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"


def classify_file(file_path: Path) -> str:
    """
    Classify an IHME CSV into BURDEN, PAF, or BMI.
    """

    name = file_path.name.upper()

    if "_BURDEN_" in name:
        return "BURDEN"

    if "_PAF_" in name:
        return "PAF"

    if not name.startswith("IHME_USA_BMI_"):
        raise ValueError(
            f"Unexpected IHME filename: {file_path.name}"
        )

    return "BMI"


def sql_quote(value: str) -> str:
    """
    Escape a string for safe use as a SQL string literal.
    """

    return value.replace("'", "''")


def import_file(file_path: Path) -> int:
    """
    Import one CSV file and return the number of rows loaded.
    """

    file_path = file_path.resolve()

    if not file_path.exists():
        raise FileNotFoundError(
            f"File does not exist: {file_path}"
        )

    dataset_type = classify_file(file_path)
    table_name = dataset_type.lower()

    file_name = file_path.name
    file_size_bytes = file_path.stat().st_size
    started_at = datetime.now()

    escaped_path = sql_quote(file_path.as_posix())
    escaped_name = sql_quote(file_name)

    con = duckdb.connect(DB_FILE)

    try:
        existing = con.execute(
            """
            SELECT status
            FROM ihme.import_log
            WHERE file_name = ?
            """,
            [file_name],
        ).fetchone()

        if existing and existing[0] == "SUCCESS":
            print(f"Skipping already imported file: {file_name}")
            return 0

        con.execute(
            """
            INSERT INTO ihme.import_log (
                file_name,
                file_path,
                dataset_type,
                file_size_bytes,
                rows_imported,
                status,
                started_at,
                completed_at,
                error_message
            )
            VALUES (?, ?, ?, ?, NULL, 'STARTED', ?, NULL, NULL)
            ON CONFLICT (file_name) DO UPDATE SET
                file_path = EXCLUDED.file_path,
                dataset_type = EXCLUDED.dataset_type,
                file_size_bytes = EXCLUDED.file_size_bytes,
                rows_imported = NULL,
                status = 'STARTED',
                started_at = EXCLUDED.started_at,
                completed_at = NULL,
                error_message = NULL
            """,
            [
                file_name,
                str(file_path),
                dataset_type,
                file_size_bytes,
                started_at,
            ],
        )

        con.execute("BEGIN TRANSACTION")

        if dataset_type in {"BURDEN", "PAF"}:
            con.execute(
                f"""
                INSERT INTO ihme.{table_name}
                SELECT
                    CAST(measure_id AS BIGINT),
                    CAST(measure_name AS VARCHAR),
                    CAST(location_id AS BIGINT),
                    CAST(location_name AS VARCHAR),

                    CASE
                        WHEN fips IS NULL THEN NULL
                        ELSE LPAD(
                            CAST(CAST(fips AS BIGINT) AS VARCHAR),
                            5,
                            '0'
                        )
                    END,

                    CAST(race_id AS BIGINT),
                    CAST(race_name AS VARCHAR),
                    CAST(sex_id AS BIGINT),
                    CAST(sex_name AS VARCHAR),
                    CAST(age_group_id AS BIGINT),
                    CAST(age_name AS VARCHAR),
                    CAST(cause_id AS BIGINT),
                    CAST(cause_name AS VARCHAR),
                    CAST(year AS INTEGER),
                    CAST(metric_id AS BIGINT),
                    CAST(metric_name AS VARCHAR),
                    CAST(val AS DOUBLE),
                    CAST(upper AS DOUBLE),
                    CAST(lower AS DOUBLE),
                    '{escaped_name}' AS source_file,
                    CURRENT_TIMESTAMP AS imported_at
                FROM read_csv_auto(
                    '{escaped_path}',
                    header = true
                )
                """
            )

        else:
            con.execute(
                f"""
                INSERT INTO ihme.bmi
                SELECT
                    CAST(measure_id AS BIGINT),
                    CAST(measure_name AS VARCHAR),
                    CAST(location_id AS BIGINT),
                    CAST(location_name AS VARCHAR),

                    CASE
                        WHEN fips IS NULL THEN NULL
                        ELSE LPAD(
                            CAST(CAST(fips AS BIGINT) AS VARCHAR),
                            5,
                            '0'
                        )
                    END,

                    CAST(race_id AS BIGINT),
                    CAST(race_name AS VARCHAR),
                    CAST(sex_id AS BIGINT),
                    CAST(sex_name AS VARCHAR),
                    CAST(age_group_id AS BIGINT),
                    CAST(age_name AS VARCHAR),
                    CAST(year AS INTEGER),
                    CAST(metric_id AS BIGINT),
                    CAST(metric_name AS VARCHAR),
                    CAST(metric AS VARCHAR),
                    CAST(val AS DOUBLE),
                    CAST(upper AS DOUBLE),
                    CAST(lower AS DOUBLE),
                    '{escaped_name}' AS source_file,
                    CURRENT_TIMESTAMP AS imported_at
                FROM read_csv_auto(
                    '{escaped_path}',
                    header = true
                )
                """
            )

        rows_imported = con.execute(
            f"""
            SELECT COUNT(*)
            FROM ihme.{table_name}
            WHERE source_file = ?
            """,
            [file_name],
        ).fetchone()[0]

        con.execute("COMMIT")

        con.execute(
            """
            UPDATE ihme.import_log
            SET
                rows_imported = ?,
                status = 'SUCCESS',
                completed_at = ?,
                error_message = NULL
            WHERE file_name = ?
            """,
            [
                rows_imported,
                datetime.now(),
                file_name,
            ],
        )

        print("=" * 70)
        print("Import successful")
        print("=" * 70)
        print(f"File         : {file_name}")
        print(f"Dataset type : {dataset_type}")
        print(f"Table        : ihme.{table_name}")
        print(f"Rows loaded  : {rows_imported:,}")
        print("=" * 70)

        return rows_imported

    except Exception as exc:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass

        con.execute(
            """
            UPDATE ihme.import_log
            SET
                rows_imported = 0,
                status = 'FAILED',
                completed_at = ?,
                error_message = ?
            WHERE file_name = ?
            """,
            [
                datetime.now(),
                str(exc),
                file_name,
            ],
        )

        raise

    finally:
        con.close()


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage:\n"
            "python scripts\\import\\import_file.py "
            "\"path-to-csv-file\""
        )
        raise SystemExit(1)

    import_file(Path(sys.argv[1]))


if __name__ == "__main__":
    main()