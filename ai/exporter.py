from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from ai.models import ResearchReport
from ai.report_writer import report_to_markdown


class ReportExportError(RuntimeError):
    """Raised when a report cannot be exported safely."""


def safe_filename_component(
    value: str,
) -> str:
    """
    Convert text into a filesystem-safe filename component.
    """
    cleaned = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        value.strip(),
    )

    cleaned = cleaned.strip("_").lower()

    return cleaned or "countyhealth_report"


def default_report_filename(
    report: ResearchReport,
    extension: str,
) -> str:
    """
    Build a descriptive report filename.
    """
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    title = safe_filename_component(
        report.title
    )

    extension = extension.lstrip(".")

    return (
        f"{title}_{timestamp}.{extension}"
    )


def export_markdown_bytes(
    report: ResearchReport,
) -> bytes:
    """
    Export a report as UTF-8 Markdown bytes.
    """
    markdown = report_to_markdown(
        report
    )

    return markdown.encode("utf-8")


def save_markdown_report(
    report: ResearchReport,
    output_path: str | Path,
) -> Path:
    """
    Save a report as a Markdown file.
    """
    path = Path(output_path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        export_markdown_bytes(report)
    )

    return path


def _set_document_defaults(
    document: Document,
) -> None:
    """
    Apply consistent document typography and margins.
    """
    section = document.sections[0]

    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

    normal_style = document.styles["Normal"]
    normal_style.font.name = "Aptos"
    normal_style.font.size = Pt(10.5)

    for style_name, size in [
        ("Title", 20),
        ("Heading 1", 15),
        ("Heading 2", 12),
    ]:
        style = document.styles[
            style_name
        ]
        style.font.name = "Aptos"
        style.font.size = Pt(size)


def _add_report_header(
    document: Document,
    report: ResearchReport,
) -> None:
    title = document.add_heading(
        report.title,
        level=0,
    )

    title.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
    )

    subtitle = document.add_paragraph(
        "CountyHealth Research Copilot"
    )

    subtitle.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
    )

    subtitle_run = subtitle.runs[0]
    subtitle_run.bold = True
    subtitle_run.font.size = Pt(11)

    generated = document.add_paragraph(
        "Generated: "
        + datetime.now().strftime(
            "%B %d, %Y at %I:%M %p"
        )
    )

    generated.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
    )

    document.add_paragraph()


def _add_bullets(
    document: Document,
    values: list[str],
) -> None:
    for value in values:
        document.add_paragraph(
            value,
            style="List Bullet",
        )


def _clean_cell_value(
    value: Any,
) -> str:
    if value is None or pd.isna(value):
        return ""

    if isinstance(value, float):
        return f"{value:,.2f}"

    return str(value)


def _add_dataframe_table(
    document: Document,
    dataframe: pd.DataFrame,
    *,
    maximum_rows: int = 20,
) -> None:
    """
    Add a compact evidence table to the DOCX report.
    """
    if dataframe.empty:
        document.add_paragraph(
            "No records were returned."
        )
        return

    display = dataframe.head(
        maximum_rows
    ).copy()

    table = document.add_table(
        rows=1,
        cols=len(display.columns),
    )

    table.alignment = (
        WD_TABLE_ALIGNMENT.CENTER
    )

    table.style = "Table Grid"

    header_cells = table.rows[0].cells

    for index, column in enumerate(
        display.columns
    ):
        header_cells[index].text = str(
            column
        )

        for run in header_cells[
            index
        ].paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(8)

    for row in display.itertuples(
        index=False,
        name=None,
    ):
        cells = table.add_row().cells

        for index, value in enumerate(
            row
        ):
            cells[index].text = (
                _clean_cell_value(value)
            )

            for paragraph in cells[
                index
            ].paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(8)

    if len(dataframe) > maximum_rows:
        document.add_paragraph(
            f"Table displays the first "
            f"{maximum_rows:,} of "
            f"{len(dataframe):,} records."
        )


def build_docx_document(
    report: ResearchReport,
    *,
    include_evidence_tables: bool = True,
    evidence_row_limit: int = 20,
) -> Document:
    """
    Build a DOCX document from a structured research report.
    """
    document = Document()

    _set_document_defaults(
        document
    )

    _add_report_header(
        document,
        report,
    )

    document.add_heading(
        "Research Question",
        level=1,
    )

    document.add_paragraph(
        report.question
    )

    document.add_heading(
        "Executive Summary",
        level=1,
    )

    document.add_paragraph(
        report.executive_summary
    )

    document.add_heading(
        "Methods",
        level=1,
    )

    document.add_paragraph(
        report.methods
    )

    document.add_heading(
        "Key Findings",
        level=1,
    )

    _add_bullets(
        document,
        report.findings,
    )

    document.add_heading(
        "Limitations",
        level=1,
    )

    _add_bullets(
        document,
        report.limitations,
    )

    if report.evidence.warnings:
        document.add_heading(
            "Data Warnings",
            level=1,
        )

        _add_bullets(
            document,
            report.evidence.warnings,
        )

    document.add_heading(
        "Analytical Provenance",
        level=1,
    )

    document.add_paragraph(
        "This report was generated from validated "
        "CountyHealth Research Copilot analytical "
        "functions. Each evidence item records the "
        "source function and execution parameters."
    )

    for index, item in enumerate(
        report.evidence.items,
        start=1,
    ):
        document.add_heading(
            f"Evidence {index}: {item.title}",
            level=2,
        )

        document.add_paragraph(
            f"Source function: "
            f"{item.source_function}"
        )

        parameters_text = ", ".join(
            f"{key}={value}"
            for key, value in (
                item.parameters.items()
            )
        )

        document.add_paragraph(
            "Parameters: "
            + (
                parameters_text
                if parameters_text
                else "None"
            )
        )

        if item.interpretation_note:
            document.add_paragraph(
                item.interpretation_note
            )

        if (
            include_evidence_tables
            and isinstance(
                item.data,
                pd.DataFrame,
            )
        ):
            _add_dataframe_table(
                document,
                item.data,
                maximum_rows=(
                    evidence_row_limit
                ),
            )

    document.add_heading(
        "Data Source and Interpretation Note",
        level=1,
    )

    document.add_paragraph(
        "The report is based on IHME-derived "
        "county-level estimates incorporated into "
        "the local CountyHealth DuckDB warehouse. "
        "Users should consult the original IHME "
        "documentation for authoritative methodological "
        "and citation guidance."
    )

    return document


def export_docx_bytes(
    report: ResearchReport,
    *,
    include_evidence_tables: bool = True,
    evidence_row_limit: int = 20,
) -> bytes:
    """
    Export a report as DOCX bytes.
    """
    document = build_docx_document(
        report,
        include_evidence_tables=(
            include_evidence_tables
        ),
        evidence_row_limit=(
            evidence_row_limit
        ),
    )

    buffer = BytesIO()

    document.save(buffer)

    buffer.seek(0)

    return buffer.getvalue()


def save_docx_report(
    report: ResearchReport,
    output_path: str | Path,
    *,
    include_evidence_tables: bool = True,
    evidence_row_limit: int = 20,
) -> Path:
    """
    Save a structured research report as a DOCX file.
    """
    path = Path(output_path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        export_docx_bytes(
            report,
            include_evidence_tables=(
                include_evidence_tables
            ),
            evidence_row_limit=(
                evidence_row_limit
            ),
        )
    )

    return path