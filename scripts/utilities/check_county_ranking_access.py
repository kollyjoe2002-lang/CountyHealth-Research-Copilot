from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.data_access import get_county_ranking  # noqa: E402


def main() -> None:
    print("=" * 80)
    print("County Ranking Data-Access Validation")
    print("=" * 80)

    ranking = get_county_ranking(
        cause_id=976,
        year=2019,
        limit=15,
    )

    if ranking.empty:
        raise AssertionError(
            "County ranking returned no rows."
        )

    required_columns = {
        "national_display_order",
        "national_county_rank",
        "fips",
        "location_name",
        "cause_id",
        "cause_name",
        "year",
        "yll_rate",
        "counties_with_estimate",
        "burden_percentile",
    }

    missing = required_columns.difference(
        ranking.columns
    )

    if missing:
        raise AssertionError(
            f"Missing columns: {sorted(missing)}"
        )

    if len(ranking) != 15:
        raise AssertionError(
            f"Expected 15 rows, received {len(ranking)}."
        )

    if not ranking["fips"].is_unique:
        raise AssertionError(
            "Ranking contains duplicate county FIPS values."
        )

    if not ranking[
        "national_display_order"
    ].is_monotonic_increasing:
        raise AssertionError(
            "Ranking is not ordered by national display order."
        )

    print(
        ranking.to_string(
            index=False
        )
    )

    print()
    print("=" * 80)
    print(
        "County ranking data-access validation "
        "completed successfully"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()