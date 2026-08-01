from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_FILE = PROJECT_ROOT / "database" / "countyhealth.duckdb"

LINE = "=" * 88
SUBLINE = "-" * 88

TARGET_SCHEMA = "ihme"
PREFERRED_TABLES = ("burden", "bmi", "paf")

DIMENSIONS = (
    ("Sex", "sex_id", "sex_name"),
    ("Race / ethnicity", "race_id", "race_name"),
    ("Age group", "age_group_id", "age_name"),
    ("Measure", "measure_id", "measure_name"),
    ("Metric", "metric_id", "metric_name"),
)

POSSIBLE_KEY_COLUMNS = (
    "measure_id",
    "metric_id",
    "metric",
    "location_id",
    "fips",
    "cause_id",
    "sex_id",
    "race_id",
    "age_group_id",
    "year",
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect the CountyHealth DuckDB warehouse."
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_FILE,
        help="Path to countyhealth.duckdb.",
    )

    parser.add_argument(
        "--table",
        action="append",
        help=(
            "Inspect only a named table. May be used more than once, "
            "for example: --table burden --table paf"
        ),
    )

    parser.add_argument(
        "--deep",
        action="store_true",
        help=(
            "Run expensive integrity checks, including exact duplicate-key "
            "analysis. This may take substantial time on very large tables."
        ),
    )

    parser.add_argument(
        "--csv-dir",
        type=Path,
        help="Optional directory in which to save audit result CSV files.",
    )

    return parser.parse_args()


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def qualified_name(schema_name: str, table_name: str) -> str:
    return (
        f"{quote_identifier(schema_name)}."
        f"{quote_identifier(table_name)}"
    )


def print_heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def print_dataframe(
    dataframe: pd.DataFrame,
    *,
    empty_message: str = "No results found.",
) -> None:
    if dataframe.empty:
        print(empty_message)
        return

    with pd.option_context(
        "display.max_rows",
        None,
        "display.max_columns",
        None,
        "display.width",
        240,
        "display.max_colwidth",
        90,
    ):
        print(dataframe.to_string(index=False))


def save_dataframe(
    dataframe: pd.DataFrame,
    csv_dir: Path | None,
    filename: str,
) -> None:
    if csv_dir is None:
        return

    csv_dir.mkdir(parents=True, exist_ok=True)
    output_file = csv_dir / filename
    dataframe.to_csv(output_file, index=False)


def get_tables(
    connection: duckdb.DuckDBPyConnection,
    schema_name: str,
) -> pd.DataFrame:
    return connection.execute(
        """
        SELECT
            table_schema,
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_schema = ?
        ORDER BY table_name
        """,
        [schema_name],
    ).fetchdf()


def resolve_requested_tables(
    available_tables: Iterable[str],
    requested_tables: list[str] | None,
) -> list[str]:
    available = list(available_tables)
    available_lookup = {
        table_name.lower(): table_name
        for table_name in available
    }

    if requested_tables:
        resolved: list[str] = []

        for requested in requested_tables:
            normalized = requested.lower()

            if "." in normalized:
                normalized = normalized.split(".")[-1]

            if normalized not in available_lookup:
                raise ValueError(
                    f"Table '{requested}' was not found in schema "
                    f"'{TARGET_SCHEMA}'. Available tables: "
                    f"{', '.join(available)}"
                )

            actual_name = available_lookup[normalized]

            if actual_name not in resolved:
                resolved.append(actual_name)

        return resolved

    preferred = [
        available_lookup[table_name]
        for table_name in PREFERRED_TABLES
        if table_name in available_lookup
    ]

    remaining = [
        table_name
        for table_name in available
        if table_name not in preferred
    ]

    return preferred


def get_columns(
    connection: duckdb.DuckDBPyConnection,
    schema_name: str,
    table_name: str,
) -> pd.DataFrame:
    return connection.execute(
        """
        SELECT
            ordinal_position,
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = ?
          AND table_name = ?
        ORDER BY ordinal_position
        """,
        [schema_name, table_name],
    ).fetchdf()


