"""Tiny, isolated DuckDB structural fixtures. NOT real-data activation evidence."""
from __future__ import annotations

from dataclasses import fields, replace
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import duckdb

from ai.capabilities import CAPABILITIES, GeographyMode, MULTIDIMENSIONAL_RELATIONS, Source
from ai.evidence_semantics import (
    Adjustment, Attribution, AttributionStatus, ProvenanceReference, UncertaintyType,
)
from ai.query_models import (
    AGE_STANDARDIZED_20_PLUS, ComparisonSpec, DemographicStratum, Dimension,
    GeographySpec, PopulationValue, QueryContractError, QueryOperation,
    ReleasePolicy, ResolvedQuery, SourceConcept, SourceTime, TimeAlignment, TimeSpec,
)
from app.multidimensional import (
    DuplicateAnalyticalKeyError, GeographyStatus, MultidimensionalError,
    ObservationStatus, compare_strata, get_stratum_values, summarize_by_rurality,
)

S, A, R, G = Dimension.SEX, Dimension.AGE, Dimension.RACE_ETHNICITY, Dimension.RURALITY
FEMALE, MALE = (PopulationValue.subgroup(S, label) for label in ("Female", "Male"))
AGE40, AGE60 = (PopulationValue.subgroup(A, label) for label in ("40-44", "60-64"))
STD = PopulationValue.subgroup(A, AGE_STANDARDIZED_20_PLUS)
TOTAL_RACE, BOTH = PopulationValue.total(R), PopulationValue.total(S)
COUNTIES = tuple(f"010{number:02d}" for number in (1, 3, 5, 7, 9, 11))


def pair(dimension, a, b):
    return ComparisonSpec(dimension=dimension, group_a=a, group_b=b)


def query(**changes):
    defaults = dict(
        capability_key="sex_age", concepts=(SourceConcept(source=Source.IHME,
            concept_id=494, name="Stroke", dataset_version="synthetic-fixture-only"),),
        stratum=DemographicStratum(sex=FEMALE, race_ethnicity=TOTAL_RACE),
        comparison=pair(A, AGE40, AGE60),
        geography=GeographySpec(mode=GeographyMode.COUNTY_UNIVERSE),
        time=TimeSpec(sources=(SourceTime(source=Source.IHME, years=(2019,),
            release_policy=ReleasePolicy.SOURCE_OBSERVATION),), alignment=TimeAlignment.SINGLE_SOURCE),
        operation=QueryOperation.COMPARE_GROUPS,
    )
    return ResolvedQuery(**(defaults | changes))


def rural_query(**changes):
    defaults = dict(capability_key="sex_rurality", comparison=None,
        stratum=DemographicStratum(sex=FEMALE, age=STD, race_ethnicity=TOTAL_RACE),
        geography=GeographySpec(mode=GeographyMode.RUCC_ADJACENCY, classification_year=2023),
        operation=QueryOperation.SUMMARIZE_BY_RURALITY)
    return query(**(defaults | changes))


def age_rural_query(**changes):
    return rural_query(**(dict(capability_key="age_rurality",
        stratum=DemographicStratum(sex=BOTH, age=AGE60, race_ethnicity=TOTAL_RACE)) | changes))


