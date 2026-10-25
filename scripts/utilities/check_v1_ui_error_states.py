"""Live UI failure-state gate for conversational UX; no fixture activation proof."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts.utilities.ui_live_support import require_live, new_app, submit, reset, text


def main():
    require_live()
    app=new_app()
    # Blank chat has no send action and must not produce a result.
    assert app.session_state['research_report_evidence'] is None
    for question, expected in (
        ('Show IHME stroke burden in Albany County, Wyoming in 2024.','Data or year unavailable'),
        ('Forecast IHME stroke burden in Albany County, Wyoming to 2035.','Unsupported analysis'),
        ('Estimate the causal effect of rurality on stroke in 2019.','Unsupported analysis'),
        ('Tell me the statistically significant difference between Black and White IHME diabetes rates in 2019.','Unsupported analysis'),
        ('Compare IHME stroke among women ages 40-44 and 60-64 in 2019.','Planned — not activated'),
    ):
        reset(app)
        submit(app,question)
        assert expected in text(app), text(app)
        assert app.session_state['research_report_evidence'] is None
        assert app.session_state['research_report_report'] is None
    reset(app)
    submit(app,'Show IHME stroke burden in Albany County, Wyoming in 2019.')
    assert app.session_state['research_report_evidence'] is not None
    submit(app,'2018')
    assert 'changes existing constraints' in text(app), text(app)
    assert app.session_state['research_report_evidence'] is None
    assert app.session_state['research_report_report'] is None
    reset(app)
    submit(app,'Show the IHME ischemic heart disease trend in Albany County, Wyoming from 2000 to 2019.')
    trend=app.session_state['research_latest_turn'].outcome
    assert trend.evidence_bundle is not None and trend.evidence_bundle.intent.value=='trend_comparison'
    assert trend.interpretation_result is not None, trend.ai_error
    reset(app)
    submit(app,'Which counties had the highest IHME diabetes YLL rates in 2019?')
    ranking=app.session_state['research_latest_turn'].outcome
    assert ranking.evidence_bundle is not None and ranking.evidence_bundle.intent.value=='county_ranking'
    assert ranking.interpretation_result is not None, ranking.ai_error
    assert ranking.evidence_bundle.question.raw_text!=trend.evidence_bundle.question.raw_text
    reset(app)
    print('PASS: live unavailable year, unsupported operation, planned capability, contradiction and stale-result clearing')


if __name__=='__main__':
    main()
