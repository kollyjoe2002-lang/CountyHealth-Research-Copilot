from app.data_access import get_places_ihme_model_diagnostics


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    overall = get_places_ihme_model_diagnostics(
        places_measure_id="DIABETES",
        places_measurement_year=2019,
        ihme_cause_id=976,
        ihme_year=2019,
        rurality_group=None,
    ).iloc[0]

    assert_true(
        int(overall["counties"]) == 3090,
        "Expected 3,090 matched counties.",
    )

    assert_true(
        0 < float(overall["pearson_r"]) < 1,
        "Expected positive Pearson correlation.",
    )

    assert_true(
        0 < float(overall["r_squared"]) < 1,
        "Expected R-squared between 0 and 1.",
    )

    assert_true(
        abs(float(overall["residual_mean"])) < 1e-8,
        "Expected residual mean near zero.",
    )

    assert_true(
        float(overall["model_slope"]) > 0,
        "Expected positive regression slope.",
    )

    assert_true(
        float(overall["rmse"]) > 0,
        "Expected positive RMSE.",
    )

    print("PLACES-IHME model diagnostics validation: PASS")
    print(f"Counties     : {int(overall['counties']):,}")
    print(f"Pearson r    : {overall['pearson_r']:.6f}")
    print(f"R-squared    : {overall['r_squared']:.6f}")
    print(f"RMSE         : {overall['rmse']:.6f}")
    print(f"Slope        : {overall['model_slope']:.6f}")
    print(f"Intercept    : {overall['model_intercept']:.6f}")


if __name__ == "__main__":
    main()
