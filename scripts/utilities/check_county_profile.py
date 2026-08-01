from pathlib import Path
import math
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.data_access import (  # noqa: E402
    DB_FILE,
    get_bmi_summary,
    get_cause_trend,
    get_counties,
    get_long_term_change,
    get_top_causes,
)


EXPECTED_BMI_METRICS = {
    "mean bmi",
    "obesity",
    "overweight",
}

EXPECTED_TREND_YEARS = list(range(2000, 2020))

TEST_CASES = [
    {
        "fips": "56001",
        "year": 2019,
        "label": "Albany County (Wyoming)",
    },
    {
        "fips": "45001",
        "year": 2019,
        "label": "Abbeville County (South Carolina)",
    },
    {
        "fips": "46079",
        "year": 2019,
        "label": "Lake County (South Dakota)",
    },
    {
        "fips": "06037",
        "year": 2010,
        "label": "Los Angeles County (California)",
    },
]


def heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_not_missing(value: object, field_name: str) -> None:
    if value is None:
        raise AssertionError(f"{field_name} is missing.")

    if isinstance(value, float) and math.isnan(value):
        raise AssertionError(f"{field_name} is NaN.")

    if isinstance(value, str) and not value.strip():
        raise AssertionError(f"{field_name} is blank.")


def validate_county_lookup() -> None:
    heading("County lookup validation")

    counties = get_counties()

    assert_true(
        not counties.empty,
        "County lookup returned no rows.",
    )

    required_columns = {
        "location_id",
        "location_name",
        "display_name",
        "fips",
        "state_fips",
        "county_fips",
        "is_rankable",
    }

    missing_columns = required_columns.difference(counties.columns)

    assert_true(
        not missing_columns,
        "County lookup is missing columns: "
        + ", ".join(sorted(missing_columns)),
    )

    assert_true(
        counties["fips"].notna().all(),
        "County lookup contains missing FIPS values.",
    )

    assert_true(
        counties["display_name"].notna().all(),
        "County lookup contains missing display names.",
    )

    assert_true(
        counties["fips"].astype(str).str.len().eq(5).all(),
        "At least one county FIPS value is not five characters long.",
    )

    print(f"County rows: {len(counties):,}")
    print("County lookup validation passed.")


def validate_bmi_summary(
    fips: str,
    year: int,
    county_label: str,
) -> None:
    heading(f"BMI summary: {county_label}, {year}")

    bmi = get_bmi_summary(
        fips=fips,
        year=year,
    )

    assert_true(
        not bmi.empty,
        f"No BMI records returned for {county_label}, {year}.",
    )

    required_columns = {
        "location_id",
        "location_name",
        "fips",
        "year",
        "metric",
        "value",
        "lower",
        "upper",
    }

    missing_columns = required_columns.difference(bmi.columns)

    assert_true(
        not missing_columns,
        "BMI summary is missing columns: "
        + ", ".join(sorted(missing_columns)),
    )

    metrics = {
        str(metric).strip().lower()
        for metric in bmi["metric"].tolist()
    }

    assert_true(
        len(bmi) == 3,
        (
            f"Expected exactly 3 BMI records for {county_label}, {year}; "
            f"received {len(bmi)}."
        ),
    )

    assert_true(
        metrics == EXPECTED_BMI_METRICS,
        (
            f"Unexpected BMI metrics for {county_label}, {year}: "
            f"{sorted(metrics)}"
        ),
    )

    assert_true(
        bmi["value"].notna().all(),
        f"BMI summary contains missing estimates for {county_label}, {year}.",
    )

    assert_true(
        bmi["lower"].notna().all(),
        f"BMI summary contains missing lower bounds for {county_label}, {year}.",
    )

    assert_true(
        bmi["upper"].notna().all(),
        f"BMI summary contains missing upper bounds for {county_label}, {year}.",
    )

    assert_true(
        (bmi["lower"] <= bmi["value"]).all(),
        f"A BMI lower bound exceeds its estimate for {county_label}, {year}.",
    )

    assert_true(
        (bmi["value"] <= bmi["upper"]).all(),
        f"A BMI estimate exceeds its upper bound for {county_label}, {year}.",
    )

    print(bmi[["metric", "value", "lower", "upper"]].to_string(index=False))
    print("BMI summary validation passed.")


