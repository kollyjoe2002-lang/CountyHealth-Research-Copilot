from pathlib import Path
import csv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IHME_DIR = PROJECT_ROOT / "data" / "raw" / "ihme"


def inspect_csv_files() -> None:
    if not IHME_DIR.exists():
        raise FileNotFoundError(f"IHME folder not found: {IHME_DIR}")

    csv_files = sorted(IHME_DIR.glob("*.csv"))

    if not csv_files:
        print(f"No CSV files found in: {IHME_DIR}")
        return

    print(f"Project root: {PROJECT_ROOT}")
    print(f"IHME folder: {IHME_DIR}")
    print(f"CSV files found: {len(csv_files)}")
    print("-" * 80)

    for index, file_path in enumerate(csv_files, start=1):
        size_mb = file_path.stat().st_size / (1024 * 1024)

        try:
            with file_path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.reader(file)
                headers = next(reader, [])
        except UnicodeDecodeError:
            with file_path.open("r", encoding="latin-1", newline="") as file:
                reader = csv.reader(file)
                headers = next(reader, [])

        print(f"{index}. {file_path.name}")
        print(f"   Size: {size_mb:,.2f} MB")
        print(f"   Columns: {len(headers)}")
        print(f"   Headers: {headers}")
        print()


if __name__ == "__main__":
    inspect_csv_files()