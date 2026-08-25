from __future__ import annotations

from dataclasses import dataclass

from ai.models import (
    AnalysisIntent,
    ClassifiedQuestion,
    ResearchQuestion,
)
from ai.resolver import (
    ResolutionError,
    resolve_demographic_groups,
)


@dataclass(frozen=True)
class DemographicResolutionCase:
    case_id: str
    dimension: str
    groups: list[str]
    should_resolve: bool
    expected_group_a: str | None = None
    expected_group_b: str | None = None


CASES = [
    DemographicResolutionCase(
        "D01",
        "Age group",
        ["60 to 64", "80 to 84"],
        True,
        "60 to 64",
        "80 to 84",
    ),
    DemographicResolutionCase(
        "D02",
        "Age group",
        ["60-64", "80-84"],
        True,
        "60 to 64",
        "80 to 84",
    ),
    DemographicResolutionCase(
        "D03",
        "Age group",
        ["60–64", "80–84"],
        True,
        "60 to 64",
        "80 to 84",
    ),
    DemographicResolutionCase(
        "D04",
        "Age group",
        ["ages 60-64", "age 80 to 84"],
        True,
        "60 to 64",
        "80 to 84",
    ),
    DemographicResolutionCase(
        "D05",
        "Age group",
        ["64-60", "80-84"],
        False,
    ),
    DemographicResolutionCase(
        "D06",
        "Race / ethnicity",
        ["Black", "White"],
        True,
        "Non-Latino, Black",
        "Non-Latino, White",
    ),
    DemographicResolutionCase(
        "D07",
        "Sex",
        ["men", "women"],
        True,
        "Male",
        "Female",
    ),
]


def main() -> None:
    failures: list[str] = []
    passed = 0

    print("=" * 100)
    print("EpiCounty Demographic Group Resolution Validation")
    print("=" * 100)

    for case in CASES:
        print("-" * 100)
        print(
            f"{case.case_id}: "
            f"{case.dimension} -> {case.groups}"
        )

        classified = ClassifiedQuestion(
            question=ResearchQuestion(
                raw_text="demographic resolution test"
            ),
            intent=AnalysisIntent.DEMOGRAPHIC_DISPARITY,
            confidence=1.0,
            extracted_entities={
                "dimension": case.dimension,
                "demographic_groups": case.groups,
                "years": [2019],
            },
        )

        try:
            result = resolve_demographic_groups(
                classified
            )

            if not case.should_resolve:
                failures.append(
                    f"{case.case_id}: expected rejection "
                    f"but resolved to {result}."
                )
                print("FAIL: expected rejection")
                continue

            errors: list[str] = []

            if (
                case.expected_group_a is not None
                and result["group_a_name"]
                != case.expected_group_a
            ):
                errors.append(
                    f"group A expected "
                    f"{case.expected_group_a!r}, "
                    f"received "
                    f"{result['group_a_name']!r}"
                )

            if (
                case.expected_group_b is not None
                and result["group_b_name"]
                != case.expected_group_b
            ):
                errors.append(
                    f"group B expected "
                    f"{case.expected_group_b!r}, "
                    f"received "
                    f"{result['group_b_name']!r}"
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
            print("RESULT:", result)
            passed += 1

        except ResolutionError as exc:
            if case.should_resolve:
                failures.append(
                    f"{case.case_id}: unexpected "
                    f"ResolutionError: {exc}"
                )
                print("FAIL:", exc)
                continue

            print("PASS: safely rejected")
            print("REASON:", exc)
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
            "Demographic-group resolution validation failed."
        )

    print()
    print(
        f"DEMOGRAPHIC GROUP RESOLUTION: "
        f"ALL {len(CASES)} CASES PASSED"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()