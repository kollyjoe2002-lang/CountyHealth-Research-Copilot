"""Table-driven Phase 3 contract validation; no warehouse or API required."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.capabilities import CAPABILITIES, REGISTRY_VERSION, GeographyMode, Source
from ai.evidence_semantics import Attribution, AttributionStatus, ProvenanceReference
from ai.query_models import (
    AGE_STANDARDIZED_20_PLUS, QUERY_CONTRACT_VERSION, CapabilityDecision,
    ComparisonSpec, DecisionReason, DecisionStatus, DemographicStratum, Dimension,
    GeographySpec, MissingGeographyPolicy, PopulationValue, QueryContractError,
    QueryOperation, ReleasePolicy, ResolvedQuery, SourceConcept, SourceTime,
    TimeAlignment, TimeSpec, ValueState, assess_query_contract, normalize_comparison,
)

S, A, R, G = Dimension.SEX, Dimension.AGE, Dimension.RACE_ETHNICITY, Dimension.RURALITY
FEMALE = PopulationValue.subgroup(S, "Female")
MALE = PopulationValue.subgroup(S, "Male")
AGE40 = PopulationValue.subgroup(A, "40-44")
AGE60 = PopulationValue.subgroup(A, "60-64")
STANDARDIZED = PopulationValue.subgroup(A, AGE_STANDARDIZED_20_PLUS)
TOTAL_RACE = PopulationValue.total(R)
TOTAL_SEX = PopulationValue.total(S)


def pair(dimension, a, b):
    return ComparisonSpec(dimension=dimension, group_a=a, group_b=b)


def ihme_time(years=(2019,)):
    return TimeSpec(sources=(SourceTime(source=Source.IHME, years=years,
                                       release_policy=ReleasePolicy.SOURCE_OBSERVATION),),
                    alignment=TimeAlignment.SINGLE_SOURCE)


def ihme_concept(**changes):
    return SourceConcept(**(dict(source=Source.IHME, concept_id=494, name="Stroke",
                                 dataset_version="unknown") | changes))


def county_geography(**changes):
    return GeographySpec(**(dict(mode=GeographyMode.COUNTY_UNIVERSE) | changes))


def rural_geography(**changes):
    return GeographySpec(**(dict(mode=GeographyMode.RUCC_ADJACENCY,
                                classification_year=2023) | changes))


def query(**changes):
    defaults = dict(capability_key="sex_age", concepts=(ihme_concept(),),
                    stratum=DemographicStratum(sex=FEMALE, race_ethnicity=TOTAL_RACE),
                    comparison=pair(A, AGE40, AGE60), geography=county_geography(),
                    time=ihme_time(), operation=QueryOperation.COMPARE_GROUPS)
    return ResolvedQuery(**(defaults | changes))


def female_rural_query(**changes):
    defaults = dict(capability_key="sex_rurality", geography=rural_geography(),
                    stratum=DemographicStratum(sex=FEMALE, age=STANDARDIZED,
                                              race_ethnicity=TOTAL_RACE),
                    comparison=None, operation=QueryOperation.SUMMARIZE_BY_RURALITY)
    return query(**(defaults | changes))


class QueryContractChecks(unittest.TestCase):
    def test_valid_sex_age_normalization_table_and_exact_round_trip(self):
        cases = (
            (DemographicStratum(sex=FEMALE, age=AGE40, race_ethnicity=TOTAL_RACE),
             DemographicStratum(sex=FEMALE, age=AGE60, race_ethnicity=TOTAL_RACE), A, FEMALE),
            (DemographicStratum(sex=FEMALE, age=AGE60, race_ethnicity=TOTAL_RACE),
             DemographicStratum(sex=MALE, age=AGE60, race_ethnicity=TOTAL_RACE), S, AGE60),
        )
        for original_a, original_b, dimension, expected_fixed in cases:
            with self.subTest(dimension=dimension):
                fixed, comparison = normalize_comparison(original_a, original_b)
                self.assertEqual(comparison.dimension, dimension)
                self.assertIs(fixed.get(dimension).state, ValueState.UNSPECIFIED)
                self.assertEqual(fixed.age if dimension is S else fixed.sex, expected_fixed)
                for original, group in ((original_a, comparison.group_a),
                                        (original_b, comparison.group_b)):
                    reconstructed = replace(fixed, **{dimension.value: group})
                    self.assertEqual(reconstructed, original)
                result = assess_query_contract(query(stratum=fixed, comparison=comparison))
                self.assertIs(result.status, DecisionStatus.PLANNED)
                self.assertFalse(result.executable)

    def test_fixed_female_rural_summary_has_explicit_rucc_dependency(self):
        request = female_rural_query()
        decision = assess_query_contract(request)
        self.assertEqual(request.required_sources, {Source.IHME, Source.RUCC})
        self.assertEqual(request.geography.classification_year, 2023)
        self.assertIsNone(request.comparison)
        self.assertIs(decision.query, request)
        self.assertIs(decision.status, DecisionStatus.PLANNED)
        self.assertFalse(decision.executable)
        self.assertFalse(CAPABILITIES[request.capability_key].executable)
        plain = query()
        self.assertEqual(plain.required_sources, {Source.IHME})
        self.assertIsNone(plain.geography.classification_year)

    def test_female_rurality_without_population_basis_requires_clarification(self):
        request = female_rural_query(stratum=DemographicStratum(sex=FEMALE))
        decision = assess_query_contract(request)
        self.assertIs(decision.status, DecisionStatus.CLARIFY)
        self.assertEqual(len(decision.missing_constraints), 2)
        self.assertIs(decision.query.stratum.sex, FEMALE)
        self.assertIs(decision.query.stratum.age.state, ValueState.UNSPECIFIED)
        self.assertIs(decision.query.stratum.race_ethnicity.state, ValueState.UNSPECIFIED)
        self.assertFalse(decision.executable)

    def test_valid_rurality_shapes_table(self):
        rural_pair = pair(G, PopulationValue.subgroup(G, "Metro"),
                          PopulationValue.subgroup(G, "Nonmetro adjacent"))
        cases = (
            female_rural_query(),
            female_rural_query(operation=QueryOperation.COMPARE_GROUPS, comparison=rural_pair),
            female_rural_query(operation=QueryOperation.COMPARE_GROUPS,
                               comparison=pair(S, FEMALE, MALE),
                               stratum=DemographicStratum(age=STANDARDIZED, race_ethnicity=TOTAL_RACE)),
            female_rural_query(capability_key="age_rurality",
                               stratum=DemographicStratum(sex=TOTAL_SEX, age=AGE60,
                                                         race_ethnicity=TOTAL_RACE)),
            female_rural_query(capability_key="age_rurality",
                               operation=QueryOperation.COMPARE_GROUPS,
                               stratum=DemographicStratum(sex=TOTAL_SEX, race_ethnicity=TOTAL_RACE),
                               comparison=pair(A, AGE40, AGE60)),
            female_rural_query(capability_key="age_rurality",
                               operation=QueryOperation.COMPARE_GROUPS,
                               stratum=DemographicStratum(sex=TOTAL_SEX, age=AGE60,
                                                         race_ethnicity=TOTAL_RACE),
                               comparison=rural_pair),
        )
        for request in cases:
            with self.subTest(request=request):
                result = assess_query_contract(request)
                self.assertIs(result.status, DecisionStatus.PLANNED)
                self.assertFalse(result.executable)

    def test_conflicting_fixed_comparison_dimensions_table(self):
        cases = (
            dict(stratum=DemographicStratum(sex=FEMALE, age=AGE40, race_ethnicity=TOTAL_RACE)),
            dict(stratum=DemographicStratum(sex=PopulationValue.total(S), age=AGE60,
                                            race_ethnicity=TOTAL_RACE),
                 comparison=pair(S, FEMALE, MALE)),
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaisesRegex(QueryContractError, "fixed filter"):
                query(**changes)
        with self.assertRaisesRegex(QueryContractError, "fixed filter"):
            female_rural_query(
                operation=QueryOperation.COMPARE_GROUPS,
                comparison=pair(G, PopulationValue.subgroup(G, "Metro"),
                                 PopulationValue.subgroup(G, "Nonmetro adjacent")),
                geography=rural_geography(rurality_filter=PopulationValue.subgroup(G, "Metro")))

    def test_duplicate_overlapping_and_nonconcrete_group_values_table(self):
        cases = (
            (S, FEMALE, FEMALE), (A, AGE40, AGE40),
            (A, AGE40, PopulationValue.subgroup(A, "44-49")),
            (A, STANDARDIZED, AGE60),
            (S, PopulationValue.total(S), FEMALE),
            (S, PopulationValue.unspecified(S), FEMALE),
            (S, PopulationValue.unavailable(S, "source unavailable"), FEMALE),
            (G, PopulationValue.subgroup(G, "Nonmetro"),
             PopulationValue.subgroup(G, "Nonmetro adjacent")),
        )
        for dimension, a, b in cases:
            with self.subTest(dimension=dimension, a=a, b=b), self.assertRaises(QueryContractError):
                pair(dimension, a, b)
        with self.assertRaisesRegex(QueryContractError, "Duplicate"):
            normalize_comparison(DemographicStratum(sex=FEMALE), DemographicStratum(sex=FEMALE))

    def test_unsupported_dimensions_and_noncanonical_values_table(self):
        for dimension in ("education", "sex", 42, None):
            with self.subTest(dimension=dimension), self.assertRaises(QueryContractError):
                pair(dimension, FEMALE, MALE)
        for dimension, value in ((S, "women"), (S, "unknown"), (A, "40 to 44"),
                                 (A, "60-40"), (A, "040-44"), (A, "999+"),
                                 (G, "rural-ish")):
            with self.subTest(value=value), self.assertRaises(QueryContractError):
                PopulationValue.subgroup(dimension, value)
        with self.assertRaises(QueryContractError):
            DemographicStratum(sex=AGE40)
        with self.assertRaises(QueryContractError):
            DemographicStratum().get(G)
        with self.assertRaises(QueryContractError):
            DemographicStratum().get("sex")

    def test_unspecified_total_and_unavailable_remain_distinct_table(self):
        cases = (
            (PopulationValue.unspecified(R), DecisionStatus.CLARIFY, DecisionReason.MISSING_CONSTRAINT),
            (PopulationValue.total(R), DecisionStatus.PLANNED, DecisionReason.PLANNED_VALIDATION_PENDING),
            (PopulationValue.unavailable(R, "not available in source"), DecisionStatus.UNAVAILABLE,
             DecisionReason.DATA_UNAVAILABLE),
        )
        for value, status, reason in cases:
            with self.subTest(state=value.state):
                request = query(stratum=DemographicStratum(sex=FEMALE, race_ethnicity=value))
                decision = assess_query_contract(request)
                self.assertIs(decision.status, status)
                self.assertIs(decision.reason, reason)
                self.assertIs(decision.query.stratum.race_ethnicity, value)
                self.assertFalse(decision.executable)
        self.assertEqual(len({value for value, _, _ in cases}), 3)
        self.assertNotEqual(PopulationValue.total(A), STANDARDIZED)
        self.assertNotEqual(PopulationValue.total(S), FEMALE)
        with self.assertRaises(QueryContractError):
            PopulationValue(dimension=R, state=ValueState.UNSPECIFIED, value="Total")

    def test_unavailable_population_preserves_the_requested_fixed_value(self):
        unavailable = PopulationValue.unavailable(S, "No matching source stratum", requested_value="Female")
        request = query(stratum=DemographicStratum(sex=unavailable, race_ethnicity=TOTAL_RACE))
        decision = assess_query_contract(request)
        self.assertIs(decision.status, DecisionStatus.UNAVAILABLE)
        self.assertEqual(decision.query.stratum.sex.requested_value, "Female")
        self.assertIs(decision.query.stratum.sex, unavailable)
        self.assertFalse(decision.executable)

    def test_shared_unknown_or_unavailable_filters_are_not_dropped_during_normalization(self):
        for race in (PopulationValue.unspecified(R), PopulationValue.total(R),
                     PopulationValue.unavailable(R, "pending source coverage")):
            left = DemographicStratum(sex=FEMALE, age=AGE40, race_ethnicity=race)
            right = replace(left, age=AGE60)
            fixed, _ = normalize_comparison(left, right)
            self.assertIs(fixed.race_ethnicity, race)
        with self.assertRaisesRegex(QueryContractError, "never discard"):
            normalize_comparison(DemographicStratum(sex=FEMALE, age=AGE40),
                                 DemographicStratum(sex=MALE, age=AGE60))
        with self.assertRaises(QueryContractError):
            normalize_comparison(DemographicStratum(sex=FEMALE, age=AGE40),
                                 DemographicStratum(age=AGE40))

    def test_unvalidated_triple_and_race_intersections_are_rejected_without_repair(self):
        cases = (
            female_rural_query(stratum=DemographicStratum(sex=FEMALE, age=AGE60,
                                                         race_ethnicity=TOTAL_RACE)),
            query(geography=rural_geography()),
            female_rural_query(operation=QueryOperation.COMPARE_GROUPS,
                               stratum=DemographicStratum(age=AGE60, race_ethnicity=TOTAL_RACE),
                               comparison=pair(S, FEMALE, MALE)),
            query(stratum=DemographicStratum(sex=FEMALE,
                    race_ethnicity=PopulationValue.subgroup(R, "Non-Latino, Black"))),
        )
        for request in cases:
            with self.subTest(request=request):
                result = assess_query_contract(request)
                self.assertIs(result.status, DecisionStatus.UNSUPPORTED)
                self.assertIs(result.reason, DecisionReason.COMBINATION_UNSUPPORTED)
                self.assertIs(result.query, request)
                self.assertEqual(result.alternatives, ())
                self.assertFalse(result.executable)

    def test_wrong_fixed_total_is_never_silently_replaced(self):
        cases = (
            female_rural_query(stratum=DemographicStratum(sex=FEMALE, age=PopulationValue.total(A),
                                                         race_ethnicity=TOTAL_RACE)),
            query(comparison=pair(S, FEMALE, MALE),
                  stratum=DemographicStratum(age=STANDARDIZED, race_ethnicity=TOTAL_RACE)),
            query(stratum=DemographicStratum(sex=TOTAL_SEX, race_ethnicity=TOTAL_RACE)),
        )
        for request in cases:
            result = assess_query_contract(request)
            self.assertIs(result.status, DecisionStatus.UNSUPPORTED)
            self.assertIs(result.query.stratum, request.stratum)

    def test_rurality_dependencies_and_grouping_modes_table(self):
        for key in ("sex_rurality", "age_rurality"):
            self.assertEqual(CAPABILITIES[key].sources, (Source.IHME, Source.RUCC))
            self.assertEqual(CAPABILITIES[key].geography_modes, (GeographyMode.RUCC_ADJACENCY,))
        cases = (
            (female_rural_query(geography=county_geography(),
                                operation=QueryOperation.COMPARE_GROUPS,
                                comparison=pair(S, FEMALE, MALE),
                                stratum=DemographicStratum(age=STANDARDIZED, race_ethnicity=TOTAL_RACE)),
             DecisionReason.SOURCE_MISMATCH),
            (query(geography=rural_geography(), comparison=pair(S, FEMALE, MALE),
                   stratum=DemographicStratum(age=STANDARDIZED, race_ethnicity=TOTAL_RACE)),
             DecisionReason.SOURCE_MISMATCH),
            (female_rural_query(geography=rural_geography(mode=GeographyMode.METRO)),
             DecisionReason.GEOGRAPHY_UNSUPPORTED),
        )
        # Summary without a rurality grouping is internally inconsistent.
        # Use an explicit pair operation when probing a missing RUCC dependency.
        for request, reason in cases:
            result = assess_query_contract(request)
            self.assertIs(result.status, DecisionStatus.UNSUPPORTED)
            self.assertIs(result.reason, reason)

    def test_geography_year_scope_and_filter_invariants_table(self):
        cases = (
            dict(mode=GeographyMode.RUCC_ADJACENCY),
            dict(mode=GeographyMode.RUCC_ADJACENCY, classification_year=2019),
            dict(mode=GeographyMode.COUNTY_UNIVERSE, classification_year=2023),
            dict(mode=GeographyMode.COUNTY),
            dict(mode=GeographyMode.COUNTY_UNIVERSE, county_fips=["55079"]),
            dict(mode=GeographyMode.COUNTY_UNIVERSE, county_fips=("55079", "55079")),
            dict(mode=GeographyMode.COUNTY_UNIVERSE, county_fips=("55079",), state_fips=("06",)),
            dict(mode=GeographyMode.RUCC_ADJACENCY, classification_year=2023,
                 rurality_filter=PopulationValue.subgroup(G, "Nonmetro")),
        )
        for values in cases:
            with self.subTest(values=values), self.assertRaises(QueryContractError):
                GeographySpec(**values)
        with self.assertRaises(QueryContractError):
            female_rural_query(geography=county_geography())
        valid = GeographySpec(mode=GeographyMode.COUNTY, county_fips=("55079",), state_fips=("55",))
        self.assertFalse(valid.requires_rurality)
        fixed = county_geography(rurality_filter=PopulationValue.subgroup(G, "Metro"),
                                 classification_year=2023)
        self.assertTrue(fixed.requires_rurality)
        self.assertIs(fixed.missingness_policy, MissingGeographyPolicy.REPORT_EXCLUSIONS)

    def test_time_range_release_and_alignment_preserve_source_years(self):
        ihme = SourceTime.year_range(source=Source.IHME, first=2017, last=2019,
                                    release_policy=ReleasePolicy.SOURCE_OBSERVATION)
        self.assertEqual(ihme.years, (2017, 2018, 2019))
        places = SourceTime(source=Source.PLACES, years=(2018, 2019, 2020), release_year=2022,
                            release_policy=ReleasePolicy.CANONICAL_MEASUREMENT)
        time = TimeSpec(sources=(ihme, places), alignment=TimeAlignment.CONTEXTUAL,
                        alignment_note="Separate ranges; do not truncate to overlap")
        self.assertEqual(time.sources, (ihme, places))
        self.assertNotEqual(places.years[-1], places.release_year)
        with self.assertRaises(QueryContractError):
            replace(time, alignment=TimeAlignment.SAME_YEARS)
        with self.assertRaises(QueryContractError):
            replace(time, alignment_note="")
        aligned = replace(places, years=ihme.years)
        self.assertIs(TimeSpec(sources=(ihme, aligned), alignment=TimeAlignment.SAME_YEARS).alignment,
                      TimeAlignment.SAME_YEARS)

    def test_invalid_source_time_contracts_table(self):
        for changes in ({"years": (2019, 2018)}, {"years": (2019, 2019)},
                        {"years": [2019]}, {"years": (True,)}, {"source": Source.RUCC},
                        {"release_year": 2018}, {"release_policy": ReleasePolicy.RELEASE_SNAPSHOT}):
            with self.subTest(changes=changes), self.assertRaises(QueryContractError):
                SourceTime(**(dict(source=Source.IHME, years=(2019,),
                                   release_policy=ReleasePolicy.SOURCE_OBSERVATION) | changes))
        with self.assertRaises(QueryContractError):
            SourceTime(source=Source.PLACES, years=(2019,), release_policy=ReleasePolicy.RELEASE_SNAPSHOT)
        with self.assertRaises(QueryContractError):
            SourceTime.year_range(source=Source.IHME, first=2019, last=2018,
                                  release_policy=ReleasePolicy.SOURCE_OBSERVATION)
        with self.assertRaises(QueryContractError):
            TimeSpec(sources=(), alignment=TimeAlignment.SINGLE_SOURCE)
        with self.assertRaises(QueryContractError):
            TimeSpec(sources=(ihme_time().sources[0], ihme_time().sources[0]),
                     alignment=TimeAlignment.SAME_YEARS)

    def test_missing_or_unavailable_years_do_not_trigger_default_years(self):
        missing = query(time=ihme_time(()))
        result = assess_query_contract(missing)
        self.assertIs(result.status, DecisionStatus.CLARIFY)
        self.assertTrue(result.missing_constraints)
        self.assertEqual(result.query.time.sources[0].years, ())
        for years in ((1999,), (2020,), (2018, 2035)):
            request = query(time=ihme_time(years))
            result = assess_query_contract(request)
            self.assertIs(result.reason, DecisionReason.YEAR_UNAVAILABLE)
            self.assertEqual(result.query.time.sources[0].years, years)

    def test_query_sources_pair_guards_and_attribution(self):
        self.assertIs(query().concepts[0].attribution.status, AttributionStatus.UNKNOWN)
        with self.assertRaises(QueryContractError):
            ihme_concept(source=Source.RUCC)
        for concept_id in (True, "494", -1):
            with self.assertRaises(QueryContractError):
                ihme_concept(concept_id=concept_id)
        with self.assertRaises(QueryContractError):
            query(concepts=(ihme_concept(), ihme_concept()))
        with self.assertRaises(QueryContractError):
            query(registry_version="old-version")
        places = SourceConcept(source=Source.PLACES, concept_id="STROKE", name="Stroke",
                               dataset_version="fixture", attribution=Attribution(
                                   status=AttributionStatus.NOT_APPLICABLE))
        t = TimeSpec(sources=(ihme_time().sources[0], SourceTime(
            source=Source.PLACES, years=(2019,), release_policy=ReleasePolicy.CANONICAL_MEASUREMENT)),
            alignment=TimeAlignment.SAME_YEARS)
        valid = query(concepts=(ihme_concept(), places), time=t)
        self.assertIs(assess_query_contract(valid).reason, DecisionReason.SOURCE_MISMATCH)
        with self.assertRaises(QueryContractError):
            replace(valid, concepts=(ihme_concept(), replace(places, concept_id="CANCER")))
        with self.assertRaises(QueryContractError):
            replace(valid, time=ihme_time())
        ref = ProvenanceReference(dataset="other", dataset_version="fixture", reference="fixture://test",
                                  verification_note="Synthetic test; wrong dataset")
        with self.assertRaises(QueryContractError):
            ihme_concept(dataset_version="fixture", attribution=Attribution(
                status=AttributionStatus.VERIFIED, label="High BMI", provenance=(ref,)))

    def test_all_contracts_are_deeply_immutable(self):
        request = female_rural_query()
        decision = assess_query_contract(request)
        for obj, attr, value in ((FEMALE, "value", "Male"), (request.stratum, "sex", MALE),
                                  (request.geography, "classification_year", 2019),
                                  (request.time, "sources", ()), (request, "capability_key", "forecast"),
                                  (decision, "status", DecisionStatus.LEGACY_UNVERIFIED)):
            with self.subTest(attr=attr), self.assertRaises(FrozenInstanceError):
                setattr(obj, attr, value)
        with self.assertRaises(QueryContractError):
            query(concepts=[ihme_concept()])
        with self.assertRaises(QueryContractError):
            query(assumptions=["assumption"])
        with self.assertRaises(QueryContractError):
            replace(decision, alternatives=[])

    def test_decisions_cannot_enable_planned_capabilities_even_with_fingerprint(self):
        for key, request in (("sex_age", query()), ("sex_rurality", female_rural_query()),
                             ("age_rurality", female_rural_query(capability_key="age_rurality",
                              stratum=DemographicStratum(sex=TOTAL_SEX, age=AGE60,
                                                        race_ethnicity=TOTAL_RACE)))):
            result = assess_query_contract(replace(request, availability_fingerprint="synthetic-catalog-fingerprint"))
            self.assertFalse(result.executable)
            self.assertIs(result.status, DecisionStatus.PLANNED)
            self.assertFalse(CAPABILITIES[key].executable)
            with self.assertRaises(QueryContractError):
                replace(result, status=DecisionStatus.LEGACY_UNVERIFIED,
                        reason=DecisionReason.LEGACY_REQUIRES_VALIDATION)
        with self.assertRaises(QueryContractError):
            replace(assess_query_contract(query()), status="execute")
        self.assertIs(assess_query_contract(query(capability_key="forecast")).reason,
                      DecisionReason.CAPABILITY_UNSUPPORTED)
        self.assertIs(assess_query_contract(query(capability_key="missing")).status,
                      DecisionStatus.UNSUPPORTED)

    def test_contracts_are_passive_and_versioned(self):
        self.assertEqual(query().version, QUERY_CONTRACT_VERSION)
        self.assertEqual(query().registry_version, REGISTRY_VERSION)
        tree = ast.parse((PROJECT_ROOT / "ai/query_models.py").read_text())
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imports |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertFalse(imports & {"duckdb", "pandas", "streamlit", "openai", "app.data_access",
                                    "ai.resolver", "ai.executor", "ai.planner", "ai.openai_semantic_parser"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