def build_summary_query(
    schema_name: str,
    table_name: str,
    columns: set[str],
) -> str:
    table = qualified_name(schema_name, table_name)

    expressions = [
        "COUNT(*) AS row_count",
    ]

    distinct_candidates = (
        "location_id",
        "fips",
        "cause_id",
        "year",
        "measure_id",
        "metric_id",
        "sex_id",
        "race_id",
        "age_group_id",
        "source_file",
    )

    for column in distinct_candidates:
        if column in columns:
            quoted = quote_identifier(column)
            expressions.append(
                f"COUNT(DISTINCT {quoted}) AS distinct_{column}"
            )

    if "year" in columns:
        expressions.extend(
            [
                'MIN("year") AS first_year',
                'MAX("year") AS last_year',
            ]
        )

    return f"""
    SELECT
        {", ".join(expressions)}
    FROM {table}
    """


def get_dimension_values(
    connection: duckdb.DuckDBPyConnection,
    schema_name: str,
    table_name: str,
    columns: set[str],
    id_column: str,
    name_column: str,
) -> pd.DataFrame:
    table = qualified_name(schema_name, table_name)

    id_exists = id_column in columns
    name_exists = name_column in columns

    if not id_exists and not name_exists:
        return pd.DataFrame()

    selected_columns: list[str] = []
    grouped_columns: list[str] = []
    ordered_columns: list[str] = []

    if id_exists:
        quoted_id = quote_identifier(id_column)
        selected_columns.append(quoted_id)
        grouped_columns.append(quoted_id)
        ordered_columns.append(quoted_id)

    if name_exists:
        quoted_name = quote_identifier(name_column)
        selected_columns.append(quoted_name)
        grouped_columns.append(quoted_name)
        ordered_columns.append(quoted_name)

    return connection.execute(
        f"""
        SELECT
            {", ".join(selected_columns)},
            COUNT(*) AS records
        FROM {table}
        GROUP BY
            {", ".join(grouped_columns)}
        ORDER BY
            {", ".join(ordered_columns)}
        """
    ).fetchdf()


def get_null_report(
    connection: duckdb.DuckDBPyConnection,
    schema_name: str,
    table_name: str,
    columns: set[str],
) -> pd.DataFrame:
    table = qualified_name(schema_name, table_name)

    candidate_columns = (
        "measure_id",
        "measure_name",
        "location_id",
        "location_name",
        "fips",
        "race_id",
        "race_name",
        "sex_id",
        "sex_name",
        "age_group_id",
        "age_name",
        "cause_id",
        "cause_name",
        "year",
        "metric_id",
        "metric_name",
        "val",
        "upper",
        "lower",
    )

    expressions: list[str] = []

    for column in candidate_columns:
        if column in columns:
            quoted = quote_identifier(column)
            alias = quote_identifier(f"null_{column}")
            expressions.append(
                f"COUNT(*) FILTER (WHERE {quoted} IS NULL) AS {alias}"
            )

    if not expressions:
        return pd.DataFrame()

    return connection.execute(
        f"""
        SELECT
            {", ".join(expressions)}
        FROM {table}
        """
    ).fetchdf()


def get_location_report(
    connection: duckdb.DuckDBPyConnection,
    schema_name: str,
    table_name: str,
    columns: set[str],
) -> pd.DataFrame:
    table = qualified_name(schema_name, table_name)

    expressions = [
        "COUNT(*) AS rows",
    ]

    if "location_id" in columns:
        expressions.append(
            'COUNT(DISTINCT "location_id") AS distinct_locations'
        )

    if "location_name" in columns:
        expressions.append(
            'COUNT(DISTINCT "location_name") AS distinct_location_names'
        )

    if "fips" in columns:
        expressions.extend(
            [
                'COUNT(DISTINCT "fips") AS distinct_non_null_fips',
                (
                    'COUNT(*) FILTER '
                    '(WHERE "fips" IS NULL OR TRIM(CAST("fips" AS VARCHAR)) = \'\') '
                    "AS rows_missing_fips"
                ),
                (
                    'COUNT(DISTINCT "location_id") FILTER '
                    '(WHERE "fips" IS NULL OR TRIM(CAST("fips" AS VARCHAR)) = \'\') '
                    "AS locations_missing_fips"
                    if "location_id" in columns
                    else (
                        'COUNT(DISTINCT "location_name") FILTER '
                        '(WHERE "fips" IS NULL OR TRIM(CAST("fips" AS VARCHAR)) = \'\') '
                        "AS locations_missing_fips"
                    )
                ),
            ]
        )

    return connection.execute(
        f"""
        SELECT
            {", ".join(expressions)}
        FROM {table}
        """
    ).fetchdf()


