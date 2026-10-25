"""Pure presentation contracts. No classification, resolution, SQL or analytics."""
from dataclasses import dataclass
from ai.capabilities import REGISTRY_VERSION, CAPABILITIES, DIMENSION_RULES, Source
from ai.conversation_contracts import FailureReason
from ai.multidimensional_integration import query_preview, validate_plan_identity, wire


@dataclass(frozen=True)
class PreviewRow:
    field: str
    interpretation: str
    status: str


def population_text(value):
    if not value or value.get('state') == 'unspecified':
        return 'Unspecified'
    if value['state'] == 'unavailable':
        return 'Unavailable: ' + str(value.get('requested_value') or value.get('unavailable_reason') or '')
    if value['state'] == 'total_population':
        return 'Both sexes' if value['dimension'] == 'sex' else 'Total population'
    return str(value['value'])


def interpreted_preview(outcome):
    """Project the canonical plan/preview; never rebuild a query from UI fields."""
    if outcome is None:
        return ()
    rows = []
    def add(label, value, status):
        if value is not None and value != '' and value != []:
            rows.append(PreviewRow(label, str(value), status))
    plan = outcome.resolved_plan
    context = plan.resolved_context if plan else {}
    if context.get('multidimensional'):
        query = context.get('resolved_query')
        preview = context['interpreted_query']
        if query is not None:
            if preview != query_preview(query):
                raise ValueError('Canonical preview/query mismatch')
            if plan.steps:
                validate_plan_identity(plan)
            data = preview['query']
            status = 'Resolved; activation/availability still required'
            add('Health concept', ', '.join(c['name'] for c in data['concepts']), status)
            add('Sources', ', '.join(preview['required_sources']), status)
            years = data['time']['sources'][0]['years']
        else:
            data = preview['normalized']
            status = 'Normalized intent; catalog resolution pending'
            add('Health concept', preview.get('cause_name'), 'Requested; unresolved')
            add('County', preview.get('county_name'), 'Requested; unresolved')
            add('State', data.get('state_name'), 'Requested; unresolved')
            add('Sources', ', '.join(preview['required_sources']), 'Required sources')
            years = data['years']
        for dimension, value in data['stratum'].items():
            if value['state'] != 'unspecified':
                add('Fixed ' + dimension.replace('_', ' '), population_text(value), status)
        comparison = data.get('comparison')
        if comparison:
            add('Comparison dimension', comparison['dimension'], status)
            add('Group A', population_text(comparison['group_a']), status)
            add('Group B', population_text(comparison['group_b']), status)
        geography = data['geography']
        add('Geography mode', geography['mode'].replace('_', ' '), status)
        add('Rurality filter', population_text(geography['rurality_filter']), status)
        if geography.get('classification_year'):
            add('Geographic lens', 'USDA RUCC 2023 (fixed classification)', status)
        # FIPS and other identifiers belong in provenance, never a name inferred here.
        add('Observation year(s)', ', '.join(map(str, years)), status)
        add('Policy assumptions/defaults', '\n'.join(data.get('assumptions', outcome.policy_result.assumptions)), 'Deterministic capability policy')
    else:
        for key, label in (('cause_name','Health concept'),('places_measure_name','PLACES health concept'),
                           ('location_name','County'),('dimension','Comparison dimension'),
                           ('group_a_name','Group A'),('group_b_name','Group B'),('year','Observation year'),
                           ('places_measurement_year','PLACES measurement year'),('ihme_year','IHME observation year')):
            add(label, context.get(key), 'Resolved by canonical plan')
        # Scalar parameters are an exact projection of the execution steps.
        for parameter, label in (('start_year','Start year'), ('end_year','End year'),
                                 ('dimension','Comparison dimension')):
            values = {step.parameters[parameter] for step in plan.steps if parameter in step.parameters} if plan else set()
            if len(values) == 1:
                add(label, next(iter(values)), 'Canonical plan parameter')
        if plan:
            caps = [CAPABILITIES[step.function_name] for step in plan.steps if step.function_name in CAPABILITIES]
            modes = {g.value.replace('_', ' ') for cap in caps for g in cap.geography_modes}
            add('Geographic scope', '; '.join(sorted(modes)), 'Canonical capability geography')
            basis = {item for cap in caps for item in cap.fixed_filters}
            rule = next((rule for rule in DIMENSION_RULES if rule.name == context.get('dimension')), None)
            if rule:
                basis.update(rule.fixed_filters)
            names = {('sex_id',3): ('IHME fixed sex','Both sexes'),
                     ('race_id',1): ('IHME fixed race/ethnicity','Total'),
                     ('age_group_id',38): ('IHME age basis','20+, age standardized')}
            for item in sorted(basis):
                if item in names:
                    label, value = names[item]
                    add(label, value, 'Validated legacy capability basis')
            if any(Source.RUCC in cap.sources for cap in caps):
                add('Geographic lens', 'USDA RUCC 2023 (fixed classification)', 'Canonical capability geography')
        request = outcome.semantic_request
        if not rows:
            for label, value in (('Health concept',request.cause_name),('County',request.county_name),
                                 ('Observation year',request.year)):
                add(label, value, 'Requested; unresolved')
        if not plan and request.multidimensional:
            md = request.multidimensional
            for field, label in (('fixed_sex','Fixed sex'),('fixed_age','Fixed age'),
                                 ('fixed_race_ethnicity','Fixed race/ethnicity'),
                                 ('comparison_dimension','Comparison dimension'),
                                 ('rurality_grouping','Rurality grouping'),('rurality_filter','Rurality filter')):
                add(label, getattr(md, field), 'Requested; unresolved')
            for group, label in ((md.group_a,'Group A'),(md.group_b,'Group B')):
                if group:
                    parts = [f'{k.replace("_", " ")}: {v}' for k,v in wire(group).items() if v]
                    add(label, ', '.join(parts), 'Requested; unresolved')
        add('Sources', request.evidence_domain, 'Requested evidence domain')
        add('Policy assumptions/defaults', '\n'.join(outcome.policy_result.assumptions), 'Deterministic policy')
    return tuple(rows)


