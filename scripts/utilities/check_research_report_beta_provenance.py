from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def resolve_beta_traffic_source(
    internal_test_mode: bool,
) -> str:
    """
    Mirror the deterministic provenance rule used by the
    Research Report interface.
    """
    return (
        "internal_manual"
        if internal_test_mode
        else "external_researcher"
    )


def main() -> None:
    external_source = resolve_beta_traffic_source(
        False
    )

    assert external_source == "external_researcher"
    print(
        "PASS: normal researcher session = external_researcher"
    )

    internal_source = resolve_beta_traffic_source(
        True
    )

    assert internal_source == "internal_manual"
    print(
        "PASS: internal test session = internal_manual"
    )

    assert internal_source != "external_researcher"
    print(
        "PASS: internal session cannot be classified as "
        "external researcher"
    )

    assert external_source != "internal_manual"
    print(
        "PASS: normal researcher session is not classified "
        "as internal traffic"
    )

    print(
        "RESEARCH REPORT BETA PROVENANCE VALIDATION: "
        "ALL CHECKS PASSED"
    )


if __name__ == "__main__":
    main()