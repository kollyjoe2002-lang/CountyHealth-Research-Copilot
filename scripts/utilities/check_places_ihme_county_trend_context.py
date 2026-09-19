from app.data_access import (
    get_places_ihme_county_trend_context,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    df = get_places_ihme_county_trend_context(
        fips="28027",
        places_measure_id="DIABETES",
        ihme_cause_id=976,
    )

    assert_true(
        len(df) == 24,
        f"Expected 24 combined year rows; got {len(df)}.",
    )

    assert_true(
        int(df["analysis_year"].min()) == 2000,
        "Expected combined trend to begin in 2000.",
    )

    assert_true(
        int(df["analysis_year"].max()) == 2023,
        "Expected combined trend to end in 2023.",
    )

    places_years = df.loc[
        df["places_available"],
        "analysis_year",
    ].astype(int).tolist()

    assert_true(
        places_years == [
            2018,
            2019,
            2020,
            2021,
            2022,
            2023,
        ],
        f"Unexpected PLACES years: {places_years}",
    )

    ihme_years = df.loc[
        df["ihme_available"],
        "analysis_year",
    ].astype(int).tolist()

    assert_true(
        ihme_years == list(range(2000, 2020)),
        f"Unexpected IHME years: {ihme_years}",
    )

    overlap_years = df.loc[
        df["same_year_overlap"],
        "analysis_year",
    ].astype(int).tolist()

    assert_true(
        overlap_years == [2018, 2019],
        f"Unexpected overlap years: {overlap_years}",
    )

    row_2019 = df[
        df["analysis_year"].eq(2019)
    ].iloc[0]

    assert_true(
        abs(
            float(
                row_2019[
                    "places_age_adjusted_prevalence"
                ]
            )
            - 18.6
        ) < 1e-9,
        "Unexpected 2019 PLACES prevalence.",
    )

    assert_true(
        abs(
            float(row_2019["ihme_yll_rate"])
            - 1747.988134
        ) < 1e-6,
        "Unexpected 2019 IHME YLL rate.",
    )

    assert_true(
        int(
            row_2019["places_release_year"]
        ) == 2021,
        "Expected 2019 PLACES measurement to come from release 2021.",
    )

    row_2023 = df[
        df["analysis_year"].eq(2023)
    ].iloc[0]

    assert_true(
        bool(row_2023["places_available"]),
        "Expected PLACES data in 2023.",
    )

    assert_true(
        not bool(row_2023["ihme_available"]),
        "IHME should not be available in 2023.",
    )

    assert_true(
        not bool(row_2023["same_year_overlap"]),
        "2023 should not be a same-year overlap.",
    )

    print("PLACES-IHME county trend context validation: PASS")
    print("Combined rows       : 24")
    print("IHME years          : 2000-2019")
    print("PLACES years        : 2018-2023")
    print("Overlap years       : 2018, 2019")
    print("2019 PLACES         : 18.6%")
    print("2019 IHME YLL rate  : 1747.988134")


if __name__ == "__main__":
    main()
