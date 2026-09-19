from app.data_access import (
    get_places_ihme_age_disparity_context,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    df = get_places_ihme_age_disparity_context(
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

    younger_higher = int(
        df["disparity_direction"]
        .eq("Ages 60-64 higher")
        .sum()
    )

    older_higher = int(
        df["disparity_direction"]
        .eq("Ages 80-84 higher")
        .sum()
    )

    assert_true(
        younger_higher == 544,
        f"Expected 544 Ages-60-64-higher counties; got {younger_higher}.",
    )

    assert_true(
        older_higher == 2546,
        f"Expected 2,546 Ages-80-84-higher counties; got {older_higher}.",
    )

    overlap = int(
        df["intervals_overlap"].sum()
    )

    assert_true(
        overlap == 3090,
        f"Expected 3,090 overlapping intervals; got {overlap}.",
    )

    assert_true(
        df[
            "clear_disparity_direction"
        ].eq("Intervals overlap").all(),
        "Expected all age comparisons to have overlapping intervals.",
    )

    assert_true(
        (
            df["age_60_64_minus_80_84_yll_gap"]
            == (
                df["age_60_64_yll_rate"]
                - df["age_80_84_yll_rate"]
            )
        ).all(),
        "Signed age gap is inconsistent.",
    )

    median_gap = float(
        df["age_60_64_minus_80_84_yll_gap"].median()
    )

    assert_true(
        abs(median_gap - (-166.918172340041)) < 1e-9,
        f"Unexpected median signed gap: {median_gap}.",
    )

    assert_true(
        df.iloc[0]["fips"] == "54047",
        "Unexpected leading signed-gap county.",
    )

    print("PLACES-IHME age disparity context validation: PASS")
    print("Matched counties       : 3,090")
    print("RUCC classified        : 3,081")
    print("Ages 60-64 higher      : 544")
    print("Ages 80-84 higher      : 2,546")
    print("Intervals overlap      : 3,090")
    print(f"Median signed gap      : {median_gap:.6f}")


if __name__ == "__main__":
    main()
