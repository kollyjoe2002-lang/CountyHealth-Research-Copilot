"""Deterministic release classification and canonical capability documentation."""
from ai.capabilities import CAPABILITIES, REGISTRY_VERSION, Surface

RELEASE_READY='RELEASE READY'
READY_DISABLED='RELEASE READY WITH NEW MULTIDIMENSIONAL CAPABILITIES STILL DISABLED'
NOT_READY='NOT RELEASE READY'


REQUIRED_RELEASE_GATES=frozenset({
    'check_capability_registry','check_evidence_semantics','check_query_contracts',
    'check_multidimensional_analytics','check_multidimensional_semantic','check_conversational_core',
    'check_research_experience','check_activation_contracts','check_release_contracts',
    'check_semantic_full_chain','check_semantic_stress_matrix','check_semantic_parser','check_ai_entailment_judge',
    'check_v1_3_live_semantics','check_places_semantic','check_places_ihme_semantic',
    'check_places_ihme_rurality_semantic','check_places_ihme_disparity_semantic',
    'check_places_ihme_concept_compatibility','check_evidence_language_guardrails',
    'check_ai_semantic_entailment','check_places_ihme_deterministic_suite',
    'check_v1_streamlit_integration','check_v1_ui_error_states','real_data_performance',
    'compileall','git_diff_check'})


def classify_release(gates, activation, *, expected_gates=None):
    # No historical count, skipped suite, or unknown prerequisite is a pass.
    names=[r.get('gate') for r in gates]
    expected=REQUIRED_RELEASE_GATES | frozenset(expected_gates or ())
    if len(names)!=len(set(names)) or not expected.issubset(names):
        return NOT_READY
    required=[r for r in gates if r.get('release_required',True)]
    if not required or any(r['status']!='PASS' for r in required):
        return NOT_READY
    if not activation or not all(c.get('data_gate_ready') for c in activation.get('capabilities',{}).values()) or len(activation.get('capabilities',{}))!=3:
        return READY_DISABLED
    if not all(CAPABILITIES[k].executable and Surface.ASSISTANT in CAPABILITIES[k].surfaces
               for k in ('sex_age','sex_rurality','age_rurality')):
        return READY_DISABLED
    return RELEASE_READY


def capability_markdown():
    rows=['# V1.3 canonical capability status','',f'Registry version: `{REGISTRY_VERSION}`.',
          '', 'Generated from the registry. Executable denotes a code path, not a fresh real-data/live-model pass.',
          '', '| Capability | Registry state | Sources | Assistant surface |', '| --- | --- | --- | --- |']
    for key,cap in sorted(CAPABILITIES.items()):
        rows.append(f'| {key} | {cap.state.value} | '+', '.join(s.value for s in cap.sources)+f' | {"yes" if Surface.ASSISTANT in cap.surfaces else "no"} |')
    rows += ['', 'Source listings do not certify condition/year/stratum coverage. IHME attribution and rate scale remain UNKNOWN.',
             'The three multidimensional capabilities have no public fixture/development activation route.']
    return '\n'.join(rows)+'\n'
