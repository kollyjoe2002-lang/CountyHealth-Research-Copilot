from app.data_access import (
    get_places_ihme_demographic_disparity_ranking,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    cases = [
        {
            "label": "Race",
            "dimension": "Race / ethnicity",
            "group_a_id": 4,
            "group_b_id": 5,
            "expected_fips": "28027",
        },
        {
            "label": "Sex",
            "dimension": "Sex",
            "group_a_id": 1,
            "group_b_id": 2,
            "expected_fips": "46102",
        },
        {
            "label": "Age",
            "dimension": "Age group",
            "group_a_id": 17,
            "group_b_id": 30,
            "expected_fips": "54047",
        },
    ]

    for case in cases:
        df = get_places_ihme_demographic_disparity_ranking(
            dimension=case["dimension"],
            group_a_id=case["group_a_id"],
            group_b_id=case["group_b_id"],
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
            f'{case["label"]}: expected 10 rows; got {len(df)}.',
        )

        assert_true(
            df["places_age_adjusted_prevalence"].ge(15.0).all(),
            f'{case["label"]}: prevalence filter failed.',
        )

        assert_true(
            df["signed_yll_gap"].is_monotonic_decreasing,
            f'{case["label"]}: ranking is not descending.',
        )

        assert_true(
            df.iloc[0]["fips"] == case["expected_fips"],
            f'{case["label"]}: unexpected leading county.',
        )

        print(
            f'{case["label"]}: PASS '
            f'({df.iloc[0]["ihme_location_name"]})'
        )

    strict_race = get_places_ihme_demographic_disparity_ranking(
        dimension="Race / ethnicity",
        group_a_id=4,
        group_b_id=5,
        places_measure_id="DIABETES",
        places_measurement_year=2019,
        ihme_cause_id=976,
        ihme_year=2019,
        minimum_places_prevalence=15.0,
        require_nonoverlap=True,
        limit=10,
    )

    assert_true(
        len(strict_race) == 1,
        f"Expected 1 strict race row; got {len(strict_race)}.",
    )

    assert_true(
        strict_race.iloc[0]["fips"] == "28027",
        "Unexpected strict race county.",
    )

    assert_true(
        strict_race["intervals_overlap"].eq(False).all(),
        "Strict race ranking contains overlapping intervals.",
    )

    print("Strict race uncertainty screen: PASS")
    print(
        "PLACES-IHME generic demographic disparity ranking "
        "validation: PASS"
    )


if __name__ == "__main__":
    main()
