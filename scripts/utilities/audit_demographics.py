from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.data_access import DB_FILE, run_query  # noqa: E402


LINE = "=" * 80
BURDEN_TABLE = "ihme.burden"


def heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def show_table_columns(table_name: str) -> None:
    sql = f"""
    DESCRIBE {table_name}
    """

    result = run_query(sql)

    print(result.to_string(index=False))


def warehouse_summary(table_name: str) -> None:
    sql = f"""
    SELECT
        COUNT(*) AS rows,
        COUNT(DISTINCT year) AS years,
        MIN(year) AS first_year,
        MAX(year) AS last_year,
        COUNT(DISTINCT location_id) AS locations,
        COUNT(DISTINCT cause_id) AS causes
    FROM {table_name}
    """

    result = run_query(sql)

    print(result.to_string(index=False))


def column_exists(
    available_columns: set[str],
    column_name: str,
) -> bool:
    return column_name.lower() in available_columns


def show_dimension(
    table_name: str,
    available_columns: set[str],
    id_column: str,
    name_column: str,
    label: str,
) -> None:
    heading(label)

    id_exists = column_exists(
        available_columns,
        id_column,
    )

    name_exists = column_exists(
        available_columns,
        name_column,
    )

    if not id_exists and not name_exists:
        print(
            f"Neither {id_column} nor {name_column} exists "
            f"in {table_name}."
        )
        return

    if id_exists and name_exists:
        sql = f"""
        SELECT
            {id_column},
            {name_column},
            COUNT(*) AS records
        FROM {table_name}
        GROUP BY
            {id_column},
            {name_column}
        ORDER BY
            {id_column},
            {name_column}
        """
    elif name_exists:
        sql = f"""
        SELECT
            {name_column},
            COUNT(*) AS records
        FROM {table_name}
        GROUP BY
            {name_column}
        ORDER BY
            {name_column}
        """
    else:
        sql = f"""
        SELECT
            {id_column},
            COUNT(*) AS records
        FROM {table_name}
        GROUP BY
            {id_column}
        ORDER BY
            {id_column}
        """

    result = run_query(sql)

    if result.empty:
        print("No values found.")
    else:
        print(result.to_string(index=False))


def null_check(
    table_name: str,
    available_columns: set[str],
) -> None:
    heading("Null demographic values")

    checks: list[str] = []

    for column_name in [
        "sex_id",
        "sex_name",
        "race_id",
        "race_name",
        "age_group_id",
        "age_name",
    ]:
        if column_exists(
            available_columns,
            column_name,
        ):
            checks.append(
                f"""
                SUM(
                    CASE
                        WHEN {column_name} IS NULL
                        THEN 1
                        ELSE 0
                    END
                ) AS null_{column_name}
                """
            )

    if not checks:
        print(
            "No demographic columns are present, "
            "so no demographic NULL check can be run."
        )
        return

    sql = f"""
    SELECT
        {", ".join(checks)}
    FROM {table_name}
    """

    result = run_query(sql)

    print(result.to_string(index=False))


def duplicate_check(
    table_name: str,
    available_columns: set[str],
) -> None:
    heading("Duplicate key check")

    candidate_key_columns = [
        "location_id",
        "cause_id",
        "sex_id",
        "race_id",
        "age_group_id",
        "year",
    ]

    key_columns = [
        column_name
        for column_name in candidate_key_columns
        if column_exists(
            available_columns,
            column_name,
        )
    ]

    if not key_columns:
        print(
            "No suitable key columns were found "
            "for duplicate checking."
        )
        return

    grouped_columns = ",\n            ".join(
        key_columns
    )

    sql = f"""
    SELECT
        COUNT(*) AS duplicate_groups
    FROM (
        SELECT
            {grouped_columns},
            COUNT(*) AS records
        FROM {table_name}
        GROUP BY
            {grouped_columns}
        HAVING COUNT(*) > 1
    )
    """

    result = run_query(sql)

    print(
        "Key columns used:"
    )
    print(
        ", ".join(key_columns)
    )
    print()
    print(result.to_string(index=False))


def distinct_counts(
    table_name: str,
    available_columns: set[str],
) -> None:
    heading("Distinct dimension counts")

    expressions: list[str] = []

    for column_name in [
        "sex_id",
        "sex_name",
        "race_id",
        "race_name",
        "age_group_id",
        "age_name",
    ]:
        if column_exists(
            available_columns,
            column_name,
        ):
            expressions.append(
                f"""
                COUNT(
                    DISTINCT {column_name}
                ) AS distinct_{column_name}
                """
            )

    if not expressions:
        print(
            "No sex, race, or age columns were found."
        )
        return

    sql = f"""
    SELECT
        {", ".join(expressions)}
    FROM {table_name}
    """

    result = run_query(sql)

    print(result.to_string(index=False))


def main() -> None:
    print(LINE)
    print("CountyHealth Warehouse Demographic Audit")
    print(LINE)

    print(f"Database: {DB_FILE}")
    print(f"Warehouse table: {BURDEN_TABLE}")

    heading("Warehouse table columns")

    columns = run_query(
        f"DESCRIBE {BURDEN_TABLE}"
    )

    print(columns.to_string(index=False))

    available_columns = {
        str(column_name).lower()
        for column_name in columns["column_name"].tolist()
    }

    heading("Warehouse summary")

    warehouse_summary(
        BURDEN_TABLE
    )

    distinct_counts(
        BURDEN_TABLE,
        available_columns,
    )

    show_dimension(
        table_name=BURDEN_TABLE,
        available_columns=available_columns,
        id_column="sex_id",
        name_column="sex_name",
        label="Sex",
    )

    show_dimension(
        table_name=BURDEN_TABLE,
        available_columns=available_columns,
        id_column="race_id",
        name_column="race_name",
        label="Race / ethnicity",
    )

    show_dimension(
        table_name=BURDEN_TABLE,
        available_columns=available_columns,
        id_column="age_group_id",
        name_column="age_name",
        label="Age groups",
    )

    null_check(
        BURDEN_TABLE,
        available_columns,
    )

    duplicate_check(
        BURDEN_TABLE,
        available_columns,
    )

    print()
    print(LINE)
    print("Warehouse audit completed successfully")
    print(LINE)


if __name__ == "__main__":
    main()