from app.data_access import get_places_rural_metro_comparison


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    df = get_places_rural_metro_comparison(
        "OBESITY",
        2023,
    )

    assert_true(
        len(df) == 2,
        f"Expected 2 rurality groups; got {len(df)}.",
    )

    assert_true(
        set(df["metro_status"]) == {"Metro", "Nonmetro"},
        f"Unexpected metro_status values: {set(df['metro_status'])}",
    )

    metro = df[df["metro_status"].eq("Metro")].iloc[0]
    nonmetro = df[df["metro_status"].eq("Nonmetro")].iloc[0]

    assert_true(
        int(metro["counties_with_estimate"]) == 1114,
        f"Expected 1,114 Metro counties; got {metro['counties_with_estimate']}.",
    )

    assert_true(
        int(nonmetro["counties_with_estimate"]) == 1842,
        (
            "Expected 1,842 Nonmetro counties; "
            f"got {nonmetro['counties_with_estimate']}."
        ),
    )

    assert_true(
        int(df["counties_with_estimate"].sum()) == 2956,
        "Expected 2,956 classified counties in total.",
    )

    assert_true(
        float(nonmetro["mean_prevalence"])
        > float(metro["mean_prevalence"]),
        "Expected Nonmetro mean obesity prevalence to exceed Metro.",
    )

    assert_true(
        df["measurement_year"].eq(2023).all(),
        "Unexpected measurement year in rural/metro comparison.",
    )

    assert_true(
        df["dataset"]
        .eq("CDC PLACES + USDA RUCC 2023")
        .all(),
        "Unexpected dataset provenance label.",
    )

    print("PLACES rural/metro comparison validation: PASS")
    print(f"Metro counties     : {int(metro['counties_with_estimate']):,}")
    print(f"Nonmetro counties  : {int(nonmetro['counties_with_estimate']):,}")
    print(
        f"Metro mean obesity : {float(metro['mean_prevalence']):.2f}%"
    )
    print(
        f"Nonmetro mean      : {float(nonmetro['mean_prevalence']):.2f}%"
    )


if __name__ == "__main__":
    main()