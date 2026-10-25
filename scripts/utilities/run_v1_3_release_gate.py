"""Fresh complete local-gate inventory, with honest external prerequisite states.

No deployment, production access, publication, inferred data or historical passes.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from ai.activation_validation import assess_warehouse, ActivationProfile, CoverageAcceptance
from ai.release_readiness import classify_release

OFFLINE=set('''check_capability_registry check_evidence_semantics check_query_contracts
check_multidimensional_analytics check_multidimensional_semantic check_conversational_core
check_research_experience check_activation_contracts check_release_contracts
check_request_policy check_v1_2_lay_language check_ai_classifier check_ai_planner
check_feedback_store check_feedback_summary check_telemetry_summary check_telemetry_scope_filter
check_telemetry_provenance check_research_report_beta_provenance check_exporter_figure_fallback
check_report_provenance check_places_schema'''.split())
API_ONLY={'check_ai_entailment_judge','check_semantic_parser','check_v1_3_live_semantics'}
API_AND_DATA=set('''check_semantic_full_chain check_semantic_stress_matrix check_ai_full_chain_all_intents
check_ai_full_interpretation_chain check_ai_openai_interpretation check_ai_research_assistant
check_research_telemetry check_telemetry_store check_v1_streamlit_integration check_v1_ui_error_states
check_v1_acceptance_suite'''.split())
ARCHIVE_INPUTS={'check_places_county_releases','check_places_2020_import','check_geojson_match'}


def row(gate,status,reason,**extra):
    return dict(gate=gate,status=status,reason=reason,release_required=True,**extra)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--warehouse',type=Path,help='Explicit actual-development source, never auto-discovered')
    parser.add_argument('--auxiliary-databases-json',type=Path,help='Explicit archive DB name to approved local path mapping')
    parser.add_argument('--geojson',type=Path,help='Explicit approved county GeoJSON input')
    parser.add_argument('--acceptance-json',type=Path,help='Reviewed coverage acceptance, never invented by this runner')
    parser.add_argument('--logs',type=Path,required=True)
    parser.add_argument('--json-output',type=Path,required=True)
    parser.add_argument('--markdown-output',type=Path,required=True)
    args=parser.parse_args()
    args.logs.mkdir(parents=True,exist_ok=True)
    source=args.warehouse.resolve() if args.warehouse else None
    if source and not source.is_file(): parser.error('Explicit source file does not exist')
    if len({args.json_output.resolve(),args.markdown_output.resolve()})!=2:
        parser.error('Matrix JSON and Markdown destinations must differ')
    if source and source.is_relative_to(args.logs.resolve()):
        parser.error('Audit logs must not contain the supplied warehouse')
    if source and any(p.resolve()==source for p in (args.json_output,args.markdown_output)):
        parser.error('Reports may not overwrite the supplied warehouse')
    before=(source.stat().st_size,source.stat().st_mtime_ns) if source else None
    auxiliaries=json.loads(args.auxiliary_databases_json.read_text()) if args.auxiliary_databases_json else {}
    allowed_aux={f'places_{y}_test.duckdb' for y in range(2020,2026)}
    if not set(auxiliaries).issubset(allowed_aux): parser.error('Unknown auxiliary source identity')
    if any(not Path(p).is_file() for p in auxiliaries.values()): parser.error('Declared auxiliary source missing')
    if args.geojson and not args.geojson.is_file(): parser.error('Declared GeoJSON missing')
    protected=([source] if source else [])+[Path(p).resolve() for p in auxiliaries.values()]+[p.resolve() for p in (args.geojson,args.acceptance_json,args.auxiliary_databases_json) if p]
    if any(p.is_relative_to(args.logs.resolve()) or p in {args.json_output.resolve(),args.markdown_output.resolve()} for p in protected):
        parser.error('Audit outputs/logs must be separate from every supplied source or configuration input')
    credential=bool(os.getenv('OPENAI_API_KEY'))
    def invoke(path):
        name=path.stem
        reasons=[]
        if name not in OFFLINE:
            if name in API_ONLY|API_AND_DATA and not credential: reasons.append('live API credentials unavailable')
            if name not in API_ONLY and source is None: reasons.append('explicit actual development warehouse not supplied')
            if name=='check_places_county_releases' and not allowed_aux.issubset(auxiliaries):
                reasons.append('six separate release archive databases not explicitly supplied')
            if name=='check_places_2020_import' and 'places_2020_test.duckdb' not in auxiliaries:
                reasons.append('2020 release archive database not explicitly supplied')
            if name=='check_geojson_match' and args.geojson is None:
                reasons.append('county GeoJSON not explicitly supplied')
        if reasons: return row(name,'BLOCKED','; '.join(reasons),invocation='fresh prerequisite evaluation; analytical body not run')
        env=dict(os.environ,PYTHONPATH=str(ROOT))
        if name in {'check_feedback_summary','check_telemetry_scope_filter'}:
            env['EPICOUNTY_BETA_LAUNCH_UTC']='2026-09-04T00:00:00+00:00'
        command=[sys.executable,str(path)]
        if name not in OFFLINE and source:
            command=[sys.executable,str(ROOT/'scripts/utilities/release_gate_worker.py'),str(path.relative_to(ROOT)),str(source),str(args.auxiliary_databases_json.resolve()) if args.auxiliary_databases_json else '-',str(args.geojson.resolve()) if args.geojson else '-']
        tick=time.perf_counter()
        try:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
            output=result.stdout.decode(errors='replace')
            for key in ('OPENAI_API_KEY','OPENAI_ADMIN_KEY','EPICOUNTY_INTERNAL_TEST_TOKEN'):
                value=os.getenv(key)
                if value: output=output.replace(value,'[REDACTED]')
            (args.logs/(name+'.log')).write_text(output)
            state='PASS' if result.returncode==0 else 'BLOCKED' if output.strip().splitlines() and output.strip().splitlines()[-1].startswith('BLOCKED:') else 'FAIL'
            return row(name,state,'Fresh executable suite passed' if state=='PASS' else
                       'External prerequisite explicitly blocked by gate' if state=='BLOCKED' else 'Fresh suite failed; inspect private log',
                       exit_code=result.returncode,seconds=time.perf_counter()-tick)
        except subprocess.TimeoutExpired:
            return row(name,'FAIL','Gate exceeded the explicit audit time budget',seconds=time.perf_counter()-tick)
    paths=sorted((ROOT/'scripts/utilities').glob('check_*.py'))
    with ThreadPoolExecutor(max_workers=3) as pool: matrix=list(pool.map(invoke,paths))
    acceptance=CoverageAcceptance(**json.loads(args.acceptance_json.read_text())) if args.acceptance_json else None
    activation=assess_warehouse(source,profile=ActivationProfile(acceptance=acceptance))
    (args.logs/'activation.json').write_text(json.dumps(activation,indent=2,allow_nan=False)+'\n')
    activation_status=('FAIL' if any(c['status']=='FAIL' for c in activation['checks']) else
                       'PASS' if all(c['data_gate_ready'] for c in activation['capabilities'].values()) else 'BLOCKED')
    matrix.append(dict(gate='real_data_multidimensional_activation',status=activation_status,
        reason='Explicit warehouse, reviewed coverage acceptance and sampled real-data checks required; no fixture substitution',release_required=False))
    performance_measured=(source is not None and
        any(c['gate']=='streamlit_catalog_refresh' and c['status']=='PASS' for c in activation['checks']) and
        all(any(c['gate'].startswith(key+'/') and c['status']=='PASS' and 'analytic_rows_returned' in c['details']
                for c in activation['checks']) for key in activation['capabilities']))
    matrix.append(row('real_data_performance','PASS' if performance_measured else 'BLOCKED',
        'Actual query/catalog repeats measured; read-count/peak-memory limitations explicit in audit artifact' if performance_measured else
        'No valid real-data operation/catalog timing available; fixture timings are not substituted'))

    if source and before!=(source.stat().st_size,source.stat().st_mtime_ns):
        matrix.append(row('warehouse_read_only_integrity','FAIL','Supplied development source changed during audit'))
    # Compile and whitespace checks are fresh, independent of analytical inputs.
    for gate,command in (('compileall',[sys.executable,'-m','compileall','-q','ai','app','scripts']),
                         ('git_diff_check',['git','diff','--check'])):
        result=subprocess.run(command,cwd=ROOT,capture_output=True)
        matrix.append(row(gate,'PASS' if result.returncode==0 else 'FAIL','Fresh local check'))
    status=classify_release(matrix,activation,expected_gates={p.stem for p in paths})
    fingerprint=hashlib.sha256()
    files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    for name in sorted(set(files)):
        path=ROOT/name
        if path.is_file() and (path.suffix in {'.py','.sql','.toml'} or name=='requirements.txt'):
            fingerprint.update(name.encode()+b'\0'+path.read_bytes()+b'\0')
    report={'tested_code_sha256':fingerprint.hexdigest(),'classification':status,'candidate_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'credential_available':credential,'explicit_warehouse_supplied':source is not None,
        'activation':activation['capabilities'],'gates':matrix}
    args.json_output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    lines=['# V1.3 fresh validation matrix','',f'Assessment: **{status}**.',
           '', 'PASS is a fresh execution. BLOCKED is an unmet prerequisite, not a fixture-equivalent pass.',
           'Detailed logs are private local audit artifacts; no credential values are included.',
           '', '| Gate | Status | Reason |', '| --- | --- | --- |']
    lines += [f"| {r['gate']} | {r['status']} | {r['reason']} |" for r in matrix]
    counts={s:sum(r['status']==s for r in matrix) for s in ('PASS','FAIL','BLOCKED')}
    lines+=['', 'Totals: '+', '.join(f'{s}={v}' for s,v in counts.items())+'.',
            '', 'The activation row is optional for releasing with the new capabilities disabled; required legacy/model/data/performance blockers still prohibit release.']
    args.markdown_output.write_text('\n'.join(lines)+'\n')
    print(json.dumps({'classification':status,'counts':counts}))
    return 1 if counts['FAIL'] else 2 if counts['BLOCKED'] else 0


if __name__=='__main__': raise SystemExit(main())
