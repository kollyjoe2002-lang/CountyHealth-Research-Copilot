"""Offline strict-parser decoding and canonical pipeline fixtures; no live LLM claims."""
from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import duckdb

from ai.capabilities import CAPABILITIES, CapabilityState
from ai.entailment_judge import validate_model_entailment
from ai.executor import ExecutionError, MULTIDIMENSIONAL_FUNCTIONS, execute_plan
from ai.models import (
    AnalysisIntent, AnalysisPlan, AnalysisStep, EntailmentJudgment, EntailmentLabel, GroundedAnswer,
    InterpretationResult, InterpretationStatement, ResearchQuestion, SemanticAnalysisRequest,
)
from ai.multidimensional_integration import FixtureIntegrationContext, validate_plan_identity, query_preview
from ai.multidimensional_request import (
    MultidimensionalRequest as MD, SemanticPopulation as Group, decode_multidimensional,
)
from ai.openai_semantic_parser import OpenAISemanticParser, SemanticParserError
from ai.research_assistant import ResearchAssistantError, run_research_assistant
from ai.report_writer import write_research_report, report_to_markdown
from ai.request_policy import apply_request_policy
from ai.query_models import Dimension, PopulationValue, ValueState
from scripts.utilities.check_multidimensional_analytics import create_fixture


POSITIVE_CASES = (
    ("Compare ischemic heart disease among women ages 40-44 and 60-64 in 2019.",
     "Ischemic heart disease", MD(fixed_sex="Female", comparison_dimension="age",
        group_a=Group(age="40-44"), group_b=Group(age="60-64")), "sex_age"),
    ("Compare women versus men aged 60-64 with stroke in 2019.", "Stroke",
     MD(fixed_age="60-64", comparison_dimension="sex", group_a=Group(sex="Female"),
        group_b=Group(sex="Male")), "sex_age"),
    ("Female ischemic heart disease burden by rurality.", "Ischemic heart disease",
     MD(fixed_sex="Female", operation="summarize_by_rurality"), "sex_rurality"),
    ("Male stroke burden by rurality.", "Stroke",
     MD(fixed_sex="Male", operation="summarize_by_rurality"), "sex_rurality"),
    ("Age 60-64 stroke burden by rurality.", "Stroke",
     MD(fixed_age="60-64", operation="summarize_by_rurality"), "age_rurality"),
    ("Compare women and men with stroke within Metro counties in 2019.", "Stroke",
     MD(comparison_dimension="sex", group_a=Group(sex="Female"), group_b=Group(sex="Male"),
        rurality_grouping="rucc_adjacency", rurality_filter="Metro"), "sex_rurality"),
    ("Compare stroke at ages 40-44 and 60-64 within Nonmetro adjacent counties in 2019.", "Stroke",
     MD(comparison_dimension="age", group_a=Group(age="40-44"), group_b=Group(age="60-64"),
        rurality_grouping="rucc_adjacency", rurality_filter="Nonmetro adjacent"), "age_rurality"),
)


class OfflineParser:
    """Exercise the actual SDK parser/schema decoder with a known structured response.

    This fixture does not simulate or certify an LLM's natural-language accuracy.
    """
    def __init__(self, question, cause, md, *, year=None, domain="IHME", county=None, scope=None, start_year=None, end_year=None):
        self.question, self.cause, self.md = question, cause, md
        self.year, self.domain, self.county, self.scope = year, domain, county, scope
        self.start_year, self.end_year = start_year, end_year
        self.payload_mutation = None
        self.last_call = None

    def parse(self, question):
        intent = AnalysisIntent.RURALITY_COMPARISON if self.md.operation == "summarize_by_rurality" else AnalysisIntent.DEMOGRAPHIC_DISPARITY
        request = SemanticAnalysisRequest(question, intent, .99, cause_name=self.cause,
            county_name=self.county, year=self.year, start_year=self.start_year, end_year=self.end_year, evidence_domain=self.domain,
            geographic_scope=self.scope, multidimensional=self.md)
        payload = asdict(request)
        payload.pop("question")
        payload["intent"] = intent.value
        if self.payload_mutation:
            self.payload_mutation(payload)
        parser = OpenAISemanticParser.__new__(OpenAISemanticParser)
        parser.model = "offline-structured-response-fixture"
        def create(**kwargs):
            self.last_call = kwargs
            return SimpleNamespace(output_text=json.dumps(payload))
        parser.client = SimpleNamespace(responses=SimpleNamespace(create=create))
        return parser.parse(question)


