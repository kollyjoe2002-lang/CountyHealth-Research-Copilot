from app.data_access import (
    get_places_ihme_race_disparity_trend_context,
    get_places_ihme_sex_disparity_trend_context,
    get_places_ihme_age_disparity_trend_context,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    race = get_places_ihme_race_disparity_trend_context(
        fips="28027",
        places_measure_id="DIABETES",
        ihme_cause_id=976,
    )

    sex = get_places_ihme_sex_disparity_trend_context(
        fips="28027",
        places_measure_id="DIABETES",
        ihme_cause_id=976,
    )

    age = get_places_ihme_age_disparity_trend_context(
        fips="28027",
        places_measure_id="DIABETES",
        ihme_cause_id=976,
    )

    for label, df in [
        ("Race", race),
        ("Sex", sex),
        ("Age", age),
    ]:
        assert_true(
            len(df) == 24,
            f"{label}: expected 24 rows; got {len(df)}.",
        )

        overlap_years = df.loc[
            df["same_year_overlap"],
            "analysis_year",
        ].astype(int).tolist()

        assert_true(
            overlap_years == [2018, 2019],
            f"{label}: unexpected overlap years {overlap_years}.",
        )

    race_2019 = race[
        race["analysis_year"].eq(2019)
    ].iloc[0]

    assert_true(
        abs(
            float(race_2019["black_white_yll_gap"])
            - 1436.706788
        ) < 1e-6,
        "Unexpected 2019 race gap.",
    )

    assert_true(
        race_2019["clear_disparity_direction"]
        == "Black clearly higher",
        "Unexpected 2019 race classification.",
    )

    sex_2019 = sex[
        sex["analysis_year"].eq(2019)
    ].iloc[0]

    assert_true(
        abs(
            float(sex_2019["male_female_yll_gap"])
            - 706.505000
        ) < 1e-6,
        "Unexpected 2019 sex gap.",
    )

    assert_true(
        sex_2019["clear_disparity_direction"]
        == "Intervals overlap",
        "Unexpected 2019 sex classification.",
    )

    age_2019 = age[
        age["analysis_year"].eq(2019)
    ].iloc[0]

    assert_true(
        abs(
            float(
                age_2019[
                    "age_60_64_minus_80_84_yll_gap"
                ]
            )
            - (-450.141088)
        ) < 1e-6,
        "Unexpected 2019 age gap.",
    )

    assert_true(
        age_2019["clear_disparity_direction"]
        == "Intervals overlap",
        "Unexpected 2019 age classification.",
    )

    print("PLACES-IHME disparity trend wrappers validation: PASS")
    print("Race 2019 gap : 1436.706788")
    print("Sex 2019 gap  : 706.505000")
    print("Age 2019 gap  : -450.141088")
    print("Overlap years : 2018, 2019")


if __name__ == "__main__":
    main()
