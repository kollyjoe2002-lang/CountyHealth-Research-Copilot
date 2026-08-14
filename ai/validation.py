from __future__ import annotations

from ai.models import (
    AnalysisIntent,
    ClassifiedQuestion,
)


SUPPORTED_FIRST_YEAR = 2000
SUPPORTED_LAST_YEAR = 2019


class QuestionValidationError(
    ValueError
):
    """
    Raised when a research question is outside the
    supported CountyHealth analytical scope.
    """


def validate_question(
    classified: ClassifiedQuestion,
) -> None:
    """
    Validate the classified question before analytical
    planning and entity resolution.
    """
    if (
        classified.intent
        is AnalysisIntent.UNKNOWN
    ):
        raise QuestionValidationError(
            "This question does not map to a supported "
            "CountyHealth analysis. Supported analyses "
            "include county profiles, disease-burden "
            "trends, county rankings, and demographic "
            "disparity comparisons."
        )

    years = (
        classified.extracted_entities.get(
            "years",
            [],
        )
    )

    if not years:
        return

    invalid_years = [
        int(year)
        for year in years
        if (
            int(year)
            < SUPPORTED_FIRST_YEAR
            or int(year)
            > SUPPORTED_LAST_YEAR
        )
    ]

    if invalid_years:
        requested = ", ".join(
            str(year)
            for year in invalid_years
        )

        raise QuestionValidationError(
            "The requested year or years "
            f"({requested}) fall outside the "
            "available CountyHealth analytical period "
            f"of {SUPPORTED_FIRST_YEAR}–"
            f"{SUPPORTED_LAST_YEAR}."
        )