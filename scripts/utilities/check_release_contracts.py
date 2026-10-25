"""Offline publication, provenance/privacy, history and capability-truth gate."""
from pathlib import Path
import json
import re
import subprocess
import sys
import tomllib
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from ai.capabilities import CAPABILITIES, CapabilityState, Surface
from ai.release_readiness import classify_release, capability_markdown, NOT_READY, READY_DISABLED, REQUIRED_RELEASE_GATES


def secret_findings():
    # Return locations/type only; never print matching secret material.
    files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    patterns={'aws_credential':r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
              'openai_credential':r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}',
              'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'}
    findings=[]
    for name in files:
        path=ROOT/name
        if path.suffix.lower() not in {'.py','.md','.toml','.sql','.txt','.yml','.yaml','.json','.sh','.ps1'} or not path.is_file(): continue
        text=path.read_text(errors='replace')
        for kind,pattern in patterns.items():
            if re.search(pattern,text): findings.append((name,kind))
    return findings


class ReleaseContractChecks(unittest.TestCase):
    def test_scoped_secret_scan_no_values_logged(self):
        self.assertEqual(secret_findings(),[])

    def test_approved_history_unchanged(self):
        chain=('7109ae7f7aabcdbf0a7cb14bdffbae9281983b88','b99e3668bb0c61105d8110a29b49bd48e4a5a0ed',
               'ae9cfca057e7d6cdb161a29a8fc7e3c685f16fa8','fea981e6239f3172bd0ecdf51f6a846c1860664d')
        for parent,child in zip(chain,chain[1:]):
            self.assertEqual(subprocess.check_output(['git','rev-parse',child+'^'],cwd=ROOT,text=True).strip(),parent)
        self.assertEqual(subprocess.run(['git','merge-base','--is-ancestor',chain[-1],'HEAD'],cwd=ROOT).returncode,0)

    def test_capability_document_exact_registry_projection(self):
        self.assertEqual((ROOT/'docs/V1.3_Capability_Status.md').read_text(),capability_markdown())
        for key in ('sex_age','sex_rurality','age_rurality'):
            cap=CAPABILITIES[key]
            self.assertIs(cap.state,CapabilityState.PLANNED)
            self.assertEqual(cap.surfaces,())
            self.assertEqual(cap.functions,())
        from ai.multidimensional_request import SemanticCapabilityDecision
        self.assertFalse(SemanticCapabilityDecision('sex_age','planned_non_executable','activation_pending','not_checked').executable)

    def test_blocked_gate_never_release_ready(self):
        self.assertEqual(classify_release([],{}),NOT_READY)
        self.assertEqual(classify_release([{'status':'BLOCKED'}],{}),NOT_READY)
        self.assertEqual(classify_release([{'status':'FAIL'}],{}),NOT_READY)
        self.assertEqual(classify_release([{'gate':'only-one-gate','status':'PASS'}],{}),NOT_READY)
        self.assertEqual(classify_release([{'gate':name,'status':'PASS'} for name in REQUIRED_RELEASE_GATES],{}),READY_DISABLED)

    def test_fixture_result_never_full_release_ready(self):
        activation={'capabilities':{k:{'data_gate_ready':False} for k in ('sex_age','sex_rurality','age_rurality')}}
        self.assertEqual(classify_release([{'gate':name,'status':'PASS'} for name in REQUIRED_RELEASE_GATES],activation),READY_DISABLED)

    def test_unknown_attribution_public_labels_and_stack_traces(self):
        for path in (ROOT/'app/pages').glob('*.py'):
            self.assertNotRegex(path.read_text(encoding='utf-8-sig'),r'(?i)high.bmi.attribut')
        config=tomllib.loads((ROOT/'.streamlit/config.toml').read_text())
        self.assertEqual(config['client']['showErrorDetails'],'none')
        text=(ROOT/'app/pages/Research_Report.py').read_text()
        self.assertNotIn('{exc}',text)
        self.assertNotIn('str(exc)',text)
        self.assertNotIn('st.write(ai_error)',text)

    def test_no_public_development_escape_or_raw_sql(self):
        import ast
        for name in ('CDC_PLACES','Rural_Health','Research_Report'):
            text=(ROOT/'app/pages'/f'{name}.py').read_text(encoding='utf-8-sig')
            tree=ast.parse(text)
            self.assertFalse(any(isinstance(n,ast.keyword) and n.arg=='fixture_context' for n in ast.walk(tree)))
            self.assertNotIn('allow_execution',text)
            self.assertNotIn('run_query(',text)
            self.assertNotIn('execute_plan(',text)

    def test_telemetry_privacy_and_internal_traffic(self):
        from scripts.utilities.check_conversational_core import request
        from ai.models import ResearchAssistantOutcome,RequestPolicyResult,RequestPolicyDecision
        from ai.telemetry import build_research_telemetry_event
        req=request(); outcome=ResearchAssistantOutcome('planned',req,RequestPolicyResult(req,RequestPolicyDecision.PLANNED,'pending'))
        event=build_research_telemetry_event(outcome)
        self.assertNotIn(req.question.raw_text,repr(event))
        self.assertNotIn('intent_json',repr(event))
        source=(ROOT/'app/pages/Research_Report.py').read_text()
        self.assertIn('"internal_manual"',source)
        self.assertIn('"external_researcher"',source)
        self.assertIn('hmac.compare_digest',source)

    def test_explicit_warehouse_worker_rejects_writes(self):
        import tempfile
        import hashlib
        from scripts.utilities.check_multidimensional_analytics import create_fixture
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)/'explicit_source.duckdb'
            create_fixture(source)
            probe=Path(temporary)/'write_probe.py'
            probe.write_text("import duckdb\nduckdb.connect('countyhealth.duckdb').execute('DELETE FROM ihme.burden')\n")
            before=hashlib.sha256(source.read_bytes()).hexdigest()
            result=subprocess.run([sys.executable,str(ROOT/'scripts/utilities/release_gate_worker.py'),str(probe),str(source)],cwd=ROOT,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertIn(b'read-only',result.stderr.lower())
            aux=Path(temporary)/'archive.duckdb'
            create_fixture(aux)
            manifest=Path(temporary)/'aux.json'
            manifest.write_text(json.dumps({'places_2020_test.duckdb':str(aux)}))
            probe.write_text("import duckdb\nduckdb.connect('places_2020_test.duckdb').execute('DELETE FROM ihme.burden')\n")
            before=hashlib.sha256(aux.read_bytes()).hexdigest()
            result=subprocess.run([sys.executable,str(ROOT/'scripts/utilities/release_gate_worker.py'),str(probe),str(source),str(manifest)],cwd=ROOT,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(b'read-only',result.stderr.lower())
            self.assertEqual(before,hashlib.sha256(aux.read_bytes()).hexdigest())

    def test_no_analytical_state_from_display_history(self):
        source=(ROOT/'app/pages/Research_Report.py').read_text()
        self.assertIn('submit_research_turn(',source)
        self.assertNotIn('conversation_history',source)
        self.assertIn('Current researcher request (intent, not a result)',source)


if __name__=='__main__': unittest.main(verbosity=2)
