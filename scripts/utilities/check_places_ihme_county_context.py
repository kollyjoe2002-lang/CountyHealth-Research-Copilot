from app.data_access import get_places_ihme_county_context


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    df = get_places_ihme_county_context(
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
        "Expected one unique row per county FIPS.",
    )

    assert_true(
        df["places_measurement_year"].eq(2019).all(),
        "Unexpected PLACES measurement year.",
    )

    assert_true(
        df["ihme_year"].eq(2019).all(),
        "Unexpected IHME year.",
    )

    assert_true(
        df["places_measure_id"].eq("DIABETES").all(),
        "Unexpected PLACES measure.",
    )

    assert_true(
        df["ihme_cause_id"].eq(976).all(),
        "Unexpected IHME cause.",
    )

    assert_true(
        df["ihme_cause_name"]
        .eq("Diabetes mellitus type 2")
        .all(),
        "Unexpected IHME cause name.",
    )

    assert_true(
        df["places_age_adjusted_prevalence"].notna().all(),
        "PLACES prevalence contains missing values.",
    )

    assert_true(
        df["ihme_yll_rate"].notna().all(),
        "IHME YLL rate contains missing values.",
    )

    assert_true(
        df["rucc_code"].notna().sum() == 3081,
        "Expected 3,081 RUCC-classified matched counties.",
    )

    assert_true(
        df["places_source"].eq("CDC PLACES").all(),
        "Unexpected PLACES provenance.",
    )

    assert_true(
        df["ihme_source"].eq("IHME").all(),
        "Unexpected IHME provenance.",
    )

    print("PLACES-IHME county context validation: PASS")
    print("Matched counties        : 3,090")
    print("Unique FIPS             : 3,090")
    print("RUCC classified         : 3,081")
    print("PLACES measure          : DIABETES")
    print("PLACES measurement year : 2019")
    print("IHME cause              : Diabetes mellitus type 2")
    print("IHME year               : 2019")


if __name__ == "__main__":
    main()
