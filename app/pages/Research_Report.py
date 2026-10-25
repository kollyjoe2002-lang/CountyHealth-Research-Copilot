from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.exporter import (
    ReportExportError,
    _data_source_note,
    default_report_filename,
    export_docx_bytes,
    export_markdown_bytes,
)

from ai.report_writer import (
    report_to_markdown,
    write_research_report,
)

from ai.figures import (
    FigureGenerationError,
    build_evidence_figure,
)

from ai.models import TelemetryContext

from app.research_conversation import refresh_catalog, submit_research_turn
from app.research_presentation import (interpreted_preview, provenance, turn_status,
    report_is_safe, interpretation_is_safe, narrative_is_safe)
from ai.conversation_state import state_is_stale
from ai.capability_conversation import capability_summary


from ai.feedback_store import (
    append_research_feedback,
    build_research_feedback,
)


# ============================================================================
# BETA CONFIGURATION
# ============================================================================

BETA_COHORT = (
    os.getenv(
        "EPICOUNTY_BETA_COHORT",
        "beta_2026_01",
    ).strip()
    or "beta_2026_01"
)

INTERNAL_TEST_TOKEN_ENV = "EPICOUNTY_INTERNAL_TEST_TOKEN"
INTERNAL_TEST_QUERY_FLAG = "admin"

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Research Report",
    page_icon="🔬",
    layout="wide",
)


# ============================================================================
# HELPERS
# ============================================================================