def create_fixture(path: Path) -> None:
    connection = duckdb.connect(str(path))
    try:
        connection.execute("""
            CREATE SCHEMA ihme; CREATE SCHEMA analytics; CREATE SCHEMA geography;
            CREATE TABLE analytics.vw_current_county_lookup (
                fips VARCHAR, location_name VARCHAR, state_fips VARCHAR);
            CREATE TABLE analytics.dim_sex (sex_id BIGINT, sex_name VARCHAR);
            CREATE TABLE analytics.dim_age_group (age_group_id BIGINT, age_name VARCHAR);
            CREATE TABLE analytics.dim_race (race_id BIGINT, race_name VARCHAR);
            CREATE TABLE geography.rucc_2023 (fips VARCHAR, rucc_code INTEGER, source_year INTEGER);
            CREATE TABLE ihme.burden (
                fips VARCHAR, year INTEGER, cause_id BIGINT, measure_id BIGINT, metric_id BIGINT,
                sex_id BIGINT, age_group_id BIGINT, race_id BIGINT,
                val DOUBLE, lower DOUBLE, upper DOUBLE);
        """)
        connection.executemany("INSERT INTO analytics.vw_current_county_lookup VALUES (?, ?, ?)",
                               [(fips, f"Fixture county {index}", "01") for index, fips in enumerate(COUNTIES)])
        # IDs deliberately differ from legacy defaults; resolution must use catalogs.
        connection.executemany("INSERT INTO analytics.dim_sex VALUES (?, ?)",
                               [(22, "Female"), (11, "Male"), (33, "Both")])
        connection.executemany("INSERT INTO analytics.dim_age_group VALUES (?, ?)",
                               [(140, "40 to 44"), (160, "60 to 64"), (138, "20 plus, age standardized")])
        connection.executemany("INSERT INTO analytics.dim_race VALUES (?, ?)", [(71, "Total"), (72, "Other")])
        connection.executemany("INSERT INTO geography.rucc_2023 VALUES (?, ?, ?)",
                               [(fips, code, 2023) for fips, code in zip(COUNTIES[:5], (1, 4, 5, 2, None))])
        rows = []
        def observation(index, sex, age, value, **changes):
            defaults = dict(fips=COUNTIES[index], year=2019, cause_id=494, measure_id=4, metric_id=3,
                            sex_id=sex, age_group_id=age, race_id=71, val=value,
                            lower=max(0, value-1) if value is not None else None,
                            upper=value+1 if value is not None else None)
            defaults.update(changes)
            rows.append(tuple(defaults.values()))
        for index, value in enumerate((10, 0, None, 8, 5, 3)):
            observation(index, 22, 140, value)
        for index, value in enumerate((4, 0, 6, None, 10, 6)):
            if index != 3:  # a genuinely absent B row, not a null B estimate
                observation(index, 22, 160, value)
        for index, value in enumerate((8, 2, 0, 4, 15, 9)):
            observation(index, 11, 160, value)
        for index, value in enumerate((2, 4, None, 0, 8, 12)):
            observation(index, 22, 138, value)
        for index, value in enumerate((8, 10, 6, 4, 20, 30)):
            observation(index, 11, 138, value)
        for index, value in enumerate((100, 200, 0, None, 500, 600)):
            observation(index, 33, 160, value)
        for index, value in enumerate((50, 100, 0, 10, 250, 300)):
            observation(index, 33, 140, value)
        # Noise must not broaden cause/year/measure/metric/race or county scope.
        observation(0, 22, 140, 999, cause_id=999)
        observation(0, 22, 140, 888, year=2018)
        observation(0, 22, 140, 777, measure_id=5)
        observation(0, 22, 140, 666, metric_id=1)
        observation(0, 22, 140, 555, race_id=72)
        observation(0, 22, 140, 444, fips="01099")
        connection.executemany("INSERT INTO ihme.burden VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    finally:
        connection.close()


class MultidimensionalFixtureChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "structural_fixture.duckdb"
        create_fixture(self.path)

    def edit(self, sql, parameters=None):
        connection = duckdb.connect(str(self.path))
        try:
            connection.execute(sql, parameters or [])
        finally:
            connection.close()

    def test_sex_age_fixed_female_exact_values_filters_and_catalog_ids(self):
        result = compare_strata(query(), database_path=self.path)
        values = {row.fips: row for row in result.comparisons}
        self.assertEqual(set(values), {COUNTIES[i] for i in (0, 1, 4, 5)})
        self.assertEqual((values[COUNTIES[0]].group_a_value, values[COUNTIES[0]].group_b_value), (10, 4))
        self.assertEqual(values[COUNTIES[0]].signed_gap, 6)
        self.assertEqual(values[COUNTIES[0]].relative_gap_percent, 150)
        self.assertEqual(dict(result.values.groups[0].catalog_ids),
                         {"sex_id": 22, "age_group_id": 140, "race_id": 71})
        self.assertEqual(result.values.query, query())

    def test_sex_age_fixed_male_age_comparison_keeps_male_filter(self):
        self.edit("INSERT INTO ihme.burden VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  [COUNTIES[0], 2019, 494, 4, 3, 11, 140, 71, 16, 15, 17])
        result = compare_strata(query(stratum=DemographicStratum(
            sex=MALE, race_ethnicity=TOTAL_RACE)), database_path=self.path)
        self.assertEqual(len(result.comparisons), 1)
        self.assertEqual(result.comparisons[0].signed_gap, 8)
        self.assertEqual(result.comparisons[0].relative_gap_percent, 100)
        self.assertEqual(dict(result.values.groups[0].catalog_ids)["sex_id"], 11)

    def test_sex_age_fixed_age_compares_female_vs_male(self):
        request = query(stratum=DemographicStratum(age=AGE60, race_ethnicity=TOTAL_RACE),
                        comparison=pair(S, FEMALE, MALE))
        result = compare_strata(request, database_path=self.path)
        values = {row.fips: row for row in result.comparisons}
        self.assertEqual(len(values), 5)
        self.assertEqual(values[COUNTIES[0]].signed_gap, -4)
        self.assertEqual(values[COUNTIES[0]].absolute_gap_magnitude, 4)
        self.assertEqual(values[COUNTIES[0]].relative_gap_percent, -50)
        self.assertEqual(values[COUNTIES[1]].relative_gap_percent, -100)
        self.assertIsNone(values[COUNTIES[2]].relative_gap_percent)

    def test_partial_pair_coverage_null_absent_and_zero(self):
        result = compare_strata(query(), database_path=self.path)
        coverage = result.coverage[0]
        self.assertEqual((coverage.candidate_counties, coverage.eligible_counties), (6, 6))
        self.assertEqual((coverage.group_a_available, coverage.group_b_available,
                          coverage.complete_paired_counties, coverage.excluded_counties), (5, 5, 4, 2))
        self.assertAlmostEqual(coverage.paired_coverage_percent, 100 * 4 / 6)
        self.assertEqual(dict(coverage.group_a_status_counts)[ObservationStatus.NULL_ESTIMATE], 1)
        self.assertEqual(dict(coverage.group_b_status_counts)[ObservationStatus.ABSENT_ROW], 1)
        self.assertEqual(dict(coverage.group_a_status_counts)[ObservationStatus.SOURCE_SUPPRESSED], 0)
        self.assertEqual(sum(n for _, n in coverage.primary_exclusions), 2)
        zeros = next(row for row in result.comparisons if row.fips == COUNTIES[1])
        self.assertEqual((zeros.group_a_value, zeros.group_b_value, zeros.signed_gap), (0, 0, 0))
        self.assertIsNone(zeros.relative_gap_percent)

    def test_signed_gap_orientation_reversal_and_relative_definition(self):
        forward = compare_strata(query(), database_path=self.path).comparisons
        reverse = compare_strata(query(comparison=pair(A, AGE60, AGE40)), database_path=self.path).comparisons
        a = next(row for row in forward if row.fips == COUNTIES[0])
        b = next(row for row in reverse if row.fips == COUNTIES[0])
        self.assertEqual((a.signed_gap, b.signed_gap), (6, -6))
        self.assertEqual(a.absolute_gap_magnitude, b.absolute_gap_magnitude)
        self.assertEqual(b.relative_gap_percent, -60)  # denominator is new B, not A

    def test_marginal_uncertainty_preserved_no_gap_interval(self):
        result = compare_strata(query(), database_path=self.path)
        row = next(row for row in result.comparisons if row.fips == COUNTIES[0])
        self.assertEqual((row.group_a_lower, row.group_a_upper, row.group_b_lower, row.group_b_upper),
                         (9, 11, 3, 5))
        self.assertFalse({"gap_lower", "gap_upper", "difference_interval"} & {field.name for field in fields(row)})
        self.assertTrue(all(item.uncertainty_type is UncertaintyType.IHME_UI for item in result.values.semantics))
        self.assertTrue(all(item.adjustment is Adjustment.AGE_SPECIFIC for item in result.values.semantics))

    def test_sex_rurality_fixed_female_county_weighted_summary(self):
        result = summarize_by_rurality(rural_query(), database_path=self.path)
        groups = {row.coverage.rurality_group: row for row in result.summaries}
        self.assertEqual(groups["Metro"].county_weighted_mean, 1)
        self.assertEqual(groups["Metro"].county_weighted_median, 1)
        self.assertEqual(groups["Nonmetro adjacent"].county_weighted_mean, 4)
        self.assertIsNone(groups["Nonmetro not adjacent"].county_weighted_mean)
        self.assertIn("not population weighted", groups["Metro"].estimate_basis)
        coverage = result.coverage[0]
        self.assertEqual((coverage.candidate_counties, coverage.eligible_counties,
                          coverage.pre_join_observations_available, coverage.observations_available), (6, 4, 5, 3))
        self.assertEqual((coverage.missing_rucc_counties, coverage.missing_outcome_observations,
                          coverage.excluded_counties), (2, 1, 3))
        self.assertEqual(coverage.coverage_percent, 75)
        self.assertEqual(coverage.universe_retention_percent, 50)
        self.assertIn("2023", result.values.geography_note)
        self.assertIn("fixed lens", result.values.geography_note)
        self.assertIn("does not describe historical", result.values.geography_note)

    def test_sex_rurality_fixed_male_is_not_replaced_by_female_or_both(self):
        result = summarize_by_rurality(rural_query(stratum=DemographicStratum(
            sex=MALE, age=STD, race_ethnicity=TOTAL_RACE)), database_path=self.path)
        groups = {row.coverage.rurality_group: row for row in result.summaries}
        self.assertEqual(groups["Metro"].county_weighted_mean, 6)
        self.assertEqual(groups["Nonmetro adjacent"].county_weighted_mean, 10)
        self.assertEqual(groups["Nonmetro not adjacent"].county_weighted_mean, 6)

    def test_sex_comparison_within_a_requested_rucc_group(self):
        request = rural_query(operation=QueryOperation.COMPARE_GROUPS, comparison=pair(S, FEMALE, MALE),
            stratum=DemographicStratum(age=STD, race_ethnicity=TOTAL_RACE),
            geography=GeographySpec(mode=GeographyMode.RUCC_ADJACENCY, classification_year=2023,
                                    rurality_filter=PopulationValue.subgroup(G, "Metro")))
        result = compare_strata(request, database_path=self.path)
        self.assertEqual({row.fips for row in result.comparisons}, {COUNTIES[0], COUNTIES[3]})
        coverage = result.coverage[0]
        self.assertEqual((coverage.candidate_counties, coverage.eligible_counties,
                          coverage.missing_rucc_counties, coverage.outside_geography_counties), (6, 2, 2, 2))
        self.assertEqual((coverage.complete_paired_counties, coverage.excluded_counties,
                          coverage.outcome_excluded_counties, coverage.paired_coverage_percent), (2, 4, 0, 100))
        self.assertEqual(len(result.coverage_by_rurality), 1)
        self.assertTrue(all(row.signed_gap < 0 for row in result.comparisons))

    def test_age_rurality_fixed_age_uses_both_sexes_and_total_race(self):
        result = summarize_by_rurality(age_rural_query(), database_path=self.path)
        self.assertEqual(dict(result.values.groups[0].catalog_ids),
                         {"sex_id": 33, "age_group_id": 160, "race_id": 71})
        groups = {row.coverage.rurality_group: row for row in result.summaries}
        self.assertEqual(groups["Metro"].county_weighted_mean, 100)
        self.assertEqual(groups["Nonmetro adjacent"].county_weighted_mean, 200)
        self.assertEqual(groups["Nonmetro not adjacent"].county_weighted_mean, 0)
        self.assertEqual(groups["Metro"].coverage.missing_outcome_observations, 1)
        self.assertEqual(groups["Metro"].coverage.coverage_percent, 50)

    def test_age_pairs_within_rurality_keep_both_sexes(self):
        request = age_rural_query(operation=QueryOperation.COMPARE_GROUPS,
            stratum=DemographicStratum(sex=BOTH, race_ethnicity=TOTAL_RACE), comparison=pair(A, AGE40, AGE60))
        result = compare_strata(request, database_path=self.path)
        self.assertEqual(len(result.comparisons), 3)
        self.assertEqual(result.coverage[0].missing_rucc_counties, 2)
        self.assertEqual(next(row for row in result.comparisons if row.fips == COUNTIES[0]).signed_gap, -50)
        self.assertEqual(len(result.coverage_by_rurality), 3)

    def test_rurality_group_selection_is_unpaired_not_a_synthetic_gap(self):
        request = rural_query(operation=QueryOperation.COMPARE_GROUPS,
            comparison=pair(G, PopulationValue.subgroup(G, "Metro"),
                               PopulationValue.subgroup(G, "Nonmetro adjacent")))
        result = summarize_by_rurality(request, database_path=self.path)
        self.assertEqual({row.coverage.rurality_group for row in result.summaries},
                         {"Metro", "Nonmetro adjacent"})
        self.assertEqual(result.coverage[0].outside_geography_counties, 1)
        self.assertFalse(hasattr(result, "comparisons"))
        self.assertFalse(hasattr(result.coverage[0], "complete_paired_counties"))
        with self.assertRaises(MultidimensionalError):
            compare_strata(request, database_path=self.path)

    def test_absent_null_rucc_and_missing_outcome_are_distinct_before_join(self):
        result = summarize_by_rurality(rural_query(), database_path=self.path)
        observations = {row.fips: row for row in result.values.observations}
        self.assertIs(observations[COUNTIES[2]].status, ObservationStatus.NULL_ESTIMATE)
        self.assertIs(observations[COUNTIES[2]].geography_status, GeographyStatus.ELIGIBLE)
        self.assertIs(observations[COUNTIES[4]].status, ObservationStatus.AVAILABLE)
        self.assertIs(observations[COUNTIES[4]].geography_status, GeographyStatus.MISSING_RUCC)
        self.assertIs(observations[COUNTIES[5]].geography_status, GeographyStatus.MISSING_RUCC)
        self.assertEqual(len(observations), 6)
        self.assertEqual(sum(n for _, n in result.coverage[0].primary_exclusions), 3)

    def test_unavailable_catalog_combination_is_not_county_absence(self):
        missing_age = PopulationValue.subgroup(A, "95-99")
        result = compare_strata(query(comparison=pair(A, AGE40, missing_age)), database_path=self.path)
        self.assertIn("No catalog entry", result.values.groups[1].unavailable_reason)
        self.assertEqual(dict(result.coverage[0].group_b_status_counts)[ObservationStatus.UNAVAILABLE_COMBINATION], 6)
        self.assertEqual(dict(result.coverage[0].group_b_status_counts)[ObservationStatus.ABSENT_ROW], 0)
        self.assertEqual(result.comparisons, ())

    def test_explicit_suppression_unavailability_and_null_are_not_inferred(self):
        self.edit("ALTER TABLE ihme.burden ADD COLUMN source_status VARCHAR")
        self.edit("UPDATE ihme.burden SET source_status='suppressed' WHERE fips=? AND sex_id=22 AND age_group_id=140", [COUNTIES[0]])
        self.edit("UPDATE ihme.burden SET source_status='unavailable' WHERE fips=? AND sex_id=22 AND age_group_id=140", [COUNTIES[1]])
        result = compare_strata(query(), database_path=self.path)
        counts = dict(result.coverage[0].group_a_status_counts)
        self.assertEqual((counts[ObservationStatus.SOURCE_SUPPRESSED], counts[ObservationStatus.UNAVAILABLE_COMBINATION],
                          counts[ObservationStatus.NULL_ESTIMATE]), (1, 1, 1))
        self.assertTrue(result.values.source_status_metadata_present)
        suppressed = next(row for row in result.values.observations if row.fips == COUNTIES[0] and row.group == "A")
        self.assertIsNone(suppressed.value)
        self.assertIsNone(suppressed.lower)
        self.assertIsNone(suppressed.upper)
        self.assertNotIn(COUNTIES[0], {row.fips for row in result.comparisons})

    def test_no_source_status_column_does_not_infer_suppression(self):
        result = get_stratum_values(query(), database_path=self.path)
        self.assertFalse(result.source_status_metadata_present)
        self.assertNotIn(ObservationStatus.SOURCE_SUPPRESSED, {row.status for row in result.observations})

    def test_unrecognized_source_status_schema_is_not_guessed(self):
        self.edit("ALTER TABLE ihme.burden ADD COLUMN source_status BOOLEAN")
        with self.assertRaisesRegex(MultidimensionalError, "normalized VARCHAR"):
            compare_strata(query(), database_path=self.path)

    def test_caller_attribution_attestation_cannot_replace_warehouse_provenance_audit(self):
        ref = ProvenanceReference(dataset="ihme.burden", dataset_version="synthetic-fixture-only",
                                  reference="fixture://synthetic-claim", verification_note=(
                                      "Synthetic fixture only; no real warehouse provenance verified"))
        concept = replace(query().concepts[0], attribution=Attribution(
            status=AttributionStatus.VERIFIED, label="High BMI", provenance=(ref,)))
        with self.assertRaisesRegex(MultidimensionalError, "not independently verified"):
            get_stratum_values(query(concepts=(concept,)), database_path=self.path)

    def test_invalid_source_status_fails_explicitly(self):
        self.edit("ALTER TABLE ihme.burden ADD COLUMN source_status VARCHAR")
        self.edit("UPDATE ihme.burden SET source_status='unknown-token'")
        with self.assertRaisesRegex(MultidimensionalError, "Unrecognized explicit source_status"):
            compare_strata(query(), database_path=self.path)

    def test_duplicate_keys_fail_before_pivot_or_summary_even_null_rows(self):
        for index, age, call, request in ((0, 140, compare_strata, query()),
                                         (2, 140, compare_strata, query()),
                                         (0, 138, summarize_by_rurality, rural_query())):
            with self.subTest(index=index, age=age):
                path = Path(self.temporary.name) / f"duplicate-{index}-{age}.duckdb"
                create_fixture(path)
                connection = duckdb.connect(str(path))
                try:
                    connection.execute("INSERT INTO ihme.burden SELECT * FROM ihme.burden WHERE fips=? "
                                       "AND cause_id=494 AND year=2019 AND measure_id=4 AND metric_id=3 "
                                       "AND race_id=71 AND sex_id=22 AND age_group_id=?", [COUNTIES[index], age])
                finally:
                    connection.close()
                with self.assertRaises(DuplicateAnalyticalKeyError):
                    call(request, database_path=path)

    def test_duplicate_eligible_county_rucc_and_catalog_fail(self):
        cases = (
            ("INSERT INTO analytics.vw_current_county_lookup SELECT * FROM analytics.vw_current_county_lookup WHERE fips='01001'", query()),
            ("INSERT INTO geography.rucc_2023 SELECT * FROM geography.rucc_2023 WHERE fips='01001'", rural_query()),
            ("INSERT INTO analytics.dim_sex VALUES (23,'Female')", query()),
            ("UPDATE analytics.dim_sex SET sex_id=22 WHERE sex_name='Male'", query(
                stratum=DemographicStratum(age=AGE60, race_ethnicity=TOTAL_RACE), comparison=pair(S, FEMALE, MALE))),
        )
        for index, (sql, request) in enumerate(cases):
            with self.subTest(index=index):
                path = Path(self.temporary.name) / f"bad-key-{index}.duckdb"
                create_fixture(path)
                connection = duckdb.connect(str(path))
                try:
                    connection.execute(sql)
                finally:
                    connection.close()
                with self.assertRaises(DuplicateAnalyticalKeyError):
                    get_stratum_values(request, database_path=path)

    def test_standardized_age_specific_and_triple_intersection_rejections(self):
        with self.assertRaises(QueryContractError):
            query(comparison=pair(A, STD, AGE60))
        requests = (
            query(comparison=pair(S, FEMALE, MALE), stratum=DemographicStratum(age=STD, race_ethnicity=TOTAL_RACE)),
            rural_query(stratum=DemographicStratum(sex=FEMALE, age=AGE60, race_ethnicity=TOTAL_RACE)),
            age_rural_query(stratum=DemographicStratum(sex=FEMALE, age=AGE60, race_ethnicity=TOTAL_RACE)),
            query(geography=GeographySpec(mode=GeographyMode.RUCC_ADJACENCY, classification_year=2023)),
        )
        for request in requests:
            with self.subTest(request=request), self.assertRaises(MultidimensionalError):
                get_stratum_values(request, database_path=self.path)

    def test_no_implicit_default_for_missing_fixed_filters(self):
        with self.assertRaises(MultidimensionalError):
            compare_strata(query(stratum=DemographicStratum(sex=FEMALE)), database_path=self.path)
        with self.assertRaises(MultidimensionalError):
            summarize_by_rurality(rural_query(stratum=DemographicStratum(sex=FEMALE)), database_path=self.path)

    def test_empty_scoped_universe_has_unavailable_percentages_not_national_fallback(self):
        request = query(geography=GeographySpec(mode=GeographyMode.COUNTY_UNIVERSE, state_fips=("99",)))
        result = compare_strata(request, database_path=self.path)
        self.assertEqual(result.coverage[0].eligible_counties, 0)
        self.assertIsNone(result.coverage[0].paired_coverage_percent)
        self.assertEqual(result.comparisons, ())

    def test_all_missing_rucc_zero_eligible_denominator(self):
        request = rural_query(geography=GeographySpec(mode=GeographyMode.RUCC_ADJACENCY,
            classification_year=2023, county_fips=COUNTIES[4:]))
        result = summarize_by_rurality(request, database_path=self.path)
        self.assertEqual((result.coverage[0].candidate_counties, result.coverage[0].eligible_counties,
                          result.coverage[0].missing_rucc_counties), (2, 0, 2))
        self.assertIsNone(result.coverage[0].coverage_percent)
        self.assertTrue(all(row.county_weighted_mean is None for row in result.summaries))

    def test_explicit_outside_universe_county_fails_instead_of_disappearing(self):
        request = query(geography=GeographySpec(mode=GeographyMode.COUNTY_UNIVERSE, county_fips=("01099",)))
        with self.assertRaisesRegex(MultidimensionalError, "outside the eligible"):
            get_stratum_values(request, database_path=self.path)

    def test_selected_cause_year_absence_is_not_suppression_or_null(self):
        request = query(concepts=(replace(query().concepts[0], concept_id=12345),))
        result = compare_strata(request, database_path=self.path)
        self.assertEqual(result.coverage[0].complete_paired_counties, 0)
        self.assertEqual(dict(result.coverage[0].group_a_status_counts)[ObservationStatus.ABSENT_ROW], 6)
        self.assertEqual(dict(result.coverage[0].group_a_status_counts)[ObservationStatus.SOURCE_SUPPRESSED], 0)
        self.assertEqual(result.coverage[0].paired_coverage_percent, 0)

    def test_multi_year_coverage_does_not_hide_an_empty_year(self):
        time = TimeSpec(sources=(SourceTime(source=Source.IHME, years=(2018, 2019),
            release_policy=ReleasePolicy.SOURCE_OBSERVATION),), alignment=TimeAlignment.SINGLE_SOURCE)
        result = compare_strata(query(time=time), database_path=self.path)
        self.assertEqual(tuple(row.year for row in result.coverage), (2018, 2019))
        self.assertEqual(tuple(row.complete_paired_counties for row in result.coverage), (0, 4))
        self.assertEqual(result.coverage[0].group_a_available, 1)

    def test_invalid_outcomes_and_rucc_fail_not_silently_dropped(self):
        cases = (
            ("UPDATE ihme.burden SET val='NaN' WHERE fips='01001'", query()),
            ("UPDATE ihme.burden SET val=-1 WHERE fips='01001'", query()),
            ("UPDATE geography.rucc_2023 SET rucc_code=10 WHERE fips='01001'", rural_query()),
            ("UPDATE geography.rucc_2023 SET source_year=2013 WHERE fips='01001'", rural_query()),
        )
        for index, (sql, request) in enumerate(cases):
            path = Path(self.temporary.name) / f"invalid-data-{index}.duckdb"
            create_fixture(path)
            connection = duckdb.connect(str(path))
            try:
                connection.execute(sql)
            finally:
                connection.close()
            with self.subTest(index=index), self.assertRaises(MultidimensionalError):
                get_stratum_values(request, database_path=path)

    def test_nonrural_query_does_not_depend_on_rucc_table(self):
        self.edit("DROP TABLE geography.rucc_2023")
        result = compare_strata(query(), database_path=self.path)
        self.assertEqual(result.coverage[0].complete_paired_counties, 4)
        self.assertIsNone(result.values.geography_note)

    def test_read_only_parameterization_and_no_database_mutation(self):
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        original = duckdb.connect
        calls = []
        class ConnectionSpy:
            def __init__(self, connection):
                self.connection = connection
            def execute(self, sql, parameters=None):
                calls.append((sql, parameters))
                return self.connection.execute(sql, parameters) if parameters is not None else self.connection.execute(sql)
            def close(self):
                self.connection.close()
        def connect(*args, **kwargs):
            self.assertTrue(kwargs.get("read_only"))
            return ConnectionSpy(original(*args, **kwargs))
        with patch("app.multidimensional.duckdb.connect", side_effect=connect):
            compare_strata(query(), database_path=self.path)
        after = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertEqual(calls[0][0], "BEGIN TRANSACTION")
        for sql, parameters in calls[1:]:
            self.assertTrue(sql.startswith("SELECT"))
            self.assertIsNotNone(parameters)
            self.assertNotIn("Female", sql)
            self.assertNotIn("494", sql)
            self.assertNotIn("MAX(", sql.upper())
            self.assertNotIn("AVG(", sql.upper())
        with self.assertRaises(ValueError):
            MULTIDIMENSIONAL_RELATIONS["burden"].column("val; DROP TABLE ihme.burden")

    def test_missing_database_is_not_created(self):
        path = Path(self.temporary.name) / "missing.duckdb"
        with self.assertRaises(FileNotFoundError):
            compare_strata(query(), database_path=path)
        self.assertFalse(path.exists())

    def test_attribution_units_and_activation_are_still_unverified(self):
        result = get_stratum_values(query(), database_path=self.path)
        for semantics in result.semantics:
            self.assertIs(semantics.attribution.status, AttributionStatus.UNKNOWN)
            self.assertEqual(semantics.unit, "unknown")
        for key in ("sex_age", "sex_rurality", "age_rurality"):
            self.assertFalse(CAPABILITIES[key].executable)
            self.assertEqual(CAPABILITIES[key].functions, ())
            self.assertEqual(CAPABILITIES[key].surfaces, ())


if __name__ == "__main__":
    unittest.main(verbosity=2)
