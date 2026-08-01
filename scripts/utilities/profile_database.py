"""
Profile the imported IHME database.

This script reports:
- database file size
- table row counts
- distinct dimensions
- year ranges
- null counts
- sample categorical values
"""

from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"


def format_bytes(size_bytes: int) -> str:
    """
    Convert bytes into a readable size.
    """

    value = float(size_bytes)

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:,.2f} {unit}"

        value /= 1024

    return f"{size_bytes:,} B"


def print_section(title: str) -> None:
    """
    Print a section heading.
    """

    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_query(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    parameters: list | None = None,
) -> None:
    """
    Execute and print a query result.
    """

    result = con.execute(
        sql,
        parameters or [],
    )

    columns = [
        description[0]
        for description in result.description
    ]

    rows = result.fetchall()

    print(" | ".join(columns))
    print("-" * 70)

    for row in rows:
        print(
            " | ".join(
                "NULL" if value is None else str(value)
                for value in row
            )
        )


def main() -> None:
    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"Database does not exist: {DB_FILE}"
        )

    con = duckdb.connect(
        str(DB_FILE),
        read_only=True,
    )

    try:
        print("=" * 70)
        print("CountyHealth Database Profile")
        print("=" * 70)
        print(f"Database: {DB_FILE}")
        print(
            f"File size: "
            f"{format_bytes(DB_FILE.stat().st_size)}"
        )

        print_section("Table Row Counts")

        print_query(
            con,
            """
            SELECT
                'ihme.bmi' AS table_name,
                COUNT(*) AS rows
            FROM ihme.bmi

            UNION ALL

            SELECT
                'ihme.burden',
                COUNT(*)
            FROM ihme.burden

            UNION ALL

            SELECT
                'ihme.paf',
                COUNT(*)
            FROM ihme.paf

            ORDER BY table_name
            """,
        )

        print_section("Import Log Status")

        print_query(
            con,
            """
            SELECT
                dataset_type,
                status,
                COUNT(*) AS files,
                SUM(rows_imported) AS rows
            FROM ihme.import_log
            GROUP BY dataset_type, status
            ORDER BY dataset_type, status
            """,
        )

        for table_name in ["bmi", "burden", "paf"]:
            print_section(
                f"{table_name.upper()} Coverage"
            )

            print_query(
                con,
                f"""
                SELECT
                    MIN(year) AS minimum_year,
                    MAX(year) AS maximum_year,
                    COUNT(DISTINCT year) AS years,
                    COUNT(DISTINCT location_id) AS locations,
                    COUNT(DISTINCT fips) AS fips_codes,
                    COUNT(DISTINCT race_id) AS races,
                    COUNT(DISTINCT sex_id) AS sexes,
                    COUNT(DISTINCT age_group_id) AS age_groups,
                    COUNT(DISTINCT measure_id) AS measures,
                    COUNT(DISTINCT metric_id) AS metrics
                FROM ihme.{table_name}
                """,
            )

        print_section("BURDEN Cause Coverage")

        print_query(
            con,
            """
            SELECT
                COUNT(DISTINCT cause_id) AS causes,
                COUNT(DISTINCT cause_name) AS cause_names
            FROM ihme.burden
            """,
        )

        print_section("PAF Cause Coverage")

        print_query(
            con,
            """
            SELECT
                COUNT(DISTINCT cause_id) AS causes,
                COUNT(DISTINCT cause_name) AS cause_names
            FROM ihme.paf
            """,
        )

        print_section("BMI Metric Values")

        print_query(
            con,
            """
            SELECT
                metric,
                COUNT(*) AS rows
            FROM ihme.bmi
            GROUP BY metric
            ORDER BY metric
            """,
        )

        dimension_queries = {
            "Measure Names": """
                SELECT DISTINCT measure_name
                FROM (
                    SELECT measure_name FROM ihme.bmi
                    UNION
                    SELECT measure_name FROM ihme.burden
                    UNION
                    SELECT measure_name FROM ihme.paf
                )
                ORDER BY measure_name
            """,
            "Metric Names": """
                SELECT DISTINCT metric_name
                FROM (
                    SELECT metric_name FROM ihme.bmi
                    UNION
                    SELECT metric_name FROM ihme.burden
                    UNION
                    SELECT metric_name FROM ihme.paf
                )
                ORDER BY metric_name
            """,
            "Sex Values": """
                SELECT DISTINCT sex_id, sex_name
                FROM (
                    SELECT sex_id, sex_name FROM ihme.bmi
                    UNION
                    SELECT sex_id, sex_name FROM ihme.burden
                    UNION
                    SELECT sex_id, sex_name FROM ihme.paf
                )
                ORDER BY sex_id
            """,
            "Race Values": """
                SELECT DISTINCT race_id, race_name
                FROM (
                    SELECT race_id, race_name FROM ihme.bmi
                    UNION
                    SELECT race_id, race_name FROM ihme.burden
                    UNION
                    SELECT race_id, race_name FROM ihme.paf
                )
                ORDER BY race_id
            """,
            "Age Values": """
                SELECT DISTINCT age_group_id, age_name
                FROM (
                    SELECT age_group_id, age_name FROM ihme.bmi
                    UNION
                    SELECT age_group_id, age_name FROM ihme.burden
                    UNION
                    SELECT age_group_id, age_name FROM ihme.paf
                )
                ORDER BY age_group_id
            """,
        }

        for title, sql in dimension_queries.items():
            print_section(title)
            print_query(con, sql)

        print_section("Null FIPS Counts")

        print_query(
            con,
            """
            SELECT
                'BMI' AS dataset_type,
                COUNT(*) FILTER (
                    WHERE fips IS NULL
                ) AS null_fips,
                COUNT(*) AS total_rows
            FROM ihme.bmi

            UNION ALL

            SELECT
                'BURDEN',
                COUNT(*) FILTER (
                    WHERE fips IS NULL
                ),
                COUNT(*)
            FROM ihme.burden

            UNION ALL

            SELECT
                'PAF',
                COUNT(*) FILTER (
                    WHERE fips IS NULL
                ),
                COUNT(*)
            FROM ihme.paf
            """,
        )

        print_section("Sample Causes")

        print_query(
            con,
            """
            SELECT DISTINCT
                cause_id,
                cause_name
            FROM ihme.burden
            ORDER BY cause_name
            LIMIT 50
            """,
        )

        print_section("Sample Locations")

        print_query(
            con,
            """
            SELECT DISTINCT
                location_id,
                location_name,
                fips
            FROM ihme.burden
            WHERE fips IS NOT NULL
            ORDER BY location_name
            LIMIT 50
            """,
        )

        print("\n" + "=" * 70)
        print("Database profiling complete.")
        print("=" * 70)

    finally:
        con.close()


if __name__ == "__main__":
    main()