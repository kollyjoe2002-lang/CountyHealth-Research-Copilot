from __future__ import annotations

from dataclasses import dataclass

from ai.resolver import (
    ResolutionError,
    resolve_county,
)


@dataclass(frozen=True)
class CountyResolutionCase:
    case_id: str
    query: str
    should_resolve: bool
    expected_fips: str | None = None
    expected_location: str | None = None
    expected_error_fragment: str | None = None


CASES = [
    # ------------------------------------------------------------
    # UNIQUE COUNTY-ONLY NAMES
    # ------------------------------------------------------------
    CountyResolutionCase(
        "C01",
        "Milwaukee County",
        True,
        expected_fips="55079",
        expected_location="Milwaukee County (Wisconsin)",
    ),
    CountyResolutionCase(
        "C02",
        "Milwaukee County, Wisconsin",
        True,
        expected_fips="55079",
        expected_location="Milwaukee County (Wisconsin)",
    ),
    CountyResolutionCase(
        "C03",
        "Milwaukee County in Wisconsin",
        True,
        expected_fips="55079",
        expected_location="Milwaukee County (Wisconsin)",
    ),

    # ------------------------------------------------------------
    # AMBIGUOUS COUNTY-ONLY NAMES
    # ------------------------------------------------------------
    CountyResolutionCase(
        "C04",
        "Albany County",
        False,
        expected_error_fragment="ambiguous",
    ),
    CountyResolutionCase(
        "C05",
        "Albany County, Wyoming",
        True,
        expected_fips="56001",
        expected_location="Albany County (Wyoming)",
    ),
    CountyResolutionCase(
        "C06",
        "Albany County, New York",
        True,
        expected_fips="36001",
        expected_location="Albany County (New York)",
    ),
    CountyResolutionCase(
        "C07",
        "Yuma County",
        False,
        expected_error_fragment="ambiguous",
    ),
    CountyResolutionCase(
        "C08",
        "Yuma County, Arizona",
        True,
        expected_fips="04027",
        expected_location="Yuma County (Arizona)",
    ),
    CountyResolutionCase(
        "C09",
        "Yuma County, Colorado",
        True,
        expected_fips="08125",
        expected_location="Yuma County (Colorado)",
    ),

    # ------------------------------------------------------------
    # NORMAL NATURAL-LANGUAGE SENTENCES
    # ------------------------------------------------------------
    CountyResolutionCase(
        "C10",
        "What is diabetes like in Milwaukee County?",
        True,
        expected_fips="55079",
        expected_location="Milwaukee County (Wisconsin)",
    ),
    CountyResolutionCase(
        "C11",
        "Show me stroke in Yuma County, Arizona.",
        True,
        expected_fips="04027",
        expected_location="Yuma County (Arizona)",
    ),
    CountyResolutionCase(
        "C12",
        "Tell me about Albany County in Wyoming.",
        True,
        expected_fips="56001",
        expected_location="Albany County (Wyoming)",
    ),

    # ------------------------------------------------------------
    # FAIL-CLOSED / FALSE-POSITIVE BOUNDARIES
    # ------------------------------------------------------------
    CountyResolutionCase(
        "C13",
        "Milwauke County",
        False,
        expected_error_fragment="No current county",
    ),
    CountyResolutionCase(
        "C14",
        "Milwaukee",
        False,
        expected_error_fragment="No current county",
    ),
    CountyResolutionCase(
        "C15",
        "Albany",
        False,
        expected_error_fragment="No current county",
    ),
    CountyResolutionCase(
        "C16",
        "Yuma",
        False,
        expected_error_fragment="No current county",
    ),
    CountyResolutionCase(
        "C17",
        "This question contains no county name.",
        False,
        expected_error_fragment="No current county",
    ),
]


def main() -> None:
    failures: list[str] = []
    passed = 0

    print("=" * 100)
    print("EpiCounty County Resolution Validation")
    print("=" * 100)

    for case in CASES:
        print("-" * 100)
        print(f"{case.case_id}: {case.query}")

        try:
            result = resolve_county(
                case.query
            )

            if not case.should_resolve:
                failures.append(
                    f"{case.case_id}: expected rejection "
                    f"but resolved to {result}."
                )
                print("FAIL: expected rejection")
                print("RESULT:", result)
                continue

            actual_fips = result.get(
                "fips"
            )

            actual_location = result.get(
                "location_name"
            )

            errors: list[str] = []

            if (
                case.expected_fips is not None
                and actual_fips != case.expected_fips
            ):
                errors.append(
                    f"expected FIPS {case.expected_fips}, "
                    f"received {actual_fips}"
                )

            if (
                case.expected_location is not None
                and actual_location
                != case.expected_location
            ):
                errors.append(
                    "expected location "
                    f"{case.expected_location!r}, "
                    f"received {actual_location!r}"
                )

            if errors:
                failures.append(
                    f"{case.case_id}: "
                    + "; ".join(errors)
                )
                print("FAIL")
                for error in errors:
                    print("ERROR:", error)
                continue

            print("PASS")
            print("FIPS:", actual_fips)
            print(
                "LOCATION:",
                actual_location,
            )

            passed += 1

        except ResolutionError as exc:
            if case.should_resolve:
                failures.append(
                    f"{case.case_id}: unexpected "
                    f"ResolutionError: {exc}"
                )
                print("FAIL:", exc)
                continue

            error_text = str(exc)

            if (
                case.expected_error_fragment
                and case.expected_error_fragment.casefold()
                not in error_text.casefold()
            ):
                failures.append(
                    f"{case.case_id}: expected error containing "
                    f"{case.expected_error_fragment!r}, received "
                    f"{error_text!r}."
                )
                print("FAIL")
                print("ERROR:", error_text)
                continue

            print("PASS: safely rejected")
            print("REASON:", error_text)
            passed += 1

    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Passed: {passed}")
    print(f"Failed: {len(failures)}")
    print(f"Total:  {len(CASES)}")

    if failures:
        print()
        print("FAILURES:")
        for failure in failures:
            print("-", failure)

        raise AssertionError(
            "County-resolution validation failed."
        )

    print()
    print(
        f"COUNTY RESOLUTION VALIDATION: "
        f"ALL {len(CASES)} CASES PASSED"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()