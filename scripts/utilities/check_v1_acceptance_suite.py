from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AcceptanceCheck:
    name: str
    module: str
    requires_openai: bool = False


CHECKS = [
    AcceptanceCheck(
        name="Database integrity",
        module="scripts.utilities.verify_database",
    ),
    AcceptanceCheck(
        name="Schema integrity",
        module="scripts.utilities.verify_schema",
    ),
    AcceptanceCheck(
        name="Geography harmonization",
        module=(
            "scripts.utilities."
            "check_geography_harmonization"
        ),
    ),
    AcceptanceCheck(
        name="County profile analytics",
        module="scripts.utilities.check_county_profile",
    ),
    AcceptanceCheck(
        name="County ranking analytics",
        module=(
            "scripts.utilities."
            "check_county_ranking_access"
        ),
    ),
    AcceptanceCheck(
        name="Disparity analytics",
        module="scripts.utilities.check_disparity_finder",
    ),
    AcceptanceCheck(
        name="AI negative cases",
        module="scripts.utilities.check_ai_negative_cases",
    ),
    AcceptanceCheck(
        name="Semantic evidence claims",
        module=(
            "scripts.utilities."
            "check_ai_evidence_claims"
        ),
    ),
    AcceptanceCheck(
        name="Interpretation input contract",
        module=(
            "scripts.utilities."
            "check_ai_interpretation_input"
        ),
    ),
    AcceptanceCheck(
        name="Structural interpretation validator",
        module=(
            "scripts.utilities."
            "check_ai_interpretation_validator"
        ),
    ),
    AcceptanceCheck(
        name="Deterministic semantic entailment",
        module=(
            "scripts.utilities."
            "check_ai_semantic_entailment"
        ),
    ),
    AcceptanceCheck(
        name="Model entailment judge",
        module=(
            "scripts.utilities."
            "check_ai_entailment_judge"
        ),
        requires_openai=True,
    ),
    AcceptanceCheck(
        name="Full AI chain across all intents",
        module=(
            "scripts.utilities."
            "check_ai_full_chain_all_intents"
        ),
        requires_openai=True,
    ),
    AcceptanceCheck(
        name="Research-assistant orchestration",
        module=(
            "scripts.utilities."
            "check_ai_research_assistant"
        ),
        requires_openai=True,
    ),
]


def run_check(
    check: AcceptanceCheck,
    *,
    warehouse: Path,
    auxiliary_databases_json: Path | None,
    geojson: Path | None,
) -> tuple[bool, float]:
    print("\n" + "=" * 88)
    print(f"CHECK: {check.name}")
    print(f"MODULE: {check.module}")
    print("=" * 88)

    if (
        check.requires_openai
        and not os.getenv("OPENAI_API_KEY")
    ):
        print(
            "FAIL: OPENAI_API_KEY is required "
            "for this acceptance check."
        )

        return False, 0.0

    started = time.perf_counter()

    target = ROOT / (
        check.module.replace(".", "/") + ".py"
    )

    worker = (
        ROOT
        / "scripts"
        / "utilities"
        / "release_gate_worker.py"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(worker),
            str(target.relative_to(ROOT)),
            str(warehouse),
            (
                str(auxiliary_databases_json)
                if auxiliary_databases_json is not None
                else "-"
            ),
            (
                str(geojson)
                if geojson is not None
                else "-"
            ),
        ],
        check=False,
        cwd=ROOT,
        env=os.environ.copy(),
    )

    duration = (
        time.perf_counter()
        - started
    )

    passed = (
        completed.returncode == 0
    )

    status = (
        "PASS"
        if passed
        else "FAIL"
    )

    print(
        f"\nRESULT: {status} "
        f"({duration:.1f}s)"
    )

    return passed, duration


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the V1 acceptance suite against an explicitly "
            "supplied read-only development warehouse."
        )
    )
    parser.add_argument(
        "--warehouse",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--auxiliary-databases-json",
        type=Path,
    )
    parser.add_argument(
        "--geojson",
        type=Path,
    )
    args = parser.parse_args()

    warehouse = args.warehouse.resolve()

    if not warehouse.is_file():
        raise SystemExit(
            "BLOCKED: explicit development warehouse missing"
        )

    print("=" * 88)
    print("EpiCounty V1 Acceptance Suite")
    print("=" * 88)

    print(
        f"Python: {sys.executable}"
    )

    print(
        "OpenAI key available: "
        f"{bool(os.getenv('OPENAI_API_KEY'))}"
    )

    results: list[
        tuple[AcceptanceCheck, bool, float]
    ] = []

    for check in CHECKS:
        passed, duration = run_check(
            check,
            warehouse=warehouse,
            auxiliary_databases_json=args.auxiliary_databases_json,
            geojson=args.geojson,
        )

        results.append(
            (
                check,
                passed,
                duration,
            )
        )

    print("\n" + "=" * 88)
    print("V1 ACCEPTANCE SUMMARY")
    print("=" * 88)

    passed_count = 0

    for check, passed, duration in results:
        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        if passed:
            passed_count += 1

        print(
            f"{status:<5} "
            f"{check.name:<42} "
            f"{duration:>8.1f}s"
        )

    total = len(results)

    print("-" * 88)

    print(
        f"Passed: {passed_count}/{total}"
    )

    if passed_count != total:
        failed_checks = [
            check.name
            for check, passed, _ in results
            if not passed
        ]

        print("\nFAILED CHECKS:")

        for name in failed_checks:
            print(
                f"  - {name}"
            )

        print("\nV1 RELEASE GATE: FAIL")

        raise SystemExit(1)

    print("\nV1 RELEASE GATE: PASS")


if __name__ == "__main__":
    main()