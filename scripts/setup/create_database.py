from pathlib import Path

import duckdb


# create_database.py is located in:
# project_root/scripts/setup/create_database.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

DB_FILE = DATABASE_DIR / "countyhealth.duckdb"

print("=" * 60)
print("CountyHealth Research Copilot")
print("Creating DuckDB database...")
print("=" * 60)

print(f"\nScript file: {Path(__file__).resolve()}")
print(f"Project root: {PROJECT_ROOT}")
print(f"Database directory: {DATABASE_DIR}")

con = duckdb.connect(str(DB_FILE))

con.execute("""
CREATE SCHEMA IF NOT EXISTS ihme;
""")

con.execute("""
CREATE TABLE IF NOT EXISTS ihme.import_log (
    file_name TEXT,
    import_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rows_imported BIGINT,
    status TEXT
);
""")

con.close()

print("\nDatabase created successfully.")
print(DB_FILE)