from pathlib import Path

import duckdb


# verify_database.py is located in:
# project_root/scripts/utilities/verify_database.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

print("=" * 60)
print("CountyHealth Research Copilot")
print("Verifying DuckDB database...")
print("=" * 60)

print(f"\nScript file: {Path(__file__).resolve()}")
print(f"Project root: {PROJECT_ROOT}")
print(f"Database file: {DB_FILE}")

if not DB_FILE.exists():
    raise FileNotFoundError(
        f"\nDatabase not found:\n{DB_FILE}\n"
        "Run scripts\\setup\\create_database.py first."
    )

con = duckdb.connect(str(DB_FILE), read_only=True)

try:
    schemas = con.execute(
        """
        SELECT schema_name
        FROM information_schema.schemata
        ORDER BY schema_name
        """
    ).fetchall()

    tables = con.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema = 'ihme'
        ORDER BY table_name
        """
    ).fetchall()

    print("\nSchemas found:")
    for schema in schemas:
        print(f"  - {schema[0]}")

    print("\nTables in ihme schema:")
    if tables:
        for table_schema, table_name in tables:
            print(f"  - {table_schema}.{table_name}")
    else:
        print("  No tables found.")

    expected_table = ("ihme", "import_log")

    if expected_table not in tables:
        raise RuntimeError(
            "\nVerification failed: ihme.import_log was not found."
        )

    row_count = con.execute(
        "SELECT COUNT(*) FROM ihme.import_log"
    ).fetchone()[0]

    print(f"\nRows currently in ihme.import_log: {row_count}")
    print("\nDatabase verification successful.")

finally:
    con.close()