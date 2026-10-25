"""Immutable, non-analytical conversation contracts. No results or transcripts."""
from dataclasses import dataclass
from enum import Enum


class FailureReason(str, Enum):
    DATA_UNAVAILABLE = 'DATA_UNAVAILABLE'
    YEAR_UNAVAILABLE = 'YEAR_UNAVAILABLE'
    HEALTH_CONCEPT_UNAVAILABLE = 'HEALTH_CONCEPT_UNAVAILABLE'
    DEMOGRAPHIC_COMBINATION_UNSUPPORTED = 'DEMOGRAPHIC_COMBINATION_UNSUPPORTED'
    GEOGRAPHIC_COMBINATION_UNSUPPORTED = 'GEOGRAPHIC_COMBINATION_UNSUPPORTED'
    OPERATION_UNSUPPORTED = 'OPERATION_UNSUPPORTED'
    AMBIGUOUS_COUNTY = 'AMBIGUOUS_COUNTY'
    AMBIGUOUS_HEALTH_CONCEPT = 'AMBIGUOUS_HEALTH_CONCEPT'
    AMBIGUOUS_DEMOGRAPHIC_VALUE = 'AMBIGUOUS_DEMOGRAPHIC_VALUE'
    CAPABILITY_PLANNED_NOT_ACTIVATED = 'CAPABILITY_PLANNED_NOT_ACTIVATED'
    INFRASTRUCTURE_UNAVAILABLE = 'INFRASTRUCTURE_UNAVAILABLE'
    SOURCE_REQUIRED = 'SOURCE_REQUIRED'
    YEAR_REQUIRED = 'YEAR_REQUIRED'
    INTENT_AMBIGUOUS = 'INTENT_AMBIGUOUS'
    CONTRADICTORY_FOLLOW_UP = 'CONTRADICTORY_FOLLOW_UP'
    STATE_INVALIDATED = 'STATE_INVALIDATED'


@dataclass(frozen=True)
class Alternative:
    capability_key: str
    label: str
    state: str
    sources: tuple[str, ...]
    restrictions: tuple[str, ...]
    closeness: int
    availability: str = 'not_checked'
    # No callable, executable request, or model-chosen function names.


@dataclass(frozen=True)
class ConversationResponse:
    text: str
    reason: FailureReason | None = None
    alternatives: tuple[Alternative, ...] = ()
    pending_field: str | None = None


@dataclass(frozen=True)
class CapabilityCatalog:
    """Trusted catalog snapshot, not an assertion of usable analytical coverage.

    Caller loads this from canonical source catalogs; the parser cannot supply it.
    Empty sources mean catalog availability is unknown, never absent disease data.
    """
    ihme_concepts: tuple[str, ...] = ()
    places_concepts: tuple[str, ...] = ()
    checked_sources: tuple[str, ...] = ()
    observation_years: tuple[tuple[str, tuple[int, ...]], ...] = ()
    resolution_fingerprint: str = "unknown"

    @property
    def fingerprint(self):
        from hashlib import sha256
        import json
        from dataclasses import asdict
        return sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()
