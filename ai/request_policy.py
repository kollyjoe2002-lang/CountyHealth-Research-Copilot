from __future__ import annotations

from dataclasses import replace

from ai.models import (
    AnalysisIntent,
    RequestPolicyDecision,
    RequestPolicyResult,
    SemanticAnalysisRequest,
)
from ai.validation import (
    SUPPORTED_FIRST_YEAR,
    SUPPORTED_LAST_YEAR,
)


NATIONAL_SCOPE = "United States"


def _requested_years(
    request: SemanticAnalysisRequest,
) -> list[int]:
    """
    Return every explicitly supplied year in a semantic request.
    """
    years: list[int] = []

    if request.year is not None:
        years.append(
            int(request.year)
        )

    if request.start_year is not None:
        years.append(
            int(request.start_year)
        )

    if request.end_year is not None:
        years.append(
            int(request.end_year)
        )

    return years


def _reject(
    request: SemanticAnalysisRequest,
    reason: str,
) -> RequestPolicyResult:
    return RequestPolicyResult(
        request=request,
        decision=RequestPolicyDecision.REJECT,
        reason=reason,
    )


def _clarify(
    request: SemanticAnalysisRequest,
    reason: str,
    question: str,
) -> RequestPolicyResult:
    return RequestPolicyResult(
        request=request,
        decision=RequestPolicyDecision.CLARIFY,
        reason=reason,
        clarification_question=question,
    )


def _execute(
    request: SemanticAnalysisRequest,
    *,
    assumptions: list[str] | None = None,
) -> RequestPolicyResult:
    return RequestPolicyResult(
        request=request,
        decision=RequestPolicyDecision.EXECUTE,
        reason=(
            "The semantic request is supported and "
            "sufficiently specified for deterministic execution."
        ),
        assumptions=list(
            assumptions or []
        ),
    )


