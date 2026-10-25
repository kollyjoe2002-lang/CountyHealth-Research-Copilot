"""Deterministic capability descriptions and non-executing fallback proposals."""
from difflib import SequenceMatcher
import re
from ai.capabilities import CAPABILITIES, CapabilityState, Surface, Source, MEASUREMENT_YEAR_BOUNDS, APPROVED_PLACES_IHME_PAIRS
from ai.conversation_contracts import Alternative, CapabilityCatalog, ConversationResponse, FailureReason as R


def state_phrase(state):
    return {CapabilityState.LEGACY_EXECUTABLE.value: 'registered executable path',
            CapabilityState.PLANNED.value: 'planned, not activated',
            CapabilityState.UNSUPPORTED.value: 'unsupported'}[state]


def summary_topic(text):
    t = text.strip().casefold().rstrip('?.!')
    if re.fullmatch(r'(what can (you|epicounty) do|help|capabilities)', t):
        return 'capabilities'
    if re.fullmatch(r'what (diseases|conditions|health conditions) (do you cover|are available)', t):
        return 'concepts'
    if re.fullmatch(r'what years (are available|do you support|do you cover|do you have)', t):
        return 'years'
    if re.fullmatch(r'can you compare (women and men|men and women|sexes)', t):
        return 'sex'
    if re.fullmatch(r'can you compare (by rurality|rural and metro counties|rural and urban counties)', t):
        return 'rurality'
    if re.fullmatch(r'do you have breast cancer(?: data)?', t):
        return 'breast cancer'
    return None


def alternatives(request=None, *, reason=None, catalog=None, resolved_context=None):
    """Rank only canonical assistant capabilities or explicitly labelled planned entries.

    Suggestions require researcher choice and complete canonical revalidation.
    They never assert record/coverage availability and never carry execution args.
    """
    words = ((request.question.raw_text if request else '') + ' ' +
             (request.cause_name or '' if request else '')).casefold()
    dimension = 'Sex' if re.search(r'women|men|female|male|sex', words) else 'Age group' if re.search(r'age|aged', words) else None
    candidates = []
    for cap in CAPABILITIES.values():
        if cap.state is CapabilityState.UNSUPPORTED:
            continue
        if cap.executable and Surface.ASSISTANT not in cap.surfaces:
            continue
        # Never suggest an unapproved paired-source analysis for a resolved cause.
        # When the concept is unresolved, explicitly retain the pair requirement.
        context = resolved_context or {}
        cause_id = context.get('cause_id')
        if cap.approved_pair_policy and cause_id is not None and not any(
            cause_id in ids for ids in APPROVED_PLACES_IHME_PAIRS.values()
        ):
            continue
        if request and request.evidence_domain == 'PLACES' and cap.state is CapabilityState.PLANNED:
            continue
        score = 0
        if request and request.evidence_domain:
            wanted = {Source.PLACES} if request.evidence_domain == 'PLACES' else {Source.IHME, Source.PLACES} if request.evidence_domain == 'PLACES_IHME' else {Source.IHME}
            score += 4 * len(wanted.intersection(cap.sources)) - 2 * len(set(cap.sources) - wanted)
        if request and request.county_name and any(g.value == 'single_county' for g in cap.geography_modes):
            score += 6
        if dimension and dimension in cap.comparison_dimensions:
            score += 7
        if re.search(r'rural|metro', words) and 'rurality' in cap.comparison_dimensions:
            score += 9
        if re.search(r'black|white|race', words) and 'Race / ethnicity' in cap.comparison_dimensions:
            score += 8
        if cap.state is CapabilityState.PLANNED:
            score -= 2
        if reason is R.OPERATION_UNSUPPORTED and cap.operation in {'cause_trend', 'county_cause_snapshot'}:
            score += 5
        if cap.operation == 'bmi_summary' and 'bmi' not in words:
            continue
        label = cap.operation.replace('_', ' ')
        if cap.key == 'get_county_disparity_ranking':
            label = 'Single-dimension race, sex, or age comparison on its validated fixed population basis'
        if cap.key == 'sex_age':
            label = 'Age comparison within one fixed sex, or sex comparison within one fixed age'
        elif cap.key == 'sex_rurality':
            label = 'One fixed sex across RUCC groups, or sex comparison in one RUCC group'
        elif cap.key == 'age_rurality':
            label = 'One fixed age across RUCC groups, or age comparison in one RUCC group'
        candidates.append(Alternative(cap.key, label, cap.state.value,
            tuple(s.value for s in cap.sources), cap.restrictions, score))
    return tuple(sorted(candidates, key=lambda a: (-a.closeness, a.capability_key))[:3])


