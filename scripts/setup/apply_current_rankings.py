from pathlib import Path
import time

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"
SQL_FILE = PROJECT_ROOT / "database" / "current_rankings.sql"


def main() -> None:
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    if not SQL_FILE.exists():
        raise FileNotFoundError(
            f"Current-ranking SQL not found: {SQL_FILE}"
        )

    sql = SQL_FILE.read_text(encoding="utf-8")

    print("=" * 72)
    print("Applying current-geography ranking layer")
    print("=" * 72)

    started = time.perf_counter()
    con = duckdb.connect(str(DB_FILE))

    try:
        con.execute(sql)

        elapsed = time.perf_counter() - started

        print(
            "Current-geography ranking layer applied successfully"
        )
        print(f"Elapsed time: {elapsed:,.2f} seconds")

    except Exception:
        print("Current-geography ranking creation failed")
        raise

    finally:
        con.close()

    print("=" * 72)


if __name__ == "__main__":
    main()