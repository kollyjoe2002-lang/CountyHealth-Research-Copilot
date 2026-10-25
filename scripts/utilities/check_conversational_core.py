"""Offline Phase 6 control-plane tests; no live NLP or warehouse certification."""
from dataclasses import replace, FrozenInstanceError
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.capabilities import CAPABILITIES, REGISTRY_VERSION, CapabilityState, Source, Surface
from ai.capability_conversation import (capability_summary, alternatives, summary_topic, fallback,
    nearby_concepts, load_capability_catalog)
from ai.conversation_contracts import CapabilityCatalog, FailureReason as R
from ai.conversation_state import (run_research_turn, ResearchState, snapshot, restore,
    MAX_TURNS, MAX_AGE_SECONDS, MAX_TEXT)
from ai.models import (AnalysisIntent as I, ResearchQuestion, SemanticAnalysisRequest as Request,
    ResearchAssistantOutcome as Outcome, RequestPolicyResult, RequestPolicyDecision as P)
from ai.multidimensional_request import MultidimensionalRequest as MD, SemanticPopulation as G
from ai.research_assistant import run_research_assistant
from ai.telemetry import build_research_telemetry_event


def request(text='Compare women ages 40-44 and 60-64 for stroke in 2019.', **kwargs):
    defaults = dict(cause_name='Stroke', year=2019, evidence_domain='IHME',
        multidimensional=MD(fixed_sex='Female', comparison_dimension='age',
            group_a=G(age='40-44'), group_b=G(age='60-64')))
    defaults.update(kwargs)
    return Request(ResearchQuestion(text), I.DEMOGRAPHIC_DISPARITY, .99, **defaults)


class Parser:
    def __init__(self, value):
        self.value = value
        self.calls = 0
    def parse(self, question):
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return replace(self.value, question=question)


