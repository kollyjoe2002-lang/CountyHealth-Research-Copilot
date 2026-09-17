from app.data_access import (
    get_places_ihme_sex_disparity_context,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    df = get_places_ihme_sex_disparity_context(
        places_measure_id="DIABETES",
        places_measurement_year=2019,
        ihme_cause_id=976,
        ihme_year=2019,
    )

    assert_true(
        len(df) == 3090,
        f"Expected 3,090 matched counties; got {len(df)}.",
    )

    assert_true(
        df["fips"].nunique() == 3090,
        "Expected one row per county FIPS.",
    )

    assert_true(
        df["rucc_code"].notna().sum() == 3081,
        "Expected 3,081 RUCC-classified counties.",
    )

    male_higher = int(
        df["disparity_direction"]
        .eq("Male higher")
        .sum()
    )

    female_higher = int(
        df["disparity_direction"]
        .eq("Female higher")
        .sum()
    )

    equal = int(
        df["disparity_direction"]
        .eq("Equal")
        .sum()
    )

    assert_true(
        male_higher == 3069,
        f"Expected 3,069 Male-higher counties; got {male_higher}.",
    )

    assert_true(
        female_higher == 21,
        f"Expected 21 Female-higher counties; got {female_higher}.",
    )

    assert_true(
        equal == 0,
        f"Expected 0 equal counties; got {equal}.",
    )

    overlap = int(
        df["intervals_overlap"].sum()
    )

    clear_male = int(
        df["clear_disparity_direction"]
        .eq("Male clearly higher")
        .sum()
    )

    clear_female = int(
        df["clear_disparity_direction"]
        .eq("Female clearly higher")
        .sum()
    )

    interval_overlap = int(
        df["clear_disparity_direction"]
        .eq("Intervals overlap")
        .sum()
    )

    assert_true(
        overlap == 3086,
        f"Expected 3,086 overlapping intervals; got {overlap}.",
    )

    assert_true(
        clear_male == 4,
        f"Expected 4 Male-clearly-higher counties; got {clear_male}.",
    )

    assert_true(
        clear_female == 0,
        f"Expected 0 Female-clearly-higher counties; got {clear_female}.",
    )

    assert_true(
        interval_overlap == 3086,
        f"Expected 3,086 overlap classifications; got {interval_overlap}.",
    )

    assert_true(
        (
            df["male_female_yll_gap"]
            == (
                df["male_yll_rate"]
                - df["female_yll_rate"]
            )
        ).all(),
        "Signed Male-Female gap is inconsistent.",
    )

    assert_true(
        df.iloc[0]["fips"] == "46102",
        "Unexpected leading signed-gap county.",
    )

    print("PLACES-IHME sex disparity context validation: PASS")
    print("Matched counties     : 3,090")
    print("RUCC classified      : 3,081")
    print("Male higher          : 3,069")
    print("Female higher        : 21")
    print("Intervals overlap    : 3,086")
    print("Male clearly higher  : 4")
    print("Female clearly higher: 0")


if __name__ == "__main__":
    main()
