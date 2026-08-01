from pathlib import Path
import time

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"
SQL_FILE = (
    PROJECT_ROOT
    / "database"
    / "remove_redundant_display_overrides.sql"
)


def main() -> None:
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    if not SQL_FILE.exists():
        raise FileNotFoundError(f"SQL file not found: {SQL_FILE}")

    print("=" * 72)
    print("Removing redundant display-label overrides")
    print("=" * 72)

    started = time.perf_counter()

    con = duckdb.connect(str(DB_FILE))

    try:
        con.execute(SQL_FILE.read_text(encoding="utf-8"))

        remaining = con.execute("""
            SELECT COUNT(*)
            FROM analytics.dim_display_label_override
        """).fetchone()[0]

        elapsed = time.perf_counter() - started

        print("Redundant overrides removed successfully")
        print(f"Remaining configured overrides: {remaining:,}")
        print(f"Elapsed time: {elapsed:,.2f} seconds")

    finally:
        con.close()

    print("=" * 72)


if __name__ == "__main__":
    main()