class ConversationalCoreChecks(unittest.TestCase):
    def setUp(self):
        telemetry = patch('ai.research_assistant.persist_research_telemetry')
        self.persist = telemetry.start()
        self.addCleanup(telemetry.stop)
        executor = patch('ai.research_assistant.execute_plan', side_effect=AssertionError('Unexpected execution'))
        self.execute = executor.start()
        self.addCleanup(executor.stop)

    def turn(self, value=None, *, text=None, **kwargs):
        req = value or request()
        return run_research_turn(text or req.question.raw_text, semantic_parser=Parser(req), now=100, **kwargs)

    def test_capability_questions_need_no_model_or_warehouse(self):
        for text in ('What can you do?', 'What diseases do you cover?', 'What years do you support?',
                     'Can you compare women and men?', 'Can you compare by rurality?',
                     'Can you compare rural and metro counties?', 'Do you have breast cancer?'):
            with self.subTest(text=text), patch('ai.research_assistant.OpenAISemanticParser', side_effect=AssertionError('No model')):
                result = run_research_turn(text)
                self.assertEqual(result.outcome.status, 'capability_summary')
                self.assertIsNone(result.state)
                self.assertIsNotNone(result.response.text)
        self.execute.assert_not_called()

    def test_summary_states_and_source_limits(self):
        text = capability_summary('capabilities').text
        self.assertIn('Registered executable paths', text)
        self.assertIn('not activated', text)
        self.assertIn('unsupported', text)
        years = capability_summary('years').text
        self.assertIn('2000–2019', years)
        self.assertIn('2017–2023', years)
        self.assertIn('2018', years)
        self.assertIn('not proof', years)
        self.assertIn('fixed 2023', capability_summary('rurality').text)

    def test_disease_summary_never_infers_coverage_from_registry(self):
        result = capability_summary('breast cancer')
        self.assertIn('live catalog check', result.text)
        self.assertIn('must not be substituted', result.text)
        catalog = CapabilityCatalog(('Breast cancer','Stroke'), ('Cancer',), ('IHME','CDC PLACES'))
        observed = capability_summary('breast cancer', catalog).text
        self.assertIn('IHME catalog: Breast cancer', observed)
        self.assertIn('CDC PLACES catalog: no matching condition', observed)
        self.assertIn('does not establish usable', observed)

    def test_catalog_refresh_failure_is_not_empty_checked_catalog(self):
        with patch('app.data_access.DB_FILE', Path('/nonexistent-phase6-warehouse.duckdb')):
            with self.assertRaises(OSError):
                load_capability_catalog()

    def test_catalog_nearby_options_are_proposals_not_mappings(self):
        catalog = CapabilityCatalog(('Stroke','Diabetes mellitus'), ('Cancer','Current asthma'), ('IHME','CDC PLACES'))
        values = nearby_concepts('Diabetes', catalog)
        self.assertEqual(values[0], ('IHME','Diabetes mellitus'))
        self.assertEqual(len(values), 4)
        self.assertEqual(nearby_concepts('Cancer', CapabilityCatalog()), ())

    def test_three_planned_fallbacks(self):
        cases = (
            request(),
            request('Female stroke burden by rurality in 2019.', multidimensional=MD(fixed_sex='Female', operation='summarize_by_rurality')),
            request('Age 60-64 stroke burden by rurality in 2019.', multidimensional=MD(fixed_age='60-64', operation='summarize_by_rurality')),
        )
        for req in cases:
            with self.subTest(req=req):
                result = self.turn(req)
                self.assertEqual(result.outcome.status, 'planned')
                self.assertIs(result.response.reason, R.CAPABILITY_PLANNED_NOT_ACTIVATED)
                self.assertIn('not yet activated', result.response.text)
                self.assertIn('not a finding that the data do not exist', result.response.text)
                self.assertIsNone(result.outcome.evidence_bundle)
        self.execute.assert_not_called()

    def test_unsupported_table_no_downgrade(self):
        cases = (
            ('Compare Black women and White men for stroke in 2019.', R.DEMOGRAPHIC_COMBINATION_UNSUPPORTED),
            ('Compare female stroke ages 40-44 and 60-64 by rurality in 2019.', R.DEMOGRAPHIC_COMBINATION_UNSUPPORTED),
            ('Forecast stroke to 2035.', R.OPERATION_UNSUPPORTED),
            ('Estimate the causal effect of rurality on stroke.', R.OPERATION_UNSUPPORTED),
            ('Female CDC PLACES stroke prevalence in 2019.', R.DEMOGRAPHIC_COMBINATION_UNSUPPORTED),
        )
        for text, reason in cases:
            req = request(text, multidimensional=None, evidence_domain='PLACES' if 'PLACES' in text else 'IHME')
            with self.subTest(text=text):
                result = self.turn(req)
                self.assertEqual(result.outcome.status, 'reject')
                self.assertIs(result.response.reason, reason)
                self.assertIsNone(result.outcome.evidence_bundle)
        self.execute.assert_not_called()

    def test_unsupported_year_not_substituted(self):
        req = request('IHME stroke burden in 2024.', year=2024, multidimensional=None)
        result = self.turn(req)
        self.assertIs(result.response.reason, R.YEAR_UNAVAILABLE)
        self.assertEqual(result.outcome.semantic_request.year, 2024)
        self.assertIn('not substituted', result.response.text)

    def test_explicit_resolution_reason_taxonomy(self):
        from ai.resolver import ResolutionError
        cases = (
            ('The requested disease or cause could not be matched to a validated CountyHealth cause.', R.HEALTH_CONCEPT_UNAVAILABLE),
            ('Cause resolution was ambiguous for X', R.AMBIGUOUS_HEALTH_CONCEPT),
            ('County resolution was ambiguous among validated locations. Please specify the state.', R.AMBIGUOUS_COUNTY),
            ('The cause lookup is missing required columns.', R.INFRASTRUCTURE_UNAVAILABLE),
        )
        for message, reason in cases:
            with self.subTest(message=message):
                self.assertIs(ResolutionError(message).reason, reason)

    def test_resolver_failure_reaches_conversational_response(self):
        # Real canonical orchestration, replacing only database-dependent resolver.
        from ai.resolver import ResolutionError
        for message, code in (
            ('Cause resolution was ambiguous for Stroke', R.AMBIGUOUS_HEALTH_CONCEPT),
            ('County resolution was ambiguous among locations. Please specify the state.', R.AMBIGUOUS_COUNTY),
            ('The requested disease or cause could not be matched to a validated CountyHealth cause.', R.HEALTH_CONCEPT_UNAVAILABLE),
        ):
            req = request('Stroke in Milwaukee County in 2019.', multidimensional=None, county_name='Milwaukee County')
            req.intent = I.COUNTY_CAUSE_SNAPSHOT
            def resolve(classified, plan):
                plan.unresolved_items.append(message)
                plan.resolved_context['failure_reason'] = ResolutionError(message).reason
                return plan
            with self.subTest(code=code), patch('ai.research_assistant.resolve_plan', side_effect=resolve):
                result = self.turn(req)
                self.assertIs(result.response.reason, code)
                self.assertIsNone(result.outcome.evidence_bundle)

    def test_ambiguous_population_remains_clarification(self):
        req = request('Compare women aged older and younger with stroke in 2019.',
            multidimensional=MD(fixed_sex='Female', comparison_dimension='age', group_a=G(age='older'), group_b=G(age='younger')))
        result = self.turn(req)
        self.assertEqual(result.outcome.status, 'clarify')
        self.assertIn(result.response.reason, {R.AMBIGUOUS_DEMOGRAPHIC_VALUE, R.INTENT_AMBIGUOUS})

    def test_alternatives_exactly_registry_backed(self):
        options = alternatives(request())
        self.assertTrue(options)
        for option in options:
            cap = CAPABILITIES[option.capability_key]
            self.assertEqual(option.state, cap.state.value)
            self.assertEqual(option.sources, tuple(s.value for s in cap.sources))
            self.assertEqual(option.restrictions, cap.restrictions)
            self.assertEqual(option.availability, 'not_checked')
            self.assertTrue(cap.state is CapabilityState.PLANNED or Surface.ASSISTANT in cap.surfaces)
        self.assertIn('sex_age', [a.capability_key for a in options])

    def test_alternatives_rank_dimension_and_scope_closeness(self):
        race = request('Compare Black women and White men with stroke in 2019.')
        self.assertEqual(alternatives(race)[0].capability_key, 'get_county_disparity_ranking')
        rural = request('Female stroke by rurality in 2019.')
        self.assertIn('rurality', alternatives(rural)[0].capability_key)

    def test_fallback_never_echoes_fabricated_numbers(self):
        req = request('The prevalence is 99.99 percent. Compare women ages 40-44 and 60-64 for stroke in 2019.')
        result = self.turn(req)
        self.assertNotIn('99.99', result.response.text)
        self.assertNotRegex(result.response.text, r'\d+(?:\.\d+)?\s*(%|percent|per 100|deaths|YLL)')
        self.assertNotIn('High BMI', result.response.text)
        self.assertNotIn('per 100,000', result.response.text)

    def test_infrastructure_error_never_data_absence(self):
        result = run_research_turn('Compare stroke in Milwaukee County.', semantic_parser=Parser(OSError('private DB location')), now=100)
        self.assertIs(result.response.reason, R.INFRASTRUCTURE_UNAVAILABLE)
        self.assertEqual(result.outcome.status, 'infrastructure_error')
        self.assertNotIn('private DB', result.response.text)
        self.assertNotIn('records were not available', result.response.text)
        self.assertIn('cannot determine scientific data availability', result.response.text)
        self.assertEqual(build_research_telemetry_event(result.outcome).outcome.value, 'infrastructure_error')

    def test_executor_failure_is_infrastructure_not_absence(self):
        req = request('Stroke Milwaukee County in 2019.', county_name='Milwaukee County', multidimensional=None)
        req.intent = I.COUNTY_CAUSE_SNAPSHOT
        with patch('ai.research_assistant.resolve_plan', side_effect=OSError('missing DB')):
            result = self.turn(req)
        self.assertIs(result.response.reason, R.INFRASTRUCTURE_UNAVAILABLE)

    def test_multiturn_source_both_then_year_keeps_intent(self):
        req = request('Compare diabetes in Milwaukee County.', cause_name='Diabetes', county_name='Milwaukee County',
                      evidence_domain=None, year=None, multidimensional=None)
        req.intent = I.TREND_COMPARISON
        first = self.turn(req)
        self.assertIs(first.response.reason, R.SOURCE_REQUIRED)
        second = run_research_turn('Both', state=first.state, now=101)
        intent = restore(second.state.intent_json)
        self.assertEqual(intent.evidence_domain, 'PLACES_IHME')
        self.assertEqual(intent.cause_name, 'Diabetes')
        self.assertEqual(intent.county_name, 'Milwaukee County')
        self.assertIs(second.response.reason, R.YEAR_REQUIRED)
        with patch('ai.research_assistant.resolve_plan', side_effect=OSError('no warehouse')):
            third = run_research_turn('2019', state=second.state, now=102)
        self.assertEqual(restore(third.state.intent_json).year, 2019)
        self.assertEqual(restore(third.state.intent_json).evidence_domain, 'PLACES_IHME')
        self.assertIs(third.response.reason, R.INFRASTRUCTURE_UNAVAILABLE)

    def test_missing_year_followup_full_pipeline_reruns(self):
        first = self.turn(request('Compare women ages 40-44 and 60-64 for stroke.', year=None))
        self.assertIs(first.response.reason, R.YEAR_REQUIRED)
        with patch('ai.research_assistant.apply_request_policy', wraps=__import__('ai.request_policy', fromlist=['apply_request_policy']).apply_request_policy) as policy:
            second = run_research_turn('2019', state=first.state, now=101)
        self.assertEqual(policy.call_count, 1)
        self.assertEqual(second.outcome.status, 'planned')
        self.assertEqual(restore(second.state.intent_json).year, 2019)
        self.execute.assert_not_called()

    def test_county_ambiguity_state_followup_goes_to_canonical_resolver(self):
        req = request('Stroke in Washington County in 2019.', multidimensional=None, county_name='Washington County')
        req.intent = I.COUNTY_CAUSE_SNAPSHOT
        def ambiguous(classified, plan):
            plan.unresolved_items.append('Please specify the state.')
            plan.resolved_context['failure_reason'] = R.AMBIGUOUS_COUNTY
            return plan
        with patch('ai.research_assistant.resolve_plan', side_effect=ambiguous):
            first = self.turn(req)
        self.assertEqual(first.state.pending_field, 'county_name')
        # A state disambiguates the county; it is not a contradictory county change.
        second = run_research_turn('Wisconsin', state=first.state, now=101)
        self.assertEqual(restore(second.state.intent_json).county_name, 'Washington County (Wisconsin)')

    def test_year_change_preserves_disease_and_population_but_requires_confirmation(self):
        first = self.turn()
        second = run_research_turn('2018', state=first.state, now=101)
        self.assertIs(second.response.reason, R.CONTRADICTORY_FOLLOW_UP)
        self.assertEqual(restore(second.state.intent_json).year, 2019)
        proposed = restore(second.state.proposed_json)
        self.assertEqual(proposed.cause_name, 'Stroke')
        self.assertEqual(proposed.multidimensional.fixed_sex, 'Female')
        third = run_research_turn('confirm change', state=second.state, now=102)
        self.assertEqual(restore(third.state.intent_json).year, 2018)
        self.assertEqual(third.outcome.status, 'planned')
        self.assertIsNone(third.outcome.evidence_bundle)

    def test_age_change_preserves_fixed_sex(self):
        req = request('Female stroke age 60-64 by rurality in 2019.',
            multidimensional=MD(fixed_sex='Female', fixed_age='60-64', operation='summarize_by_rurality'))
        # Even an unsupported intent is retained; changing age cannot erase sex.
        first = self.turn(req)
        delta = Request(ResearchQuestion('Use age 40-44'), I.UNKNOWN, .9,
                        multidimensional=MD(fixed_age='40-44'))
        second = self.turn(delta, state=first.state, text='Use age 40-44')
        proposed = restore(second.state.proposed_json)
        self.assertEqual(proposed.multidimensional.fixed_age, '40-44')
        self.assertEqual(proposed.multidimensional.fixed_sex, 'Female')
        self.assertIs(second.response.reason, R.CONTRADICTORY_FOLLOW_UP)
        self.execute.assert_not_called()

    def test_no_scope_broadening_or_fixed_filter_loss(self):
        first = self.turn(request(county_name='Autauga County (Alabama)'))
        delta = Request(ResearchQuestion('2018'), I.UNKNOWN, .9, year=2018)
        second = self.turn(delta, state=first.state, text='2018')
        prior, proposed = restore(first.state.intent_json), restore(second.state.proposed_json)
        self.assertEqual(prior.county_name, proposed.county_name)
        self.assertEqual(prior.multidimensional, proposed.multidimensional)

    def test_ambiguous_pronoun_never_guessed(self):
        first = self.turn()
        result = run_research_turn('What about them?', state=first.state, now=101)
        self.assertIs(result.response.reason, R.INTENT_AMBIGUOUS)
        self.assertEqual(restore(result.state.intent_json).multidimensional, restore(first.state.intent_json).multidimensional)
        self.execute.assert_not_called()

    def test_capability_catalog_and_time_invalidate_state(self):
        first = self.turn()
        changed = CapabilityCatalog(('Stroke',), checked_sources=('IHME',))
        cases = (
            dict(state=replace(first.state, registry_version='old'), now=101),
            dict(state=first.state, capability_catalog=changed, now=101),
            dict(state=first.state, now=100+MAX_AGE_SECONDS+1),
            dict(state=replace(first.state, turns=MAX_TURNS), now=101),
        )
        for options in cases:
            result = run_research_turn('2019', **options)
            self.assertIs(result.response.reason, R.STATE_INVALIDATED)
            self.assertIsNone(result.state)
            self.assertIsNone(result.outcome)

    def test_bounded_state_contains_no_results_or_transcript(self):
        first = self.turn()
        self.assertLessEqual(len(first.state.intent_json.encode()), 8192)
        fields = set(first.state.__dataclass_fields__)
        self.assertFalse(fields.intersection({'evidence','results','history','transcript','fixture_context'}))
        with self.assertRaises(FrozenInstanceError):
            first.state.turns = 0
        self.assertIsNone(run_research_turn('x'*(MAX_TEXT+1)).state)
        with self.assertRaises(ValueError):
            replace(first.state, turns=MAX_TURNS+1)

    def test_summary_does_not_destroy_pending_state(self):
        first = self.turn(request('Compare women ages 40-44 and 60-64 for stroke.', year=None))
        help_turn = run_research_turn('What can you do?', state=first.state, now=101)
        self.assertEqual(help_turn.state, first.state)
        next_turn = run_research_turn('2019', state=help_turn.state, now=102)
        self.assertEqual(next_turn.outcome.status, 'planned')

    def test_telemetry_preserves_privacy_and_legacy_states(self):
        result = self.turn()
        event = build_research_telemetry_event(result.outcome)
        self.assertEqual(event.outcome.value, 'planned')
        self.assertNotIn('intent_json', event.metadata)
        self.assertNotIn('question', event.metadata)
        for outcome in ('answer','clarify','reject','planned','unavailable'):
            value = replace(result.outcome, status=outcome)
            self.assertEqual(build_research_telemetry_event(value).outcome.value, outcome)

    def test_rejected_unparsed_constraints_survive_year_followup(self):
        # A parser may omit a constraint. The raw policy guard must still see it
        # after a follow-up; re-rendering only parsed fields would be unsafe.
        req = request('Compare Black women and White men for stroke in 2019.', multidimensional=None)
        first = self.turn(req)
        changed = run_research_turn('2018', state=first.state, now=101)
        confirmed = run_research_turn('confirm change', state=changed.state, now=102)
        self.assertEqual(confirmed.outcome.status, 'reject')
        self.assertIn('Black women', restore(confirmed.state.intent_json).question.raw_text)
        self.execute.assert_not_called()

    def test_resolved_unapproved_cause_excludes_cross_source_proposals(self):
        options = alternatives(request(), resolved_context={'cause_id': 999999})
        self.assertTrue(options)
        self.assertFalse(any(CAPABILITIES[a.capability_key].approved_pair_policy for a in options))

    def test_resolution_catalog_revision_invalidates_state(self):
        first = self.turn()
        catalog = CapabilityCatalog(resolution_fingerprint='changed-county-or-demographic-catalog')
        result = run_research_turn('2019', state=first.state, capability_catalog=catalog, now=101)
        self.assertIs(result.response.reason, R.STATE_INVALIDATED)

    def test_all_required_failure_codes_exist(self):
        required = {'DATA_UNAVAILABLE', 'YEAR_UNAVAILABLE', 'HEALTH_CONCEPT_UNAVAILABLE',
            'DEMOGRAPHIC_COMBINATION_UNSUPPORTED', 'GEOGRAPHIC_COMBINATION_UNSUPPORTED',
            'OPERATION_UNSUPPORTED', 'AMBIGUOUS_COUNTY', 'AMBIGUOUS_HEALTH_CONCEPT',
            'AMBIGUOUS_DEMOGRAPHIC_VALUE', 'CAPABILITY_PLANNED_NOT_ACTIVATED', 'INFRASTRUCTURE_UNAVAILABLE'}
        self.assertTrue(required.issubset({r.value for r in R}))

    def test_followup_executes_only_canonical_guarded_fixture_and_never_reuses_results(self):
        from scripts.utilities.check_multidimensional_semantic import (
            MultidimensionalSemanticChecks, OfflineParser, EchoProvider, ExactEvidenceJudge, POSITIVE_CASES)
        from ai.executor import execute_plan
        harness = MultidimensionalSemanticChecks('test_seven_positive_structured_parses_and_guarded_full_pipeline')
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        text, cause, md, key = POSITIVE_CASES[0]
        text = text.replace(' in 2019', '')
        first = run_research_turn(text, semantic_parser=OfflineParser(text, cause, md), now=100,
            fixture_context=harness.context, provider=EchoProvider(), judge=ExactEvidenceJudge())
        self.assertIs(first.response.reason, R.YEAR_REQUIRED)
        judge = ExactEvidenceJudge()
        with patch('ai.research_assistant.execute_plan', wraps=execute_plan) as executor:
            second = run_research_turn('2019', state=first.state, now=101,
                fixture_context=harness.context, provider=EchoProvider(), judge=judge)
        self.assertEqual(second.outcome.status, 'answer')
        self.assertIsNotNone(second.outcome.interpretation_result)
        self.assertEqual(executor.call_count, 1)
        self.assertGreater(judge.calls, 0)
        self.assertNotIn('coverage', second.state.intent_json)
        self.assertNotIn('fixture', second.state.intent_json)
        changed = run_research_turn('2018', state=second.state, now=102)
        self.assertIsNone(changed.outcome.evidence_bundle)
        confirmed = run_research_turn('confirm change', state=changed.state, now=103,
            fixture_context=harness.context, provider=EchoProvider(), judge=ExactEvidenceJudge())
        self.assertEqual(confirmed.outcome.status, 'unavailable')
        self.assertIsNone(confirmed.outcome.evidence_bundle)
        self.assertIs(confirmed.response.reason, R.DATA_UNAVAILABLE)

    def test_parser_outage_during_followup_preserves_pending_intent(self):
        first = self.turn()
        failed = run_research_turn('Change the health condition', state=first.state,
            semantic_parser=Parser(OSError('API offline')), now=101)
        self.assertIs(failed.response.reason, R.INFRASTRUCTURE_UNAVAILABLE)
        self.assertEqual(failed.state.intent_json, first.state.intent_json)
        self.assertIsNone(failed.outcome.evidence_bundle)

    def test_independently_changing_sex_and_age_is_demographic_unsupported(self):
        req = request('Compare women aged 40-44 and men aged 60-64 for stroke in 2019.',
            multidimensional=MD(comparison_dimension='multiple', group_a=G(sex='Female',age='40-44'),
                                group_b=G(sex='Male',age='60-64')))
        result = self.turn(req)
        self.assertIs(result.response.reason, R.DEMOGRAPHIC_COMBINATION_UNSUPPORTED)
        self.assertIsNone(result.outcome.evidence_bundle)

    def test_llm_source_clarification_gets_explicit_pending_slot(self):
        req = request('Compare diabetes in Milwaukee County.', cause_name='Diabetes', county_name='Milwaukee County',
                      evidence_domain=None, year=None, multidimensional=None)
        req.intent = I.TREND_COMPARISON
        req.needs_clarification = True
        req.clarification_question = 'Do you mean CDC PLACES prevalence, IHME burden, or both?'
        first = self.turn(req)
        self.assertEqual(first.state.pending_field, 'evidence_domain')
        second = run_research_turn('Both', state=first.state, now=101)
        self.assertEqual(restore(second.state.intent_json).evidence_domain, 'PLACES_IHME')
        self.assertIs(second.response.reason, R.YEAR_REQUIRED)

    def test_all_three_capabilities_remain_planned(self):
        for key in ('sex_age','sex_rurality','age_rurality'):
            self.assertIs(CAPABILITIES[key].state, CapabilityState.PLANNED)
            self.assertFalse(CAPABILITIES[key].executable)
            self.assertEqual(CAPABILITIES[key].surfaces, ())


if __name__ == '__main__':
    unittest.main(verbosity=2)
