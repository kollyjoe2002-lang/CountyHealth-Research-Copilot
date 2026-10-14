from __future__ import annotations

import re

from ai.models import (
    AnalysisIntent,
    ClassifiedQuestion,
)


SUPPORTED_FIRST_YEAR = 2000
SUPPORTED_LAST_YEAR = 2019

PLACES_FIRST_YEAR = 2018
PLACES_LAST_YEAR = 2023

CROSS_SOURCE_FIRST_YEAR = min(
    SUPPORTED_FIRST_YEAR,
    PLACES_FIRST_YEAR,
)
CROSS_SOURCE_LAST_YEAR = max(
    SUPPORTED_LAST_YEAR,
    PLACES_LAST_YEAR,
)
RURALITY_SHARED_FIRST_YEAR = max(
    SUPPORTED_FIRST_YEAR,
    PLACES_FIRST_YEAR,
)

RURALITY_SHARED_LAST_YEAR = min(
    SUPPORTED_LAST_YEAR,
    PLACES_LAST_YEAR,
)

class QuestionValidationError(
    ValueError
):
    """
    Raised when a research question is outside the
    supported CountyHealth analytical scope.
    """


def _validate_unsupported_inference(
    classified: ClassifiedQuestion,
) -> None:
    """
    Reject requests for inferential conclusions that are not
    supported by the current V1 analytical engine.
    """
    text = (
        classified.question.raw_text
        .casefold()
    )

    unsupported_patterns = {
        (
            r"\bstatistically significant\b"
        ): (
            "statistical significance"
        ),
        (
            r"\bsignificant difference\b"
        ): (
            "statistical significance"
        ),
        (
            r"\bp[- ]?value\b"
        ): (
            "p-values"
        ),
        (
            r"\bconfidence interval\b"
        ): (
            "confidence-interval inference"
        ),
        (
            r"\bhypothesis test"
        ): (
            "hypothesis testing"
        ),
    }

    for pattern, capability in (
        unsupported_patterns.items()
    ):
        if re.search(
            pattern,
            text,
        ):
            raise QuestionValidationError(
                "The current CountyHealth V1 analytical "
                f"engine does not perform {capability}. "
                "It can provide descriptive county-level "
                "estimates and disparities, but formal "
                "inferential testing must be performed "
                "separately."
            )


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
            "EpiCounty analysis. Supported analyses include "
            "county profiles, county disease-burden snapshots, "
            "disease-burden trends, county rankings, and "
            "demographic disparity comparisons."
        )

    _validate_unsupported_inference(
        classified
    )

    years = (
        classified.extracted_entities.get(
            "years",
            [],
        )
    )

    if not years:
        return

    evidence_domain = (
        classified.extracted_entities.get(
            "evidence_domain"
        )
    )

    if evidence_domain == "PLACES":
        supported_first_year = PLACES_FIRST_YEAR
        supported_last_year = PLACES_LAST_YEAR

    elif (
        evidence_domain == "PLACES_IHME"
        and classified.intent
        is AnalysisIntent.RURALITY_COMPARISON
    ):
        supported_first_year = (
            RURALITY_SHARED_FIRST_YEAR
        )
        supported_last_year = (
            RURALITY_SHARED_LAST_YEAR
        )

    elif evidence_domain == "PLACES_IHME":
        supported_first_year = CROSS_SOURCE_FIRST_YEAR
        supported_last_year = CROSS_SOURCE_LAST_YEAR

    else:
        supported_first_year = SUPPORTED_FIRST_YEAR
        supported_last_year = SUPPORTED_LAST_YEAR

    invalid_years = [
        int(year)
        for year in years
        if (
            int(year) < supported_first_year
            or int(year) > supported_last_year
        )
    ]

    if invalid_years:
        requested = ", ".join(
            str(year)
            for year in invalid_years
        )

        raise QuestionValidationError(
            "Requested years are outside the supported range "
            f"of {supported_first_year}-{supported_last_year}: "
            f"{requested}."
        )