def capability_summary(topic, catalog=None):
    catalog = catalog or CapabilityCatalog()
    if topic == 'years':
        bounds = '; '.join(f'{s.value}: {lo}–{hi}' for s, (lo, hi) in MEASUREMENT_YEAR_BOUNDS.items())
        text = f'The registry code envelopes are {bounds}. CDC PLACES semantic requests start in 2018. These are supported limits, not proof of every condition, county, or stratum being available.'
        if catalog.observation_years:
            text += ' Catalog-observed years: ' + '; '.join(f'{s}: {", ".join(map(str, ys))}' for s, ys in catalog.observation_years) + '. Observed years do not prove complete coverage.'
    elif topic in {'concepts', 'breast cancer'}:
        parts = []
        for source, values in ((Source.IHME.value, catalog.ihme_concepts), (Source.PLACES.value, catalog.places_concepts)):
            if source in catalog.checked_sources:
                chosen = tuple(v for v in values if topic != 'breast cancer' or 'breast' in v.casefold())
                parts.append(f'{source} catalog: ' + (', '.join(chosen[:12]) if chosen else 'no matching condition in this checked catalog') + '.')
            else:
                parts.append(f'{source}: a live catalog check is required to confirm condition coverage.')
        text = ' '.join(parts) + ' A catalog listing does not establish usable county/year coverage. Breast cancer must not be substituted with PLACES CANCER.'
    elif topic == 'sex':
        cap = CAPABILITIES['get_county_disparity_ranking']
        text = f'The registry lists a single-dimension sex comparison as {state_phrase(cap.state.value)}, using its fixed Total race and standardized age basis. A comparison within a specified age or rurality group is planned and not activated. Record availability still requires validation.'
    elif topic == 'rurality':
        cap = CAPABILITIES['get_places_ihme_rurality_comparison']
        text = f'The registry lists approved PLACES–IHME rurality comparisons as {state_phrase(cap.state.value)}. RUCC is a fixed 2023 geographic classification, not historical rural-status change. Fixed-sex or fixed-age rurality analyses are planned and not activated. Source-specific records and approved concept pairs must be checked.'
    else:
        live = sorted(c.operation.replace('_', ' ') for c in CAPABILITIES.values() if c.executable and Surface.ASSISTANT in c.surfaces)
        planned = sorted(c.key.replace('_', ' × ') for c in CAPABILITIES.values() if c.state is CapabilityState.PLANNED)
        text = 'Registered executable paths: ' + '; '.join(live) + '. Planned, not activated: ' + '; '.join(planned) + '. Forecasts, causal inference, PLACES subgroup prevalence, and unvalidated demographic intersections are unsupported. Execution requires working infrastructure and catalog/availability checks.'
    return ConversationResponse(text + ' Which analysis or condition would you like to explore?')


def failure_reason(outcome):
    """Compatibility adapter for legacy text reasons; structured codes take precedence.

    Exceptions are handled separately as infrastructure errors, never mapped to
    scientific absence. Unclassified legacy messages remain intent ambiguity.
    """
    if outcome.failure_reason:
        return outcome.failure_reason
    if outcome.status == 'planned':
        return R.CAPABILITY_PLANNED_NOT_ACTIVATED
    text = ' '.join(filter(None, [outcome.rejection_reason, outcome.clarification_question,
                                 outcome.policy_result.reason])).casefold()
    if 'year' in text and any(x in text for x in ('outside', 'supported', 'between', 'range', 'unavailable')):
        return R.YEAR_UNAVAILABLE
    if outcome.status == 'unavailable':
        return R.DATA_UNAVAILABLE
    if 'county' in text and ('ambiguous' in text or 'state' in text or 'which county' in text):
        return R.AMBIGUOUS_COUNTY
    if ('cause' in text or 'concept' in text or 'disease' in text) and 'ambiguous' in text:
        return R.AMBIGUOUS_HEALTH_CONCEPT
    if 'matched to a validated' in text or 'could not be resolved safely to a cdc places measure' in text:
        return R.HEALTH_CONCEPT_UNAVAILABLE
    if any(x in text for x in ('not validated', 'intersections', 'demographic prevalence', 'population fields', 'changing dimension', 'changing demographic', 'comparison dimension', 'fixed filter conflicts', 'demographic combinations')):
        return R.DEMOGRAPHIC_COMBINATION_UNSUPPORTED
    if any(x in text for x in ('geograph', 'rucc grouping', 'rurality filter')) and outcome.status == 'reject':
        return R.GEOGRAPHIC_COMBINATION_UNSUPPORTED
    if outcome.status == 'reject':
        return R.OPERATION_UNSUPPORTED
    if any(x in text for x in ('demographic', 'population', 'age group', 'age label', 'sex value', 'sex label')):
        return R.AMBIGUOUS_DEMOGRAPHIC_VALUE
    return R.INTENT_AMBIGUOUS


