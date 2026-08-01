from pathlib import Path
import time

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"
SQL_FILE = PROJECT_ROOT / "database" / "display_labels.sql"


def main() -> None:
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    if not SQL_FILE.exists():
        raise FileNotFoundError(
            f"Display-label SQL not found: {SQL_FILE}"
        )

    print("=" * 72)
    print("Applying display-label layer")
    print("=" * 72)

    started = time.perf_counter()

    con = duckdb.connect(str(DB_FILE))

    try:
        sql = SQL_FILE.read_text(encoding="utf-8")
        con.execute(sql)

        elapsed = time.perf_counter() - started

        print("Display-label layer applied successfully")
        print(f"Elapsed time: {elapsed:,.2f} seconds")

    except Exception:
        print("Display-label layer failed")
        raise

    finally:
        con.close()

    print("=" * 72)


if __name__ == "__main__":
    main()