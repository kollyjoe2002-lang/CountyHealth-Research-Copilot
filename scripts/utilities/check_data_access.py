from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.data_access import (  # noqa: E402
    DB_FILE,
    get_available_years,
    get_bmi_summary,
    get_causes,
    get_counties,
    get_cause_trend,
    get_long_term_change,
    get_top_causes,
    run_query,
)


def heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> None:
    print("=" * 80)
    print("Data-Access Layer Validation")
    print("=" * 80)

    print(f"Database: {DB_FILE}")

    heading("County lookup")

    counties = get_counties()

    print(f"Rows: {len(counties):,}")
    print(counties.head(5).to_string(index=False))

    heading("Available years")

    years = get_available_years()

    print(years)
    print(f"Year count: {len(years)}")

    heading("Cause lookup")

    causes = get_causes()

    print(f"Rows: {len(causes):,}")
    print(causes.head(10).to_string(index=False))

    test_fips = "56001"
    test_year = 2019

    heading("Albany County top causes")

    top_causes = get_top_causes(
        fips=test_fips,
        year=test_year,
        limit=10,
    )

    print(top_causes.to_string(index=False))

    if top_causes.empty:
        raise RuntimeError(
            "No top-cause records returned for Albany County."
        )

    test_cause_id = int(top_causes.iloc[0]["cause_id"])

    heading("Leading-cause trend")

    trend = get_cause_trend(
        fips=test_fips,
        cause_id=test_cause_id,
    )

    print(trend.to_string(index=False))

    heading("Long-term cause change")

    long_term = get_long_term_change(test_fips)

    print(f"Rows: {len(long_term):,}")
    print(long_term.head(10).to_string(index=False))

    heading("BMI metric values")

    metrics = run_query(
        """
        SELECT DISTINCT
            metric,
            LENGTH(metric) AS metric_length,
            HEX(metric) AS hex_value
        FROM analytics.vw_county_bmi_summary
        ORDER BY metric
        """
    )

    print(metrics.to_string(index=False))

    heading("BMI summary schema and sample")

    bmi = get_bmi_summary(
        fips=test_fips,
        year=test_year,
    )

    print("Columns:")
    print(bmi.columns.tolist())

    print()
    print("Rows:")
    print(bmi.to_string(index=False))

    print()
    print("=" * 80)
    print("Data-access validation completed successfully")
    print("=" * 80)


if __name__ == "__main__":
    main()