"""
Upgrade ihme.import_log to the current production schema.
"""

from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

con = duckdb.connect(DB_FILE)

row_count = con.execute(
    "SELECT COUNT(*) FROM ihme.import_log"
).fetchone()[0]

print(f"Existing import_log rows: {row_count}")

if row_count == 0:
    con.execute("DROP TABLE ihme.import_log")

    con.execute(
        """
        CREATE TABLE ihme.import_log (
            file_name          VARCHAR PRIMARY KEY,
            file_path          VARCHAR,
            dataset_type       VARCHAR,
            file_size_bytes    BIGINT,
            rows_imported      BIGINT,
            status             VARCHAR,
            started_at         TIMESTAMP,
            completed_at       TIMESTAMP,
            error_message      VARCHAR
        )
        """
    )

    print("Empty legacy import_log replaced successfully.")

else:
    con.execute(
        """
        CREATE TABLE ihme.import_log_new (
            file_name          VARCHAR PRIMARY KEY,
            file_path          VARCHAR,
            dataset_type       VARCHAR,
            file_size_bytes    BIGINT,
            rows_imported      BIGINT,
            status             VARCHAR,
            started_at         TIMESTAMP,
            completed_at       TIMESTAMP,
            error_message      VARCHAR
        )
        """
    )

    con.execute(
        """
        INSERT INTO ihme.import_log_new (
            file_name,
            dataset_type,
            rows_imported,
            status,
            completed_at,
            error_message
        )
        SELECT
            filename,
            measure_family,
            records_loaded,
            status,
            imported_at,
            error_message
        FROM ihme.import_log
        """
    )

    con.execute("DROP TABLE ihme.import_log")
    con.execute(
        "ALTER TABLE ihme.import_log_new RENAME TO import_log"
    )

    print(f"Migrated {row_count} legacy rows successfully.")

con.close()

print("Import-log upgrade complete.")