from app.data_access import get_places_ihme_rurality_comparison


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    df = get_places_ihme_rurality_comparison(
        places_measure_id="DIABETES",
        places_measurement_year=2019,
        ihme_cause_id=976,
        ihme_year=2019,
    )

    expected_counts = {
        "Metro": 1158,
        "Nonmetro adjacent": 1039,
        "Nonmetro not adjacent": 884,
    }

    observed_counts = {
        row["rurality_group"]: int(row["counties"])
        for _, row in df.iterrows()
    }

    assert_true(
        observed_counts == expected_counts,
        f"Unexpected county counts: {observed_counts}",
    )

    assert_true(
        int(df["counties"].sum()) == 3081,
        "Expected 3,081 RUCC-classified matched counties.",
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

    assert_true(
        df["dataset"]
        .eq("CDC PLACES + IHME + USDA RUCC 2023")
        .all(),
        "Unexpected provenance label.",
    )

    metro = df[df["rurality_group"] == "Metro"].iloc[0]
    adjacent = df[
        df["rurality_group"] == "Nonmetro adjacent"
    ].iloc[0]

    assert_true(
        adjacent["mean_places_prevalence"]
        > metro["mean_places_prevalence"],
        "Expected higher mean diabetes prevalence in adjacent nonmetro counties.",
    )

    assert_true(
        adjacent["mean_ihme_yll_rate"]
        > metro["mean_ihme_yll_rate"],
        "Expected higher mean IHME YLL rate in adjacent nonmetro counties.",
    )

    print("PLACES-IHME rurality comparison validation: PASS")
    print("Metro counties              : 1,158")
    print("Nonmetro adjacent           : 1,039")
    print("Nonmetro not adjacent       : 884")
    print("Total counties              : 3,081")
    print()
    print(
        df[
            [
                "rurality_group",
                "counties",
                "mean_places_prevalence",
                "mean_ihme_yll_rate",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()