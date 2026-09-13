from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data_access import get_places_county_measure_ranking  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    ranking = get_places_county_measure_ranking(
        measure_id="OBESITY",
        measurement_year=2023,
        limit=25,
    )

    assert_true(
        len(ranking) == 25,
        f"Expected 25 ranked rows; received {len(ranking)}.",
    )

    required_columns = {
        "national_rank",
        "counties_with_estimate",
        "fips",
        "geography_name",
        "state_abbr",
        "state_name",
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

    missing_columns = required_columns.difference(ranking.columns)

    assert_true(
        not missing_columns,
        "Ranking output missing columns: "
        + ", ".join(sorted(missing_columns)),
    )

    assert_true(
        ranking["measure_id"].eq("OBESITY").all(),
        "Unexpected measure returned.",
    )

    assert_true(
        ranking["measurement_year"].eq(2023).all(),
        "Unexpected measurement year returned.",
    )

    assert_true(
        ranking["release_year"].eq(2025).all(),
        "2023 OBESITY should originate from the 2025 release.",
    )

    assert_true(
        ranking["dataset"].eq("CDC PLACES").all(),
        "Dataset provenance is incorrect.",
    )

    assert_true(
        ranking["age_adjusted_prevalence"].notna().all(),
        "Ranking contains missing age-adjusted estimates.",
    )

    ranks = ranking["national_rank"].astype(int).tolist()

    assert_true(
        ranks == list(range(1, 26)),
        f"Unexpected national ranks: {ranks}",
    )

    values = ranking["age_adjusted_prevalence"].astype(float).tolist()

    assert_true(
        values == sorted(values, reverse=True),
        "Ranking is not ordered by descending age-adjusted prevalence.",
    )

    assert_true(
        not ranking["carry_forward"].astype(bool).any(),
        "2023 OBESITY rows must not be carry-forward estimates.",
    )

    county_counts = set(
        ranking["counties_with_estimate"]
        .astype(int)
        .tolist()
    )

    assert_true(
        len(county_counts) == 1,
        "counties_with_estimate is not constant.",
    )

    total_counties = next(iter(county_counts))

    assert_true(
        total_counties == 2956,
        (
            "Expected 2,956 counties with 2023 OBESITY estimates "
            f"after Kentucky/Pennsylvania missingness; got {total_counties}."
        ),
    )

    assert_true(
        not ranking["state_abbr"].isin(["KY", "PA"]).any(),
        "2023 OBESITY ranking unexpectedly contains Kentucky or Pennsylvania.",
    )

    print("PLACES county measure ranking validation: PASS")
    print("Measure               : OBESITY")
    print("Measurement year      : 2023")
    print("Release year          : 2025")
    print(f"Counties with estimate: {total_counties:,}")
    print()
    print(
        ranking[
            [
                "national_rank",
                "fips",
                "geography_name",
                "state_abbr",
                "age_adjusted_prevalence",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
