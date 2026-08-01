from pathlib import Path

import duckdb


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
IHME_DIR = PROJECT_ROOT / "data" / "raw" / "ihme"
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

print("=" * 60)
print("CountyHealth Research Copilot")
print("Testing import of one IHME CSV file")
print("=" * 60)

print(f"\nIHME folder: {IHME_DIR}")
print(f"Database file: {DB_FILE}")

if not IHME_DIR.exists():
    raise FileNotFoundError(f"IHME folder not found:\n{IHME_DIR}")

if not DB_FILE.exists():
    raise FileNotFoundError(f"Database not found:\n{DB_FILE}")

csv_files = sorted(IHME_DIR.rglob("*.csv"))

if not csv_files:
    raise FileNotFoundError(
        f"No CSV files were found inside:\n{IHME_DIR}"
    )

test_file = csv_files[0]

print(f"\nCSV files found: {len(csv_files):,}")
print(f"Test file selected: {test_file.name}")
print(f"Full file path: {test_file}")

con = duckdb.connect(str(DB_FILE))

try:
    con.execute("DROP TABLE IF EXISTS ihme.test_import")

    con.execute(
        """
        CREATE TABLE ihme.test_import AS
        SELECT *
        FROM read_csv_auto(
            ?,
            header = true,
            sample_size = 100000,
            all_varchar = false
        )
        """,
        [str(test_file)],
    )

    row_count = con.execute(
        "SELECT COUNT(*) FROM ihme.test_import"
    ).fetchone()[0]

    columns = con.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'ihme'
          AND table_name = 'test_import'
        ORDER BY ordinal_position
        """
    ).fetchall()

    preview = con.execute(
        "SELECT * FROM ihme.test_import LIMIT 5"
    ).fetchdf()

    print(f"\nRows imported: {row_count:,}")

    print("\nColumns detected:")
    for column_name, data_type in columns:
        print(f"  - {column_name}: {data_type}")

    print("\nFirst 5 rows:")
    print(preview.to_string(index=False))

    print("\nTest import completed successfully.")

finally:
    con.close()