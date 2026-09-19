import subprocess
import sys
from pathlib import Path


CHECKS = [
    "check_places_ihme_county_context.py",
    "check_places_ihme_race_disparity_context.py",
    "check_places_ihme_sex_disparity_context.py",
    "check_places_ihme_age_disparity_context.py",
    "check_places_ihme_race_disparity_ranking.py",
    "check_places_ihme_sex_disparity_ranking.py",
    "check_places_ihme_age_disparity_ranking.py",
    "check_places_ihme_demographic_disparity_ranking.py",
    "check_places_ihme_county_trend_context.py",
    "check_places_ihme_demographic_disparity_trend_context.py",
    "check_places_ihme_disparity_trend_wrappers.py",
    "check_places_ihme_cross_source_regression_matrix.py",
]


def main():
    utilities_dir = Path(__file__).resolve().parent

    failures = []

    for check in CHECKS:
        path = utilities_dir / check

        print()
        print("=" * 72)
        print(check)
        print("=" * 72)

        result = subprocess.run(
            [sys.executable, str(path)],
            text=True,
        )

        if result.returncode != 0:
            failures.append(check)

    print()
    print("=" * 72)

    if failures:
        print("PLACES-IHME DETERMINISTIC SUITE: FAIL")
        print("Failed checks:")
        for check in failures:
            print(f"  - {check}")
        raise SystemExit(1)

    print("PLACES-IHME DETERMINISTIC SUITE: PASS")
    print(f"Checks passed: {len(CHECKS)}")


if __name__ == "__main__":
    main()
