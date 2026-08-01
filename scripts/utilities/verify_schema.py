"""
Verify the CountyHealth DuckDB schema.
"""

from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

EXPECTED_TABLES = [
    "ihme.import_log",
    "ihme.burden",
    "ihme.paf",
    "ihme.bmi",
]

con = duckdb.connect(DB_FILE, read_only=True)

print("=" * 70)
print("CountyHealth schema verification")
print("=" * 70)

tables = con.execute(
    """
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_schema = 'ihme'
    ORDER BY table_name
    """
).fetchall()

existing_tables = {
    f"{schema}.{table}"
    for schema, table in tables
}

print("\nTables found:\n")

for table in sorted(existing_tables):
    print(f"  {table}")

print("\nExpected-table check:\n")

all_present = True

for table in EXPECTED_TABLES:
    if table in existing_tables:
        print(f"  [OK]      {table}")
    else:
        print(f"  [MISSING] {table}")
        all_present = False

print("\nTable columns:\n")

for table in EXPECTED_TABLES:
    if table not in existing_tables:
        continue

    print("-" * 70)
    print(table)
    print("-" * 70)

    columns = con.execute(
        f"DESCRIBE {table}"
    ).fetchall()

    for column in columns:
        column_name = column[0]
        column_type = column[1]
        nullable = column[2]
        print(
            f"{column_name:<22} "
            f"{column_type:<15} "
            f"nullable={nullable}"
        )

con.close()

print("\n" + "=" * 70)

if all_present:
    print("Schema verification passed.")
else:
    print("Schema verification failed: one or more tables are missing.")

print("=" * 70)