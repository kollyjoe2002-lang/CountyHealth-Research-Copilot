"""Public presentation adapter: deliberately no fixture/activation arguments."""
from ai.capability_conversation import load_capability_catalog
from ai.conversation_contracts import CapabilityCatalog
from ai.conversation_state import run_research_turn, state_is_stale
from app.research_presentation import interpreted_preview


def refresh_catalog(previous=None):
    try:
        return load_capability_catalog(), None
    except Exception:
        return previous or CapabilityCatalog(), ('Catalog refresh is unavailable because a required database/service could not be read. '
            'Scientific availability is not established. Any previous snapshot is retained only for intent continuity.')


def submit_research_turn(text, *, state, catalog, telemetry_context):
    turn = run_research_turn(text, state=state, capability_catalog=catalog, telemetry_context=telemetry_context)
    # Project/validate before displaying evidence. This does not construct a query.
    interpreted_preview(turn.outcome)
    return turn
