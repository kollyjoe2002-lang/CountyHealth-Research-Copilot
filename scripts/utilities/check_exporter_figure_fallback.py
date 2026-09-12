from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from docx import Document


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.exporter import _add_research_figure
from ai.figures import FigureGenerationError


class DummyReport:
    evidence = object()


def main() -> None:
    document = Document()
    report = DummyReport()

    with patch(
        "ai.exporter.export_evidence_figure_png",
        side_effect=FigureGenerationError(
            "Figure generation is not implemented for intent "
            "'county_cause_snapshot'."
        ),
    ):
        result = _add_research_figure(
            document,
            report,
        )

    assert result is False

    print(
        "PASS: unsupported research figure does not "
        "abort DOCX export"
    )

    print(
        "EXPORTER FIGURE FALLBACK VALIDATION: "
        "ALL CHECKS PASSED"
    )


if __name__ == "__main__":
    main()