def get_locations_without_fips(
    connection: duckdb.DuckDBPyConnection,
    schema_name: str,
    table_name: str,
    columns: set[str],
) -> pd.DataFrame:
    required = {"fips"}

    if not required.issubset(columns):
        return pd.DataFrame()

    table = qualified_name(schema_name, table_name)

    selected: list[str] = []

    if "location_id" in columns:
        selected.append('"location_id"')

    if "location_name" in columns:
        selected.append('"location_name"')

    if not selected:
        return pd.DataFrame()

    return connection.execute(
        f"""
        SELECT DISTINCT
            {", ".join(selected)}
        FROM {table}
        WHERE "fips" IS NULL
           OR TRIM("fips") = ''
        ORDER BY
            {", ".join(selected)}
        LIMIT 100
        """
    ).fetchdf()


def get_duplicate_report(
    connection: duckdb.DuckDBPyConnection,
    schema_name: str,
    table_name: str,
    columns: set[str],
) -> tuple[pd.DataFrame, list[str]]:
    key_columns = [
        column
        for column in POSSIBLE_KEY_COLUMNS
        if column in columns
    ]

    if not key_columns:
        return pd.DataFrame(), []

    table = qualified_name(schema_name, table_name)
    grouped = ", ".join(
        quote_identifier(column)
        for column in key_columns
    )

    result = connection.execute(
        f"""
        SELECT
            COUNT(*) AS duplicate_groups,
            COALESCE(SUM(records - 1), 0) AS excess_rows
        FROM (
            SELECT
                {grouped},
                COUNT(*) AS records
            FROM {table}
            GROUP BY
                {grouped}
            HAVING COUNT(*) > 1
        )
        """
    ).fetchdf()

    return result, key_columns