def apply_request_policy(
    request: SemanticAnalysisRequest,
) -> RequestPolicyResult:
    """
    Apply deterministic execution policy to a parsed semantic request.

    This function performs no analytics and does not access the
    CountyHealth database.

    Responsibilities:
    - reject unsupported analytical operations;
    - clarify genuinely missing required analytical entities;
    - apply safe, explicit defaults for optional parameters;
    - preserve an auditable list of assumptions.

    The semantic parser determines what the user appears to mean.
    This policy determines what EpiCounty is allowed to do with that
    interpretation.
    """

    # ------------------------------------------------------------
    # 1. Reject explicitly unsupported analytical operations.
    # ------------------------------------------------------------

    if request.intent is AnalysisIntent.UNKNOWN:
        if request.needs_clarification:
            clarification = (
                request.clarification_question
                or (
                    "Could you provide more detail about the "
                    "analysis you would like EpiCounty to perform?"
                )
            )

            return _clarify(
                request,
                (
                    "The analytical operation could not be "
                    "determined from the available information."
                ),
                clarification,
            )

        return _reject(
            request,
            (
                "The requested analytical operation is not supported "
                "by the current EpiCounty analytical engine."
            ),
        )

    # Cross-county long-term-change ranking is semantically recognized,
    # but deterministic aggregation is not yet implemented.
    if request.intent is AnalysisIntent.LONG_TERM_CHANGE:
        return _reject(
            request,
            (
                "Cross-county long-term-change ranking is recognized "
                "but is not yet available for validated execution."
            ),
        )

    # ------------------------------------------------------------
    # 2. Reject explicitly requested years outside the supported data
    #    period before defaults are applied.
    # ------------------------------------------------------------

    explicit_years = _requested_years(
        request
    )

    invalid_years = [
        year
        for year in explicit_years
        if (
            year < SUPPORTED_FIRST_YEAR
            or year > SUPPORTED_LAST_YEAR
        )
    ]

    if invalid_years:
        requested = ", ".join(
            str(year)
            for year in sorted(
                set(invalid_years)
            )
        )

        return _reject(
            request,
            (
                "The requested year or years "
                f"({requested}) fall outside the available "
                f"EpiCounty analytical period of "
                f"{SUPPORTED_FIRST_YEAR}-"
                f"{SUPPORTED_LAST_YEAR}."
            ),
        )

    assumptions: list[str] = []

    # ------------------------------------------------------------
    # 3. County profile
    # ------------------------------------------------------------

    if request.intent is AnalysisIntent.COUNTY_PROFILE:
        if not request.county_name:
            return _clarify(
                request,
                "A county is required for a county profile.",
                "Which county would you like EpiCounty to profile?",
            )

        normalized = request

        if normalized.year is None:
            normalized = replace(
                normalized,
                year=SUPPORTED_LAST_YEAR,
            )

            assumptions.append(
                "No year was specified; EpiCounty used the "
                f"latest available year, {SUPPORTED_LAST_YEAR}."
            )

        return _execute(
            normalized,
            assumptions=assumptions,
        )

    # ------------------------------------------------------------
    # 4. County disease-burden snapshot
    # ------------------------------------------------------------

    if request.intent is AnalysisIntent.COUNTY_CAUSE_SNAPSHOT:
        if not request.county_name:
            return _clarify(
                request,
                (
                    "A county is required for a county "
                    "disease-burden snapshot."
                ),
                "Which county would you like to analyze?",
            )

        if not request.cause_name:
            return _clarify(
                request,
                (
                    "A disease or cause is required for a county "
                    "disease-burden snapshot."
                ),
                "Which disease or cause would you like to analyze?",
            )

        normalized = request

        if normalized.year is None:
            normalized = replace(
                normalized,
                year=SUPPORTED_LAST_YEAR,
            )

            assumptions.append(
                "No year was specified; EpiCounty used the "
                f"latest available year, {SUPPORTED_LAST_YEAR}."
            )

        return _execute(
            normalized,
            assumptions=assumptions,
        )

    # ------------------------------------------------------------
    # 5. County disease trend
    # ------------------------------------------------------------

    if request.intent is AnalysisIntent.TREND_COMPARISON:
        if not request.county_name:
            return _clarify(
                request,
                "A county is required for the current trend analysis.",
                "Which county would you like to analyze?",
            )

        if not request.cause_name:
            return _clarify(
                request,
                "A disease or cause is required for trend analysis.",
                "Which disease or cause would you like to analyze?",
            )

        normalized = request

        if (
            normalized.start_year is None
            and normalized.end_year is None
        ):
            normalized = replace(
                normalized,
                start_year=SUPPORTED_FIRST_YEAR,
                end_year=SUPPORTED_LAST_YEAR,
            )

            assumptions.append(
                "No trend period was specified; EpiCounty used "
                f"the full available period, "
                f"{SUPPORTED_FIRST_YEAR}-"
                f"{SUPPORTED_LAST_YEAR}."
            )

        elif (
            normalized.start_year is not None
            and normalized.end_year is None
        ):
            normalized = replace(
                normalized,
                end_year=SUPPORTED_LAST_YEAR,
            )

            assumptions.append(
                "No ending year was specified; EpiCounty used "
                f"the latest available year, "
                f"{SUPPORTED_LAST_YEAR}."
            )

        elif (
            normalized.start_year is None
            and normalized.end_year is not None
        ):
            normalized = replace(
                normalized,
                start_year=SUPPORTED_FIRST_YEAR,
            )

            assumptions.append(
                "No starting year was specified; EpiCounty used "
                f"the earliest available year, "
                f"{SUPPORTED_FIRST_YEAR}."
            )

        if (
            normalized.start_year is not None
            and normalized.end_year is not None
            and normalized.start_year >= normalized.end_year
        ):
            return _clarify(
                normalized,
                (
                    "Trend analysis requires a starting year "
                    "earlier than the ending year."
                ),
                (
                    "What start and end years would you like "
                    "to use for the trend analysis?"
                ),
            )

        return _execute(
            normalized,
            assumptions=assumptions,
        )

    # ------------------------------------------------------------
    # 6. National county ranking
    # ------------------------------------------------------------

    if request.intent is AnalysisIntent.COUNTY_RANKING:
        if not request.cause_name:
            return _clarify(
                request,
                "A disease or cause is required for county ranking.",
                "Which disease or cause should the counties be ranked by?",
            )

        normalized = request

        if normalized.year is None:
            normalized = replace(
                normalized,
                year=SUPPORTED_LAST_YEAR,
            )

            assumptions.append(
                "No year was specified; EpiCounty used the "
                f"latest available year, {SUPPORTED_LAST_YEAR}."
            )

        if normalized.geographic_scope is None:
            normalized = replace(
                normalized,
                geographic_scope=NATIONAL_SCOPE,
            )

            assumptions.append(
                "No geographic scope was specified; EpiCounty "
                "used all supported U.S. counties."
            )

        return _execute(
            normalized,
            assumptions=assumptions,
        )

    # ------------------------------------------------------------
    # 7. Demographic disparity
    # ------------------------------------------------------------

    if request.intent is AnalysisIntent.DEMOGRAPHIC_DISPARITY:
        if not request.cause_name:
            return _clarify(
                request,
                (
                    "A disease or cause is required for a "
                    "demographic disparity comparison."
                ),
                "Which disease or cause would you like to compare?",
            )

        if not request.demographic_dimension:
            return _clarify(
                request,
                (
                    "A demographic dimension is required for a "
                    "disparity comparison."
                ),
                (
                    "Would you like to compare race/ethnicity, "
                    "sex, or age groups?"
                ),
            )

        if len(request.demographic_groups) < 2:
            return _clarify(
                request,
                (
                    "Two demographic groups are required for a "
                    "disparity comparison."
                ),
                "Which two demographic groups would you like to compare?",
            )

        normalized = request

        if normalized.year is None:
            normalized = replace(
                normalized,
                year=SUPPORTED_LAST_YEAR,
            )

            assumptions.append(
                "No year was specified; EpiCounty used the "
                f"latest available year, {SUPPORTED_LAST_YEAR}."
            )

        if normalized.geographic_scope is None:
            normalized = replace(
                normalized,
                geographic_scope=NATIONAL_SCOPE,
            )

            assumptions.append(
                "No geographic scope was specified; EpiCounty "
                "used all supported U.S. counties."
            )

        return _execute(
            normalized,
            assumptions=assumptions,
        )

    # ------------------------------------------------------------
    # 8. Fail closed for any future intent not explicitly covered.
    # ------------------------------------------------------------

    return _reject(
        request,
        (
            "No deterministic request policy has been defined "
            f"for intent '{request.intent.value}'."
        ),
    )