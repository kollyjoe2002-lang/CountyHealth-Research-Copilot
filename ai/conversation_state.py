"""Bounded intent state around the sole canonical research pipeline.

No evidence, results, model transcript, database handle, or fixture activation is
stored. Each accepted merge is parsed/typed then reruns canonical policy through
entailment. The caller supplies a current catalog snapshot to detect revisions.
"""
from dataclasses import dataclass, asdict, replace
import json
import re
from time import time
from ai.capabilities import REGISTRY_VERSION
from ai.conversation_contracts import CapabilityCatalog, ConversationResponse, FailureReason as R
from ai.models import (ResearchQuestion, SemanticAnalysisRequest, AnalysisIntent,
                       RequestPolicyResult, RequestPolicyDecision)
from ai.multidimensional_request import decode_multidimensional

MAX_TEXT = 4000
MAX_INTENT_BYTES = 8192
MAX_TURNS = 8
MAX_AGE_SECONDS = 1800


@dataclass(frozen=True)
class ResearchState:
    intent_json: str
    registry_version: str
    catalog_fingerprint: str
    created_at: float
    turns: int
    pending_field: str | None = None
    proposed_json: str | None = None

    def __post_init__(self):
        if len(self.intent_json.encode()) > MAX_INTENT_BYTES or (self.proposed_json and len(self.proposed_json.encode()) > MAX_INTENT_BYTES):
            raise ValueError('Research intent exceeds state bound')
        if not 1 <= self.turns <= MAX_TURNS:
            raise ValueError('Research turn bound exceeded')
        # Decode now; reject invalid structured state rather than carry it forward.
        restore(self.intent_json)
        if self.proposed_json:
            restore(self.proposed_json)


@dataclass(frozen=True)
class ResearchTurn:
    outcome: object | None
    response: ConversationResponse | None
    state: ResearchState | None


def snapshot(request):
    if len(request.question.raw_text) > MAX_TEXT:
        raise ValueError('Research question exceeds state bound')
    data = asdict(request)
    # Reasoning prose and confidence are not research constraints.
    data['explanation'] = ''
    data['clarification_question'] = None
    data['needs_clarification'] = False
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def restore(payload):
    data = json.loads(payload)
    data['question'] = ResearchQuestion(**data['question'])
    data['intent'] = AnalysisIntent(data['intent'])
    data['multidimensional'] = decode_multidimensional(data.get('multidimensional'))
    return SemanticAnalysisRequest(**data)


def conversation_preflight(request):
    # A conversational user can choose these instead of inheriting legacy
    # deterministic defaults. The legacy one-shot API retains its prior policy.
    reason = R.SOURCE_REQUIRED if request.evidence_domain is None else R.YEAR_REQUIRED if request.year is None and request.start_year is None and request.end_year is None else None
    if reason:
        return RequestPolicyResult(request, RequestPolicyDecision.CLARIFY,
            'An explicit conversational source/year choice is required', failure_reason=reason)
    return None


def render(request, previous, updates):
    """Retain original lexical constraints, replacing only explicit changed fields.

    Unresolved constraints and rejected operation words must survive follow-ups;
    rendering only successfully parsed fields would silently weaken the question.
    This is a bounded current intent, not concatenated conversation history.
    """
    text = previous.question.raw_text

    def substitute(old, new):
        nonlocal text
        if old is not None and str(old).casefold() in text.casefold():
            text = re.sub(re.escape(str(old)), lambda _: str(new), text, flags=re.I)
        elif new is not None:
            text += ' ' + str(new)

    for field, value in updates.items():
        old = getattr(previous, field)
        if field == 'multidimensional':
            for name, new_value in asdict(value).items():
                prior_value = getattr(old, name) if old else None
                if name in {'group_a', 'group_b'}:
                    new_group = getattr(value, name)
                    if new_group:
                        for dimension, label in asdict(new_group).items():
                            before = getattr(prior_value, dimension) if prior_value else None
                            if label is not None and before != label:
                                substitute(before, label)
                elif new_value is not None and prior_value != new_value:
                    substitute(prior_value, new_value)
        elif value != old:
            substitute(old, value)
    return ResearchQuestion(text)


class LazySemanticParser:
    def parse(self, question):
        from ai.openai_semantic_parser import OpenAISemanticParser
        return OpenAISemanticParser().parse(question)