def inspect_table(
    connection: duckdb.DuckDBPyConnection,
    schema_name: str,
    table_name: str,
    *,
    deep: bool,
    csv_dir: Path | None,
) -> None:
    started = time.perf_counter()
    full_name = f"{schema_name}.{table_name}"

    print()
    print(LINE)
    print(f"TABLE: {full_name}")
    print(LINE)

    columns_df = get_columns(
        connection,
        schema_name,
        table_name,
    )

    columns = {
        str(column).lower()
        for column in columns_df["column_name"].tolist()
    }

    print_heading("Columns")
    print_dataframe(columns_df)
    save_dataframe(
        columns_df,
        csv_dir,
        f"{table_name}_columns.csv",
    )

    print_heading("Warehouse summary")

    summary_df = connection.execute(
        build_summary_query(
            schema_name,
            table_name,
            columns,
        )
    ).fetchdf()

    print_dataframe(summary_df)
    save_dataframe(
        summary_df,
        csv_dir,
        f"{table_name}_summary.csv",
    )

    for label, id_column, name_column in DIMENSIONS:
        print_heading(label)

        values_df = get_dimension_values(
            connection,
            schema_name,
            table_name,
            columns,
            id_column,
            name_column,
        )

        print_dataframe(
            values_df,
            empty_message=(
                f"{id_column} and {name_column} are not present "
                f"in {full_name}."
            ),
        )

        if not values_df.empty:
            save_dataframe(
                values_df,
                csv_dir,
                f"{table_name}_{id_column.removesuffix('_id')}.csv",
            )

    print_heading("Location and FIPS coverage")

    location_df = get_location_report(
        connection,
        schema_name,
        table_name,
        columns,
    )

    print_dataframe(location_df)
    save_dataframe(
        location_df,
        csv_dir,
        f"{table_name}_location_coverage.csv",
    )

    no_fips_df = get_locations_without_fips(
        connection,
        schema_name,
        table_name,
        columns,
    )

    if not no_fips_df.empty:
        print()
        print("First 100 distinct locations without FIPS:")
        print_dataframe(no_fips_df)

        save_dataframe(
            no_fips_df,
            csv_dir,
            f"{table_name}_locations_without_fips.csv",
        )

    print_heading("Null-value report")

    null_df = get_null_report(
        connection,
        schema_name,
        table_name,
        columns,
    )

    print_dataframe(null_df)
    save_dataframe(
        null_df,
        csv_dir,
        f"{table_name}_nulls.csv",
    )

    print_heading("Duplicate logical-key check")

    if not deep:
        print(
            "Skipped in standard mode because this table may contain "
            "hundreds of millions of rows."
        )
        print(
            "Run again with --deep to perform the exact duplicate-key check."
        )
    else:
        duplicate_df, key_columns = get_duplicate_report(
            connection,
            schema_name,
            table_name,
            columns,
        )

        if not key_columns:
            print("No suitable logical-key columns were found.")
        else:
            print("Candidate logical key:")
            print(", ".join(key_columns))
            print()
            print_dataframe(duplicate_df)

            save_dataframe(
                duplicate_df,
                csv_dir,
                f"{table_name}_duplicates.csv",
            )

    elapsed = time.perf_counter() - started

    print()
    print(f"Inspection time: {elapsed:,.1f} seconds")


def main() -> int:
    arguments = parse_arguments()
    db_file = arguments.db.resolve()

    if not db_file.exists():
        print(
            f"ERROR: Database file was not found:\n{db_file}",
            file=sys.stderr,
        )
        return 1

    print(LINE)
    print("CountyHealth Warehouse Inspector")
    print(LINE)
    print(f"Database: {db_file}")
    print(f"Schema:   {TARGET_SCHEMA}")
    print(f"Mode:     {'deep' if arguments.deep else 'standard'}")

    try:
        connection = duckdb.connect(
            str(db_file),
            read_only=True,
        )
    except Exception as exc:
        print(
            f"ERROR: Could not open the database: {exc}",
            file=sys.stderr,
        )
        return 1

    try:
        tables_df = get_tables(
            connection,
            TARGET_SCHEMA,
        )

        print_heading("Available IHME tables")
        print_dataframe(tables_df)

        if tables_df.empty:
            print(
                f"No tables were found in schema '{TARGET_SCHEMA}'.",
                file=sys.stderr,
            )
            return 1

        table_names = resolve_requested_tables(
            tables_df["table_name"].tolist(),
            arguments.table,
        )

        print()
        print("Tables selected for inspection:")
        print(", ".join(table_names))

        if arguments.csv_dir is not None:
            csv_dir = arguments.csv_dir.resolve()
            csv_dir.mkdir(parents=True, exist_ok=True)
            tables_df.to_csv(
                csv_dir / "ihme_tables.csv",
                index=False,
            )
            print(f"CSV output directory: {csv_dir}")
        else:
            csv_dir = None

        for table_name in table_names:
            inspect_table(
                connection,
                TARGET_SCHEMA,
                table_name,
                deep=arguments.deep,
                csv_dir=csv_dir,
            )

    except KeyboardInterrupt:
        print("\nInspection cancelled.")
        return 130
    except Exception as exc:
        print(
            f"\nERROR: Warehouse inspection failed: {exc}",
            file=sys.stderr,
        )
        return 1
    finally:
        connection.close()

    print()
    print(LINE)
    print("Warehouse inspection completed successfully")
    print(LINE)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())