from pathlib import Path
import sys

import duckdb

from scripts.places.load_metadata import (
    DEFAULT_DICTIONARY,
    SCHEMA_FILE,
    build_measure_catalog,
    build_measure_versions,
    build_releases,
    load_dictionary,
)


def write_metadata(
    db_path: Path,
    dictionary_path: Path = DEFAULT_DICTIONARY,
) -> None:
    db_path = db_path.resolve()
    dictionary_path = dictionary_path.resolve()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not dictionary_path.exists():
        raise FileNotFoundError(
            f"PLACES dictionary not found: {dictionary_path}"
        )

    dictionary = load_dictionary(dictionary_path)

    measures = build_measure_catalog(dictionary)
    versions = build_measure_versions(dictionary)
    releases = build_releases()

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    con = duckdb.connect(str(db_path))

    try:
        con.execute(schema_sql)
        con.execute("BEGIN TRANSACTION")

        # Metadata is rebuilt deterministically.
        con.execute("DELETE FROM places.measure_versions")
        con.execute("DELETE FROM places.measures")
        con.execute("DELETE FROM places.releases")

        con.register("releases_df", releases)
        con.execute(
            """
            INSERT INTO places.releases (
                release_year,
                release_label,
                release_date,
                source_name,
                methodology,
                notes
            )
            SELECT
                release_year,
                release_label,
                release_date,
                source_name,
                methodology,
                notes
            FROM releases_df
            """
        )

        con.register("measures_df", measures)
        con.execute(
            """
            INSERT INTO places.measures (
                measure_id,
                canonical_name,
                category,
                frequency,
                unit,
                age_adjusted_available,
                first_release_year,
                last_release_year,
                notes
            )
            SELECT
                measure_id,
                canonical_name,
                category,
                frequency,
                unit,
                age_adjusted_available,
                first_release_year,
                last_release_year,
                notes
            FROM measures_df
            """
        )

        con.register("versions_df", versions)
        con.execute(
            """
            INSERT INTO places.measure_versions (
                release_year,
                measure_id,
                measure_name,
                measure_definition,
                data_source,
                measurement_year,
                frequency,
                carry_forward,
                definition_version,
                notes
            )
            SELECT
                release_year,
                measure_id,
                measure_name,
                measure_definition,
                data_source,
                measurement_year,
                frequency,
                carry_forward,
                definition_version,
                notes
            FROM versions_df
            """
        )

        con.execute("COMMIT")

        counts = {
            "releases": con.execute(
                "SELECT COUNT(*) FROM places.releases"
            ).fetchone()[0],
            "measures": con.execute(
                "SELECT COUNT(*) FROM places.measures"
            ).fetchone()[0],
            "measure_versions": con.execute(
                "SELECT COUNT(*) FROM places.measure_versions"
            ).fetchone()[0],
        }

    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise

    finally:
        con.close()

    print("=" * 70)
    print("PLACES metadata write: SUCCESS")
    print("=" * 70)
    print(f"Database         : {db_path}")
    print(f"Releases         : {counts['releases']}")
    print(f"Measures         : {counts['measures']}")
    print(f"Measure versions : {counts['measure_versions']}")


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        print(
            "Usage:\n"
            "python scripts\\places\\write_metadata.py "
            "\"database.duckdb\" "
            "[\"places-data-dictionary.csv\"]"
        )
        raise SystemExit(1)

    db_path = Path(sys.argv[1])

    if len(sys.argv) == 3:
        write_metadata(
            db_path,
            Path(sys.argv[2]),
        )
    else:
        write_metadata(db_path)


if __name__ == "__main__":
    main()