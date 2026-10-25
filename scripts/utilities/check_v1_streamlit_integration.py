"""Live Streamlit regression gate, migrated from the V1 one-shot form to chat.

Requires actual warehouse + API; never substitutes mocked turns or fixtures.
"""
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts.utilities.ui_live_support import require_live, new_app, submit, reset, text


def main():
    require_live()
    app=new_app()
    assert app.chat_input and not app.session_state['research_latest_turn']
    assert 'AI Research Assistant' in [t.value for t in app.title]
    submit(app,'Show IHME stroke YLL burden in Albany County, Wyoming in 2019.')
    turn=app.session_state['research_latest_turn']
    assert turn.outcome.status=='answer', text(app)
    assert app.session_state['research_report_evidence'] is not None
    assert turn.outcome.evidence_bundle.items
    # Retain the original live grounding/entailment assertions even when a
    # legacy template's attribution wording is withheld by presentation policy.
    assert turn.outcome.interpretation_input is not None
    result=turn.outcome.interpretation_result
    assert result is not None and turn.outcome.ai_error is None
    assert result.direct_answer.text.strip() and result.direct_answer.supporting_claim_ids
    assert result.interpretation

    # Legacy prose with unverified attribution may be deliberately withheld.
    if app.session_state['research_report_report'] is None:
        assert 'withheld' in text(app), text(app)
    reset(app)
    submit(app,'Show IHME stroke burden in Atlantis County, Wyoming in 2019.')
    assert app.session_state['research_report_evidence'] is None
    assert app.session_state['research_latest_turn'].outcome.status!='answer'
    reset(app)
    key=os.environ.pop('OPENAI_API_KEY')
    try:
        submit(app,'Show IHME stroke burden in Albany County, Wyoming in 2019.')
        assert 'Infrastructure error' in text(app)
        assert app.session_state['research_report_evidence'] is None
        assert 'cannot determine scientific data availability' in text(app)
    finally:
        os.environ['OPENAI_API_KEY']=key
    reset(app)
    print('PASS: live chat initialization, canonical answer, invalid county, API outage distinction and bounded reset')


if __name__=='__main__':
    main()
