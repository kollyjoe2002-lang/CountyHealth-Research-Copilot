from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

con = duckdb.connect(DB_FILE)

print("=" * 70)
print("Import Log Summary")
print("=" * 70)

rows = con.execute("""
SELECT
    dataset_type,
    status,
    COUNT(*) AS files,
    SUM(rows_imported) AS rows
FROM ihme.import_log
GROUP BY dataset_type, status
ORDER BY dataset_type, status
""").fetchall()

for row in rows:
    print(row)

print("\nTable Row Counts")
print("-" * 70)

for table in ["burden", "bmi", "paf"]:
    count = con.execute(
        f"SELECT COUNT(*) FROM ihme.{table}"
    ).fetchone()[0]
    print(f"{table.upper():8}: {count:,}")

con.close()