def fallback(outcome, catalog=None):
    reason = failure_reason(outcome)
    request = outcome.semantic_request
    # Describe only typed intent, never echo untrusted prose or model results.
    parts = []
    if request.cause_name:
        parts.append('the requested health condition')
    md = request.multidimensional
    if md:
        if md.fixed_sex:
            population = {'female': 'specifically among women', 'women': 'specifically among women',
                          'male': 'specifically among men', 'men': 'specifically among men',
                          'both sexes': 'among both sexes'}.get(md.fixed_sex.casefold(), 'within the specified sex')
            parts.append(population)
        if md.fixed_age:
            parts.append('within the specified age group')
        if md.comparison_dimension:
            parts.append('comparing ' + {'sex':'sexes', 'age':'age groups', 'race_ethnicity':'race/ethnicity groups'}.get(md.comparison_dimension, 'population groups'))
        if md.rurality_grouping or md.operation == 'summarize_by_rurality':
            parts.append('across or within rurality groups')
    if request.county_name:
        parts.append('in the requested county')
    acknowledge = 'I understand you want to analyze ' + (', '.join(parts) if parts else 'the specified research question') + '. '
    explanations = {
        R.CAPABILITY_PLANNED_NOT_ACTIVATED: 'EpiCounty can represent this multidimensional analysis, but it is implemented and not yet activated against the production analytical warehouse. This is an activation limit, not a finding that the data do not exist.',
        R.HEALTH_CONCEPT_UNAVAILABLE: 'The requested condition could not be matched in the checked source catalog. This does not establish absence from every evidence source.',
        R.DATA_UNAVAILABLE: 'The requested combination was checked and the required records were not available. This does not imply source-declared suppression.',
        R.DEMOGRAPHIC_COMBINATION_UNSUPPORTED: 'This population combination is outside the validated capability envelope. Multiple changing demographic dimensions, race intersections, and sex × age × rurality cannot be executed. PLACES demographic subgroup prevalence is unsupported.',
        R.GEOGRAPHIC_COMBINATION_UNSUPPORTED: 'This geographic combination is outside the validated capability envelope.',
        R.OPERATION_UNSUPPORTED: 'This analytical operation is outside the validated capability envelope. Forecasts and causal inference cannot be executed.',
        R.AMBIGUOUS_COUNTY: 'The county is not uniquely resolved. Which state identifies the county you mean?',
        R.AMBIGUOUS_HEALTH_CONCEPT: 'The requested condition is ambiguous. Which specific health condition do you mean?',
        R.AMBIGUOUS_DEMOGRAPHIC_VALUE: 'The population description is not uniquely resolved. Please specify the sex, age group, and any fixed population filters independently.',
        R.INFRASTRUCTURE_UNAVAILABLE: 'A required API, database, or execution service could not complete the request. I cannot determine scientific data availability from this infrastructure failure.',
        R.SOURCE_REQUIRED: 'Do you want CDC PLACES prevalence, IHME burden, or both? The sources measure different outcomes; a combined analysis requires an approved concept pair and supported operation.',
        R.YEAR_REQUIRED: 'Which observation year would you like to analyze?',
        R.INTENT_AMBIGUOUS: 'I need a more specific research intent before analysis. Please identify the condition, comparison, source, geography, or year that is unresolved.',
    }
    context = outcome.resolved_plan.resolved_context if outcome.resolved_plan else {}
    options = alternatives(request, reason=reason, catalog=catalog, resolved_context=context)
    explanation = explanations.get(reason, 'Please clarify the unresolved research intent.')
    if reason is R.YEAR_UNAVAILABLE:
        from ai.request_policy import _supported_year_bounds
        bounds = MEASUREMENT_YEAR_BOUNDS[Source.IHME] if request.multidimensional else _supported_year_bounds(request)
        explanation = (f'The requested observation year is outside the applicable validated policy period, {bounds[0]}–{bounds[1]}. '
                       'I have not substituted another year. These limits do not establish complete county/condition coverage.')
    text = acknowledge + explanation
    if reason is R.HEALTH_CONCEPT_UNAVAILABLE:
        text += ' ' + capability_summary('concepts', catalog).text
        if catalog:
            nearby = nearby_concepts(request.cause_name or '', catalog)
            if nearby:
                text += ' Closest catalog labels (suggestions only): ' + '; '.join(f'{label} [{source}]' for source, label in nearby) + '.'
    if options:
        text += ' Related registered options: ' + '; '.join(f'{a.label} [{state_phrase(a.state)}; availability not checked' + ('; approved concept pair required]' if CAPABILITIES[a.capability_key].approved_pair_policy else ']') for a in options) + '.'
    text += ' Choose an option or rephrase; I will preserve your constraints and validate the full request before execution.'
    pending = {R.SOURCE_REQUIRED:'evidence_domain', R.YEAR_REQUIRED:'year', R.AMBIGUOUS_COUNTY:'county_name', R.AMBIGUOUS_HEALTH_CONCEPT:'cause_name'}.get(reason)
    return ConversationResponse(text, reason, options, pending)


