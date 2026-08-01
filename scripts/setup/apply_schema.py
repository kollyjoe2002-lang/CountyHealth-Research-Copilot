"""
CountyHealth Research Copilot

Apply database/schema.sql to DuckDB.
"""

from pathlib import Path
import duckdb

# -------------------------------------------------------
# Paths
# -------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"
SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"

print("=" * 60)
print("Applying database schema")
print("=" * 60)

print(f"\nDatabase : {DB_FILE}")
print(f"Schema   : {SCHEMA_FILE}")

# -------------------------------------------------------
# Read SQL
# -------------------------------------------------------

sql = SCHEMA_FILE.read_text(encoding="utf-8")

# -------------------------------------------------------
# Execute
# -------------------------------------------------------

con = duckdb.connect(DB_FILE)

con.execute(sql)

con.close()

print("\nSchema applied successfully.")