def validate_top_causes_and_trends(
    fips: str,
    year: int,
    county_label: str,
) -> None:
    heading(f"Top causes and trends: {county_label}, {year}")

    top_causes = get_top_causes(
        fips=fips,
        year=year,
        limit=10,
    )

    assert_true(
        not top_causes.empty,
        f"No top causes returned for {county_label}, {year}.",
    )

    assert_true(
        len(top_causes) <= 10,
        (
            f"Top-cause query returned {len(top_causes)} rows "
            f"for {county_label}, {year}; expected no more than 10."
        ),
    )

    required_columns = {
        "county_cause_rank",
        "cause_id",
        "cause_name",
        "yll_rate",
        "lower",
        "upper",
        "national_county_rank",
        "burden_percentile",
    }

    missing_columns = required_columns.difference(top_causes.columns)

    assert_true(
        not missing_columns,
        "Top-causes output is missing columns: "
        + ", ".join(sorted(missing_columns)),
    )

    for row in top_causes.itertuples(index=False):
        assert_not_missing(row.cause_id, "cause_id")
        assert_not_missing(row.cause_name, "cause_name")
        assert_not_missing(row.county_cause_rank, "county_cause_rank")
        assert_not_missing(row.yll_rate, "yll_rate")

        assert_true(
            row.lower <= row.yll_rate <= row.upper,
            (
                f"YLL estimate is outside its uncertainty interval for "
                f"{row.cause_name}, {county_label}, {year}."
            ),
        )

        trend = get_cause_trend(
            fips=fips,
            cause_id=int(row.cause_id),
        )

        assert_true(
            not trend.empty,
            (
                f"No trend records returned for {row.cause_name}, "
                f"{county_label}."
            ),
        )

        trend_years = (
            trend["year"]
            .astype(int)
            .sort_values()
            .tolist()
        )

        assert_true(
            trend_years == EXPECTED_TREND_YEARS,
            (
                f"Trend years are incomplete for {row.cause_name}, "
                f"{county_label}. Received: {trend_years}"
            ),
        )

        assert_true(
            len(trend) == 20,
            (
                f"Expected 20 trend rows for {row.cause_name}, "
                f"{county_label}; received {len(trend)}."
            ),
        )

        assert_true(
            trend["yll_rate"].notna().all(),
            (
                f"Trend contains missing YLL estimates for "
                f"{row.cause_name}, {county_label}."
            ),
        )

        selected_year_row = trend.loc[
            trend["year"].astype(int) == year
        ]

        assert_true(
            len(selected_year_row) == 1,
            (
                f"Expected one {year} trend record for "
                f"{row.cause_name}, {county_label}."
            ),
        )

        trend_year_value = float(
            selected_year_row.iloc[0]["yll_rate"]
        )

        assert_true(
            math.isclose(
                trend_year_value,
                float(row.yll_rate),
                rel_tol=1e-9,
                abs_tol=1e-9,
            ),
            (
                f"Top-cause YLL rate does not match trend value for "
                f"{row.cause_name}, {county_label}, {year}."
            ),
        )

    print(
        top_causes[
            [
                "county_cause_rank",
                "cause_id",
                "cause_name",
                "yll_rate",
            ]
        ].to_string(index=False)
    )

    print("Top-causes and trend validation passed.")


