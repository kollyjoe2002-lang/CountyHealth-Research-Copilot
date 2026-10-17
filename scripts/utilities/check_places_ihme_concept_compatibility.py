from __future__ import annotations

from ai.resolver import (
    PLACES_IHME_ALLOWED_PAIRS,
    ResolutionError,
    resolve_cause,
    resolve_places_measure,
    validate_places_ihme_pair,
)


def pass_case(case_id: str, message: str) -> bool:
    print(f"{case_id} PASS: {message}")
    return True


def fail_case(case_id: str, message: str) -> bool:
    print(f"{case_id} FAIL: {message}")
    return False


def expect_allowed(
    case_id: str,
    places_text: str,
    cause_text: str,
    *,
    disparity: bool = False,
) -> bool:
    try:
        places_measure = resolve_places_measure(
            places_text
        )

        cause = resolve_cause(
            cause_text,
            disparity=disparity,
        )

        validate_places_ihme_pair(
            places_measure,
            cause,
        )

    except ResolutionError as exc:
        return fail_case(
            case_id,
            f"approved pair was blocked: {exc}",
        )

    return pass_case(
        case_id,
        (
            f"{places_measure['measure_id']} ↔ "
            f"IHME cause {cause['cause_id']} "
            f"({cause['cause_name']})"
        ),
    )


def expect_pair_blocked(
    case_id: str,
    places_text: str,
    cause_text: str,
    *,
    disparity: bool = False,
) -> bool:
    try:
        places_measure = resolve_places_measure(
            places_text
        )

        cause = resolve_cause(
            cause_text,
            disparity=disparity,
        )

        validate_places_ihme_pair(
            places_measure,
            cause,
        )

    except ResolutionError as exc:
        return pass_case(
            case_id,
            f"blocked safely: {exc}",
        )

    return fail_case(
        case_id,
        (
            "unsupported pair was incorrectly allowed: "
            f"{places_measure['measure_id']} ↔ "
            f"IHME cause {cause['cause_id']}"
        ),
    )


def expect_places_resolution_blocked(
    case_id: str,
    places_text: str,
) -> bool:
    try:
        places_measure = resolve_places_measure(
            places_text
        )

    except ResolutionError as exc:
        return pass_case(
            case_id,
            f"PLACES concept blocked safely: {exc}",
        )

    return fail_case(
        case_id,
        (
            "unsupported PLACES concept resolved unexpectedly "
            f"to {places_measure['measure_id']}."
        ),
    )


def expect_measure_not_approved(
    case_id: str,
    measure_id: str,
) -> bool:
    try:
        places_measure = resolve_places_measure(
            measure_id
        )

    except ResolutionError as exc:
        return fail_case(
            case_id,
            (
                f"expected PLACES measure {measure_id} "
                f"did not resolve: {exc}"
            ),
        )

    resolved_id = str(
        places_measure["measure_id"]
    ).upper()

    if resolved_id in PLACES_IHME_ALLOWED_PAIRS:
        return fail_case(
            case_id,
            (
                f"{resolved_id} unexpectedly appears in "
                "PLACES_IHME_ALLOWED_PAIRS."
            ),
        )

    return pass_case(
        case_id,
        (
            f"{resolved_id} exists in PLACES but has no "
            "approved IHME cross-source pair."
        ),
    )


def main() -> None:
    print("=" * 100)
    print(
        "EpiCounty PLACES_IHME Concept "
        "Compatibility Validation"
    )
    print("=" * 100)

    results = [
        expect_allowed(
            "C01",
            "diabetes",
            "type 2 diabetes",
        ),
        expect_allowed(
            "C02",
            "stroke",
            "stroke",
        ),
        expect_allowed(
            "C03",
            "asthma",
            "asthma",
        ),
        expect_pair_blocked(
            "C04",
            "stroke",
            "type 2 diabetes",
        ),
        expect_pair_blocked(
            "C05",
            "diabetes",
            "stroke",
        ),
        expect_places_resolution_blocked(
            "C06",
            "breast cancer",
        ),
        expect_pair_blocked(
            "C07",
            "CANCER",
            "breast cancer",
        ),
        expect_measure_not_approved(
            "C08",
            "CHD",
        ),
        expect_measure_not_approved(
            "C09",
            "KIDNEY",
        ),
        expect_measure_not_approved(
            "C10",
            "COPD",
        ),
    ]

    passed = sum(results)
    total = len(results)

    print("=" * 100)
    print(
        "PLACES_IHME CONCEPT COMPATIBILITY: "
        f"{passed}/{total} PASSED"
    )
    print("=" * 100)

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()