def initialize_session_state() -> None:
    """
    Initialize Research Assistant page state.
    """
    defaults = {
        "research_report_question": "",
        "research_conversation_state": None,
        "research_latest_turn": None,
        "research_catalog": None,
        "research_last_message": "",
        "research_report_outcome": None,
        "research_report_classified": None,
        "research_report_feedback_submitted": False,
        "research_report_plan": None,
        "research_report_evidence": None,
        "research_report_anonymous_session_id": None,
        "research_report_report": None,
        "research_report_interpretation_input": None,
        "research_report_interpretation": None,
        "research_report_ai_error": None,
        "research_report_message_type": None,
        "research_report_error": None,
        "research_report_internal_test_mode": False,
        "research_report_internal_test_error": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if st.session_state[
        "research_report_anonymous_session_id"
    ] is None:
        st.session_state[
            "research_report_anonymous_session_id"
        ] = str(uuid4())


def _query_flag_enabled(
    name: str,
) -> bool:
    """
    Return True when one supported boolean query flag is enabled.

    The admin query flag is not a credential. It only reveals the
    token-entry control. The actual credential remains server-side.
    """
    value = st.query_params.get(name)

    if isinstance(value, list):
        value = (
            value[-1]
            if value
            else ""
        )

    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def is_internal_test_session() -> bool:
    """
    Return whether this Streamlit session is explicitly marked
    as an internal EpiCounty test session.
    """
    return bool(
        st.session_state.get(
            "research_report_internal_test_mode",
            False,
        )
    )


def render_internal_test_controls() -> None:
    """
    Provide session-specific internal-test controls.

    Normal visitors never see these controls.

    A user must deliberately add ?admin=1 to the Research Report
    page and then enter the server-side internal-test token.

    The token itself is never placed in the URL.
    """
    if is_internal_test_session():
        st.sidebar.warning(
            "Internal test mode is active."
        )

        st.sidebar.caption(
            "Research requests from this browser session are "
            "tagged as internal traffic. Researcher feedback "
            "is disabled."
        )

        if st.sidebar.button(
            "Exit internal test mode",
            key="research_report_exit_internal_test",
        ):
            st.session_state[
                "research_report_internal_test_mode"
            ] = False

            st.session_state[
                "research_report_internal_test_error"
            ] = None

            st.rerun()

        return

    if not _query_flag_enabled(
        INTERNAL_TEST_QUERY_FLAG
    ):
        return

    configured_token = os.getenv(
        INTERNAL_TEST_TOKEN_ENV,
        "",
    ).strip()

    with st.sidebar.expander(
        "Internal test mode",
        expanded=True,
    ):
        if not configured_token:
            st.error(
                "Internal test mode is not configured "
                "on this server."
            )
            return

        supplied_token = st.text_input(
            "Internal test token",
            type="password",
            key="research_report_internal_test_token",
        )

        enable_clicked = st.button(
            "Enable internal test mode",
            key="research_report_enable_internal_test",
        )

        if enable_clicked:
            if (
                supplied_token
                and hmac.compare_digest(
                    supplied_token,
                    configured_token,
                )
            ):
                st.session_state[
                    "research_report_internal_test_mode"
                ] = True

                st.session_state[
                    "research_report_internal_test_error"
                ] = None

                st.rerun()

            else:
                st.session_state[
                    "research_report_internal_test_error"
                ] = (
                    "The internal test token was not accepted."
                )

        error = st.session_state.get(
            "research_report_internal_test_error"
        )

        if error:
            st.error(error)


def clear_results() -> None:
    """
    Clear all generated Research Assistant results while preserving
    the current research-question text.
    """
    st.session_state[
        "research_report_outcome"
    ] = None

    st.session_state[
        "research_report_classified"
    ] = None

    st.session_state[
        "research_report_plan"
    ] = None

    st.session_state[
        "research_report_evidence"
    ] = None

    st.session_state[
        "research_report_report"
    ] = None

    st.session_state[
        "research_report_interpretation_input"
    ] = None

    st.session_state[
        "research_report_interpretation"
    ] = None

    st.session_state[
        "research_report_ai_error"
    ] = None

    st.session_state[
        "research_report_message_type"
    ] = None

    st.session_state[
    "research_report_feedback_submitted"
    ] = False

    st.session_state[
        "research_report_error"
    ] = None


def resolve_beta_traffic_source(
    internal_test_mode: bool,
) -> str:
    """
    Resolve the telemetry traffic source for the current session.

    Internal manual testing must never be counted as genuine
    external-researcher beta traffic.
    """
    return (
        "internal_manual"
        if internal_test_mode
        else "external_researcher"
    )


def run_research_pipeline(question: str) -> None:
    """Presentation only; every submission uses the canonical bounded turn API."""
    clear_results()
    st.session_state['research_last_message'] = question
    try:
        context = TelemetryContext(environment='beta',
            traffic_source=resolve_beta_traffic_source(is_internal_test_session()),
            beta_cohort=BETA_COHORT,
            anonymous_session_id=st.session_state['research_report_anonymous_session_id'])
        turn = submit_research_turn(question, state=st.session_state['research_conversation_state'],
            catalog=st.session_state['research_catalog'], telemetry_context=context)
        st.session_state['research_latest_turn'] = turn
        st.session_state['research_conversation_state'] = turn.state
        outcome = turn.outcome
        st.session_state['research_report_outcome'] = outcome
        if outcome is None:
            return
        st.session_state['research_report_classified'] = outcome.classified_question
        st.session_state['research_report_plan'] = outcome.resolved_plan
        if outcome.status != 'answer' or outcome.evidence_bundle is None:
            return
        st.session_state['research_report_evidence'] = outcome.evidence_bundle
        report = write_research_report(outcome.evidence_bundle)
        if not report_is_safe(report):
            st.session_state['research_report_ai_error'] = 'Narrative/export presentation is withheld pending source provenance or validated interpretation. Deterministic evidence remains available.'
            return
        st.session_state['research_report_report'] = report
        st.session_state['research_report_interpretation_input'] = outcome.interpretation_input
        st.session_state['research_report_interpretation'] = outcome.interpretation_result if interpretation_is_safe(outcome.interpretation_result) else None
        st.session_state['research_report_ai_error'] = outcome.ai_error or (None if interpretation_is_safe(outcome.interpretation_result) else 'A validated narrative with verified source semantics is not available.')
    except Exception:
        # No raw resolver/API/database internals in normal conversation.
        st.session_state['research_latest_turn'] = None
        st.session_state['research_report_error'] = ('A required service could not complete this turn. '
            'This infrastructure problem does not establish absence of scientific data.')


def display_plan() -> None:
    outcome = st.session_state.get('research_report_outcome')
    if outcome is None:
        return
    rows = interpreted_preview(outcome)
    if rows:
        st.markdown('### Interpreted query')
        st.dataframe(pd.DataFrame([{'Field': row.field, 'Interpretation': row.interpretation,
            'Status': row.status} for row in rows]), hide_index=True, width='stretch')
        st.caption('Requested or normalized intent is labelled separately from catalog-resolved values. Planned capabilities remain non-executable.')
    with st.expander('Query provenance and identifiers'):
        st.json(provenance(outcome))


def display_evidence() -> None:
    evidence = st.session_state.get(
        "research_report_evidence"
    )

    if evidence is None:
        return

    st.markdown("### Evidence")

    for index, item in enumerate(
        evidence.items,
        start=1,
    ):
        with st.expander(
            f"Evidence {index}: {item.title if narrative_is_safe(item.title) else 'Canonical evidence table'}",
            expanded=(
                index == 1
            ),
        ):
            st.write(
                f"**Source function:** "
                f"`{item.source_function}`"
            )

            st.write(
                "**Parameters:**"
            )

            if item.parameters:
                st.json(
                    item.parameters
                )
            else:
                st.write(
                    "No parameters."
                )

            if item.interpretation_note and narrative_is_safe(item.interpretation_note):
                st.write(
                    f"**Purpose:** "
                    f"{item.interpretation_note}"
                )

            if isinstance(
                item.data,
                pd.DataFrame,
            ):
                st.write(
                    f"**Rows:** "
                    f"{len(item.data):,}"
                )

                st.write(
                    f"**Columns:** "
                    f"{len(item.data.columns):,}"
                )

                st.dataframe(
                    item.data.head(100),
                    width="stretch",
                    hide_index=True,
                )

                if len(item.data) > 100:
                    st.caption(
                        "Displaying the first 100 rows. "
                        "The complete data remain in the "
                        "evidence bundle."
                    )

    if evidence.warnings:
        st.markdown("#### Data warnings")

        for warning in evidence.warnings:
            st.warning(
                warning
            )


def display_report() -> None:
    report = st.session_state.get(
        "research_report_report"
    )

    if report is None:
        return

    st.markdown("---")

    st.markdown(
        f"# {report.title}"
    )

    st.markdown(
        "## Research Question"
    )

    st.write(
        report.question
    )

    st.markdown(
        "## Executive Summary"
    )

    st.info(
        report.executive_summary
    )

    st.markdown(
        "## Methods"
    )

    st.write(
        report.methods
    )

    st.markdown(
        "## Key Findings"
    )

    for finding in report.findings:
        st.write(
            f"- {finding}"
        )

    st.markdown(
        "## Limitations"
    )

    for limitation in report.limitations:
        st.write(
            f"- {limitation}"
        )

    st.markdown(
        "## Analytical Provenance"
    )

    st.write(
        _data_source_note(report)
    )

    st.caption(
        "The execution plan, source functions, parameters, "
        "and evidence tables are available below."
    )


def display_ai_interpretation() -> None:
    interpretation = st.session_state.get(
        "research_report_interpretation"
    )

    interpretation_input = st.session_state.get(
        "research_report_interpretation_input"
    )

    ai_error = st.session_state.get(
        "research_report_ai_error"
    )

    st.markdown("## AI Research Interpretation")

    if interpretation is None:
        if ai_error:
            st.warning(
                "The deterministic research report was generated "
                "successfully, but the AI interpretation did not "
                "pass the complete validation pipeline."
            )

            with st.expander(
                "Technical details"
            ):
                st.write(
                    ai_error
                )
        else:
            st.info(
                "No validated AI interpretation is available."
            )

        return

    st.success(
        "This interpretation passed structural grounding, "
        "deterministic semantic validation, and model-based "
        "semantic entailment checks."
    )

    st.markdown(
        "### Direct Answer"
    )

    st.info(
        interpretation.direct_answer.text
    )

    with st.expander(
        "Direct-answer evidence"
    ):
        for claim_id in (
            interpretation.direct_answer.supporting_claim_ids
        ):
            st.caption(
                f"Evidence ID: `{claim_id}`"
            )

            if interpretation_input is not None:
                matching_claims = [
                    claim
                    for claim in interpretation_input.claims
                    if claim.claim_id == claim_id
                ]

                for claim in matching_claims:
                    if narrative_is_safe(claim.text):
                        st.write(claim.text)
                    else:
                        st.caption("Legacy attribution/unit wording withheld pending provenance.")

    if interpretation.interpretation:
        st.markdown(
            "### Interpretation"
        )

        for index, statement in enumerate(
            interpretation.interpretation,
            start=1,
        ):
            st.write(
                f"**{index}. {statement.text}**"
            )

            with st.expander(
                f"Evidence for statement {index}"
            ):
                for claim_id in (
                    statement.supporting_claim_ids
                ):
                    st.caption(
                        f"Evidence ID: `{claim_id}`"
                    )

                    if interpretation_input is not None:
                        matching_claims = [
                            claim
                            for claim in interpretation_input.claims
                            if claim.claim_id == claim_id
                        ]

                        for claim in matching_claims:
                            if narrative_is_safe(claim.text):
                                st.write(claim.text)
                            else:
                                st.caption("Legacy attribution/unit wording withheld pending provenance.")

    if interpretation.follow_up_questions:
        st.markdown(
            "### Suggested Follow-up Questions"
        )

        for follow_up in (
            interpretation.follow_up_questions
        ):
            st.write(
                f"- {follow_up}"
            )

    if interpretation.warnings:
        st.markdown(
            "### Interpretation Warnings"
        )

        for warning in interpretation.warnings:
            st.warning(
                warning
            )


def display_downloads() -> None:
    """
    Display report download controls.

    Export failures are isolated so that one unavailable export
    format cannot crash the completed Research Report page.
    """
    report = st.session_state.get(
        "research_report_report"
    )

    if report is None:
        return

    st.markdown("### Download report")

    markdown_bytes = None
    docx_bytes = None
    markdown_error = None
    docx_error = None

    try:
        markdown_bytes = export_markdown_bytes(
            report
        )
    except Exception as exc:
        markdown_error = str(exc)

    try:
        docx_bytes = export_docx_bytes(
            report,
            include_evidence_tables=True,
            evidence_row_limit=20,
        )
    except ReportExportError as exc:
        docx_error = str(exc)
    except Exception as exc:
        docx_error = (
            f"Unexpected DOCX export failure: {exc}"
        )

    markdown_filename = (
        default_report_filename(
            report,
            "md",
        )
    )

    docx_filename = (
        default_report_filename(
            report,
            "docx",
        )
    )

    download_col_1, download_col_2 = (
        st.columns(2)
    )

    with download_col_1:
        if markdown_bytes is not None:
            st.download_button(
                label="Download Markdown",
                data=markdown_bytes,
                file_name=markdown_filename,
                mime="text/markdown",
                width="stretch",
            )
        else:
            st.warning(
                "Markdown export is temporarily unavailable."
            )

            if markdown_error:
                with st.expander(
                    "Markdown export details"
                ):
                    st.write(markdown_error)

    with download_col_2:
        if docx_bytes is not None:
            st.download_button(
                label="Download DOCX",
                data=docx_bytes,
                file_name=docx_filename,
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.wordprocessingml.document"
                ),
                width="stretch",
            )
        else:
            st.warning(
                "DOCX export is temporarily unavailable."
            )

            if docx_error:
                with st.expander(
                    "DOCX export details"
                ):
                    st.write(docx_error)

