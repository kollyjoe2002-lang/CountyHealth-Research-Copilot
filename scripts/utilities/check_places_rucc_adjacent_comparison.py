from app.data_access import get_places_rucc_adjacent_comparison


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    df = get_places_rucc_adjacent_comparison(
        "OBESITY",
        2023,
    )

    expected_counts = {
        "Metro": 1114,
        "Nonmetro adjacent": 978,
        "Nonmetro not adjacent": 864,
    }

    observed_groups = set(df["rurality_group"].tolist())

    assert_true(
        observed_groups == set(expected_counts),
        f"Unexpected rurality groups: {observed_groups}",
    )

    observed_counts = {
        row["rurality_group"]: int(row["counties_with_estimate"])
        for _, row in df.iterrows()
    }

    assert_true(
        observed_counts == expected_counts,
        f"Unexpected county counts: {observed_counts}",
    )

    assert_true(
        int(df["counties_with_estimate"].sum()) == 2956,
        "Expected 2,956 counties in total.",
    )

    assert_true(
        df["measurement_year"].eq(2023).all(),
        "Unexpected measurement year.",
    )

    assert_true(
        df["dataset"]
        .eq("CDC PLACES + USDA RUCC 2023")
        .all(),
        "Unexpected provenance label.",
    )

    print("PLACES RUCC adjacency comparison validation: PASS")
    print("Measurement year        : 2023")
    print("Measure                 : OBESITY")
    print("Metro counties          : 1,114")
    print("Nonmetro adjacent       : 978")
    print("Nonmetro not adjacent   : 864")
    print("Total counties          : 2,956")
    print()

    print(
        df[
            [
                "rurality_group",
                "counties_with_estimate",
                "mean_prevalence",
                "median_prevalence",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
