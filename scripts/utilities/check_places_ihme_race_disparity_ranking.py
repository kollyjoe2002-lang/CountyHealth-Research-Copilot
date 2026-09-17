from app.data_access import (
    get_places_ihme_race_disparity_ranking,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    broad = get_places_ihme_race_disparity_ranking(
        places_measure_id="DIABETES",
        places_measurement_year=2019,
        ihme_cause_id=976,
        ihme_year=2019,
        minimum_places_prevalence=15.0,
        require_nonoverlap=False,
        limit=15,
    )

    assert_true(
        len(broad) == 15,
        f"Expected 15 broad ranking rows; got {len(broad)}.",
    )

    assert_true(
        broad["fips"].nunique() == 15,
        "Expected unique FIPS in broad ranking.",
    )

    assert_true(
        (
            broad["places_age_adjusted_prevalence"]
            >= 15.0
        ).all(),
        "Broad ranking contains prevalence below 15%.",
    )

    assert_true(
        broad["black_white_yll_gap"]
        .is_monotonic_decreasing,
        "Broad ranking must be ordered by descending signed gap.",
    )

    assert_true(
        broad.iloc[0]["fips"] == "28027",
        "Unexpected leading broad-ranking county.",
    )

    strict = get_places_ihme_race_disparity_ranking(
        places_measure_id="DIABETES",
        places_measurement_year=2019,
        ihme_cause_id=976,
        ihme_year=2019,
        minimum_places_prevalence=15.0,
        require_nonoverlap=True,
        limit=15,
    )

    assert_true(
        len(strict) == 1,
        f"Expected 1 strict ranking row; got {len(strict)}.",
    )

    assert_true(
        strict["intervals_overlap"].eq(False).all(),
        "Strict ranking must exclude overlapping intervals.",
    )

    assert_true(
        strict[
            "clear_disparity_direction"
        ].eq("Black clearly higher").all(),
        "Expected strict ranking to show Black clearly higher.",
    )

    assert_true(
        strict.iloc[0]["fips"] == "28027",
        "Unexpected strict-ranking county.",
    )

    assert_true(
        float(
            strict.iloc[0][
                "places_age_adjusted_prevalence"
            ]
        ) == 18.6,
        "Unexpected Coahoma PLACES prevalence.",
    )

    print("PLACES-IHME race disparity ranking validation: PASS")
    print("Minimum PLACES prevalence : 15.0%")
    print("Broad ranking rows        : 15")
    print("Strict non-overlap rows   : 1")
    print(
        "Leading county            : "
        f"{broad.iloc[0]['ihme_location_name']}"
    )
    print()
    print("STRICT RANKING")
    print(
        strict[
            [
                "fips",
                "ihme_location_name",
                "places_age_adjusted_prevalence",
                "black_yll_rate",
                "white_yll_rate",
                "black_white_yll_gap",
                "clear_disparity_direction",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
