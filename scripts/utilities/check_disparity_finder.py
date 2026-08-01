from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.data_access import (  # noqa: E402
    DB_FILE,
    get_county_disparity_ranking,
    get_county_disparity_trend,
    get_disparity_causes,
    get_disparity_groups,
    get_disparity_years,
)


LINE = "=" * 88


TEST_CASES = [
    {
        "dimension": "Race / ethnicity",
        "cause_name": "Diabetes mellitus type 2",
        "year": 2019,
        "group_a": "Non-Latino, Black",
        "group_b": "Non-Latino, White",
    },
    {
        "dimension": "Sex",
        "cause_name": "Ischemic heart disease",
        "year": 2019,
        "group_a": "Male",
        "group_b": "Female",
    },
    {
        "dimension": "Age group",
        "cause_name": "Diabetes mellitus type 2",
        "year": 2019,
        "group_a": "65 to 69",
        "group_b": "45 to 49",
    },
]


def heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def assert_true(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AssertionError(message)


def assert_close(
    actual: float,
    expected: float,
    message: str,
    *,
    absolute_tolerance: float = 1e-6,
) -> None:
    if not math.isclose(
        float(actual),
        float(expected),
        rel_tol=1e-9,
        abs_tol=absolute_tolerance,
    ):
        raise AssertionError(
            f"{message} "
            f"Actual={actual}; expected={expected}."
        )


def find_cause_id(
    causes: pd.DataFrame,
    cause_name: str,
) -> int:
    match = causes.loc[
        causes["cause_name"]
        .astype(str)
        .str.casefold()
        == cause_name.casefold()
    ]

    assert_true(
        len(match) == 1,
        (
            f"Expected exactly one cause named '{cause_name}', "
            f"but found {len(match)}."
        ),
    )

    return int(match.iloc[0]["cause_id"])


def find_group_id(
    groups: pd.DataFrame,
    group_name: str,
) -> int:
    match = groups.loc[
        groups["group_name"]
        .astype(str)
        .str.casefold()
        == group_name.casefold()
    ]

    assert_true(
        len(match) == 1,
        (
            f"Expected exactly one demographic group named "
            f"'{group_name}', but found {len(match)}."
        ),
    )

    return int(match.iloc[0]["group_id"])


def validate_lookup_data() -> tuple[
    pd.DataFrame,
    list[int],
]:
    heading("Lookup validation")

    causes = get_disparity_causes()
    years = get_disparity_years()

    assert_true(
        not causes.empty,
        "Disparity cause lookup returned no rows.",
    )

    assert_true(
        {"cause_id", "cause_name"}.issubset(
            causes.columns
        ),
        "Cause lookup is missing required columns.",
    )

    assert_true(
        causes["cause_id"].notna().all(),
        "Cause lookup contains missing cause IDs.",
    )

    assert_true(
        causes["cause_name"].notna().all(),
        "Cause lookup contains missing cause names.",
    )

    assert_true(
        causes["cause_id"].is_unique,
        "Cause lookup contains duplicate cause IDs.",
    )

    assert_true(
        len(years) == 20,
        f"Expected 20 years; received {len(years)}.",
    )

    assert_true(
        sorted(years) == list(range(2000, 2020)),
        (
            "Disparity years do not cover exactly "
            "2000 through 2019."
        ),
    )

    print(f"Causes: {len(causes):,}")
    print(
        f"Years: {min(years)}–{max(years)} "
        f"({len(years)} years)"
    )
    print("Lookup validation passed.")

    return causes, years


def validate_dimension_groups() -> None:
    heading("Demographic-group validation")

    expected_groups = {
        "Race / ethnicity": {
            "Latino, Any race",
            "Non-Latino, Black",
            "Non-Latino, White",
            (
                "Non-Latino, American Indian or "
                "Alaska Native"
            ),
            (
                "Non-Latino, Asian or "
                "Pacific Islander"
            ),
        },
        "Sex": {
            "Male",
            "Female",
            "Both",
        },
        "Age group": {
            "20 to 24",
            "25 to 29",
            "30 to 34",
            "35 to 39",
            "40 to 44",
            "45 to 49",
            "50 to 54",
            "55 to 59",
            "60 to 64",
            "65 to 69",
            "70 to 74",
            "75 to 79",
            "80 to 84",
            "20 plus",
            "20 plus, age standardized",
            "85 plus",
        },
    }

    for dimension, expected in expected_groups.items():
        groups = get_disparity_groups(dimension)

        assert_true(
            not groups.empty,
            f"No groups returned for {dimension}.",
        )

        assert_true(
            {
                "group_id",
                "group_name",
            }.issubset(groups.columns),
            (
                f"Group lookup for {dimension} is "
                "missing required columns."
            ),
        )

        actual = set(
            groups["group_name"].astype(str)
        )

        missing = expected.difference(actual)

        assert_true(
            not missing,
            (
                f"{dimension} is missing groups: "
                f"{sorted(missing)}"
            ),
        )

        if dimension == "Race / ethnicity":
            assert_true(
                "Total" not in actual,
                (
                    "The overlapping Total population "
                    "category should be excluded from "
                    "race/ethnicity comparisons."
                ),
            )

        print(
            f"{dimension}: {len(groups)} groups"
        )

    print("Demographic-group validation passed.")


def validate_ranking_structure(
    ranking: pd.DataFrame,
    *,
    dimension: str,
    cause_name: str,
    year: int,
) -> None:
    required_columns = {
        "fips",
        "location_name",
        "group_a_value",
        "group_a_lower",
        "group_a_upper",
        "group_b_value",
        "group_b_lower",
        "group_b_upper",
        "absolute_gap",
        "absolute_gap_magnitude",
        "relative_gap_percent",
    }

    missing_columns = required_columns.difference(
        ranking.columns
    )

    assert_true(
        not missing_columns,
        (
            f"{dimension}, {cause_name}, {year}: "
            f"ranking is missing columns "
            f"{sorted(missing_columns)}."
        ),
    )

    assert_true(
        not ranking.empty,
        (
            f"{dimension}, {cause_name}, {year}: "
            "ranking returned no counties."
        ),
    )

    assert_true(
        ranking["fips"].notna().all(),
        "Ranking contains missing FIPS values.",
    )

    assert_true(
        ranking["location_name"].notna().all(),
        "Ranking contains missing county names.",
    )

    normalized_fips = (
        ranking["fips"]
        .astype(str)
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
        .str.zfill(5)
    )

    assert_true(
        normalized_fips.str.len().eq(5).all(),
        "Ranking contains invalid county FIPS values.",
    )

    assert_true(
        normalized_fips.is_unique,
        (
            "Ranking contains more than one row "
            "for at least one county FIPS."
        ),
    )

    required_numeric_columns = [
        "group_a_value",
        "group_a_lower",
        "group_a_upper",
        "group_b_value",
        "group_b_lower",
        "group_b_upper",
        "absolute_gap",
        "absolute_gap_magnitude",
    ]

    for column in required_numeric_columns:
        assert_true(
            ranking[column].notna().all(),
            f"Ranking contains missing {column} values.",
        )

    assert_true(
        (
            ranking["group_a_lower"]
            <= ranking["group_a_value"]
        ).all(),
        "At least one Group A lower bound exceeds its estimate.",
    )

    assert_true(
        (
            ranking["group_a_value"]
            <= ranking["group_a_upper"]
        ).all(),
        "At least one Group A estimate exceeds its upper bound.",
    )

    assert_true(
        (
            ranking["group_b_lower"]
            <= ranking["group_b_value"]
        ).all(),
        "At least one Group B lower bound exceeds its estimate.",
    )

    assert_true(
        (
            ranking["group_b_value"]
            <= ranking["group_b_upper"]
        ).all(),
        "At least one Group B estimate exceeds its upper bound.",
    )

    calculated_gap = (
        ranking["group_a_value"]
        - ranking["group_b_value"]
    )

    maximum_gap_error = (
        calculated_gap
        - ranking["absolute_gap"]
    ).abs().max()

    assert_true(
        maximum_gap_error <= 1e-6,
        (
            "At least one signed gap does not equal "
            "Group A minus Group B. Maximum error: "
            f"{maximum_gap_error}"
        ),
    )

    calculated_magnitude = ranking[
        "absolute_gap"
    ].abs()

    maximum_magnitude_error = (
        calculated_magnitude
        - ranking["absolute_gap_magnitude"]
    ).abs().max()

    assert_true(
        maximum_magnitude_error <= 1e-6,
        (
            "At least one gap magnitude does not equal "
            "the absolute signed gap. Maximum error: "
            f"{maximum_magnitude_error}"
        ),
    )

    nonzero_reference = ranking.loc[
        ranking["group_b_value"] != 0
    ].copy()

    calculated_relative = (
        (
            nonzero_reference["absolute_gap"]
            / nonzero_reference["group_b_value"]
        )
        * 100
    )

    relative_error = (
        calculated_relative
        - nonzero_reference[
            "relative_gap_percent"
        ]
    ).abs()

    if not relative_error.empty:
        assert_true(
            relative_error.max() <= 1e-6,
            (
                "At least one relative gap is "
                "inconsistent. Maximum error: "
                f"{relative_error.max()}"
            ),
        )


def validate_trend_against_ranking(
    ranking: pd.DataFrame,
    *,
    cause_id: int,
    dimension: str,
    group_a_id: int,
    group_b_id: int,
    year: int,
) -> None:
    counties_to_test = pd.concat(
        [
            ranking.nlargest(
                1,
                "absolute_gap",
            ),
            ranking.nsmallest(
                1,
                "absolute_gap",
            ),
            ranking.sample(
                n=1,
                random_state=42,
            ),
        ],
        ignore_index=True,
    ).drop_duplicates(
        subset=["fips"]
    )

    for county in counties_to_test.itertuples(
        index=False
    ):
        fips = str(county.fips).zfill(5)

        trend = get_county_disparity_trend(
            fips=fips,
            cause_id=cause_id,
            dimension=dimension,
            group_a_id=group_a_id,
            group_b_id=group_b_id,
        )

        assert_true(
            not trend.empty,
            (
                f"No trend returned for "
                f"{county.location_name} ({fips})."
            ),
        )

        required_columns = {
            "year",
            "group_a_value",
            "group_a_lower",
            "group_a_upper",
            "group_b_value",
            "group_b_lower",
            "group_b_upper",
            "absolute_gap",
            "absolute_gap_magnitude",
            "relative_gap_percent",
        }

        missing = required_columns.difference(
            trend.columns
        )

        assert_true(
            not missing,
            (
                f"Trend for {county.location_name} "
                f"is missing columns {sorted(missing)}."
            ),
        )

        assert_true(
            trend["year"].is_unique,
            (
                f"Trend for {county.location_name} "
                "contains duplicate years."
            ),
        )

        assert_true(
            trend["year"].between(
                2000,
                2019,
            ).all(),
            (
                f"Trend for {county.location_name} "
                "contains years outside 2000–2019."
            ),
        )

        selected_year_row = trend.loc[
            trend["year"].astype(int) == int(year)
        ]

        assert_true(
            len(selected_year_row) == 1,
            (
                f"Expected exactly one {year} row "
                f"for {county.location_name}; "
                f"received {len(selected_year_row)}."
            ),
        )

        selected = selected_year_row.iloc[0]

        assert_close(
            selected["group_a_value"],
            county.group_a_value,
            (
                f"Group A ranking and trend values "
                f"do not agree for {county.location_name}."
            ),
        )

        assert_close(
            selected["group_b_value"],
            county.group_b_value,
            (
                f"Group B ranking and trend values "
                f"do not agree for {county.location_name}."
            ),
        )

        assert_close(
            selected["absolute_gap"],
            county.absolute_gap,
            (
                f"Ranking and trend signed gaps "
                f"do not agree for {county.location_name}."
            ),
        )


def validate_test_case(
    test_case: dict[str, object],
    causes: pd.DataFrame,
) -> None:
    dimension = str(
        test_case["dimension"]
    )

    cause_name = str(
        test_case["cause_name"]
    )

    year = int(
        test_case["year"]
    )

    group_a_name = str(
        test_case["group_a"]
    )

    group_b_name = str(
        test_case["group_b"]
    )

    print()
    print(LINE)
    print(
        f"{dimension}: {group_a_name} versus "
        f"{group_b_name}"
    )
    print(
        f"{cause_name}, {year}"
    )
    print(LINE)

    cause_id = find_cause_id(
        causes,
        cause_name,
    )

    groups = get_disparity_groups(
        dimension
    )

    group_a_id = find_group_id(
        groups,
        group_a_name,
    )

    group_b_id = find_group_id(
        groups,
        group_b_name,
    )

    started = time.perf_counter()

    ranking = get_county_disparity_ranking(
        cause_id=cause_id,
        year=year,
        dimension=dimension,
        group_a_id=group_a_id,
        group_b_id=group_b_id,
    )

    elapsed = time.perf_counter() - started

    validate_ranking_structure(
        ranking,
        dimension=dimension,
        cause_name=cause_name,
        year=year,
    )

    validate_trend_against_ranking(
        ranking,
        cause_id=cause_id,
        dimension=dimension,
        group_a_id=group_a_id,
        group_b_id=group_b_id,
        year=year,
    )

    positive_count = int(
        (ranking["absolute_gap"] > 0).sum()
    )

    negative_count = int(
        (ranking["absolute_gap"] < 0).sum()
    )

    zero_count = int(
        (ranking["absolute_gap"] == 0).sum()
    )

    print(f"Counties returned : {len(ranking):,}")
    print(f"Group A higher    : {positive_count:,}")
    print(f"Group B higher    : {negative_count:,}")
    print(f"No difference     : {zero_count:,}")
    print(
        "Median signed gap : "
        f"{ranking['absolute_gap'].median():,.2f}"
    )
    print(
        "Largest gap       : "
        f"{ranking['absolute_gap'].max():,.2f}"
    )
    print(
        "Smallest gap      : "
        f"{ranking['absolute_gap'].min():,.2f}"
    )
    print(f"Query duration     : {elapsed:,.2f}s")
    print("Validation passed.")


def main() -> None:
    print(LINE)
    print("Disparity Finder Validation")
    print(LINE)
    print(f"Database: {DB_FILE}")

    causes, _ = validate_lookup_data()

    validate_dimension_groups()

    for test_case in TEST_CASES:
        validate_test_case(
            test_case,
            causes,
        )

    print()
    print(LINE)
    print(
        "Disparity Finder validation completed successfully"
    )
    print(LINE)


if __name__ == "__main__":
    main()