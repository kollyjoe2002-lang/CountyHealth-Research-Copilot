from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.classifier import classify_question
from ai.executor import ExecutionError, execute_plan
from ai.exporter import (
    default_report_filename,
    export_docx_bytes,
    export_markdown_bytes,
)
from ai.planner import build_analysis_plan
from ai.resolver import resolve_plan
from ai.report_writer import (
    report_to_markdown,
    write_research_report,
)
from ai.figures import (
    FigureGenerationError,
    build_evidence_figure,
)
from ai.validation import (
    QuestionValidationError,
    validate_question,
)


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Research Report",
    page_icon="🧠",
    layout="wide",
)


# ============================================================================
# HELPERS
# ============================================================================

def initialize_session_state() -> None:
    defaults = {
        "research_report_question": "",
        "research_report_classified": None,
        "research_report_plan": None,
        "research_report_evidence": None,
        "research_report_report": None,
        "research_report_error": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_results() -> None:
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
        "research_report_error"
    ] = None


def run_research_pipeline(
    question: str,
) -> None:
    clear_results()

    try:
        classified = classify_question(
            question
        )
        validate_question(
            classified
        ) 
        plan = build_analysis_plan(
            classified
        )

        resolved_plan = resolve_plan(
            classified,
            plan,
        )

        if resolved_plan.unresolved_items:
            unresolved_text = "; ".join(
                resolved_plan.unresolved_items
            )

            raise ExecutionError(
                "The research question could not be fully "
                f"resolved: {unresolved_text}"
            )

        evidence = execute_plan(
            resolved_plan
        )

        report = write_research_report(
            evidence
        )

        st.session_state[
            "research_report_classified"
        ] = classified

        st.session_state[
            "research_report_plan"
        ] = resolved_plan

        st.session_state[
            "research_report_evidence"
        ] = evidence

        st.session_state[
            "research_report_report"
        ] = report

    except Exception as exc:
        st.session_state[
            "research_report_error"
        ] = str(exc)


def display_plan() -> None:
    plan = st.session_state.get(
        "research_report_plan"
    )

    if plan is None:
        return

    st.markdown("### Analysis plan")

    st.write(
        f"**Detected intent:** "
        f"`{plan.intent.value}`"
    )

    if plan.assumptions:
        st.markdown("**Resolved assumptions**")

        for assumption in plan.assumptions:
            st.write(f"- {assumption}")

    plan_rows = []

    for step in plan.steps:
        plan_rows.append(
            {
                "Step": step.step_number,
                "Operation": step.operation,
                "Function": step.function_name,
                "Parameters": str(
                    step.parameters
                ),
                "Purpose": step.purpose,
            }
        )

    plan_dataframe = pd.DataFrame(
        plan_rows
    )

    st.dataframe(
        plan_dataframe,
        width="stretch",
        hide_index=True,
    )


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
            f"Evidence {index}: {item.title}",
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

            if item.interpretation_note:
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
        "This report was generated from validated "
        "CountyHealth Research Copilot analytics. "
        "The execution plan, source functions, parameters, "
        "and evidence tables are available below."
    )


def display_downloads() -> None:
    report = st.session_state.get(
        "research_report_report"
    )

    if report is None:
        return

    st.markdown("### Download report")

    markdown_bytes = export_markdown_bytes(
        report
    )

    docx_bytes = export_docx_bytes(
        report,
        include_evidence_tables=True,
        evidence_row_limit=20,
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
        st.download_button(
            label="Download Markdown",
            data=markdown_bytes,
            file_name=markdown_filename,
            mime="text/markdown",
            width="stretch",
        )

    with download_col_2:
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

# ============================================================================
# PAGE
# ============================================================================

initialize_session_state()

st.title(
    "AI Research Assistant"
)

st.caption(
    "Ask a supported county-level public health question. "
    "The system classifies the request, builds a transparent "
    "analysis plan, resolves validated entities, executes approved "
    "analytics, and generates an evidence-backed report."
)

st.warning(
    "This first version uses deterministic analytical rules. "
    "It does not use a generative language model."
)

st.markdown("## Ask a research question")

example_questions = [
    "Tell me about Albany County, Wyoming.",
    (
        "Show the trend in ischemic heart disease "
        "in Albany County, Wyoming from 2000 to 2019."
    ),
    (
        "Which counties had the highest diabetes "
        "YLL rates in 2019?"
    ),
    (
        "Compare diabetes burden among Black and "
        "White adults in 2019."
    ),
]

selected_example = st.selectbox(
    "Example questions",
    options=[
        "Write my own question",
        *example_questions,
    ],
)

if (
    selected_example
    != "Write my own question"
):
    current_question = (
        selected_example
    )
else:
    current_question = st.session_state.get(
        "research_report_question",
        "",
    )

question = st.text_area(
    "Research question",
    value=current_question,
    height=120,
    placeholder=(
        "Example: Tell me about Albany County, Wyoming."
    ),
)

st.session_state[
    "research_report_question"
] = question

button_col_1, button_col_2 = (
    st.columns(
        [
            3,
            1,
        ]
    )
)

with button_col_1:
    generate_clicked = st.button(
        "Generate validated report",
        type="primary",
        width="stretch",
    )

with button_col_2:
    clear_clicked = st.button(
        "Clear",
        width="stretch",
    )

if clear_clicked:
    clear_results()

    st.session_state[
        "research_report_question"
    ] = ""

    st.rerun()

if generate_clicked:
    cleaned_question = (
        question.strip()
    )

    if not cleaned_question:
        st.warning(
            "Enter a research question before generating a report."
        )
    else:
        with st.spinner(
            "Classifying, planning, resolving, "
            "executing, and generating the report..."
        ):
            run_research_pipeline(
                cleaned_question
            )

error_message = st.session_state.get(
    "research_report_error"
)

if error_message:
    st.error(
        error_message
    )

    st.info(
        "Try one of the example questions. "
        "The current deterministic version supports county profiles, "
        "single-county trends, county rankings, and demographic "
        "disparity comparisons."
    )

report = st.session_state.get(
    "research_report_report"
)

if report is not None:
    display_report()

    st.markdown("---")

    display_research_figure()

    st.markdown("---")

    inspection_tab, evidence_tab, raw_tab = (
        st.tabs(
            [
                "Analysis plan",
                "Evidence",
                "Markdown preview",
            ]
        )
    )

    with inspection_tab:
        display_plan()

    with evidence_tab:
        display_evidence()

    with raw_tab:
        st.code(
            report_to_markdown(
                report
            ),
            language="markdown",
        )

    st.markdown("---")

    display_downloads()


# ============================================================================
# METHODS NOTE
# ============================================================================

with st.expander(
    "How this research assistant works"
):
    st.markdown(
        """
### Processing pipeline

1. **Question classifier** identifies the supported analytical intent.
2. **Analysis planner** selects approved analytics operations.
3. **Entity resolver** resolves county names, causes, years, and groups.
4. **Executor** calls only approved data-access functions.
5. **Evidence interpreter** converts returned tables into findings.
6. **Report writer** creates a structured research report.
7. **Exporter** produces Markdown and DOCX files.

### Current supported question types

- County profiles
- Single-county disease-burden trends
- National county rankings
- Race, ethnicity, sex, or age-group disparity comparisons

### Important limitation

The current system is deterministic. It does not yet support unrestricted
conversation, causal inference, statistical significance testing, or every
possible phrasing of a research question.
"""
    )