"""Offline Phase 7 catalogs/controllers and actual Streamlit page rendering.

Tiny synthetic catalogs validate structure only, never warehouse activation.
"""
from pathlib import Path
import ast
from dataclasses import replace
import tempfile
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb
import pandas as pd
from streamlit.testing.v1 import AppTest
from app import research_catalogs as catalog, research_controls as controller
from app.research_presentation import interpreted_preview, provenance, turn_status, narrative_is_safe
from app.research_conversation import submit_research_turn
from ai.capabilities import APPROVED_PLACES_IHME_PAIRS, CAPABILITIES, CapabilityState
from ai.conversation_contracts import CapabilityCatalog
from ai.models import AnalysisIntent, ResearchQuestion, SemanticAnalysisRequest
from ai.multidimensional_request import MultidimensionalRequest as MD, SemanticPopulation as G
from ai.research_assistant import run_research_assistant
from scripts.utilities.check_conversational_core import Parser, request


class ResearchExperienceChecks(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)/'catalog_fixture.duckdb'
        con = duckdb.connect(str(self.path))
        con.execute('CREATE SCHEMA places')
        con.execute('CREATE SCHEMA analytics')
        con.execute('CREATE SCHEMA geography')
        con.execute('CREATE SCHEMA ihme')
        con.execute('CREATE TABLE places.measures(measure_id VARCHAR, canonical_name VARCHAR)')
        con.executemany('INSERT INTO places.measures VALUES (?,?)', [
            ('DIABETES','Diagnosed diabetes among adults'), ('STROKE','Stroke among adults'),
            ('CASTHMA','Current asthma among adults'), ('CANCER','Cancer among adults'), ('CHD','Coronary heart disease'),
            ('OBESITY','Obesity among adults'), ('EMPTY','No eligible observations')])
        con.execute('CREATE TABLE places.releases(release_year INT)')
        con.executemany('INSERT INTO places.releases VALUES (?)', [(2020,), (2024,), (2025,)])
        con.execute('CREATE TABLE places.measure_versions(release_year INT, measure_id VARCHAR)')
        con.executemany('INSERT INTO places.measure_versions VALUES (?,?)', [(y,m) for y in (2020,2024,2025) for m in ('DIABETES','STROKE','CASTHMA','CANCER','EMPTY')])
        con.execute('''CREATE TABLE places.estimates(geoid VARCHAR, geography_name VARCHAR, state_name VARCHAR,
            state_abbr VARCHAR, geography_level VARCHAR, measure_id VARCHAR, release_year INT,
            measurement_year INT, age_adjusted_prevalence DOUBLE, carry_forward BOOLEAN)''')
        rows = [
            ('55079','Milwaukee','Wisconsin','WI','county','DIABETES',2020,2019,10,False),
            ('55131','Washington','Wisconsin','WI','county','DIABETES',2020,2019,0,False),
            ('27163','Washington','Minnesota','MN','county','DIABETES',2020,2019,8,False),
            ('55079','Milwaukee','Wisconsin','WI','county','DIABETES',2024,2022,12,False),
            ('55079','Milwaukee','Wisconsin','WI','county','STROKE',2025,2023,3,True),
            ('55079','Milwaukee','Wisconsin','WI','county','STROKE',2020,2019,2,False),
            ('55079','Milwaukee','Wisconsin','WI','county','CASTHMA',2025,2023,5,False),
            ('55079','Milwaukee','Wisconsin','WI','county','EMPTY',2024,2022,None,True),
            ('55079','Milwaukee','Wisconsin','WI','county','DIABETES',2020,2017,9,False),
            # No matching release-specific definition: not a valid trend year.
            ('55079','Milwaukee','Wisconsin','WI','county','CHD',2025,2023,6,False),
        ]
        con.executemany('INSERT INTO places.estimates VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
        con.execute('CREATE TABLE analytics.vw_current_county_lookup(fips VARCHAR, location_name VARCHAR)')
        con.executemany('INSERT INTO analytics.vw_current_county_lookup VALUES (?,?)', [
            ('55079','Milwaukee County (Wisconsin)'), ('55131','Washington County (Wisconsin)'),
            ('27163','Washington County (Minnesota)')])
        con.execute('CREATE TABLE analytics.dim_cause(cause_id INT,cause_name VARCHAR)')
        con.executemany('INSERT INTO analytics.dim_cause VALUES (?,?)',[(976,'Diabetes mellitus type 2'),(494,'Stroke'),(515,'Asthma'),(493,'Ischemic heart disease'),(999,'Breast cancer')])
        con.execute('CREATE TABLE geography.rucc_2023(fips VARCHAR,rucc_code INT,source_year INT,metro_status VARCHAR)')
        con.executemany('INSERT INTO geography.rucc_2023 VALUES (?,?,?,?)', [('55079',1,2023,'Metro'),('55131',4,2023,'Nonmetro')])
        con.execute('CREATE TABLE ihme.burden(fips VARCHAR,year INT,cause_id INT,sex_id INT,race_id INT,age_group_id INT,measure_id INT,metric_id INT,val DOUBLE)')
        con.executemany('INSERT INTO ihme.burden VALUES (?,?,?,?,?,?,?,?,?)', [('55079',2019,976,3,1,38,4,3,20),('55079',2019,494,3,1,38,4,3,30),('55079',2019,515,3,1,38,4,3,40)])
        con.close()
        self.queries = []
        def run(sql, parameters=None):
            self.queries.append((sql,parameters))
            connection = duckdb.connect(str(self.path),read_only=True)
            try:
                return connection.execute(sql, parameters or []).fetchdf()
            finally:
                connection.close()
        p = patch('app.research_catalogs.run_query',side_effect=run)
        p.start(); self.addCleanup(p.stop)
        p = patch('ai.research_assistant.persist_research_telemetry')
        p.start(); self.addCleanup(p.stop)

    def write(self, sql):
        con = duckdb.connect(str(self.path))
        try: con.execute(sql)
        finally: con.close()

    def page(self, name):
        at=AppTest.from_file(str(ROOT/'app/pages'/f'{name}.py'), default_timeout=25).run()
        self.assertEqual(len(at.exception),0,[e.value for e in at.exception])
        return at

    def messages(self, at):
        return '\n'.join(str(item.value) for kind in ('markdown','info','warning','error','caption','success') for item in at.get(kind))

    def test_county_labels_fips_and_ambiguity(self):
        counties=catalog.places_counties()
        washington=[c for c in counties if c.county=='Washington County']
        self.assertEqual(len(washington),2)
        self.assertEqual({c.state for c in washington},{'Wisconsin','Minnesota'})
        self.assertEqual({catalog.selected_county(c,counties) for c in washington},{'55131','27163'})
        with self.assertRaises(catalog.CatalogError): catalog.selected_county(None,counties)
        milwaukee=next(c for c in counties if c.fips=='55079')
        self.assertEqual(milwaukee.label,'Milwaukee County, Wisconsin (WI)')
        self.assertEqual(catalog.selected_county(milwaukee,counties),'55079')

    def test_conflicting_county_identity_never_first_match(self):
        self.write("INSERT INTO analytics.vw_current_county_lookup VALUES ('55079','Other County (Wisconsin)')")
        with self.assertRaises(catalog.CatalogError): catalog.places_counties()

    def test_measure_labels_are_canonical_and_data_driven(self):
        choices=catalog.places_measures()
        self.assertEqual(next(m.measure_id for m in choices if m.label=='Diagnosed diabetes among adults'),'DIABETES')
        self.write("INSERT INTO places.measures VALUES ('NEW','New catalog concept')")
        self.assertIn('New catalog concept',[m.label for m in catalog.places_measures()])

    def test_years_are_observed_measure_and_policy_specific(self):
        self.assertEqual(catalog.places_years('DIABETES',catalog.YearPolicy.RANKING),(2022,2019))
        self.assertEqual(catalog.places_years('STROKE',catalog.YearPolicy.TREND,fips='55079'),(2023,2019))
        self.assertEqual(catalog.places_years('STROKE',catalog.YearPolicy.RANKING),(2019,))
        self.assertEqual(catalog.places_years('EMPTY',catalog.YearPolicy.RANKING),())
        self.assertEqual(catalog.places_years('CHD',catalog.YearPolicy.TREND),())

    def test_release_and_measurement_years_are_distinct(self):
        self.assertEqual(catalog.places_releases('55079','DIABETES'),(2024,2020))
        self.assertEqual(catalog.places_years('DIABETES',catalog.YearPolicy.TREND,fips='55079'),(2022,2019))

    def test_catalog_queries_read_only_and_parameterized(self):
        self.assertEqual(catalog.places_years("x'; DROP TABLE places.measures; --",catalog.YearPolicy.RANKING),())
        self.assertTrue(catalog.places_measures())
        self.assertTrue(all(sql.strip().upper().startswith('SELECT') for sql,params in self.queries))
        self.assertNotIn('DROP TABLE',self.queries[0][0])
        self.assertIn('DROP TABLE',self.queries[0][1][0])

    def test_rural_years_require_rucc_without_claiming_complete_coverage(self):
        self.assertEqual(catalog.places_years('DIABETES',catalog.YearPolicy.ADJACENCY),(2022,2019))
        self.assertEqual(catalog.rural_releases('DIABETES',2019,adjacency=True),(2020,))
        self.write('DELETE FROM geography.rucc_2023')
        self.assertEqual(catalog.places_years('DIABETES',catalog.YearPolicy.ADJACENCY),())

    def test_approved_pairs_exact_and_catalog_driven(self):
        pairs=catalog.approved_pairs()
        self.assertEqual({(p.measure.measure_id,p.cause_id) for p in pairs},
            {(mid,cid) for mid,ids in APPROVED_PLACES_IHME_PAIRS.items() for cid in ids})
        self.assertFalse(any('Cancer' in p.label or 'Ischemic' in p.label for p in pairs))
        self.write('DELETE FROM analytics.dim_cause WHERE cause_id=515')
        self.assertEqual(len(catalog.approved_pairs()),2)

    def test_pair_years_require_exact_basis_and_match(self):
        pair=next(p for p in catalog.approved_pairs() if p.measure.measure_id=='DIABETES')
        self.assertEqual(catalog.pair_years(pair),(2019,))
        self.assertEqual(catalog.pair_releases(pair,2019),(2020,))
        self.write('UPDATE ihme.burden SET sex_id=22')
        self.assertEqual(catalog.pair_years(pair),())
        with self.assertRaises(catalog.CatalogError): catalog.pair_years(replace(pair,cause_id=999))

    def test_rurality_labels_exact_semantics(self):
        self.assertEqual(tuple(catalog.RURALITY_LABELS),('Metro','Nonmetro','Nonmetro adjacent','Nonmetro not adjacent'))
        self.assertIn('2023',catalog.RUCC_NOTE)
        self.assertIn('not describe historical',catalog.RUCC_NOTE)
        self.assertIn('confidence intervals',catalog.SOURCE_NOTE)
        self.assertIn('uncertainty intervals',catalog.SOURCE_NOTE)

    def test_unavailable_year_cannot_execute_or_fallback(self):
        measure=next(m for m in catalog.places_measures() if m.measure_id=='STROKE')
        with patch('app.data_access.get_places_county_measure_ranking') as run:
            with self.assertRaises(catalog.CatalogError): controller.places_ranking(measure,2023,25)
            run.assert_not_called()
        with patch('app.data_access.get_places_county_measure_ranking',return_value=pd.DataFrame()) as run:
            controller.places_ranking(measure,2019,25)
            run.assert_called_once_with('STROKE',2019,25)

    def test_rural_controller_exact_separate_metrics(self):
        pair=catalog.approved_pairs()[0]
        expected=pd.DataFrame({'mean_places_prevalence':[1.0],'mean_ihme_yll_rate':[2.0]})
        with patch('app.data_access.get_places_ihme_rurality_comparison',return_value=expected) as run:
            result=controller.cross_source_summary(pair,2019)
            run.assert_called_once_with(pair.measure.measure_id,2019,pair.cause_id,2019)
            self.assertEqual(list(result),['mean_places_prevalence','mean_ihme_yll_rate'])

    def test_places_page_no_technical_input_and_no_first_selection(self):
        at=self.page('CDC_PLACES')
        self.assertEqual(len(at.text_input),0)
        self.assertIsNone(at.selectbox[1].value)
        self.assertIsNone(at.selectbox[2].value)
        self.assertTrue(at.button[0].disabled)
        self.assertIn('Milwaukee County, Wisconsin (WI)',at.selectbox[2].options)
        self.assertNotIn('55079',' '.join(at.selectbox[2].options))

    def test_places_page_year_dependency_and_empty_disabled(self):
        at=self.page('CDC_PLACES')
        at.selectbox[0].select('National county ranking').run()
        at.selectbox[1].select('Stroke among adults').run()
        self.assertEqual(at.selectbox[2].options,['2019'])
        at.selectbox[1].select('No eligible observations').run()
        self.assertEqual(at.selectbox[2].options,[])
        self.assertTrue(at.button[0].disabled)
        self.assertIn('Execution is disabled',self.messages(at))

    def test_snapshot_page_provenance_includes_fips(self):
        frame=pd.DataFrame([dict(measure_id='DIABETES',release_year=2020,measurement_year=2019,
            crude_prevalence=9,crude_ci_lower=8,crude_ci_upper=10,age_adjusted_prevalence=9,
            age_adjusted_ci_lower=8,age_adjusted_ci_upper=10,carry_forward=False,missing_reason=None)])
        with patch('app.data_access.get_places_county_snapshot',return_value=frame) as run:
            at=self.page('CDC_PLACES')
            at.selectbox[1].select('Diagnosed diabetes among adults').run()
            at.selectbox[2].select('Milwaukee County, Wisconsin (WI)').run()
            at.selectbox[3].select(2020).run()
            at.button[0].click().run()
            self.assertEqual(len(at.exception),0)
            run.assert_called_once_with('55079',2020)
            self.assertTrue(any('55079' in item.value and 'DIABETES' in item.value for item in at.json))
            self.assertEqual(at.dataframe[0].value.iloc[0]['measurement_year'],2019)

    def test_rural_page_only_approved_pair_choices_and_human_labels(self):
        at=self.page('Rural_Health')
        at.selectbox[0].select('PLACES + IHME rurality comparison').run()
        self.assertEqual(len(at.selectbox[1].options),3)
        self.assertFalse(any('Cancer' in label or 'Coronary' in label for label in at.selectbox[1].options))
        self.assertTrue(at.button[0].disabled)
        self.assertEqual(len(at.text_input),0)
        self.assertIn('fixed geographic',self.messages(at))

    def test_rural_page_separate_metric_panels(self):
        frame=pd.DataFrame([dict(rurality_group='Metro',counties=2,mean_places_prevalence=1,
            median_places_prevalence=1,mean_ihme_yll_rate=2,median_ihme_yll_rate=2)])
        with patch('app.data_access.get_places_ihme_rurality_comparison',return_value=frame):
            at=self.page('Rural_Health')
            at.selectbox[0].select('PLACES + IHME rurality comparison').run()
            at.selectbox[1].select(at.selectbox[1].options[0]).run()
            at.selectbox[2].select(2019).run()
            at.button[0].click().run()
            self.assertEqual(len(at.exception),0,[e.value for e in at.exception])
            self.assertIn('CDC PLACES prevalence',[v.value for v in at.subheader])
            self.assertIn('IHME YLL rate — unit scale unverified',[v.value for v in at.subheader])
            self.assertEqual(at.dataframe[0].value.iloc[0]['rurality_group'],'Metropolitan')

    def test_report_source_followup_survives_rerun(self):
        req=request('Compare diabetes in Milwaukee County.',cause_name='Diabetes',county_name='Milwaukee County',year=None,evidence_domain=None,multidimensional=None)
        req.intent=AnalysisIntent.TREND_COMPARISON
        with patch('app.research_conversation.load_capability_catalog',return_value=CapabilityCatalog()), \
             patch('ai.conversation_state.LazySemanticParser.parse',side_effect=Parser(req).parse):
            at=self.page('Research_Report')
            at.chat_input[0].set_value(req.question.raw_text).run()
            self.assertIn('Do you want CDC PLACES',self.messages(at))
            state=at.session_state['research_conversation_state']
            at.run()
            self.assertEqual(state,at.session_state['research_conversation_state'])
            at.chat_input[0].set_value('Both').run()
            self.assertIn('Which observation year',self.messages(at))
            self.assertEqual(len(at.chat_message),2)
            self.assertEqual(len(at.exception),0)

    def test_report_planned_preview_exact_normalized_query(self):
        req=request()
        with patch('app.research_conversation.load_capability_catalog',return_value=CapabilityCatalog()), \
             patch('ai.conversation_state.LazySemanticParser.parse',side_effect=Parser(req).parse), \
             patch('ai.research_assistant.execute_plan') as execute:
            at=self.page('Research_Report')
            at.chat_input[0].set_value(req.question.raw_text).run()
            self.assertEqual(len(at.exception),0,[e.value for e in at.exception])
            self.assertIn('Planned — not activated',self.messages(at))
            self.assertIn('not yet activated',self.messages(at))
            preview=at.dataframe[0].value
            self.assertEqual(preview.loc[preview.Field=='Fixed sex','Interpretation'].iloc[0],'Female')
            self.assertEqual(preview.loc[preview.Field=='Observation year(s)','Interpretation'].iloc[0],'2019')
            self.assertTrue(any('catalog resolution pending' in s for s in preview.Status))
            self.assertIsNone(at.session_state['research_report_report'])
            execute.assert_not_called()

    def test_report_unsupported_and_infrastructure_are_distinct(self):
        with patch('app.research_conversation.load_capability_catalog',return_value=CapabilityCatalog()), \
             patch('ai.conversation_state.LazySemanticParser.parse',side_effect=Parser(request('Forecast stroke to 2035.')).parse):
            at=self.page('Research_Report')
            at.chat_input[0].set_value('Forecast stroke to 2035.').run()
            self.assertIn('Unsupported analysis',self.messages(at))
        with patch('app.research_conversation.load_capability_catalog',return_value=CapabilityCatalog()), \
             patch('ai.conversation_state.LazySemanticParser.parse',side_effect=OSError('private path')):
            at=self.page('Research_Report')
            at.chat_input[0].set_value('Show stroke in Milwaukee County.').run()
            text=self.messages(at)
            self.assertIn('Infrastructure error',text)
            self.assertIn('cannot determine scientific data availability',text)
            self.assertNotIn('private path',text)
            self.assertEqual(len(at.exception),0)

    def test_report_stale_state_clears_old_exchange(self):
        with patch('app.research_conversation.load_capability_catalog',return_value=CapabilityCatalog()), \
             patch('ai.conversation_state.LazySemanticParser.parse',side_effect=Parser(request()).parse):
            at=self.page('Research_Report')
            at.chat_input[0].set_value(request().question.raw_text).run()
            state=at.session_state['research_conversation_state']
            at.session_state['research_conversation_state']=replace(state,created_at=0)
            at.run()
            self.assertIsNone(at.session_state['research_conversation_state'])
            self.assertEqual(len(at.chat_message),0)
            self.assertIn('session expired',self.messages(at))

    def test_capability_question_aliases_no_live_api_needed(self):
        for text in ('What health conditions do you cover?','What years do you have?','Do you have breast cancer data?'):
            result=submit_research_turn(text,state=None,catalog=CapabilityCatalog(),telemetry_context=None)
            self.assertEqual(result.outcome.status,'capability_summary')

    def test_ui_contains_no_fixture_or_execution_escape_controls(self):
        for path in [ROOT/'app/pages'/f'{name}.py' for name in ('CDC_PLACES','Rural_Health','Research_Report')]+[ROOT/'app/research_conversation.py']:
            tree=ast.parse(path.read_text(encoding='utf-8-sig'))
            text=path.read_text(encoding='utf-8-sig')
            self.assertNotIn('FixtureIntegrationContext',text)
            self.assertNotIn('fixture_context=',text)
            self.assertNotIn('allow_execution',text)
            self.assertNotIn('execute_plan(',text)
            self.assertNotIn('run_query(',text)
            self.assertFalse(any(isinstance(n,ast.keyword) and n.arg=='fixture_context' for n in ast.walk(tree)))

    def test_preview_identity_tamper_fails_closed(self):
        # Exercise Phase 5 exact-query identity projection on its marked fixture,
        # without exposing fixture controls to any page or public controller.
        from scripts.utilities.check_multidimensional_semantic import MultidimensionalSemanticChecks
        helper=MultidimensionalSemanticChecks('test_seven_positive_structured_parses_and_guarded_full_pipeline')
        helper.setUp(); self.addCleanup(helper.doCleanups)
        outcome,_,_=helper.run_case()
        rows=interpreted_preview(outcome)
        self.assertIn('Fixed sex',[r.field for r in rows])
        outcome.resolved_plan.resolved_context['interpreted_query']['query_digest']='tampered'
        with self.assertRaises(ValueError): interpreted_preview(outcome)

    def test_legacy_unknown_attribution_prose_is_not_published(self):
        self.assertFalse(narrative_is_safe('High-BMI-attributable YLL rate'))
        self.assertFalse(narrative_is_safe('YLL rate per 100,000'))
        self.assertTrue(narrative_is_safe('YLL rate; attribution and unit scale unknown.'))

    def test_report_missing_year_followup_uses_same_state(self):
        req=request('Compare women ages 40-44 and 60-64 for stroke.',year=None)
        with patch('app.research_conversation.load_capability_catalog',return_value=CapabilityCatalog()), \
             patch('ai.conversation_state.LazySemanticParser.parse',side_effect=Parser(req).parse), \
             patch('ai.research_assistant.execute_plan') as execute:
            at=self.page('Research_Report')
            at.chat_input[0].set_value(req.question.raw_text).run()
            self.assertIn('Which observation year',self.messages(at))
            at.chat_input[0].set_value('2019').run()
            self.assertIn('Planned — not activated',self.messages(at))
            self.assertEqual(len(at.chat_message),2)
            execute.assert_not_called()

    def test_catalog_revision_invalidates_ui_intent(self):
        with patch('app.research_conversation.load_capability_catalog',return_value=CapabilityCatalog()) as loader, \
             patch('ai.conversation_state.LazySemanticParser.parse',side_effect=Parser(request()).parse):
            at=self.page('Research_Report')
            at.chat_input[0].set_value(request().question.raw_text).run()
            loader.return_value=CapabilityCatalog(resolution_fingerprint='different-county-catalog')
            at.run()
            self.assertIsNone(at.session_state['research_conversation_state'])
            self.assertIsNone(at.session_state['research_latest_turn'])
            self.assertIsNone(at.session_state['research_report_evidence'])

    def test_detailed_rurality_uses_description_not_required_codes(self):
        measure=next(m for m in catalog.places_measures() if m.measure_id=='DIABETES')
        with patch('app.data_access.get_places_rucc_comparison',return_value=pd.DataFrame()) as run:
            controller.rural_summary(measure,2019,detailed=True)
            run.assert_called_once_with('DIABETES',2019)
        at=self.page('Rural_Health')
        self.assertIn('Detailed rurality categories',at.selectbox[0].options)

    def test_pair_without_eligible_year_keeps_execution_disabled(self):
        self.write('DELETE FROM ihme.burden')
        at=self.page('Rural_Health')
        at.selectbox[0].select('PLACES + IHME rurality comparison').run()
        at.selectbox[1].select(at.selectbox[1].options[0]).run()
        self.assertEqual(at.selectbox[2].options,[])
        self.assertTrue(at.button[0].disabled)
        self.assertIn('no matched year',self.messages(at))

    def test_unsafe_legacy_report_export_is_withheld_in_ui(self):
        from types import SimpleNamespace
        from ai.models import EvidenceBundle, EvidenceItem, ResearchAssistantOutcome, RequestPolicyResult, RequestPolicyDecision
        from ai.conversation_state import ResearchTurn
        req=request('Stroke in Milwaukee County in 2019.',multidimensional=None)
        evidence=EvidenceBundle(req.question,req.intent,[EvidenceItem('table','High-BMI-attributable YLL evidence',pd.DataFrame({'yll_rate':[1.0]}),'get_county_cause_record',{},'High-BMI-attributable findings')],context={'evidence_domain':'IHME'})
        outcome=ResearchAssistantOutcome('answer',req,RequestPolicyResult(req,RequestPolicyDecision.EXECUTE,'fixture presentation'),evidence_bundle=evidence)
        turn=ResearchTurn(outcome,None,None)
        report=SimpleNamespace(title='Test report',executive_summary='YLL evidence',methods='High-BMI-attributable YLL rate',findings=[],limitations=[])
        with patch('app.research_conversation.load_capability_catalog',return_value=CapabilityCatalog()), \
             patch('app.research_conversation.run_research_turn',return_value=turn), \
             patch('ai.report_writer.write_research_report',return_value=report):
            at=self.page('Research_Report')
            at.chat_input[0].set_value(req.question.raw_text).run()
            self.assertEqual(len(at.exception),0,[e.value for e in at.exception])
            self.assertIn('Narrative/export presentation is withheld',self.messages(at))
            self.assertNotIn('High-BMI-attributable',self.messages(at))
            self.assertEqual(len(at.get('download_button')),0)
            self.assertIsNone(at.session_state['research_report_report'])

    def test_all_planned_capabilities_still_disabled(self):
        for key in ('sex_age','sex_rurality','age_rurality'):
            self.assertIs(CAPABILITIES[key].state,CapabilityState.PLANNED)
            self.assertFalse(CAPABILITIES[key].executable)


if __name__=='__main__':
    unittest.main(verbosity=2)