def load_capability_catalog():
    """Explicit read-only canonical catalog refresh. Errors propagate to caller.

    Never invoked implicitly to answer a static capability question. An API/DB
    exception must not be replaced with an empty checked source catalog.
    """
    from app.data_access import DB_FILE
    from ai.capabilities import MULTIDIMENSIONAL_RELATIONS
    import duckdb
    import hashlib
    import json
    if not DB_FILE.is_file():
        raise FileNotFoundError('Canonical analytical warehouse is unavailable')
    connection = duckdb.connect(str(DB_FILE), read_only=True)
    try:
        connection.execute('BEGIN TRANSACTION')
        catalogs = {}
        for key in ('causes', 'sex', 'age', 'race_ethnicity', 'counties', 'rucc'):
            relation = MULTIDIMENSIONAL_RELATIONS[key]
            columns = ', '.join(relation.column(c) for c in relation.columns)
            catalogs[key] = connection.execute(f'SELECT DISTINCT {columns} FROM {relation.qualified_name} ORDER BY ALL').fetchall()
        catalogs['places'] = connection.execute('SELECT measure_id, canonical_name FROM places.measures ORDER BY measure_id').fetchall()
        catalogs['ihme_years'] = connection.execute('SELECT DISTINCT year FROM ihme.burden WHERE measure_id=4 AND metric_id=3 AND year IS NOT NULL ORDER BY year').fetchall()
        catalogs['places_years'] = connection.execute('SELECT DISTINCT measurement_year FROM places.estimates WHERE measurement_year IS NOT NULL ORDER BY measurement_year').fetchall()
    finally:
        connection.close()
    fingerprint = hashlib.sha256(json.dumps(catalogs, default=str, sort_keys=True).encode()).hexdigest()
    return CapabilityCatalog(tuple(str(row[1]) for row in catalogs['causes']),
        tuple(str(row[1]) for row in catalogs['places']), (Source.IHME.value, Source.PLACES.value),
        ((Source.IHME.value, tuple(int(r[0]) for r in catalogs['ihme_years'])),
         (Source.PLACES.value, tuple(int(r[0]) for r in catalogs['places_years']))), fingerprint)



def nearby_concepts(requested, catalog):
    """Lexical proposals from observed catalogs, never automatic cause mappings."""
    candidates = [(source, label) for source, labels in (
        (Source.IHME.value, catalog.ihme_concepts), (Source.PLACES.value, catalog.places_concepts))
        if source in catalog.checked_sources for label in labels]
    return tuple(sorted(candidates, key=lambda pair: (
        -SequenceMatcher(None, requested.casefold(), pair[1].casefold()).ratio(), pair))[:5])
