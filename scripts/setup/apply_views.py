from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"
VIEWS_FILE = PROJECT_ROOT / "database" / "views.sql"


def main() -> None:
    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_FILE}"
        )

    if not VIEWS_FILE.exists():
        raise FileNotFoundError(
            f"Views file not found: {VIEWS_FILE}"
        )

    sql = VIEWS_FILE.read_text(encoding="utf-8")

    con = duckdb.connect(str(DB_FILE))

    try:
        con.execute(sql)
        print("=" * 70)
        print("Views applied successfully")
        print("=" * 70)

    finally:
        con.close()


if __name__ == "__main__":
    main()