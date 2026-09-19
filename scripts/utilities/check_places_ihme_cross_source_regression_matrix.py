from app.data_access import (
    get_places_ihme_county_trend_context,
    get_places_ihme_race_disparity_trend_context,
    get_places_ihme_sex_disparity_trend_context,
    get_places_ihme_age_disparity_trend_context,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


CASES = [
    {
        "label": "Coahoma diabetes",
        "fips": "28027",
        "places_measure_id": "DIABETES",
        "ihme_cause_id": 976,
        "sex_ihme_expected": True,
    },
    {
        "label": "Milwaukee breast cancer",
        "fips": "55079",
        "places_measure_id": "CANCER",
        "ihme_cause_id": 429,
        "sex_ihme_expected": False,
    },
    {
        "label": "Milwaukee stroke",
        "fips": "55079",
        "places_measure_id": "STROKE",
        "ihme_cause_id": 494,
        "sex_ihme_expected": True,
    },
]


def validate_base(case):
    df = get_places_ihme_county_trend_context(
        fips=case["fips"],
        places_measure_id=case["places_measure_id"],
        ihme_cause_id=case["ihme_cause_id"],
    )

    assert_true(
        not df.empty,
        f'{case["label"]}: base trend returned no rows.',
    )

    assert_true(
        df["analysis_year"].is_monotonic_increasing,
        f'{case["label"]}: years are not ordered.',
    )

    assert_true(
        df["analysis_year"].is_unique,
        f'{case["label"]}: duplicate analysis years found.',
    )

    assert_true(
        df["ihme_available"].any(),
        f'{case["label"]}: no IHME observations found.',
    )

    assert_true(
        df["places_available"].any(),
        f'{case["label"]}: no PLACES observations found.',
    )

    return df


def validate_disparity(
    case,
    label,
    fn,
    gap_column,
    ihme_expected=True,
):
    df = fn(
        fips=case["fips"],
        places_measure_id=case["places_measure_id"],
        ihme_cause_id=case["ihme_cause_id"],
    )

    assert_true(
        not df.empty,
        f'{case["label"]} {label}: returned no rows.',
    )

    assert_true(
        gap_column in df.columns,
        f'{case["label"]} {label}: missing {gap_column}.',
    )

    assert_true(
        df["analysis_year"].is_unique,
        f'{case["label"]} {label}: duplicate years found.',
    )

    assert_true(
        df["places_available"].any(),
        f'{case["label"]} {label}: no PLACES rows found.',
    )

    if ihme_expected:
        assert_true(
            df["ihme_available"].any(),
            f'{case["label"]} {label}: expected IHME data.',
        )

        ihme_rows = df[
            df["ihme_available"]
        ]

        assert_true(
            ihme_rows[gap_column].notna().all(),
            f'{case["label"]} {label}: missing IHME gap values.',
        )

    else:
        assert_true(
            not df["ihme_available"].any(),
            f'{case["label"]} {label}: unexpected IHME data.',
        )

        assert_true(
            df[gap_column].isna().all(),
            f'{case["label"]} {label}: gap should be missing.',
        )

        assert_true(
            not df["same_year_overlap"].any(),
            f'{case["label"]} {label}: unexpected overlap.',
        )

    return df


def main():
    for case in CASES:
        base = validate_base(case)

        race = validate_disparity(
            case,
            "race",
            get_places_ihme_race_disparity_trend_context,
            "black_white_yll_gap",
        )

        sex = validate_disparity(
            case,
            "sex",
            get_places_ihme_sex_disparity_trend_context,
            "male_female_yll_gap",
            ihme_expected=case["sex_ihme_expected"],
        )

        age = validate_disparity(
            case,
            "age",
            get_places_ihme_age_disparity_trend_context,
            "age_60_64_minus_80_84_yll_gap",
        )

        print(
            f'{case["label"]}: PASS | '
            f'base={len(base)} '
            f'race={len(race)} '
            f'sex={len(sex)} '
            f'age={len(age)}'
        )

    print(
        "PLACES-IHME cross-source regression matrix: PASS"
    )


if __name__ == "__main__":
    main()
