"""
Discover and classify IHME CSV files.
"""

from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IHME_DIR = PROJECT_ROOT / "data" / "raw" / "ihme"


def classify_file(file_path: Path) -> str:
    """
    Classify an IHME CSV into one of the three dataset families.
    """

    name = file_path.name.upper()

    if "_BURDEN_" in name:
        return "BURDEN"

    if "_PAF_" in name:
        return "PAF"

    if not name.startswith("IHME_USA_BMI_"):
        raise ValueError(
            f"Unexpected filename: {file_path.name}"
        )

    return "BMI"

def discover_files() -> list[dict]:
    """
    Return metadata for every CSV file in the IHME directory.
    """

    csv_files = sorted(
        file_path
        for file_path in IHME_DIR.rglob("*")
        if file_path.is_file()
        and file_path.suffix.lower() == ".csv"
    )

    discovered = []

    for file_path in csv_files:
        discovered.append(
            {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "dataset_type": classify_file(file_path),
                "file_size_bytes": file_path.stat().st_size,
            }
        )

    return discovered


def main() -> None:
    files = discover_files()

    counts = Counter(
        file_info["dataset_type"]
        for file_info in files
    )

    print("=" * 70)
    print("IHME File Discovery")
    print("=" * 70)

    print(f"\nDirectory: {IHME_DIR}")
    print(f"Total CSV files: {len(files):,}")

    print("\nFiles by dataset type:\n")

    for dataset_type in ["BURDEN", "PAF", "BMI"]:
        print(
            f"  {dataset_type:<8} {counts.get(dataset_type, 0):,}"
        )

    print("\nFirst five files:\n")

    for file_info in files[:5]:
        size_mb = file_info["file_size_bytes"] / (1024 ** 2)

        print(
            f"{file_info['dataset_type']:<8}"
            f"{size_mb:10.2f} MB  "
            f"{file_info['file_name']}"
        )

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()