def display_research_figure() -> None:
    """
    Display the deterministic research figure generated
    from the validated evidence bundle.
    """
    evidence = st.session_state.get(
        "research_report_evidence"
    )

    if evidence is None:
        return

    st.markdown("### Research Figure")

    try:
        figure = build_evidence_figure(
            evidence
        )

        st.pyplot(
            figure,
            clear_figure=True,
            width="stretch",
        )

        st.caption(
            "Figure generated directly from validated "
            "CountyHealth Research Copilot analytical evidence."
        )

    except FigureGenerationError as exc:
        st.info(
            f"A research figure could not be generated: {exc}"
        )


def display_research_feedback_form() -> None:
    """
    Display a privacy-conscious feedback form for one completed
    external-beta result.

    Feedback collection is intentionally disabled during internal
    testing so internal validation cannot contaminate researcher
    feedback evidence.
    """
    if is_internal_test_session():
        st.info(
            "Researcher feedback is disabled during internal "
            "test sessions."
        )
        return

    outcome = st.session_state.get(
        "research_report_outcome"
    )

    anonymous_session_id = st.session_state.get(
        "research_report_anonymous_session_id"
    )

    if st.session_state.get(
        "research_report_feedback_submitted",
        False,
    ):
        st.success(
            "Thank you. Feedback has already been recorded "
            "for this result."
        )
        return

    if (
        outcome is None
        or outcome.status != "answer"
        or anonymous_session_id is None
    ):
        return

    st.markdown("### Researcher Feedback")

    st.caption(
        "Help us evaluate the EpiCounty research beta. "
        "Your raw research question is not stored with this feedback."
    )

    with st.form(
        "research_feedback_form",
        clear_on_submit=True,
    ):
        helpfulness = st.radio(
            "Was this result helpful?",
            options=[
                "Yes",
                "Partly",
                "No",
            ],
            horizontal=True,
        )

        clarity = st.radio(
            "Was the result clear?",
            options=[
                "Clear",
                "Somewhat clear",
                "Unclear",
            ],
            horizontal=True,
        )

        perceived_accuracy = st.radio(
            "How accurate did the result appear?",
            options=[
                "Accurate",
                "Unsure",
                "Inaccurate",
            ],
            horizontal=True,
        )

        optional_comment = st.text_area(
            "Optional comment",
            placeholder=(
                "What worked well, or what could be improved?"
            ),
            height=100,
        )

        submitted = st.form_submit_button(
            "Submit feedback"
        )

    if submitted:
        feedback = build_research_feedback(
            anonymous_session_id=(
                anonymous_session_id
            ),
            beta_cohort=BETA_COHORT,
            helpfulness=helpfulness,
            clarity=clarity,
            perceived_accuracy=(
                perceived_accuracy
            ),
            intent=outcome.semantic_request.intent.value,
            optional_comment=optional_comment,
        )

        try:
            append_research_feedback(
                feedback
            )

        except Exception as exc:
            st.error(
                "Feedback could not be saved. "
                f"Please try again. Technical detail: {exc}"
            )

        else:
            st.session_state[
                "research_report_feedback_submitted"
            ] = True

            st.success(
                "Thank you. Your feedback was recorded."
            )


