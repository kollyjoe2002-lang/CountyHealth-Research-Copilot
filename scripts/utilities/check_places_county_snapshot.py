from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data_access import get_places_county_snapshot  # noqa: E402


EXPECTED_2025_CARRY_FORWARD = {
    "COLON_SCREEN",
    "DENTAL",
    "MAMMOUSE",
    "SLEEP",
    "TEETHLOST",
}


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    snapshot = get_places_county_snapshot(
        fips="01001",
        release_year=2025,
    )

    assert_true(
        len(snapshot) == 40,
        f"Expected 40 PLACES measures; received {len(snapshot)}.",
    )

    required_columns = {
        "fips",
        "geography_name",
        "state_abbr",
        "state_name",
        "release_year",
        "measurement_year",
        "measure_id",
        "measure_name",
        "category",
        "frequency",
        "unit",
        "measure_definition",
        "data_source",
        "crude_prevalence",
        "crude_ci_lower",
        "crude_ci_upper",
        "age_adjusted_prevalence",
        "age_adjusted_ci_lower",
        "age_adjusted_ci_upper",
        "carry_forward",
        "missing_reason",
        "dataset",
    }

    missing_columns = required_columns.difference(snapshot.columns)

    assert_true(
        not missing_columns,
        "Snapshot missing columns: "
        + ", ".join(sorted(missing_columns)),
    )

    assert_true(
        snapshot["fips"].eq("01001").all(),
        "Unexpected FIPS returned.",
    )

    assert_true(
        snapshot["release_year"].eq(2025).all(),
        "Unexpected release year returned.",
    )

    assert_true(
        snapshot["dataset"].eq("CDC PLACES").all(),
        "Dataset provenance is incorrect.",
    )

    measurement_years = set(
        snapshot["measurement_year"]
        .dropna()
        .astype(int)
        .tolist()
    )

    assert_true(
        measurement_years == {2022, 2023},
        f"Unexpected measurement years: {measurement_years}",
    )

    carry_forward = set(
        snapshot.loc[
            snapshot["carry_forward"] == True,  # noqa: E712
            "measure_id",
        ].tolist()
    )

    assert_true(
        carry_forward == EXPECTED_2025_CARRY_FORWARD,
        f"Unexpected carry-forward set: {sorted(carry_forward)}",
    )

    obesity = snapshot.loc[
        snapshot["measure_id"] == "OBESITY"
    ]

    assert_true(
        len(obesity) == 1,
        "Expected exactly one OBESITY record.",
    )

    obesity_row = obesity.iloc[0]

    assert_true(
        int(obesity_row["measurement_year"]) == 2023,
        "OBESITY measurement year should be 2023.",
    )

    assert_true(
        float(obesity_row["age_adjusted_prevalence"]) == 39.5,
        "Unexpected Autauga 2025 obesity estimate.",
    )

    assert_true(
        not bool(obesity_row["carry_forward"]),
        "OBESITY must not be marked as carry-forward.",
    )

    print("PLACES county snapshot validation: PASS")
    print(f"County             : {snapshot.iloc[0]['geography_name']}")
    print("Release year       : 2025")
    print(f"Measures           : {len(snapshot)}")
    print(
        "Measurement years  : "
        + ", ".join(
            str(year)
            for year in sorted(measurement_years)
        )
    )
    print(
        "Carry-forward      : "
        + ", ".join(sorted(carry_forward))
    )
    print(
        "Autauga obesity    : "
        f"{obesity_row['age_adjusted_prevalence']}%"
    )


if __name__ == "__main__":
    main()
