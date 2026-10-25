"""Shared helpers for prerequisite-dependent live Streamlit regression gates."""
import os
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT/'app/pages/Research_Report.py'


def require_live():
    missing = []
    if not os.getenv('OPENAI_API_KEY'):
        missing.append('live semantic-parser/entailment API credentials')
    if not (ROOT/'database/countyhealth.duckdb').is_file():
        missing.append('actual analytical warehouse')
    if missing:
        raise SystemExit('BLOCKED: ' + '; '.join(missing) + '. Offline UI fixtures do not satisfy this live gate.')


def new_app():
    app = AppTest.from_file(str(PAGE), default_timeout=300)
    app.session_state['research_report_internal_test_mode'] = True
    app.run()
    healthy(app)
    return app


def healthy(app):
    assert not app.exception, [str(e.value) for e in app.exception]


def submit(app, text):
    app.chat_input[0].set_value(text).run(timeout=300)
    healthy(app)
    return app


def text(app):
    return '\n'.join(str(v.value) for group in ('markdown','caption','info','warning','error','success') for v in app.get(group))


def reset(app):
    next(b for b in app.button if b.label=='Start a new research question').click().run()
    healthy(app)
    assert app.session_state['research_conversation_state'] is None
    assert app.session_state['research_report_evidence'] is None
    assert not app.chat_message
