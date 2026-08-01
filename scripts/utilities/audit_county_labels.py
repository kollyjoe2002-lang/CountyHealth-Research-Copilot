from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.data_access import get_counties  # noqa: E402


def heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def find_issues(display_name: str) -> list[str]:
    issues: list[str] = []

    if display_name != display_name.strip():
        issues.append("leading or trailing whitespace")

    if "  " in display_name:
        issues.append("double space")

    if re.search(r"\S\(", display_name):
        issues.append("missing space before opening parenthesis")

    if re.search(r"\(\s+", display_name):
        issues.append("space immediately after opening parenthesis")

    if re.search(r"\s+\)", display_name):
        issues.append("space immediately before closing parenthesis")

    if display_name.count("(") != display_name.count(")"):
        issues.append("unbalanced parentheses")

    return issues


def main() -> None:
    print("=" * 80)
    print("County Display-Label Audit")
    print("=" * 80)

    counties = get_counties()

    if counties.empty:
        raise RuntimeError("No county records were returned.")

    required_columns = {
        "location_id",
        "location_name",
        "display_name",
        "fips",
    }

    missing_columns = required_columns.difference(counties.columns)

    if missing_columns:
        raise RuntimeError(
            "County lookup is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    audit_rows: list[dict[str, object]] = []

    for row in counties.itertuples(index=False):
        display_name = str(row.display_name)
        issues = find_issues(display_name)

        if issues:
            audit_rows.append(
                {
                    "location_id": row.location_id,
                    "fips": row.fips,
                    "location_name": row.location_name,
                    "display_name": display_name,
                    "issues": "; ".join(issues),
                }
            )

    heading("Audit summary")

    print(f"County rows checked: {len(counties):,}")
    print(f"County rows with issues: {len(audit_rows):,}")

    if not audit_rows:
        print("No county display-label formatting issues were found.")
    else:
        heading("Formatting issues")

        for item in audit_rows:
            print(
                f"FIPS {item['fips']} | "
                f"{item['display_name']} | "
                f"{item['issues']}"
            )

            if item["location_name"] != item["display_name"]:
                print(f"  Source name: {item['location_name']}")

    heading("Duplicate display names")

    duplicates = (
        counties.groupby("display_name", dropna=False)
        .size()
        .reset_index(name="row_count")
        .query("row_count > 1")
        .sort_values(
            by=["row_count", "display_name"],
            ascending=[False, True],
        )
    )

    print(f"Duplicate display names: {len(duplicates):,}")

    if not duplicates.empty:
        print(duplicates.to_string(index=False))

    print()
    print("=" * 80)

    if audit_rows or not duplicates.empty:
        print("County display-label audit completed with issues.")
    else:
        print("County display-label audit completed successfully.")

    print("=" * 80)


if __name__ == "__main__":
    main()