class TurnParser:
    def __init__(self, parser, prior=None, pending=None, proposed=None):
        self.parser, self.prior, self.pending, self.proposed = parser, prior, pending, proposed
        self.proposal = None
        self.merge_conflict = False
        self.parsed_request = None

    def parse(self, question):
        self.parsed_request = self._parse(question)
        return self.parsed_request

    def _parse(self, question):
        if self.prior is None:
            return self.parser.parse(question)
        text = question.raw_text.strip()
        low = text.casefold().rstrip('.!')
        if self.proposed and low in {'confirm', 'confirm change', 'yes, change it'}:
            return restore(self.proposed)
        if re.search(r'\b(it|that|them|those|same|there)\b', low):
            self.merge_conflict = True
            return replace(self.prior, needs_clarification=True,
                clarification_question='Please name the field or population you mean; I cannot resolve that reference safely.')
        updates = {}
        disambiguating_county = False
        if re.fullmatch(r'(?:change (?:the )?year to |use )?\d{4}', low):
            updates['year'] = int(low[-4:])
        elif self.pending == 'evidence_domain' and low in {'both', 'ihme', 'cdc places', 'places', 'ihme burden', 'cdc places prevalence'}:
            updates['evidence_domain'] = 'PLACES_IHME' if low == 'both' else 'IHME' if low.startswith('ihme') else 'PLACES'
        elif self.pending == 'county_name' and re.fullmatch(r'[A-Za-z ]{2,40}', text):
            # The state answer remains a label, never a guessed FIPS/ID; canonical
            # county resolution must uniquely validate the combined name.
            updates['county_name'] = f'{self.prior.county_name or ""} ({text})'
            disambiguating_county = True
        else:
            delta = self.parser.parse(question)
            for field in ('cause_name','county_name','year','start_year','end_year','evidence_domain',
                          'geographic_scope','direction','demographic_dimension'):
                value = getattr(delta, field)
                if value is not None:
                    updates[field] = value
            if delta.demographic_groups:
                updates['demographic_groups'] = list(delta.demographic_groups)
            if delta.multidimensional:
                old = self.prior.multidimensional
                if old:
                    md_updates = {k:v for k,v in asdict(delta.multidimensional).items()
                                  if v is not None and k != 'operation'}
                    # Nested typed comparison groups must remain immutable values.
                    for k in ('group_a', 'group_b'):
                        if getattr(delta.multidimensional, k) is not None:
                            md_updates[k] = getattr(delta.multidimensional, k)
                    if delta.multidimensional.operation != 'compare_groups':
                        md_updates['operation'] = delta.multidimensional.operation
                    updates['multidimensional'] = replace(old, **md_updates)
                else:
                    updates['multidimensional'] = delta.multidimensional
            if delta.intent is not AnalysisIntent.UNKNOWN and delta.intent != self.prior.intent:
                updates['intent'] = delta.intent
            if delta.needs_clarification or not updates:
                self.merge_conflict = True
                return replace(self.prior, needs_clarification=True,
                    clarification_question='Please specify the field you want to change; the follow-up is ambiguous.')
        merged = replace(self.prior, **updates, needs_clarification=False, clarification_question=None)
        merged = replace(merged, question=render(merged, self.prior, updates))
        conflicts = [key for key, value in updates.items() if getattr(self.prior, key) not in (None, [], '') and getattr(self.prior, key) != value
                     and not (key == 'county_name' and disambiguating_county)]
        if conflicts:
            self.proposal = snapshot(merged)
            self.merge_conflict = True
            return replace(self.prior, needs_clarification=True,
                clarification_question='This changes existing constraints (' + ', '.join(conflicts) + '). Say “confirm change” or specify a correction.')
        return merged


def run_research_turn(text, *, state=None, semantic_parser=None, capability_catalog=None, now=None, **pipeline_options):
    """Conversation control only. All analytical work uses run_research_assistant.

    No alternative is executed automatically. State is caller-owned, memory-only;
    existing privacy-conscious telemetry remains the sole persistence mechanism.
    """
    from ai.research_assistant import run_research_assistant, ResearchAssistantError
    from ai.capability_conversation import summary_topic
    catalog = capability_catalog or CapabilityCatalog()
    clock = time() if now is None else now
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        return ResearchTurn(None, ConversationResponse('Please provide a research question within the supported length.', R.INTENT_AMBIGUOUS), None)
    if state and (state.registry_version != REGISTRY_VERSION or state.catalog_fingerprint != catalog.fingerprint
                  or state.turns >= MAX_TURNS or not 0 <= clock - state.created_at <= MAX_AGE_SECONDS):
        return ResearchTurn(None, ConversationResponse('The capability/catalog context changed or the bounded session expired. Please restate the full research question so it can be validated again.', R.STATE_INVALIDATED), None)
    # Descriptions do not mutate a pending research intent or require a live API.
    if summary_topic(text):
        outcome = run_research_assistant(text, capability_catalog=catalog, **pipeline_options)
        return ResearchTurn(outcome, outcome.conversation_response, state)
    prior = restore(state.intent_json) if state else None
    try:
        parser = TurnParser(semantic_parser or LazySemanticParser(), prior,
                            state.pending_field if state else None, state.proposed_json if state else None)
        outcome = run_research_assistant(text, semantic_parser=parser, capability_catalog=catalog,
                                        conversation_mode=True, **pipeline_options)
    except ResearchAssistantError:
        return ResearchTurn(None, ConversationResponse(
            'A required API, database, or execution service could not complete the request. This infrastructure failure does not tell us whether scientific data exist. Please retry when the service is available.', R.INFRASTRUCTURE_UNAVAILABLE), state)
    except Exception:
        # Includes parser construction/credentials. Do not expose credentials or
        # database internals, and never translate an exception into data absence.
        return ResearchTurn(None, ConversationResponse(
            'A required service could not complete the request. Scientific data availability is unknown. Please retry when infrastructure is available.', R.INFRASTRUCTURE_UNAVAILABLE), state)
    if parser.merge_conflict:
        # No execution should be possible for a contradictory/ambiguous merge.
        if outcome.evidence_bundle is not None:
            raise RuntimeError('Conversation clarification unexpectedly executed')
        response = ConversationResponse(outcome.semantic_request.clarification_question or 'Please clarify the follow-up.',
            R.CONTRADICTORY_FOLLOW_UP if parser.proposal else R.INTENT_AMBIGUOUS)
    else:
        response = outcome.conversation_response
    if outcome.status == "infrastructure_error" and prior and parser.parsed_request is None:
        return ResearchTurn(outcome, response, replace(state, turns=state.turns + 1))
    request = prior if parser.merge_conflict else outcome.semantic_request
    try:
        updated = ResearchState(snapshot(request), REGISTRY_VERSION, catalog.fingerprint,
            state.created_at if state else clock, state.turns + 1 if state else 1,
            response.pending_field if response else None, parser.proposal)
    except ValueError:
        return ResearchTurn(outcome, ConversationResponse(
            'This intent exceeds the bounded session size. Please restate a shorter complete research question.', R.STATE_INVALIDATED), None)
    return ResearchTurn(outcome, response, updated)
