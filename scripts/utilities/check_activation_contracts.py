"""Offline tests of activation/provenance gate behavior, never real-data proof."""
from pathlib import Path
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch
import hashlib
import duckdb
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from ai.activation_validation import ActivationProfile, CoverageAcceptance, assess_warehouse, lineage_audit, query_cases
from ai.capabilities import CAPABILITIES, CapabilityState
from scripts.utilities.check_multidimensional_analytics import create_fixture


class ActivationContractChecks(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'structural_only.duckdb'
        create_fixture(self.path)
        con=duckdb.connect(str(self.path))
        con.execute('CREATE TABLE analytics.dim_cause(cause_id INT,cause_name VARCHAR)')
        con.execute("INSERT INTO analytics.dim_cause VALUES (494,'Stroke'),(493,'Ischemic heart disease')")
        con.execute('ALTER TABLE ihme.burden ADD COLUMN source_file VARCHAR')
        con.execute('ALTER TABLE ihme.burden ADD COLUMN imported_at TIMESTAMP')
        con.execute("UPDATE ihme.burden SET source_file='TEST_BURDEN.csv',imported_at=now()")
        con.execute('CREATE TABLE ihme.import_log(file_name VARCHAR,dataset_type VARCHAR,status VARCHAR,completed_at TIMESTAMP)')
        con.execute("INSERT INTO ihme.import_log VALUES ('TEST_BURDEN.csv','BURDEN','SUCCESS',now())")
        con.close()
        self.profile=ActivationProfile(years=(2019,),scope='structural_fixture_only')

    def edit(self,sql):
        con=duckdb.connect(str(self.path))
        try: con.execute(sql)
        finally: con.close()

    def test_no_implicit_or_missing_warehouse(self):
        for path in (None,self.path.parent/'absent.duckdb'):
            result=assess_warehouse(path)
            self.assertEqual(result['checks'][0]['status'],'BLOCKED')
            self.assertTrue(all(not c['data_gate_ready'] for c in result['capabilities'].values()))
        self.assertFalse((self.path.parent/'absent.duckdb').exists())

    def test_invalid_profile_has_no_guessed_acceptance(self):
        with self.assertRaises(ValueError): CoverageAcceptance(1,float('nan'),95,'review')
        with self.assertRaises(ValueError): CoverageAcceptance(0,95,95,'review')
        with self.assertRaises(ValueError): CoverageAcceptance(1,95,95,'')
        with self.assertRaises(ValueError): ActivationProfile(years=(2035,))
        with self.assertRaises(ValueError): ActivationProfile(ages=('40-44','60-64'))
        self.assertIsNone(ActivationProfile().acceptance)

    def test_import_linkage_never_proves_attribution_or_units(self):
        con=duckdb.connect(str(self.path),read_only=True)
        try: audit=lineage_audit(con)
        finally: con.close()
        self.assertEqual(audit['import_linkage'],'PASS')
        for key in ('attribution','unit_scale','dataset_version','source_identity'):
            self.assertEqual(audit[key],'UNKNOWN')
        self.edit("UPDATE ihme.import_log SET status='FAILED'")
        con=duckdb.connect(str(self.path),read_only=True)
        try: self.assertEqual(lineage_audit(con)['import_linkage'],'FAIL')
        finally: con.close()

    def test_fixture_marker_cannot_pass_actual_gate(self):
        self.edit("CREATE TABLE analytics.multidimensional_fixture_marker(marker VARCHAR); INSERT INTO analytics.multidimensional_fixture_marker VALUES ('synthetic_structural_fixture_only')")
        report=assess_warehouse(self.path)
        self.assertTrue(any(c['gate']=='real_data_identity' and c['status']=='FAIL' for c in report['checks']))
        self.assertFalse(any(c['data_gate_ready'] for c in report['capabilities'].values()))

    def test_real_api_queries_not_mocked_and_read_only_fixture_stays_nonactivating(self):
        before=hashlib.sha256(self.path.read_bytes()).hexdigest()
        result=assess_warehouse(self.path,profile=self.profile)
        self.assertFalse(result['public_activation_performed'])
        self.assertTrue(result['read_only_file_unchanged'])
        self.assertEqual(before,hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertFalse(any(c['data_gate_ready'] for c in result['capabilities'].values()))
        self.assertTrue(any(c['gate'].startswith('sex_age/Stroke/') and 'seconds' in c['details'] for c in result['checks']))

    def test_rural_duplicate_keys_are_capability_specific(self):
        self.complete_structural_source()
        profile=ActivationProfile(years=(2010,2019),scope='structural_fixture_only',acceptance=CoverageAcceptance(1,100,100,'STRUCTURAL ONLY'))
        self.edit('INSERT INTO geography.rucc_2023 SELECT * FROM geography.rucc_2023 LIMIT 1')
        report=assess_warehouse(self.path,profile=profile)
        self.assertEqual(report['capabilities']['sex_age']['status'],'BLOCKED')
        self.assertEqual(report['capabilities']['sex_rurality']['status'],'FAIL')
        rural=[c for c in report['checks'] if c['gate'].endswith('/rucc_key_integrity')]
        self.assertEqual(len(rural),2)
        self.assertTrue(all(c['status']=='FAIL' for c in rural))
        self.assertFalse(any(c['gate'].startswith('sex_age/rucc') for c in report['checks']))

    def test_duplicate_source_keys_fail_without_deduplication(self):
        self.edit('INSERT INTO ihme.burden SELECT * FROM ihme.burden LIMIT 1')
        report=assess_warehouse(self.path,profile=self.profile)
        self.assertTrue(any(c['details'].get('error_type')=='DuplicateAnalyticalKeyError' for c in report['checks']))

    def test_nonfinite_values_and_missing_age_are_detected(self):
        self.edit("UPDATE ihme.burden SET val='Infinity'::DOUBLE")
        report=assess_warehouse(self.path,profile=self.profile)
        self.assertTrue(any(c['status']=='FAIL' and c['gate'].startswith('sex_age/Stroke/') for c in report['checks']))
        self.assertTrue(any('unavailable requested demographic catalog label' in c['reason'] for c in report['checks']))

    def complete_structural_source(self):
        self.edit("INSERT INTO analytics.dim_age_group VALUES (180,'80 to 84')")
        self.edit('DELETE FROM ihme.burden')
        self.edit('DELETE FROM geography.rucc_2023')
        con=duckdb.connect(str(self.path))
        try:
            counties=[r[0] for r in con.execute('SELECT fips FROM analytics.vw_current_county_lookup ORDER BY fips').fetchall()]
            con.executemany('INSERT INTO geography.rucc_2023 VALUES (?,?,?)',[(f,c,2023) for f,c in zip(counties,(1,4,5,2,6,7))])
            rows=[(f,y,c,4,3,s,a,71,0.0,0.0,0.0,'TEST_BURDEN.csv')
                for f in counties for y in (2010,2019) for c in (493,494)
                for s in (11,22,33) for a in (140,160,180,138)]
            con.executemany('INSERT INTO ihme.burden(fips,year,cause_id,measure_id,metric_id,sex_id,age_group_id,race_id,val,lower,upper,source_file) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',rows)
            con.execute('UPDATE ihme.burden SET imported_at=now()')
            con.execute('CREATE SCHEMA places')
            con.execute('CREATE TABLE places.measures(measure_id VARCHAR,canonical_name VARCHAR)')
            con.execute('CREATE TABLE places.estimates(measurement_year INT)')
        finally: con.close()

    def test_complete_structural_fixture_never_becomes_real_activation(self):
        self.complete_structural_source()
        profile=ActivationProfile(years=(2010,2019),scope='structural_fixture_only',
            acceptance=CoverageAcceptance(1,100,100,'STRUCTURAL TEST ONLY; not production acceptance'))
        result=assess_warehouse(self.path,profile=profile)
        self.assertFalse(any(c['status']=='FAIL' for c in result['checks']),[c for c in result['checks'] if c['status']=='FAIL'])
        self.assertTrue(all(c['status']=='BLOCKED' and not c['data_gate_ready'] for c in result['capabilities'].values()))
        self.assertTrue(any(c['gate']=='triple_intersection_guard' and c['status']=='PASS' for c in result['checks']))
        self.assertEqual(result['semantics']['attribution'],'UNKNOWN')

    def test_explicit_readers_disallow_external_access(self):
        original=duckdb.connect
        calls=[]
        def guarded(*args,**kwargs):
            calls.append(kwargs)
            self.assertTrue(kwargs.get('read_only'))
            self.assertEqual(kwargs.get('config',{}).get('enable_external_access'),'false')
            return original(*args,**kwargs)
        with patch('duckdb.connect',side_effect=guarded):
            assess_warehouse(self.path,profile=self.profile)
        self.assertTrue(calls)

    def test_catalog_and_legacy_reader_connection_policy_matches(self):
        self.complete_structural_source()
        from ai.capability_conversation import load_capability_catalog_path
        from app import data_access
        con=duckdb.connect(str(self.path),read_only=True,config={'enable_external_access':'false'})
        try:
            with patch('app.data_access.DB_FILE',self.path):
                self.assertEqual(data_access.run_query('SELECT 1 AS value').iloc[0]['value'],1)
            self.assertTrue(load_capability_catalog_path(self.path).fingerprint)
        finally: con.close()

    def test_both_orientations_and_rural_basis(self):
        cases=list(query_cases(494,'Stroke',ActivationProfile()))
        self.assertTrue(any(q.comparison and q.comparison.dimension.value=='sex' and q.stratum.age.value=='60-64' for _,q in cases))
        self.assertTrue(any(q.comparison and q.comparison.dimension.value=='age' and q.stratum.sex.value=='Female' for _,q in cases))
        for _,q in cases:
            if q.capability_key=='age_rurality':
                self.assertEqual(q.stratum.sex.state.value,'total_population')
                self.assertEqual(q.stratum.race_ethnicity.state.value,'total_population')
                self.assertEqual(q.geography.classification_year,2023)
        for key in ('sex_age','sex_rurality','age_rurality'):
            self.assertIs(CAPABILITIES[key].state,CapabilityState.PLANNED)


if __name__=='__main__': unittest.main(verbosity=2)
