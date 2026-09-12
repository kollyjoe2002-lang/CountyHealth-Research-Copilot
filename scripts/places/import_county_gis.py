from pathlib import Path
import re
import sys

import duckdb
import pandas as pd


CI_PATTERN = re.compile(
    r"^\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)$"
)


def parse_population(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.str.replace(",", "", regex=False),
        errors="coerce",
    ).astype("Int64")


def parse_ci(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    extracted = series.str.extract(CI_PATTERN)

    lower = pd.to_numeric(extracted[0], errors="coerce")
    upper = pd.to_numeric(extracted[1], errors="coerce")

    return lower, upper


def import_county_gis(
    db_path: Path,
    csv_path: Path,
    release_year: int,
) -> int:
    db_path = db_path.resolve()
    csv_path = csv_path.resolve()

    if not db_path.exists():
        raise FileNotFoundError(f"Database does not exist: {db_path}")

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV does not exist: {csv_path}")

    df = pd.read_csv(csv_path, dtype=str)

    required_geography = {
        "StateAbbr",
        "StateDesc",
        "CountyName",
        "CountyFIPS",
        "TotalPopulation",
    }

    missing_geography = required_geography - set(df.columns)

    if missing_geography:
        raise ValueError(
            f"Missing required geography columns: "
            f"{sorted(missing_geography)}"
        )

    if df["CountyFIPS"].isna().any():
        raise ValueError("CountyFIPS contains missing values")

    if df["CountyFIPS"].duplicated().any():
        raise ValueError("CountyFIPS contains duplicates")

    if not df["CountyFIPS"].str.fullmatch(r"\d{5}").all():
        raise ValueError(
            "CountyFIPS must contain exactly five digits"
        )

    con = duckdb.connect(str(db_path))

    try:
        metadata = con.execute(
            """
            SELECT
                measure_id,
                measurement_year,
                carry_forward
            FROM places.measure_versions
            WHERE release_year = ?
            ORDER BY measure_id
            """,
            [release_year],
        ).df()

        if metadata.empty:
            raise ValueError(
                f"No PLACES metadata found for release {release_year}"
            )

        records = []

        total_population = parse_population(
            df["TotalPopulation"]
        )

        if "TotalPop18plus" in df.columns:
            total_pop_18plus = parse_population(
                df["TotalPop18plus"]
            )
        else:
            total_pop_18plus = pd.Series(
                pd.array(
                    [pd.NA] * len(df),
                    dtype="Int64",
                )
            )

        for meta in metadata.itertuples(index=False):
            measure_id = meta.measure_id

            crude_prev_col = f"{measure_id}_CrudePrev"
            crude_ci_col = f"{measure_id}_Crude95CI"
            adj_prev_col = f"{measure_id}_AdjPrev"
            adj_ci_col = f"{measure_id}_Adj95CI"

            required_measure_columns = {
                crude_prev_col,
                crude_ci_col,
                adj_prev_col,
                adj_ci_col,
            }

            missing_measure_columns = (
                required_measure_columns - set(df.columns)
            )

            if missing_measure_columns:
                raise ValueError(
                    f"{measure_id}: missing columns "
                    f"{sorted(missing_measure_columns)}"
                )

            crude_lower, crude_upper = parse_ci(
                df[crude_ci_col]
            )

            adj_lower, adj_upper = parse_ci(
                df[adj_ci_col]
            )

            measure_df = pd.DataFrame(
                {
                    "release_year": release_year,
                    "measurement_year": int(
                        meta.measurement_year
                    ),
                    "geography_level": "county",
                    "geoid": df["CountyFIPS"],
                    "geography_name": df["CountyName"],
                    "state_abbr": df["StateAbbr"],
                    "state_name": df["StateDesc"],
                    "total_population": total_population,
                    "total_pop_18plus": total_pop_18plus,
                    "measure_id": measure_id,
                    "crude_prevalence": pd.to_numeric(
                        df[crude_prev_col],
                        errors="coerce",
                    ),
                    "crude_ci_lower": crude_lower,
                    "crude_ci_upper": crude_upper,
                    "age_adjusted_prevalence": pd.to_numeric(
                        df[adj_prev_col],
                        errors="coerce",
                    ),
                    "age_adjusted_ci_lower": adj_lower,
                    "age_adjusted_ci_upper": adj_upper,
                    "carry_forward": bool(
                        meta.carry_forward
                    ),
                    "missing_reason": None,
                    "source_file": csv_path.name,
                }
            )

            records.append(measure_df)

        long_df = pd.concat(
            records,
            ignore_index=True,
        )

        expected_rows = len(df) * len(metadata)

        if len(long_df) != expected_rows:
            raise AssertionError(
                f"Unexpected transformed row count: "
                f"{len(long_df):,}; "
                f"expected {expected_rows:,}"
            )

        con.execute("BEGIN TRANSACTION")

        con.execute(
            """
            DELETE FROM places.estimates
            WHERE release_year = ?
              AND geography_level = 'county'
            """,
            [release_year],
        )

        con.register("places_county_df", long_df)

        con.execute(
            """
            INSERT INTO places.estimates (
                release_year,
                measurement_year,
                geography_level,
                geoid,
                geography_name,
                state_abbr,
                state_name,
                total_population,
                total_pop_18plus,
                measure_id,
                crude_prevalence,
                crude_ci_lower,
                crude_ci_upper,
                age_adjusted_prevalence,
                age_adjusted_ci_lower,
                age_adjusted_ci_upper,
                carry_forward,
                missing_reason,
                source_file
            )
            SELECT
                release_year,
                measurement_year,
                geography_level,
                geoid,
                geography_name,
                state_abbr,
                state_name,
                total_population,
                total_pop_18plus,
                measure_id,
                crude_prevalence,
                crude_ci_lower,
                crude_ci_upper,
                age_adjusted_prevalence,
                age_adjusted_ci_lower,
                age_adjusted_ci_upper,
                carry_forward,
                missing_reason,
                source_file
            FROM places_county_df
            """
        )

        inserted = con.execute(
            """
            SELECT COUNT(*)
            FROM places.estimates
            WHERE release_year = ?
              AND geography_level = 'county'
            """,
            [release_year],
        ).fetchone()[0]

        if inserted != expected_rows:
            raise AssertionError(
                f"Database row count {inserted:,} "
                f"does not match expected {expected_rows:,}"
            )

        con.execute("COMMIT")

    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise

    finally:
        con.close()

    print("=" * 70)
    print("PLACES county import: SUCCESS")
    print("=" * 70)
    print(f"Release         : {release_year}")
    print(f"Source counties : {len(df):,}")
    print(f"Measures        : {len(metadata)}")
    print(f"Rows imported   : {inserted:,}")
    print(f"Source file     : {csv_path.name}")

    return inserted


def main() -> None:
    if len(sys.argv) != 4:
        print(
            "Usage:\n"
            "python scripts\\places\\import_county_gis.py "
            "\"database.duckdb\" "
            "\"county-file.csv\" "
            "2020"
        )
        raise SystemExit(1)

    import_county_gis(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        int(sys.argv[3]),
    )


if __name__ == "__main__":
    main()