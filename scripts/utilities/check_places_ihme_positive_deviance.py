from app.data_access import get_places_ihme_positive_deviance


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    df = get_places_ihme_positive_deviance(
        places_measure_id="DIABETES",
        places_measurement_year=2019,
        ihme_cause_id=976,
        ihme_year=2019,
        rurality_group="Nonmetro adjacent",
        limit=15,
    )

    assert_true(
        len(df) == 15,
        f"Expected 15 rows; got {len(df)}.",
    )

    assert_true(
        df["fips"].nunique() == 15,
        "Expected unique county FIPS.",
    )

    assert_true(
        df["rurality_group"]
        .eq("Nonmetro adjacent")
        .all(),
        "Unexpected rurality group.",
    )

    assert_true(
        (df["yll_residual"] < 0).all(),
        "Expected all top positive-deviance residuals to be negative.",
    )

    assert_true(
        df["yll_residual"].is_monotonic_increasing,
        "Residuals must be ordered from most negative upward.",
    )

    assert_true(
        df["model_slope"].nunique() == 1,
        "Expected one fitted slope.",
    )

    assert_true(
        df["model_intercept"].nunique() == 1,
        "Expected one fitted intercept.",
    )

    assert_true(
        float(df["model_slope"].iloc[0]) > 0,
        "Expected positive prevalence-YLL slope.",
    )

    assert_true(
        df.iloc[0]["fips"] == "48427",
        "Unexpected leading positive-deviance candidate.",
    )

    print("PLACES-IHME positive deviance validation: PASS")
    print("Rurality group : Nonmetro adjacent")
    print("Candidates     : 15")
    print(
        "Model slope    : "
        f"{df['model_slope'].iloc[0]:.6f}"
    )
    print(
        "Model intercept: "
        f"{df['model_intercept'].iloc[0]:.6f}"
    )
    print()
    print(
        df[
            [
                "fips",
                "ihme_location_name",
                "places_age_adjusted_prevalence",
                "ihme_yll_rate",
                "expected_ihme_yll_rate",
                "yll_residual",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