def provenance(outcome):
    if outcome is None or outcome.resolved_plan is None:
        return {'Capability registry version': REGISTRY_VERSION}
    context = outcome.resolved_plan.resolved_context
    result = {'Capability registry version': REGISTRY_VERSION}
    for key in ('fips','county_fips','cause_id','places_measure_id','year','places_measurement_year','ihme_year','group_a_id','group_b_id'):
        if context.get(key) is not None:
            result[key] = context[key]
    if any(Source.RUCC in CAPABILITIES[step.function_name].sources for step in outcome.resolved_plan.steps if step.function_name in CAPABILITIES):
        result['RUCC classification year'] = 2023
    decision = outcome.capability_decision
    if decision:
        result['Capability'] = decision.capability_key
    if context.get('multidimensional'):
        query = context.get('resolved_query')
        if query:
            result['County FIPS'] = list(query.geography.county_fips)
            result['IHME cause ID'] = query.concepts[0].concept_id
    # IDs/years are metadata, not measurements or claims of coverage.
    return result


def turn_status(turn):
    reason = turn.response.reason if turn.response else None
    if reason is FailureReason.INFRASTRUCTURE_UNAVAILABLE:
        return 'Infrastructure error'
    if reason is FailureReason.CAPABILITY_PLANNED_NOT_ACTIVATED:
        return 'Planned — not activated'
    if reason in {FailureReason.DATA_UNAVAILABLE, FailureReason.YEAR_UNAVAILABLE, FailureReason.HEALTH_CONCEPT_UNAVAILABLE}:
        return 'Data or year unavailable'
    if turn.outcome and turn.outcome.status == 'reject':
        return 'Unsupported analysis'
    if turn.outcome and turn.outcome.status == 'capability_summary':
        return 'Capability guidance'
    if turn.outcome and turn.outcome.status == 'answer':
        return 'Validated answer' if turn.outcome.interpretation_result else 'Deterministic evidence; interpretation unavailable'
    return 'Clarification needed'


def narrative_is_safe(text):
    """Do not publish legacy prose that upgrades unknown IHME semantics.

    This supplements canonical entailment; it neither edits claims nor produces
    replacement analytical language. Unsafe narratives/exports are withheld.
    """
    from ai.multidimensional_evidence import validate_language
    try:
        validate_language(text)
        return True
    except ValueError:
        return False


def report_is_safe(report):
    return all(narrative_is_safe(t) for t in (report.title, report.executive_summary,
        report.methods, *report.findings, *report.limitations))


def interpretation_is_safe(result):
    return result is not None and all(narrative_is_safe(t) for t in (
        result.direct_answer.text, *(s.text for s in result.interpretation),
        *result.limitations, *result.warnings, *result.follow_up_questions))
