from pathlib import Path
import csv
import re
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IHME_DIR = PROJECT_ROOT / "data" / "raw" / "ihme"
OUTPUT_FILE = PROJECT_ROOT / "docs" / "ihme_file_inventory.csv"

SEX_VALUES = {"BOTH", "MALE", "FEMALE"}


def parse_filename(filename: str) -> dict:
    stem = Path(filename).stem
    parts = stem.split("_")

    measure_family = ""
    if "_PAF_" in stem:
        measure_family = "PAF"
    elif "_BURDEN_" in stem:
        measure_family = "BURDEN"
    elif "_BMI_" in stem:
        measure_family = "BMI"
    elif "_OBESITY_" in stem:
        measure_family = "OBESITY"
    elif "_OVERWEIGHT_" in stem:
        measure_family = "OVERWEIGHT"

    sex = next((part for part in parts if part in SEX_VALUES), "")

    year_matches = re.findall(r"(?<!Y)(?:19|20)\d{2}", stem)
    data_year = year_matches[-1] if year_matches else ""

    release_match = re.search(r"Y(\d{4})M(\d{2})D(\d{2})", stem)
    release_date = ""
    if release_match:
        release_date = "-".join(release_match.groups())

    size_mb = (IHME_DIR / filename).stat().st_size / (1024 * 1024)

    return {
        "filename": filename,
        "measure_family": measure_family,
        "sex": sex,
        "data_year": data_year,
        "release_date": release_date,
        "size_mb": round(size_mb, 2),
    }


def main() -> None:
    files = sorted(IHME_DIR.glob("*.csv"))

    if not files:
        raise FileNotFoundError(f"No CSV files found in {IHME_DIR}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    rows = [parse_filename(file.name) for file in files]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "filename",
                "measure_family",
                "sex",
                "data_year",
                "release_date",
                "size_mb",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    measure_counts = Counter(row["measure_family"] for row in rows)
    sex_counts = Counter(row["sex"] for row in rows)
    year_counts = Counter(row["data_year"] for row in rows)

    print(f"Files inventoried: {len(rows):,}")
    print(f"Inventory saved to: {OUTPUT_FILE}")

    print("\nMeasure families:")
    for name, count in sorted(measure_counts.items()):
        print(f"  {name or 'Unclassified'}: {count:,}")

    print("\nSex:")
    for name, count in sorted(sex_counts.items()):
        print(f"  {name or 'Unclassified'}: {count:,}")

    print("\nData years:")
    for name, count in sorted(year_counts.items()):
        print(f"  {name or 'Unclassified'}: {count:,}")


if __name__ == "__main__":
    main()