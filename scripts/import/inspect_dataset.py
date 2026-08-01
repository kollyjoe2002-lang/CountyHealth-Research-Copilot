"""
CountyHealth Research Copilot

Inspect representative IHME datasets
"""

from pathlib import Path
import duckdb

# ----------------------------------------------------------
# Project paths
# ----------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

IHME_DIR = PROJECT_ROOT / "data" / "raw" / "ihme"

DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"


# ----------------------------------------------------------
# Find one representative file
# ----------------------------------------------------------

def find_file(dataset_type: str):
    """
    Find one representative IHME file for the requested dataset family.

    Dataset families:
    - BURDEN: filename contains BURDEN
    - PAF: filename contains PAF
    - BMI: filename contains neither BURDEN nor PAF
    """

    csv_files = sorted(
        list(IHME_DIR.rglob("*.CSV")) +
        list(IHME_DIR.rglob("*.csv"))
    )

    dataset_type = dataset_type.upper()

    for file in csv_files:
        name = file.name.upper()

        if dataset_type == "BURDEN" and "_BURDEN_" in name:
            return file

        if dataset_type == "PAF" and "_PAF_" in name:
            return file

        if (
            dataset_type == "BMI"
            and "_BURDEN_" not in name
            and "_PAF_" not in name
        ):
            return file

    return None

# ----------------------------------------------------------
# Inspect a dataset
# ----------------------------------------------------------

def inspect_dataset(file_path):

    print("=" * 70)
    print(file_path.name)
    print("=" * 70)

    con = duckdb.connect(DB_FILE)

    query = f"""
        DESCRIBE
        SELECT *
        FROM read_csv_auto('{file_path.as_posix()}')
    """

    columns = con.execute(query).fetchall()

    print("\nColumns\n")

    for col in columns:
        print(f"{col[0]:20} {col[1]}")

    rows = con.execute(
        f"""
        SELECT COUNT(*)
        FROM read_csv_auto('{file_path.as_posix()}')
        """
    ).fetchone()[0]

    print(f"\nRows : {rows}")

    preview = con.execute(
        f"""
        SELECT *
        FROM read_csv_auto('{file_path.as_posix()}')
        LIMIT 5
        """
    ).fetchdf()

    print("\nFirst five rows\n")
    print(preview)

    con.close()


# ----------------------------------------------------------
# Main
# ----------------------------------------------------------

burden = find_file("BURDEN")
bmi = find_file("BMI")
paf = find_file("PAF")

print("\nRepresentative files found\n")

print("BURDEN :", burden.name if burden else "Not found")
print("BMI    :", bmi.name if bmi else "Not found")
print("PAF    :", paf.name if paf else "Not found")

print()

inspect_dataset(burden)
inspect_dataset(bmi)
inspect_dataset(paf)