# ============================================================================
# PAGE
# ============================================================================

initialize_session_state()
render_internal_test_controls()

st.title('AI Research Assistant')
st.caption('Ask a research question, answer a clarification, or explore EpiCounty capabilities. Only the current exchange is retained for display; research intent is bounded by the core session rules.')
if is_internal_test_session():
    st.warning('INTERNAL TEST MODE — excluded from external-beta telemetry; researcher feedback is disabled.')

catalog, catalog_warning = refresh_catalog(st.session_state['research_catalog'])
st.session_state['research_catalog'] = catalog
if catalog_warning:
    st.caption(catalog_warning)

# Reruns use the same invalidation rule as the canonical turn API. Old results
# are not displayed under an expired or changed capability/catalog context.
if state_is_stale(st.session_state['research_conversation_state'], catalog):
    clear_results()
    st.session_state['research_conversation_state'] = None
    st.session_state['research_latest_turn'] = None
    st.session_state['research_last_message'] = ''
    st.info('The research session expired or its capability/catalog context changed. Please restate the complete question.')

with st.expander('Research capability guidance'):
    st.write(capability_summary('capabilities', catalog).text)
    st.caption('Try: What health conditions do you cover? What years do you have? Can you compare women and men? Do you have breast cancer data?')

if st.button('Start a new research question'):
    clear_results()
    st.session_state['research_conversation_state'] = None
    st.session_state['research_latest_turn'] = None
    st.session_state['research_last_message'] = ''
    st.rerun()

