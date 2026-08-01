from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"
SQL_FILE = PROJECT_ROOT / "database" / "metadata.sql"

if not DB_FILE.exists():
    raise FileNotFoundError(f"Database not found: {DB_FILE}")

if not SQL_FILE.exists():
    raise FileNotFoundError(f"Metadata SQL not found: {SQL_FILE}")

sql = SQL_FILE.read_text(encoding="utf-8")

print("=" * 70)
print("Applying analytics metadata")
print("=" * 70)

con = duckdb.connect(str(DB_FILE))

try:
    con.execute(sql)

    print("Metadata tables applied successfully")

finally:
    con.close()

print("=" * 70)