from pathlib import Path
import tempfile

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_FILE = PROJECT_ROOT / "database" / "places" / "schema.sql"

EXPECTED_TABLES = {
    "estimates",
    "import_log",
    "measure_versions",
    "measures",
    "releases",
}


def main() -> None:
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Missing schema file: {SCHEMA_FILE}")

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "places_schema_test.duckdb"

        con = duckdb.connect(str(db_path))

        try:
            con.execute(schema_sql)

            schemas = {
                row[0]
                for row in con.execute(
                    """
                    SELECT schema_name
                    FROM information_schema.schemata
                    """
                ).fetchall()
            }

            if "places" not in schemas:
                raise AssertionError("places schema was not created")

            tables = {
                row[0]
                for row in con.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'places'
                    """
                ).fetchall()
            }

            if tables != EXPECTED_TABLES:
                raise AssertionError(
                    f"Unexpected PLACES tables.\n"
                    f"Expected: {sorted(EXPECTED_TABLES)}\n"
                    f"Actual:   {sorted(tables)}"
                )

        finally:
            con.close()

    print("=" * 60)
    print("PLACES schema validation: PASS")
    print("=" * 60)
    print(f"Schema file : {SCHEMA_FILE}")
    print(f"Tables      : {', '.join(sorted(EXPECTED_TABLES))}")


if __name__ == "__main__":
    main()