message = st.chat_input('Ask a research question or answer the pending clarification', max_chars=4000)
if message:
    with st.spinner('Validating research intent and evidence…'):
        run_research_pipeline(message)

turn = st.session_state['research_latest_turn']
if st.session_state['research_last_message']:
    with st.chat_message('user'):
        st.write(st.session_state['research_last_message'])
if turn is not None:
    with st.chat_message('assistant'):
        status = turn_status(turn)
        if status == 'Validated answer' and not interpretation_is_safe(turn.outcome.interpretation_result):
            status = 'Deterministic evidence; narrative provenance pending'
        if status == 'Infrastructure error':
            st.error(status)
        elif status in {'Unsupported analysis', 'Data or year unavailable', 'Planned — not activated'}:
            st.warning(status)
        elif status == 'Validated answer':
            st.success(status)
        else:
            st.info(status)
        if turn.response:
            st.write(turn.response.text)
        elif turn.outcome and interpretation_is_safe(turn.outcome.interpretation_result):
            st.write(turn.outcome.interpretation_result.direct_answer.text)
        elif turn.outcome and turn.outcome.evidence_bundle:
            st.write('Deterministic evidence is available below. A validated narrative interpretation is not available.')
    display_plan()
if st.session_state['research_report_error']:
    st.error(st.session_state['research_report_error'])

if st.session_state['research_report_ai_error'] and st.session_state['research_report_report'] is None:
    st.warning(st.session_state['research_report_ai_error'])
    display_evidence()

if st.session_state['research_report_report'] is not None:
    display_report()
    display_ai_interpretation()
    display_research_figure()
    with st.expander('Analytical evidence and provenance'):
        display_evidence()
    display_downloads()
    display_research_feedback_form()

with st.expander('How this research assistant works'):
    st.write('Semantic parser → typed request → capability decision → canonical resolver → availability validation → analysis plan → allowlisted executor → deterministic analytics → evidence → grounded interpretation → entailment validation.')
    st.caption('Sex × age, sex × rurality and age × rurality remain PLANNED pending real warehouse activation. Suggestions require your choice and full revalidation. IHME attribution and unit scale remain provenance-pending. RUCC 2023 is a fixed geographic lens.')
