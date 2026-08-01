"""
Import all discovered IHME CSV files into DuckDB.

Features:
- Resumes safely after interruption
- Skips files already marked SUCCESS
- Supports dataset filtering
- Supports small test batches with --limit
- Continues after individual file failures by default
"""

import argparse
import time
from collections import Counter
from pathlib import Path

import duckdb

from discover_files import discover_files
from import_file import import_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"


def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description="Import IHME CSV files into DuckDB."
    )

    parser.add_argument(
        "--dataset",
        choices=["BURDEN", "PAF", "BMI"],
        help="Import only one dataset family.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of pending files to import.",
    )

    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately when a file fails.",
    )

    return parser.parse_args()


def get_successful_files() -> set[str]:
    """
    Return filenames already imported successfully.
    """

    con = duckdb.connect(str(DB_FILE), read_only=True)

    try:
        rows = con.execute(
            """
            SELECT file_name
            FROM ihme.import_log
            WHERE status = 'SUCCESS'
            """
        ).fetchall()

        return {row[0] for row in rows}

    finally:
        con.close()


def format_duration(seconds: float) -> str:
    """
    Convert seconds into a readable duration.
    """

    seconds = int(seconds)

    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes}m {seconds}s"

    if minutes:
        return f"{minutes}m {seconds}s"

    return f"{seconds}s"


def main() -> None:
    args = parse_arguments()

    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1.")

    discovered = discover_files()
    successful_files = get_successful_files()

    if args.dataset:
        discovered = [
            file_info
            for file_info in discovered
            if file_info["dataset_type"] == args.dataset
        ]

    pending_files = [
        file_info
        for file_info in discovered
        if file_info["file_name"] not in successful_files
    ]

    if args.limit is not None:
        pending_files = pending_files[:args.limit]

    counts = Counter(
        file_info["dataset_type"]
        for file_info in pending_files
    )

    total_size_bytes = sum(
        file_info["file_size_bytes"]
        for file_info in pending_files
    )

    total_size_gb = total_size_bytes / (1024 ** 3)

    print("=" * 70)
    print("IHME Batch Import")
    print("=" * 70)
    print(f"Database             : {DB_FILE}")
    print(f"Discovered files     : {len(discovered):,}")
    print(f"Already successful   : {len(successful_files):,}")
    print(f"Files in this run    : {len(pending_files):,}")
    print(f"Source size this run : {total_size_gb:,.2f} GB")

    if args.dataset:
        print(f"Dataset filter       : {args.dataset}")

    print("\nFiles scheduled by dataset:")

    for dataset_type in ["BURDEN", "PAF", "BMI"]:
        print(
            f"  {dataset_type:<8} "
            f"{counts.get(dataset_type, 0):,}"
        )

    if not pending_files:
        print("\nNo pending files matched this request.")
        print("=" * 70)
        return

    print("\nStarting import...\n")

    batch_started = time.time()

    imported_files = 0
    failed_files = 0
    total_rows = 0

    for index, file_info in enumerate(pending_files, start=1):
        file_path = Path(file_info["file_path"])
        file_size_mb = file_info["file_size_bytes"] / (1024 ** 2)

        print("-" * 70)
        print(
            f"[{index:,}/{len(pending_files):,}] "
            f"{file_info['dataset_type']} | "
            f"{file_size_mb:,.2f} MB"
        )
        print(file_info["file_name"])

        file_started = time.time()

        try:
            rows_imported = import_file(file_path)

            imported_files += 1
            total_rows += rows_imported

            elapsed = time.time() - file_started

            print(
                f"File duration : {format_duration(elapsed)}"
            )

        except Exception as exc:
            failed_files += 1

            print(f"IMPORT FAILED: {exc}")

            if args.stop_on_error:
                print("\nStopping because --stop-on-error was used.")
                raise

    total_elapsed = time.time() - batch_started

    print("\n" + "=" * 70)
    print("Batch Import Summary")
    print("=" * 70)
    print(f"Files scheduled : {len(pending_files):,}")
    print(f"Files imported  : {imported_files:,}")
    print(f"Files failed    : {failed_files:,}")
    print(f"Rows imported   : {total_rows:,}")
    print(f"Total duration  : {format_duration(total_elapsed)}")
    print("=" * 70)

    if failed_files:
        raise SystemExit(1)


if __name__ == "__main__":
    main()