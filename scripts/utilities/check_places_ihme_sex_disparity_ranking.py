from app.data_access import (
    get_places_ihme_sex_disparity_ranking,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    df = get_places_ihme_sex_disparity_ranking(
        places_measure_id="DIABETES",
        places_measurement_year=2019,
        ihme_cause_id=976,
        ihme_year=2019,
        minimum_places_prevalence=15.0,
        require_nonoverlap=False,
        limit=10,
    )

    assert_true(
        len(df) == 10,
        f"Expected 10 rows; got {len(df)}.",
    )

    assert_true(
        df["places_age_adjusted_prevalence"].ge(15.0).all(),
        "Sex ranking contains prevalence below 15%.",
    )

    assert_true(
        df["male_female_yll_gap"].is_monotonic_decreasing,
        "Sex ranking must be descending by signed gap.",
    )

    assert_true(
        df.iloc[0]["fips"] == "46102",
        "Unexpected leading sex-disparity county.",
    )

    assert_true(
        abs(
            float(df.iloc[0]["male_female_yll_gap"])
            - 1677.776602
        ) < 1e-6,
        "Unexpected leading Male-Female gap.",
    )

    print("PLACES-IHME sex disparity ranking validation: PASS")
    print("Rows                 : 10")
    print("Minimum prevalence   : 15.0%")
    print(
        "Leading county       : "
        f"{df.iloc[0]['ihme_location_name']}"
    )


if __name__ == "__main__":
    main()
