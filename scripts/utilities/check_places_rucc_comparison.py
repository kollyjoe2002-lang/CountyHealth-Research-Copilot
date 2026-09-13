from app.data_access import get_places_rucc_comparison


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    df = get_places_rucc_comparison(
        "OBESITY",
        2023,
    )

    expected_counts = {
        1: 415,
        2: 360,
        3: 339,
        4: 188,
        5: 73,
        6: 353,
        7: 229,
        8: 437,
        9: 562,
    }

    assert_true(
        len(df) == 9,
        f"Expected 9 RUCC groups; got {len(df)}.",
    )

    observed_codes = set(
        df["rucc_code"].astype(int).tolist()
    )

    assert_true(
        observed_codes == set(range(1, 10)),
        f"Unexpected RUCC codes: {sorted(observed_codes)}",
    )

    observed_counts = {
        int(row["rucc_code"]): int(row["counties_with_estimate"])
        for _, row in df.iterrows()
    }

    assert_true(
        observed_counts == expected_counts,
        (
            "Unexpected county counts by RUCC code: "
            f"{observed_counts}"
        ),
    )

    assert_true(
        int(df["counties_with_estimate"].sum()) == 2956,
        "Expected 2,956 classified counties in total.",
    )

    metro_codes = df[df["rucc_code"].isin([1, 2, 3])]

    assert_true(
        metro_codes["metro_status"].eq("Metro").all(),
        "RUCC codes 1-3 must be classified as Metro.",
    )

    nonmetro_codes = df[df["rucc_code"].isin([4, 5, 6, 7, 8, 9])]

    assert_true(
        nonmetro_codes["metro_status"].eq("Nonmetro").all(),
        "RUCC codes 4-9 must be classified as Nonmetro.",
    )

    adjacent_codes = df[df["rucc_code"].isin([4, 6, 8])]

    assert_true(
        adjacent_codes["adjacency_status"]
        .eq("Adjacent to metro")
        .all(),
        "RUCC codes 4, 6, and 8 must be metro-adjacent.",
    )

    nonadjacent_codes = df[df["rucc_code"].isin([5, 7, 9])]

    assert_true(
        nonadjacent_codes["adjacency_status"]
        .eq("Not adjacent to metro")
        .all(),
        "RUCC codes 5, 7, and 9 must be nonadjacent.",
    )

    assert_true(
        df["measurement_year"].eq(2023).all(),
        "Unexpected measurement year.",
    )

    assert_true(
        df["dataset"]
        .eq("CDC PLACES + USDA RUCC 2023")
        .all(),
        "Unexpected dataset provenance.",
    )

    print("PLACES RUCC comparison validation: PASS")
    print("Measurement year : 2023")
    print("Measure          : OBESITY")
    print("RUCC groups      : 1-9")
    print("Total counties   : 2,956")
    print()

    print(
        df[
            [
                "rucc_code",
                "counties_with_estimate",
                "mean_prevalence",
                "median_prevalence",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()