def validate_long_term_change(
    fips: str,
    county_label: str,
) -> None:
    heading(f"Long-term change: {county_label}")

    long_term = get_long_term_change(fips)

    assert_true(
        not long_term.empty,
        f"No long-term records returned for {county_label}.",
    )

    required_columns = {
        "cause_id",
        "cause_name",
        "yll_rate_2000",
        "yll_rate_2019",
        "absolute_change_2000_2019",
        "percent_change_2000_2019",
        "trend_direction",
    }

    missing_columns = required_columns.difference(long_term.columns)

    assert_true(
        not missing_columns,
        "Long-term output is missing columns: "
        + ", ".join(sorted(missing_columns)),
    )

    for row in long_term.itertuples(index=False):
        assert_not_missing(row.cause_id, "cause_id")
        assert_not_missing(row.cause_name, "cause_name")
        assert_not_missing(row.yll_rate_2000, "yll_rate_2000")
        assert_not_missing(row.yll_rate_2019, "yll_rate_2019")
        assert_not_missing(
            row.absolute_change_2000_2019,
            "absolute_change_2000_2019",
        )
        assert_not_missing(row.trend_direction, "trend_direction")

        trend = get_cause_trend(
            fips=fips,
            cause_id=int(row.cause_id),
        )

        assert_true(
            not trend.empty,
            (
                f"No trend returned while validating long-term change for "
                f"{row.cause_name}, {county_label}."
            ),
        )

        start_row = trend.loc[
            trend["year"].astype(int) == 2000
        ]

        end_row = trend.loc[
            trend["year"].astype(int) == 2019
        ]

        assert_true(
            len(start_row) == 1,
            (
                f"Missing or duplicate 2000 trend record for "
                f"{row.cause_name}, {county_label}."
            ),
        )

        assert_true(
            len(end_row) == 1,
            (
                f"Missing or duplicate 2019 trend record for "
                f"{row.cause_name}, {county_label}."
            ),
        )

        trend_2000 = float(start_row.iloc[0]["yll_rate"])
        trend_2019 = float(end_row.iloc[0]["yll_rate"])

        assert_true(
            math.isclose(
                trend_2000,
                float(row.yll_rate_2000),
                rel_tol=1e-9,
                abs_tol=1e-9,
            ),
            (
                f"Long-term 2000 value does not match trend for "
                f"{row.cause_name}, {county_label}."
            ),
        )

        assert_true(
            math.isclose(
                trend_2019,
                float(row.yll_rate_2019),
                rel_tol=1e-9,
                abs_tol=1e-9,
            ),
            (
                f"Long-term 2019 value does not match trend for "
                f"{row.cause_name}, {county_label}."
            ),
        )

        expected_absolute_change = trend_2019 - trend_2000

        assert_true(
            math.isclose(
                expected_absolute_change,
                float(row.absolute_change_2000_2019),
                rel_tol=1e-9,
                abs_tol=1e-6,
            ),
            (
                f"Absolute change is inconsistent for "
                f"{row.cause_name}, {county_label}."
            ),
        )

        if trend_2000 != 0:
            expected_percent_change = (
                expected_absolute_change
                / trend_2000
                * 100
            )

            assert_true(
                math.isclose(
                    expected_percent_change,
                    float(row.percent_change_2000_2019),
                    rel_tol=1e-4,
                    abs_tol=0.02,
                ),
                (
                    f"Percent change is inconsistent for "
                    f"{row.cause_name}, {county_label}."
                ),
            )

        if expected_absolute_change > 0:
            expected_direction = "Increased"
        elif expected_absolute_change < 0:
            expected_direction = "Decreased"
        else:
            expected_direction = "No change"

        assert_true(
            str(row.trend_direction) == expected_direction,
            (
                f"Trend direction is inconsistent for "
                f"{row.cause_name}, {county_label}. "
                f"Expected {expected_direction}; "
                f"received {row.trend_direction}."
            ),
        )

    print(f"Long-term rows: {len(long_term):,}")
    print("Long-term change validation passed.")


def validate_test_case(test_case: dict[str, object]) -> None:
    fips = str(test_case["fips"])
    year = int(test_case["year"])
    county_label = str(test_case["label"])

    print()
    print("=" * 80)
    print(f"Validating {county_label} — {year}")
    print("=" * 80)

    validate_bmi_summary(
        fips=fips,
        year=year,
        county_label=county_label,
    )

    validate_top_causes_and_trends(
        fips=fips,
        year=year,
        county_label=county_label,
    )

    validate_long_term_change(
        fips=fips,
        county_label=county_label,
    )


def main() -> None:
    print("=" * 80)
    print("County Profile Validation")
    print("=" * 80)
    print(f"Database: {DB_FILE}")

    validate_county_lookup()

    for test_case in TEST_CASES:
        validate_test_case(test_case)

    print()
    print("=" * 80)
    print("County Profile validation completed successfully")
    print("=" * 80)


if __name__ == "__main__":
    main()