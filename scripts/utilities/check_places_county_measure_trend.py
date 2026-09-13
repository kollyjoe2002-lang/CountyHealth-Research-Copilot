from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data_access import get_places_county_measure_trend  # noqa: E402


EXPECTED_OBESITY = [
    (2020, 2018, 35.5, False),
    (2021, 2019, 35.3, False),
    (2022, 2020, 37.3, False),
    (2023, 2021, 38.9, False),
    (2024, 2022, 38.4, False),
    (2025, 2023, 39.5, False),
]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    trend = get_places_county_measure_trend(
        fips="01001",
        measure_id="OBESITY",
    )

    assert_true(
        len(trend) == 6,
        f"Expected 6 OBESITY rows; received {len(trend)}.",
    )

    required_columns = {
        "fips",
        "geography_name",
        "release_year",
        "measurement_year",
        "measure_id",
        "measure_name",
        "age_adjusted_prevalence",
        "age_adjusted_ci_lower",
        "age_adjusted_ci_upper",
        "carry_forward",
        "dataset",
    }

    missing_columns = required_columns.difference(trend.columns)

    assert_true(
        not missing_columns,
        "Trend output missing columns: "
        + ", ".join(sorted(missing_columns)),
    )

    assert_true(
        trend["fips"].eq("01001").all(),
        "Unexpected FIPS returned.",
    )

    assert_true(
        trend["measure_id"].eq("OBESITY").all(),
        "Unexpected measure returned.",
    )

    assert_true(
        trend["dataset"].eq("CDC PLACES").all(),
        "Dataset provenance is incorrect.",
    )

    actual = [
        (
            int(row.release_year),
            int(row.measurement_year),
            float(row.age_adjusted_prevalence),
            bool(row.carry_forward),
        )
        for row in trend.itertuples(index=False)
    ]

    assert_true(
        actual == EXPECTED_OBESITY,
        f"Unexpected OBESITY trend: {actual}",
    )

    measurement_years = trend["measurement_year"].astype(int).tolist()

    assert_true(
        measurement_years == sorted(measurement_years),
        "Trend is not ordered by measurement year.",
    )

    assert_true(
        len(set(measurement_years)) == len(measurement_years),
        "OBESITY trend contains duplicate measurement years.",
    )

    print("PLACES county measure trend validation: PASS")
    print("County             : Autauga")
    print("Measure            : OBESITY")
    print("Measurement years  : 2018-2023")
    print("Rows               : 6")

    for row in actual:
        print(row)


if __name__ == "__main__":
    main()
