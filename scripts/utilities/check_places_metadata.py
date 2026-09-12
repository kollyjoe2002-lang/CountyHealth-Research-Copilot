from scripts.places.load_metadata import (
    CARRY_FORWARD_2025,
    build_measure_catalog,
    build_measure_versions,
    build_releases,
    load_dictionary,
    DEFAULT_DICTIONARY,
)


EXPECTED_COUNTS = {
    2020: 28,
    2021: 30,
    2022: 30,
    2023: 37,
    2024: 40,
    2025: 40,
}


def main() -> None:
    dictionary = load_dictionary(DEFAULT_DICTIONARY)

    measures = build_measure_catalog(dictionary)
    versions = build_measure_versions(dictionary)
    releases = build_releases()

    # ---------------------------------------------------------
    # Canonical catalog
    # ---------------------------------------------------------

    assert len(measures) == 45, (
        f"Expected 45 canonical measures, got {len(measures)}"
    )

    assert measures["measure_id"].is_unique, (
        "Canonical measure IDs are not unique"
    )

    # ---------------------------------------------------------
    # Releases
    # ---------------------------------------------------------

    assert len(releases) == 6, (
        f"Expected 6 releases, got {len(releases)}"
    )

    assert set(releases["release_year"]) == set(range(2020, 2026))

    # ---------------------------------------------------------
    # Measure versions
    # ---------------------------------------------------------

    counts = (
        versions.groupby("release_year")
        .size()
        .to_dict()
    )

    assert counts == EXPECTED_COUNTS, (
        f"Unexpected release counts: {counts}"
    )

    duplicate_versions = versions.duplicated(
        subset=["release_year", "measure_id"]
    )

    assert not duplicate_versions.any(), (
        "Duplicate release-year / measure-id rows found"
    )

    # ---------------------------------------------------------
    # 2025 carry-forward validation
    # ---------------------------------------------------------

    versions_2025 = versions[
        versions["release_year"] == 2025
    ]

    actual_carry_forward = set(
        versions_2025.loc[
            versions_2025["carry_forward"],
            "measure_id",
        ]
    )

    assert actual_carry_forward == CARRY_FORWARD_2025, (
        f"Unexpected 2025 carry-forward set: "
        f"{sorted(actual_carry_forward)}"
    )

    carry_forward_years = set(
        versions_2025.loc[
            versions_2025["carry_forward"],
            "measurement_year",
        ]
    )

    assert carry_forward_years == {2022}

    current_years = set(
        versions_2025.loc[
            ~versions_2025["carry_forward"],
            "measurement_year",
        ]
    )

    assert current_years == {2023}

    # ---------------------------------------------------------
    # ISOLATION / LONELINESS boundary
    # ---------------------------------------------------------

    isolation_years = set(
        versions.loc[
            versions["measure_id"] == "ISOLATION",
            "release_year",
        ]
    )

    loneliness_years = set(
        versions.loc[
            versions["measure_id"] == "LONELINESS",
            "release_year",
        ]
    )

    assert isolation_years == {2024}
    assert loneliness_years == {2025}

    # ---------------------------------------------------------
    # Measurement-year sanity
    # ---------------------------------------------------------

    assert versions["measurement_year"].notna().all()

    assert (
        versions["measurement_year"]
        <= versions["release_year"]
    ).all()

    print("=" * 70)
    print("PLACES metadata validation: PASS")
    print("=" * 70)

    print("Canonical measures :", len(measures))
    print("Measure versions   :", len(versions))
    print("Releases           :", len(releases))

    print()
    print("Release counts:")
    for year, count in EXPECTED_COUNTS.items():
        print(f"{year}: {count}")

    print()
    print(
        "2025 carry-forward:",
        ", ".join(sorted(CARRY_FORWARD_2025)),
    )

    print("ISOLATION releases :", sorted(isolation_years))
    print("LONELINESS releases:", sorted(loneliness_years))


if __name__ == "__main__":
    main()