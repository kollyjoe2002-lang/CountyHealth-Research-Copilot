"""
Inspect the structure and coverage of the county-level IHME PAF table.

The large PAF table is profiled in one aggregate scan. This preserves the
original structural diagnostics without repeatedly scanning hundreds of
millions of rows.
"""

from pathlib import Path

import duckdb

from app import data_access


DB_FILE = Path(data_access.DB_FILE).resolve()


def main() -> None:
    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"Qualification warehouse not found: {DB_FILE}"
        )

    con = duckdb.connect(str(DB_FILE), read_only=True)

    try:
        print("=" * 70)
        print("County PAF Structure Check")
        print("=" * 70)

        profile = con.execute(
            """
            SELECT
                COUNT(*) AS rows,
                MIN(year) AS first_year,
                MAX(year) AS last_year,
                COUNT(DISTINCT year) AS years,
                COUNT(DISTINCT cause_name) AS distinct_causes,
                LIST(DISTINCT cause_name ORDER BY cause_name)
                    AS causes,
                LIST(DISTINCT measure_name ORDER BY measure_name)
                    AS measures,
                LIST(DISTINCT metric_name ORDER BY metric_name)
                    AS metrics,
                LIST(DISTINCT sex_name ORDER BY sex_name)
                    AS sexes,
                LIST(DISTINCT race_name ORDER BY race_name)
                    AS races,
                LIST(DISTINCT age_name ORDER BY age_name)
                    AS age_groups,
                COUNT(DISTINCT location_id) AS locations,
                COUNT(DISTINCT fips) AS fips_codes,
                COUNT(*) FILTER (WHERE fips IS NULL)
                    AS null_fips
            FROM ihme.paf
            """
        ).fetchone()

        (
            rows,
            first_year,
            last_year,
            years,
            distinct_causes,
            causes,
            measures,
            metrics,
            sexes,
            races,
            age_groups,
            locations,
            fips_codes,
            null_fips,
        ) = profile

        print("\nRow count")
        print(rows)

        print("\nYear coverage")
        print(
            f"first_year={first_year}, "
            f"last_year={last_year}, "
            f"years={years}"
        )

        print("\nCauses")
        print(f"distinct_causes={distinct_causes}")
        for value in causes:
            print(value)

        print("\nMeasures")
        for value in measures:
            print(value)

        print("\nMetrics")
        for value in metrics:
            print(value)

        print("\nSexes")
        for value in sexes:
            print(value)

        print("\nRaces")
        for value in races:
            print(value)

        print("\nAge groups")
        for value in age_groups:
            print(value)

        print("\nDistinct locations")
        print(
            f"locations={locations}, "
            f"fips_codes={fips_codes}"
        )

        print("\nNull FIPS")
        print(null_fips)

        print("\nPAF table columns")
        columns = con.execute(
            "DESCRIBE ihme.paf"
        ).fetchall()

        for column in columns:
            print(column)

    finally:
        con.close()


if __name__ == "__main__":
    main()
