from pathlib import Path

import sys
import duckdb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DB = PROJECT_ROOT / "database" / "countyhealth.duckdb"
DEFAULT_SOURCE = Path(
    r"D:\CDC places data\Ruralurbancontinuumcodes2023.csv"
)
SCHEMA_FILE = PROJECT_ROOT / "database" / "geography" / "schema.sql"


def classify_metro(rucc_code):
    if pd.isna(rucc_code):
        return None

    code = int(rucc_code)

    if code in {1, 2, 3}:
        return "Metro"

    if code in {4, 5, 6, 7, 8, 9}:
        return "Nonmetro"

    raise ValueError(f"Unexpected RUCC code: {code}")


def classify_adjacency(rucc_code):
    if pd.isna(rucc_code):
        return None

    code = int(rucc_code)

    if code in {1, 2, 3}:
        return "Not applicable"

    if code in {4, 6, 8}:
        return "Adjacent to metro"

    if code in {5, 7, 9}:
        return "Not adjacent to metro"

    raise ValueError(f"Unexpected RUCC code: {code}")


def load_rucc_source(source_path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        source_path,
        dtype=str,
        encoding="cp1252",
    )

    required = {
        "FIPS",
        "State",
        "County_Name",
        "Attribute",
        "Value",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required RUCC columns: {sorted(missing)}"
        )

    return df


def build_rucc_records(df: pd.DataFrame) -> pd.DataFrame:
    base = (
        df[df["Attribute"].eq("Population_2020")]
        [["FIPS", "State", "County_Name", "Value"]]
        .rename(columns={"Value": "population_2020"})
        .copy()
    )

    rucc = (
        df[df["Attribute"].eq("RUCC_2023")]
        [["FIPS", "Value"]]
        .rename(columns={"Value": "rucc_code"})
        .copy()
    )

    descriptions = (
        df[df["Attribute"].eq("Description")]
        [["FIPS", "Value"]]
        .rename(columns={"Value": "rucc_description"})
        .copy()
    )

    records = (
        base
        .merge(rucc, on="FIPS", how="left", validate="one_to_one")
        .merge(
            descriptions,
            on="FIPS",
            how="left",
            validate="one_to_one",
        )
    )

    records["FIPS"] = records["FIPS"].astype(str).str.zfill(5)

    if records["FIPS"].duplicated().any():
        duplicates = (
            records.loc[
                records["FIPS"].duplicated(keep=False),
                "FIPS",
            ]
            .tolist()
        )
        raise ValueError(f"Duplicate RUCC FIPS values: {duplicates}")

    if not records["FIPS"].str.fullmatch(r"\d{5}").all():
        raise ValueError("RUCC contains invalid FIPS values.")

    records["population_2020"] = pd.to_numeric(
        records["population_2020"],
        errors="raise",
    ).astype("Int64")

    records["rucc_code"] = pd.to_numeric(
        records["rucc_code"],
        errors="coerce",
    ).astype("Int64")

    valid_codes = set(range(1, 10))

    observed_codes = set(
        records["rucc_code"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    unexpected = observed_codes - valid_codes

    if unexpected:
        raise ValueError(
            f"Unexpected RUCC codes: {sorted(unexpected)}"
        )

    records["metro_status"] = records["rucc_code"].apply(
        classify_metro
    )

    records["adjacency_status"] = records["rucc_code"].apply(
        classify_adjacency
    )

    records["missing_reason"] = None

    no_rucc = records["rucc_code"].isna()

    records.loc[
        no_rucc,
        "missing_reason",
    ] = "RUCC classification not applicable in source"

    return pd.DataFrame(
        {
            "fips": records["FIPS"],
            "state_abbr": records["State"],
            "county_name": records["County_Name"],
            "population_2020": records["population_2020"],
            "rucc_code": records["rucc_code"],
            "rucc_description": records["rucc_description"],
            "metro_status": records["metro_status"],
            "adjacency_status": records["adjacency_status"],
            "source_year": 2023,
            "source_name": "USDA Rural-Urban Continuum Codes",
            "missing_reason": records["missing_reason"],
        }
    )


def import_rucc(
    db_path: Path = DEFAULT_DB,
    source_path: Path = DEFAULT_SOURCE,
):
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    if not source_path.exists():
        raise FileNotFoundError(f"RUCC source not found: {source_path}")

    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(
            f"RUCC schema file not found: {SCHEMA_FILE}"
        )

    source = load_rucc_source(source_path)
    records = build_rucc_records(source)

    if len(records) != 3235:
        raise ValueError(
            f"Expected 3,235 RUCC geography records; got {len(records)}."
        )

    if records["rucc_code"].notna().sum() != 3233:
        raise ValueError(
            "Expected 3,233 geographies with RUCC classifications."
        )

    con = duckdb.connect(str(db_path))

    try:
        con.execute(SCHEMA_FILE.read_text(encoding="utf-8"))

        con.register("rucc_records", records)

        con.execute("BEGIN")

        con.execute(
            """
            DELETE FROM geography.rucc_2023
            """
        )

        con.execute(
            """
            INSERT INTO geography.rucc_2023
            SELECT *
            FROM rucc_records
            """
        )

        con.execute("COMMIT")

        count = con.execute(
            """
            SELECT COUNT(*)
            FROM geography.rucc_2023
            """
        ).fetchone()[0]

    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise

    finally:
        con.close()

    print("RUCC import: SUCCESS")
    print(f"Rows imported     : {count}")
    print(
        "Classified RUCC   : "
        f"{records['rucc_code'].notna().sum()}"
    )
    print(
        "RUCC unavailable  : "
        f"{records['rucc_code'].isna().sum()}"
    )


def main() -> None:
    if len(sys.argv) not in {1, 3}:
        print(
            "Usage:\n"
            "python scripts\\geography\\import_rucc_2023.py "
            "[\"database.duckdb\" \"rucc-2023.csv\"]"
        )
        raise SystemExit(1)

    if len(sys.argv) == 3:
        import_rucc(
            Path(sys.argv[1]),
            Path(sys.argv[2]),
        )
    else:
        import_rucc()


if __name__ == "__main__":
    main()