class EchoProvider:
    def interpret(self, source):
        first = source.claims[0]
        return InterpretationResult(GroundedAnswer(first.text, [first.claim_id]),
            [InterpretationStatement(claim.text, [claim.claim_id]) for claim in source.claims[1:]],
            list(source.limitations), [], list(source.warnings))


class ExactEvidenceJudge:
    def __init__(self):
        self.calls = 0
    def judge(self, *, statement_text, evidence_text):
        self.calls += 1
        return EntailmentJudgment(EntailmentLabel.ENTAILED if statement_text in evidence_text else EntailmentLabel.UNSUPPORTED,
                                  "Offline exact-evidence fixture judge; not live semantic entailment")


class MultidimensionalSemanticChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "semantic_fixture.duckdb"
        create_fixture(self.path)
        connection = duckdb.connect(str(self.path))
        try:
            connection.execute("CREATE TABLE analytics.multidimensional_fixture_marker(marker VARCHAR)")
            connection.execute("INSERT INTO analytics.multidimensional_fixture_marker VALUES ('synthetic_structural_fixture_only')")
            connection.execute("CREATE TABLE analytics.dim_cause(cause_id BIGINT, cause_name VARCHAR)")
            connection.executemany("INSERT INTO analytics.dim_cause VALUES (?,?)", [(493,"Ischemic heart disease"), (494,"Stroke")])
            connection.execute("INSERT INTO ihme.burden SELECT fips,year,493,measure_id,metric_id,sex_id,age_group_id,race_id,val,lower,upper FROM ihme.burden WHERE cause_id=494")
            names = ["Autauga", "Baldwin", "Barbour", "Bibb", "Blount", "Bullock"]
            for index, name in enumerate(names):
                connection.execute("UPDATE analytics.vw_current_county_lookup SET location_name=? WHERE fips=?",
                    [f"{name} County (Alabama)", f"010{(1,3,5,7,9,11)[index]:02d}"])
        finally:
            connection.close()
        self.context = FixtureIntegrationContext(self.path, allow_execution=True)
        self.telemetry = patch("ai.research_assistant.persist_research_telemetry")
        self.telemetry.start()
        self.addCleanup(self.telemetry.stop)

    def run_case(self, case=POSITIVE_CASES[0], *, context="fixture", provider=None, **parser_options):
        text, cause, md, key = case
        year = 2019 if "2019" in text else None
        parser = OfflineParser(text, cause, md, year=year, **parser_options)
        judge = ExactEvidenceJudge()
        result = run_research_assistant(text, semantic_parser=parser,
            provider=provider or EchoProvider(), judge=judge,
            fixture_context=self.context if context == "fixture" else context)
        return result, parser, judge

    def test_seven_positive_structured_parses_and_guarded_full_pipeline(self):
        for case in POSITIVE_CASES:
            with self.subTest(question=case[0]):
                result, parser, judge = self.run_case(case)
                self.assertEqual(result.status, "answer")
                self.assertIsNone(result.ai_error, result.ai_error)
                self.assertIsNotNone(result.interpretation_result)
                self.assertGreater(judge.calls, 1)
                query = result.resolved_plan.resolved_context["resolved_query"]
                self.assertEqual(query.capability_key, case[3])
                self.assertEqual(validate_plan_identity(result.resolved_plan), query)
                self.assertEqual(result.evidence_bundle.context["interpreted_query"], query_preview(query))
                self.assertFalse(result.capability_decision.executable)
                self.assertTrue(result.evidence_bundle.context["fixture_only"])
                self.assertIs(CAPABILITIES[case[3]].state, CapabilityState.PLANNED)
                self.assertIs(query.stratum.race_ethnicity.state, ValueState.TOTAL)
                schema = parser.last_call["text"]["format"]
                self.assertTrue(schema["strict"])
                self.assertFalse(schema["schema"]["additionalProperties"])
                self.assertIn("multidimensional", schema["schema"]["required"])

    def test_public_queries_understood_but_never_execute(self):
        for case in POSITIVE_CASES:
            with self.subTest(question=case[0]), patch("ai.research_assistant.execute_plan") as execute:
                result, _, judge = self.run_case(case, context=None)
                self.assertEqual(result.status, "planned")
                self.assertEqual(result.capability_decision.reason, "activation_pending")
                self.assertIsNone(result.capability_decision.resolved_query)  # no invented IDs without catalog access
                self.assertIsNone(result.evidence_bundle)
                self.assertEqual(judge.calls, 0)
                execute.assert_not_called()

    def test_fixture_catalog_resolution_can_plan_without_executing(self):
        result, _, _ = self.run_case(context=FixtureIntegrationContext(self.path, allow_execution=False))
        self.assertEqual(result.status, "planned")
        self.assertIsNotNone(result.resolved_plan.resolved_context["resolved_query"])
        self.assertEqual(len(result.resolved_plan.steps), 1)
        self.assertIsNone(result.evidence_bundle)
        self.assertEqual(validate_plan_identity(result.resolved_plan), result.capability_decision.resolved_query)

    def test_explicit_defaults_are_traceable_not_llm_population_choices(self):
        for case in POSITIVE_CASES:
            result, _, _ = self.run_case(case)
            query = result.capability_decision.resolved_query
            defaults = query.assumptions
            self.assertTrue(any("race=Total" in item for item in defaults))
            self.assertEqual(tuple(result.resolved_plan.assumptions), defaults)
            self.assertEqual(result.resolved_plan.resolved_context["interpreted_query"]["query"]["assumptions"], list(defaults))
            if case[3] == "age_rurality":
                self.assertTrue(any("sex=Both sexes" in item for item in defaults))
            if case[3] == "sex_rurality":
                self.assertTrue(any("age=20+, age standardized" in item for item in defaults))

    def test_explicit_population_basis_is_not_replaced(self):
        case = ("Compare women and men aged 60-64 of all races with stroke in 2019.", "Stroke",
                MD(fixed_age="60-64", fixed_race_ethnicity="Total", comparison_dimension="sex",
                   group_a=Group(sex="Female"), group_b=Group(sex="Male")), "sex_age")
        result, _, _ = self.run_case(case)
        query = result.capability_decision.resolved_query
        self.assertEqual(query.stratum.age.value, "60-64")
        self.assertFalse(any("race=Total" in item for item in query.assumptions))

    def test_model_invented_population_defaults_and_ids_are_rejected(self):
        text, cause, md, key = POSITIVE_CASES[0]
        bad = replace(md, fixed_race_ethnicity="Total")
        result, _, _ = self.run_case((text, cause, bad, key))
        self.assertEqual(result.status, "clarify")
        parser = OfflineParser(text, cause, md, year=2019)
        parser.payload_mutation = lambda payload: payload["multidimensional"].update(sex_id=2)
        with self.assertRaises(SemanticParserError):
            parser.parse(ResearchQuestion(text))
        payload = asdict(md)
        payload["group_a"]["age_group_id"] = 12
        with self.assertRaises(ValueError):
            decode_multidimensional(payload)

    def test_nine_negative_population_source_time_and_operation_cases(self):
        cases = (
            ("Compare women aged 40-44 versus men aged 60-64 with stroke in 2019.", "Stroke",
             MD(comparison_dimension="multiple", group_a=Group(sex="Female", age="40-44"),
                group_b=Group(sex="Male", age="60-64")), "IHME", "reject"),
            ("Compare Black women versus White men with stroke in 2019.", "Stroke",
             MD(comparison_dimension="multiple", group_a=Group(sex="Female", race_ethnicity="Black"),
                group_b=Group(sex="Male", race_ethnicity="White")), "IHME", "reject"),
            ("Compare female stroke ages 40-44 and 60-64 by rurality in 2019.", "Stroke",
             MD(fixed_sex="Female", comparison_dimension="age", group_a=Group(age="40-44"),
                group_b=Group(age="60-64")), "IHME", "reject"),
            ("Compare female breast cancer with PLACES CANCER by rurality in 2019.", "Breast cancer",
             MD(fixed_sex="Female", operation="summarize_by_rurality"), "PLACES_IHME", "reject"),
            ("Forecast female stroke by rurality to 2035.", "Stroke",
             MD(fixed_sex="Female", operation="summarize_by_rurality"), "IHME", "reject"),
            ("PLACES stroke prevalence among women ages 40-44 and 60-64 in 2019.", "Stroke",
             MD(fixed_sex="Female", comparison_dimension="age", group_a=Group(age="40-44"),
                group_b=Group(age="60-64")), "PLACES", "reject"),
            ("Compare female stroke ages 40-44 and 60-64 in 2020.", "Stroke",
             MD(fixed_sex="Female", comparison_dimension="age", group_a=Group(age="40-44"),
                group_b=Group(age="60-64")), "IHME", "reject"),
            ("Compare stroke among older women and younger women in 2019.", "Stroke",
             MD(fixed_sex="Female", comparison_dimension="age", group_a=Group(age="older"),
                group_b=Group(age="younger")), "IHME", "clarify"),
            ("Compare female stroke age-standardized 20 plus and ages 60-64 in 2019.", "Stroke",
             MD(fixed_sex="Female", comparison_dimension="age", group_a=Group(age="20 plus, age standardized"),
                group_b=Group(age="60-64")), "IHME", "reject"),
        )
        for text, cause, md, domain, expected in cases:
            with self.subTest(question=text), patch("ai.research_assistant.execute_plan") as execute:
                case = (text, cause, md, "unused")
                result, _, _ = self.run_case(case, domain=domain)
                self.assertEqual(result.status, expected, result.policy_result.reason)
                self.assertIsNone(result.evidence_bundle)
                execute.assert_not_called()

    def test_omitted_structure_cannot_fall_through_to_weaker_legacy_analysis(self):
        text = POSITIVE_CASES[0][0]
        request = SemanticAnalysisRequest(ResearchQuestion(text), AnalysisIntent.DEMOGRAPHIC_DISPARITY, .9,
            cause_name="Ischemic heart disease", year=2019, demographic_dimension="Age group",
            demographic_groups=["40-44", "60-64"])
        self.assertEqual(apply_request_policy(request).decision.value, "clarify")

    def test_missing_catalog_values_and_cause_year_availability_are_not_fixture_activation(self):
        text, cause, md, key = POSITIVE_CASES[0]
        missing = replace(md, group_a=Group(age="95-99"))
        result, _, _ = self.run_case((text.replace("40-44", "95-99"), cause, missing, key))
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.evidence_bundle)
        connection = duckdb.connect(str(self.path))
        try:
            connection.execute("DELETE FROM ihme.burden WHERE year=2019 AND cause_id=493")
        finally:
            connection.close()
        result, _, _ = self.run_case()
        self.assertEqual(result.status, "unavailable")
        self.assertFalse(result.capability_decision.executable)

    def test_cause_and_county_ambiguity_remain_clarification(self):
        result, _, _ = self.run_case((POSITIVE_CASES[0][0].replace("ischemic heart disease", "mystery disease"),
                                    "mystery disease", POSITIVE_CASES[0][2], "sex_age"))
        self.assertEqual(result.status, "clarify")
        connection = duckdb.connect(str(self.path))
        try:
            connection.execute("INSERT INTO analytics.vw_current_county_lookup VALUES ('06001','Autauga County (California)','06')")
        finally:
            connection.close()
        case = (POSITIVE_CASES[0][0] + " In Autauga County.", *POSITIVE_CASES[0][1:])
        result, _, _ = self.run_case(case, county="Autauga County")
        self.assertEqual(result.status, "clarify")

    def test_county_and_state_scope_resolve_without_dropping_population_filters(self):
        case = (POSITIVE_CASES[0][0] + " In Autauga County, Alabama.", *POSITIVE_CASES[0][1:])
        result, _, _ = self.run_case(case, county="Autauga County, Alabama", scope="Alabama")
        self.assertEqual(result.status, "answer")
        query = result.capability_decision.resolved_query
        self.assertEqual(query.geography.county_fips, ("01001",))
        self.assertEqual(query.geography.state_fips, ("01",))
        self.assertEqual(query.stratum.sex.value, "Female")
        self.assertEqual(result.evidence_bundle.items[0].data.coverage[0].candidate_counties, 1)

    def test_preview_query_step_and_assumption_tampering_cannot_execute(self):
        for target in ("preview", "parameters", "function", "assumptions", "receipt"):
            result, _, _ = self.run_case(context=FixtureIntegrationContext(self.path))
            plan = result.resolved_plan
            if target == "preview":
                plan.resolved_context["interpreted_query"]["query"]["stratum"]["sex"]["value"] = "Male"
            elif target == "parameters":
                q = plan.steps[0].parameters["query"]
                plan.steps[0].parameters["query"] = replace(q, stratum=replace(q.stratum, sex=PopulationValue.subgroup(Dimension.SEX,"Male")))
            elif target == "function":
                plan.steps[0].function_name = "run_arbitrary_sql"
            elif target == "assumptions":
                plan.assumptions.append("unreviewed default")
            else:
                plan.resolved_context["availability_receipt"] = None
            with self.subTest(target=target), self.assertRaises(ExecutionError):
                execute_plan(plan, fixture_context=self.context)

    def test_no_context_readonly_context_and_changed_database_are_blocked_at_executor(self):
        result, _, _ = self.run_case(context=FixtureIntegrationContext(self.path))
        plan = result.resolved_plan
        for context in (None, FixtureIntegrationContext(self.path)):
            with self.assertRaises(ExecutionError):
                execute_plan(plan, fixture_context=context)
        connection = duckdb.connect(str(self.path))
        try:
            connection.execute("UPDATE ihme.burden SET val=val+1")
        finally:
            connection.close()
        with self.assertRaisesRegex(ExecutionError,"changed after availability"):
            execute_plan(plan, fixture_context=self.context)

    def test_unmarked_database_is_not_a_development_activation_shortcut(self):
        path = self.path.parent / "unmarked.duckdb"
        create_fixture(path)
        with self.assertRaises(Exception):
            FixtureIntegrationContext(path, allow_execution=True).validate(execution=True)
        fake = SimpleNamespace(allow_execution=True, validate=lambda:self.path)
        with self.assertRaises(ResearchAssistantError):
            self.run_case(context=fake)

    def test_evidence_and_deterministic_report_retain_unknown_semantics_and_coverage(self):
        result, _, _ = self.run_case(POSITIVE_CASES[2])
        bundle = result.evidence_bundle
        self.assertTrue(bundle.context["attribution_unknown"])
        self.assertTrue(bundle.context["unit_unknown"])
        self.assertIn("coverage", bundle.context)
        report = write_research_report(bundle)
        rendered = report_to_markdown(report)
        self.assertIn("attribution", rendered)
        self.assertIn("unknown", rendered)
        self.assertIn("2023", rendered)
        self.assertNotIn("per 100,000", rendered)
        self.assertNotIn("high-BMI-attributable", rendered)
        self.assertIn("marginal", " ".join(report.limitations).casefold())
        json.dumps(bundle.context)  # provider input must remain JSON serializable

    def test_grounded_interpretation_cannot_upgrade_unknown_attribution_units_or_weighting(self):
        bad_texts = ("These rates are attributable to High BMI.", "The rate is per 100,000 population.",
                     "These are population-weighted national estimates.")
        for text in bad_texts:
            class BadProvider(EchoProvider):
                def interpret(self, source):
                    result = super().interpret(source)
                    result.direct_answer = GroundedAnswer(text, [source.claims[0].claim_id])
                    return result
            result, _, _ = self.run_case(provider=BadProvider())
            self.assertIsNone(result.interpretation_result)
            self.assertIn("upgrades unknown", result.ai_error)

    def test_explicit_time_range_is_retained_through_execution(self):
        connection = duckdb.connect(str(self.path))
        try:
            connection.execute("INSERT INTO ihme.burden VALUES ('01001',2018,493,4,3,22,160,71,111,110,112)")
        finally:
            connection.close()
        text = "Compare ischemic heart disease among women ages 40-44 and 60-64 from 2018 to 2019."
        parser = OfflineParser(text, "Ischemic heart disease", POSITIVE_CASES[0][2], start_year=2018, end_year=2019)
        result = run_research_assistant(text, semantic_parser=parser, fixture_context=self.context,
                                       provider=EchoProvider(), judge=ExactEvidenceJudge())
        self.assertEqual(result.status, "answer")
        self.assertEqual(result.capability_decision.resolved_query.time.sources[0].years, (2018, 2019))
        self.assertEqual(tuple(row.year for row in result.evidence_bundle.items[0].data.coverage), (2018, 2019))

    def test_model_defaults_in_shared_groups_or_year_are_not_accepted(self):
        text, cause, md, key = POSITIVE_CASES[0]
        md = replace(md, group_a=Group(age="40-44", race_ethnicity="Total"),
                     group_b=Group(age="60-64", race_ethnicity="Total"))
        result, _, _ = self.run_case((text, cause, md, key))
        self.assertEqual(result.status, "clarify")
        text, cause, md, _ = POSITIVE_CASES[2]
        request = OfflineParser(text, cause, md, year=2019).parse(ResearchQuestion(text))
        self.assertEqual(apply_request_policy(request).decision.value, "clarify")

    def test_unsupported_operations_dimensions_and_measures_remain_rejected(self):
        for text in ("Did obesity cause female stroke differences by rurality?",
                     "Are female stroke differences by rurality statistically significant?",
                     "Predict female stroke by rurality in 2035.",
                     "Investigate causation in female stroke burden by rurality.",
                     "Female stroke ages 40-44 and 60-64 by income.",
                     "Female stroke hospitalizations by rurality."):
            case = (text, "Stroke", MD(fixed_sex="Female", operation="summarize_by_rurality"), "sex_rurality")
            result, _, _ = self.run_case(case)
            self.assertEqual(result.status, "reject")
            self.assertIsNone(result.evidence_bundle)

    def test_model_entailment_stage_is_not_bypassed(self):
        class UnsupportedProvider(EchoProvider):
            def interpret(self, source):
                result = super().interpret(source)
                result.direct_answer = GroundedAnswer("The observed rates diverged astronomically.", [source.claims[0].claim_id])
                return result
        result, _, judge = self.run_case(provider=UnsupportedProvider())
        self.assertIsNone(result.interpretation_result)
        self.assertGreater(judge.calls, 0)
        self.assertIn("semantic entailment", result.ai_error)

    def test_legacy_executor_transformations_remain_unchanged(self):
        import pandas as pd
        frames = (
            ("filter_dataframe", "restrict_year_range", pd.DataFrame({"year":[2018,2019],"v":[1,2]}),
             {"first_year":2019,"last_year":2019}),
            ("filter_analysis_year_dataframe", "restrict_analysis_year_range", pd.DataFrame({"analysis_year":[2018,2019],"v":[1,2]}),
             {"first_year":2019,"last_year":2019}),
            ("filter_measurement_year_dataframe", "restrict_measurement_year", pd.DataFrame({"measurement_year":[2019,2019],"carry_forward":[True,False],"v":[1,2]}),
             {"measurement_year":2019}),
        )
        for function, operation, frame, parameters in frames:
            plan = AnalysisPlan(ResearchQuestion("legacy transform fixture"), AnalysisIntent.TREND_COMPARISON,
                [AnalysisStep(1,"cause_trend","get_cause_trend",{},"fixture read"),
                 AnalysisStep(2,operation,function,parameters,"legacy filtering")])
            with patch.dict("ai.executor.APPROVED_FUNCTIONS", {"get_cause_trend": lambda:frame}):
                evidence = execute_plan(plan)
            self.assertEqual(len(evidence.items),1)
            self.assertEqual(evidence.items[0].data["v"].tolist(),[2])

    def test_ambiguous_demographic_catalog_is_clarification_not_a_default(self):
        connection = duckdb.connect(str(self.path))
        try:
            connection.execute("INSERT INTO analytics.dim_sex VALUES (23,'Female')")
        finally:
            connection.close()
        result, _, _ = self.run_case()
        self.assertEqual(result.status, "clarify")
        self.assertIn("Ambiguous", result.clarification_question)
        self.assertIsNone(result.evidence_bundle)

    def test_model_cannot_invert_comparison_orientation(self):
        text, cause, md, key = POSITIVE_CASES[1]
        result, _, _ = self.run_case((text, cause, replace(md, group_a=md.group_b, group_b=md.group_a), key))
        self.assertEqual(result.status, "reject")
        self.assertIn("orientation", result.policy_result.reason)

    def test_competing_legacy_and_structured_population_fields_require_clarification(self):
        text, cause, md, _ = POSITIVE_CASES[0]
        request = OfflineParser(text, cause, md, year=2019).parse(ResearchQuestion(text))
        request.demographic_dimension = "Sex"
        request.demographic_groups = ["Female", "Male"]
        self.assertEqual(apply_request_policy(request).decision.value, "clarify")

    def test_unresolved_qualitative_age_is_not_replaced_by_standardized_default(self):
        case = ("Older female stroke burden by rurality.", "Stroke",
                MD(fixed_sex="Female", operation="summarize_by_rurality"), "sex_rurality")
        result, _, _ = self.run_case(case)
        self.assertEqual(result.status, "clarify")
        self.assertIsNone(result.evidence_bundle)

    def test_county_name_is_not_treated_as_a_race_constraint(self):
        connection = duckdb.connect(str(self.path))
        try:
            connection.execute("UPDATE analytics.vw_current_county_lookup SET location_name='White County (Alabama)' WHERE fips='01001'")
        finally:
            connection.close()
        case = (POSITIVE_CASES[0][0] + " In White County, Alabama.", *POSITIVE_CASES[0][1:])
        result, _, _ = self.run_case(case, county="White County, Alabama")
        self.assertEqual(result.status, "answer")
        self.assertEqual(result.capability_decision.resolved_query.geography.county_fips, ("01001",))

    def test_rucc_classification_year_is_not_silently_used_as_health_year(self):
        case = ("Female stroke burden by RUCC 2023.", "Stroke",
                MD(fixed_sex="Female", operation="summarize_by_rurality"), "sex_rurality")
        result, _, _ = self.run_case(case)
        self.assertEqual(result.status, "answer")
        query = result.capability_decision.resolved_query
        self.assertEqual(query.time.sources[0].years, (2019,))
        self.assertEqual(query.geography.classification_year, 2023)
        self.assertTrue(any("year=2019" in item for item in query.assumptions))

    def test_explicit_allowlist_and_public_capability_state(self):
        self.assertEqual(set(MULTIDIMENSIONAL_FUNCTIONS), {"compare_strata", "summarize_by_rurality"})
        for key in ("sex_age", "sex_rurality", "age_rurality"):
            self.assertIs(CAPABILITIES[key].state, CapabilityState.PLANNED)
            self.assertFalse(CAPABILITIES[key].executable)
            self.assertFalse(CAPABILITIES[key].functions)
            self.assertFalse(CAPABILITIES[key].surfaces)


if __name__ == "__main__":
    unittest.main(verbosity=2)
