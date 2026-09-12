from pathlib import Path

import duckdb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_FILE = PROJECT_ROOT / "database" / "places" / "schema.sql"

DEFAULT_DICTIONARY = (
    Path(r"D:\CDC places data")
    / "PLACES_and_500_Cities__Data_Dictionary_20260911.csv"
)

DEFAULT_2025_COUNTY_FILE = (
    Path(r"D:\CDC places data")
    / "PLACES__County_Data_(GIS_Friendly_Format),_2025_release_20260911.csv"
)

CARRY_FORWARD_2025 = {
    "COLON_SCREEN",
    "DENTAL",
    "MAMMOUSE",
    "SLEEP",
    "TEETHLOST",
}

RELEASE_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]


def load_dictionary(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str)


def available_release_rows(
    dictionary: pd.DataFrame,
    release_year: int,
) -> pd.DataFrame:
    column = f"PLACES Release {release_year}"

    if column not in dictionary.columns:
        raise KeyError(f"Missing release column: {column}")

    return dictionary[
        dictionary[column].notna()
        & dictionary[column].ne("X")
    ].copy()


def build_measure_catalog(dictionary: pd.DataFrame) -> pd.DataFrame:
    catalog = dictionary[
        [
            "MeasureID",
            "Measure full name",
            "Category name",
            "Frequency_BRFSS_year",
        ]
    ].copy()

    catalog.columns = [
        "measure_id",
        "canonical_name",
        "category",
        "frequency",
    ]

    catalog["unit"] = "Percent"
    catalog["age_adjusted_available"] = True

    first_release = {}
    last_release = {}

    for _, row in dictionary.iterrows():
        measure_id = row["MeasureID"]
        present_years = []

        for year in range(2020, 2025):
            value = row[f"PLACES Release {year}"]
            if pd.notna(value) and value != "X":
                present_years.append(year)

        if present_years:
            first_release[measure_id] = min(present_years)
            last_release[measure_id] = max(present_years)
        else:
            first_release[measure_id] = None
            last_release[measure_id] = None

    catalog["first_release_year"] = catalog["measure_id"].map(first_release)
    catalog["last_release_year"] = catalog["measure_id"].map(last_release)
    catalog["notes"] = None

    loneliness = pd.DataFrame(
        [
            {
                "measure_id": "LONELINESS",
                "canonical_name": "Loneliness among adults",
                "category": "Health-Related Social Needs",
                "frequency": "Vary",
                "unit": "Percent",
                "age_adjusted_available": True,
                "first_release_year": 2025,
                "last_release_year": 2025,
                "notes": (
                    "Introduced in the 2025 PLACES release; "
                    "kept distinct from ISOLATION."
                ),
            }
        ]
    )

    catalog = pd.concat([catalog, loneliness], ignore_index=True)

    return catalog


def build_measure_versions(dictionary: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for release_year in range(2020, 2025):
        release_rows = available_release_rows(
            dictionary,
            release_year,
        )

        release_column = f"PLACES Release {release_year}"

        for _, row in release_rows.iterrows():
            measurement_year = int(row[release_column])

            rows.append(
                {
                    "release_year": release_year,
                    "measure_id": row["MeasureID"],
                    "measure_name": row["Measure full name"],
                    "measure_definition": None,
                    "data_source": "BRFSS",
                    "measurement_year": measurement_year,
                    "frequency": row["Frequency_BRFSS_year"],
                    "carry_forward": (
                        measurement_year < release_year - 2
                    ),
                    "definition_version": str(release_year),
                    "notes": None,
                }
            )

    measures_2025 = {
        "ACCESS2",
        "ARTHRITIS",
        "BINGE",
        "BPHIGH",
        "BPMED",
        "CANCER",
        "CASTHMA",
        "CHD",
        "CHECKUP",
        "CHOLSCREEN",
        "COGNITION",
        "COLON_SCREEN",
        "COPD",
        "CSMOKING",
        "DENTAL",
        "DEPRESSION",
        "DIABETES",
        "DISABILITY",
        "EMOTIONSPT",
        "FOODINSECU",
        "FOODSTAMP",
        "GHLTH",
        "HEARING",
        "HIGHCHOL",
        "HOUSINSECU",
        "INDEPLIVE",
        "LACKTRPT",
        "LONELINESS",
        "LPA",
        "MAMMOUSE",
        "MHLTH",
        "MOBILITY",
        "OBESITY",
        "PHLTH",
        "SELFCARE",
        "SHUTUTILITY",
        "SLEEP",
        "STROKE",
        "TEETHLOST",
        "VISION",
    }

    name_lookup = dictionary.set_index("MeasureID")[
        "Measure full name"
    ].to_dict()

    frequency_lookup = dictionary.set_index("MeasureID")[
        "Frequency_BRFSS_year"
    ].to_dict()

    for measure_id in sorted(measures_2025):
        carry_forward = measure_id in CARRY_FORWARD_2025

        rows.append(
            {
                "release_year": 2025,
                "measure_id": measure_id,
                "measure_name": (
                    "Loneliness among adults"
                    if measure_id == "LONELINESS"
                    else name_lookup.get(measure_id)
                ),
                "measure_definition": None,
                "data_source": "BRFSS",
                "measurement_year": 2022 if carry_forward else 2023,
                "frequency": (
                    "Vary"
                    if measure_id == "LONELINESS"
                    else frequency_lookup.get(measure_id)
                ),
                "carry_forward": carry_forward,
                "definition_version": "2025",
                "notes": (
                    "2022 estimate carried forward into 2025 release."
                    if carry_forward
                    else None
                ),
            }
        )

    return pd.DataFrame(rows)


def build_releases() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "release_year": year,
                "release_label": f"CDC PLACES {year} release",
                "release_date": None,
                "source_name": "CDC PLACES",
                "methodology": (
                    "Model-based small-area prevalence estimates "
                    "derived from BRFSS and Census/ACS inputs."
                ),
                "notes": None,
            }
            for year in RELEASE_YEARS
        ]
    )


def main() -> None:
    dictionary = load_dictionary(DEFAULT_DICTIONARY)

    measures = build_measure_catalog(dictionary)
    versions = build_measure_versions(dictionary)
    releases = build_releases()

    print("=" * 70)
    print("PLACES metadata build")
    print("=" * 70)
    print(f"Measures         : {len(measures)}")
    print(f"Measure versions : {len(versions)}")
    print(f"Releases         : {len(releases)}")

    print()
    print("Versions by release:")
    print(
        versions.groupby("release_year")
        .size()
        .to_string()
    )

    print()
    print("2025 carry-forward measures:")
    print(
        ", ".join(
            versions.loc[
                (versions["release_year"] == 2025)
                & versions["carry_forward"],
                "measure_id",
            ].tolist()
        )
    )


if __name__ == "__main__":
    main()