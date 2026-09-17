from app.data_access import (
    get_places_ihme_race_disparity_context,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    df = get_places_ihme_race_disparity_context(
        places_measure_id="DIABETES",
        places_measurement_year=2019,
        ihme_cause_id=976,
        ihme_year=2019,
    )

    assert_true(
        len(df) == 1489,
        f"Expected 1,489 matched counties; got {len(df)}.",
    )

    assert_true(
        df["fips"].nunique() == 1489,
        "Expected one row per county FIPS.",
    )

    assert_true(
        df["rucc_code"].notna().sum() == 1481,
        "Expected 1,481 RUCC-classified counties.",
    )

    assert_true(
        df["places_measure_id"].eq("DIABETES").all(),
        "Unexpected PLACES measure.",
    )

    assert_true(
        df["places_measurement_year"].eq(2019).all(),
        "Unexpected PLACES measurement year.",
    )

    assert_true(
        df["ihme_cause_id"].eq(976).all(),
        "Unexpected IHME cause.",
    )

    assert_true(
        df["ihme_year"].eq(2019).all(),
        "Unexpected IHME year.",
    )

    black_higher = int(
        df["disparity_direction"]
        .eq("Black higher")
        .sum()
    )

    white_higher = int(
        df["disparity_direction"]
        .eq("White higher")
        .sum()
    )

    equal = int(
        df["disparity_direction"]
        .eq("Equal")
        .sum()
    )

    assert_true(
        black_higher == 1468,
        f"Expected 1,468 Black-higher counties; got {black_higher}.",
    )

    assert_true(
        white_higher == 21,
        f"Expected 21 White-higher counties; got {white_higher}.",
    )

    assert_true(
        equal == 0,
        f"Expected no equal point estimates; got {equal}.",
    )

    assert_true(
        (
            df["black_white_yll_gap"]
            == (
                df["black_yll_rate"]
                - df["white_yll_rate"]
            )
        ).all(),
        "Signed Black-White gap is inconsistent.",
    )

    assert_true(
        df.iloc[0]["fips"] == "42111",
        "Unexpected leading signed-gap county.",
    )

    print("PLACES-IHME race disparity context validation: PASS")
    print("Matched counties    : 1,489")
    print("Unique FIPS         : 1,489")
    print("RUCC classified     : 1,481")
    print("Black higher        : 1,468")
    print("White higher        : 21")
    print("Equal               : 0")
    print()
    print(
        df[
            [
                "fips",
                "ihme_location_name",
                "places_age_adjusted_prevalence",
                "black_yll_rate",
                "white_yll_rate",
                "black_white_yll_gap",
                "disparity_direction",
            ]
        ].head(10).to_string(index=False)
    )


if __name__ == "__main__":
    main()
