from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from ai.conversation_contracts import FailureReason

from ai.models import (
    AnalysisIntent,
    AnalysisPlan,
    ClassifiedQuestion,
)
from app.data_access import (
    get_causes,
    get_counties,
    get_disparity_causes,
    get_disparity_groups,
    run_query,
)


class ResolutionError(ValueError):
    """Raised when an analytical entity cannot be resolved safely."""

    def __init__(self, message, *, reason=None):
        super().__init__(message)
        from ai.conversation_contracts import FailureReason as R
        text = message.casefold()
        if reason is None:
            if 'lookup' in text and ('no records' in text or 'missing required' in text):
                reason = R.INFRASTRUCTURE_UNAVAILABLE
            elif 'county' in text and ('ambiguous' in text or 'specify the state' in text):
                reason = R.AMBIGUOUS_COUNTY
            elif ('cause' in text or 'concept' in text) and 'ambiguous' in text:
                reason = R.AMBIGUOUS_HEALTH_CONCEPT
            elif 'matched to a validated' in text or 'to a cdc places measure' in text:
                reason = R.HEALTH_CONCEPT_UNAVAILABLE
            elif 'approved' in text and ('pair' in text or 'concept' in text):
                reason = R.HEALTH_CONCEPT_UNAVAILABLE
            elif 'group' in text or 'demographic' in text:
                reason = R.AMBIGUOUS_DEMOGRAPHIC_VALUE
            else:
                reason = R.INTENT_AMBIGUOUS
        self.reason = reason


def _normalize_text(value: str) -> str:
    """
    Normalize text for deterministic matching.
    """
    normalized = value.casefold()

    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        normalized,
    )

    return " ".join(
        normalized.split()
    )


def _similarity(
    first: str,
    second: str,
) -> float:
    return SequenceMatcher(
        None,
        _normalize_text(first),
        _normalize_text(second),
    ).ratio()


def _best_text_match(
    question_text: str,
    candidates: list[str],
    *,
    minimum_score: float = 0.58,
) -> tuple[str | None, float]:
    """
    Resolve the best candidate appearing in, or resembling text from,
    the research question.

    Exact phrase matches are preferred over fuzzy similarity.
    """
    normalized_question = _normalize_text(
        question_text
    )

    exact_matches = [
        candidate
        for candidate in candidates
        if _normalize_text(candidate)
        in normalized_question
    ]

    if exact_matches:
        best_exact = max(
            exact_matches,
            key=lambda value: len(
                _normalize_text(value)
            ),
        )

        return best_exact, 1.0

    best_candidate: str | None = None
    best_score = 0.0

    question_tokens = normalized_question.split()

    for candidate in candidates:
        normalized_candidate = _normalize_text(
            candidate
        )

        candidate_tokens = (
            normalized_candidate.split()
        )

        candidate_length = len(
            candidate_tokens
        )

        if candidate_length == 0:
            continue

        # Compare candidate against question token windows.
        for window_size in {
            candidate_length,
            max(1, candidate_length - 1),
            candidate_length + 1,
        }:
            if window_size > len(question_tokens):
                continue

            for index in range(
                len(question_tokens)
                - window_size
                + 1
            ):
                question_window = " ".join(
                    question_tokens[
                        index:index + window_size
                    ]
                )

                score = _similarity(
                    candidate,
                    question_window,
                )

                if score > best_score:
                    best_score = score
                    best_candidate = candidate

    if best_score < minimum_score:
        return None, best_score

    return best_candidate, best_score


def resolve_cause(
    question_text: str,
    *,
    disparity: bool = False,
    catalog: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Resolve a cause name and ID against the validated lookup.

    Cause resolution is intentionally conservative:
    - exact validated cause names are accepted;
    - approved shorthand aliases are accepted;
    - unknown causes are rejected rather than fuzzily mapped
      to a different validated cause.
    """
    causes = catalog if catalog is not None else (
        get_disparity_causes()
        if disparity
        else get_causes()
    )

    required_columns = {
        "cause_id",
        "cause_name",
    }

    if causes.empty:
        raise ResolutionError(
            "The cause lookup returned no records."
        )

    if not required_columns.issubset(
        causes.columns
    ):
        raise ResolutionError(
            "The cause lookup is missing required columns."
        )

    cause_names = (
        causes["cause_name"]
        .dropna()
        .astype(str)
        .tolist()
    )

    normalized_question = _normalize_text(
        question_text
    )

    matched_name: str | None = None
    score = 0.0

    # Exact validated cause-name matching.
    exact_matches = [
        cause_name
        for cause_name in cause_names
        if _normalize_text(
            cause_name
        )
        in normalized_question
    ]

    if exact_matches:
        matched_name = max(
            exact_matches,
            key=lambda value: len(
                _normalize_text(
                    value
                )
            ),
        )

        score = 1.0

    # Approved researcher shorthand.
    shorthand_map = {
        "diabetes": [
            "Diabetes mellitus type 2",
            "Diabetes mellitus",
        ],
        "heart disease": [
            "Ischemic heart disease",
        ],
        "alzheimer": [
            (
                "Alzheimer's disease and "
                "other dementias"
            ),
        ],
    }

    for shorthand, preferred_names in (
        shorthand_map.items()
    ):
        if shorthand in normalized_question:
            for preferred_name in preferred_names:
                preferred_match = causes.loc[
                    causes["cause_name"]
                    .astype(str)
                    .str.casefold()
                    == preferred_name.casefold()
                ]

                if not preferred_match.empty:
                    matched_name = preferred_name
                    score = 1.0
                    break

            if matched_name is not None:
                break

    # Fail closed when no validated cause or approved
    # shorthand can be resolved.
    if matched_name is None:
        raise ResolutionError(
            "The requested disease or cause could not be "
            "matched to a validated CountyHealth cause."
        )

    matched_rows = causes.loc[
        causes["cause_name"]
        .astype(str)
        .str.casefold()
        == matched_name.casefold()
    ]

    if len(matched_rows) != 1:
        raise ResolutionError(
            f"Cause resolution was ambiguous for "
            f"'{matched_name}'."
        )

    row = matched_rows.iloc[0]

    return {
        "cause_id": int(
            row["cause_id"]
        ),
        "cause_name": str(
            row["cause_name"]
        ),
        "match_score": round(
            float(score),
            3,
        ),
    }

PLACES_IHME_ALLOWED_PAIRS: dict[str, set[int]] = {
    "DIABETES": {976},
    "STROKE": {494},
    "CASTHMA": {515},
}


def validate_places_ihme_pair(
    places_measure: dict[str, Any],
    cause: dict[str, Any],
) -> None:
    """
    Validate that a resolved CDC PLACES measure and IHME cause form
    an explicitly approved cross-source conceptual pair.

    Cross-source compatibility is deterministic and fail-closed.
    Independently resolvable concepts are not assumed to be
    epidemiologically equivalent.
    """
    measure_id = str(
        places_measure["measure_id"]
    ).upper()

    cause_id = int(
        cause["cause_id"]
    )

    allowed_cause_ids = (
        PLACES_IHME_ALLOWED_PAIRS.get(
            measure_id
        )
    )

    if (
        allowed_cause_ids is None
        or cause_id not in allowed_cause_ids
    ):
        raise ResolutionError(
            "The resolved CDC PLACES measure and IHME cause "
            "are not an approved cross-source conceptual pair: "
            f"{measure_id} and IHME cause {cause_id}."
        )


def _extract_places_resolution_text(
    question_text: str,
) -> str:
    """
    Isolate the CDC PLACES portion of an explicitly cross-source
    PLACES_IHME question.

    This prevents an IHME-side disease concept from being mistaken
    for the requested PLACES measure.
    """
    normalized = _normalize_text(
        question_text
    )

    places_marker = "cdc places"
    ihme_marker = "ihme"

    places_index = normalized.find(
        places_marker
    )
    ihme_index = normalized.find(
        ihme_marker
    )

    if places_index == -1:
        return question_text

    if (
        ihme_index != -1
        and places_index < ihme_index
    ):
        return normalized[
            places_index:ihme_index
        ].strip()

    return normalized[
        places_index:
    ].strip()


def resolve_places_measure(
    question_text: str,
) -> dict[str, Any]:
    """
    Resolve a CDC PLACES measure conservatively.

    Accepted:
    - exact PLACES measure IDs;
    - exact canonical measure names;
    - explicitly approved researcher shorthand.

    Unsupported or ambiguous concepts are rejected rather than
    fuzzily mapped to a different PLACES measure.
    """
    measures = run_query(
        """
        SELECT
            measure_id,
            canonical_name,
            category,
            unit
        FROM places.measures
        ORDER BY measure_id
        """
    )

    required_columns = {
        "measure_id",
        "canonical_name",
    }

    if measures.empty:
        raise ResolutionError(
            "The CDC PLACES measure lookup returned no records."
        )

    if not required_columns.issubset(
        measures.columns
    ):
        raise ResolutionError(
            "The CDC PLACES measure lookup is missing required columns."
        )

    normalized_question = _normalize_text(
        question_text
    )

    # Exact PLACES measure ID.
    for row in measures.itertuples(
        index=False
    ):
        measure_id = str(
            row.measure_id
        ).strip()

        if _normalize_text(measure_id) == normalized_question:
            return {
                "measure_id": measure_id,
                "measure_name": str(
                    row.canonical_name
                ),
                "category": getattr(
                    row,
                    "category",
                    None,
                ),
                "unit": getattr(
                    row,
                    "unit",
                    None,
                ),
                "match_type": "exact_measure_id",
            }

    # Exact canonical-name matching.
    canonical_matches = []

    for row in measures.itertuples(
        index=False
    ):
        canonical_name = str(
            row.canonical_name
        )

        if (
            _normalize_text(
                canonical_name
            )
            in normalized_question
        ):
            canonical_matches.append(
                row
            )

    if canonical_matches:
        matched = max(
            canonical_matches,
            key=lambda row: len(
                _normalize_text(
                    str(row.canonical_name)
                )
            ),
        )

        return {
            "measure_id": str(
                matched.measure_id
            ),
            "measure_name": str(
                matched.canonical_name
            ),
            "category": getattr(
                matched,
                "category",
                None,
            ),
            "unit": getattr(
                matched,
                "unit",
                None,
            ),
            "match_type": "exact_canonical_name",
        }

    shorthand_map = {
        "diabetes": "DIABETES",
        "diagnosed diabetes": "DIABETES",
        "obesity": "OBESITY",
        "stroke": "STROKE",
        "coronary heart disease": "CHD",
        "heart disease": "CHD",
        "high blood pressure": "BPHIGH",
        "hypertension": "BPHIGH",
        "high cholesterol": "HIGHCHOL",
        "chronic kidney disease": "KIDNEY",
        "kidney disease": "KIDNEY",
        "copd": "COPD",
        "asthma": "CASTHMA",
        "arthritis": "ARTHRITIS",
        "depression": "DEPRESSION",
    }

    matched_aliases = [
        alias
        for alias in shorthand_map
        if _normalize_text(
            alias
        )
        in normalized_question
    ]

    if matched_aliases:
        alias = max(
            matched_aliases,
            key=lambda value: len(
                _normalize_text(
                    value
                )
            ),
        )

        measure_id = shorthand_map[
            alias
        ]

        matched_rows = measures[
            measures[
                "measure_id"
            ].astype(str).str.upper()
            == measure_id
        ]

        if len(matched_rows) != 1:
            raise ResolutionError(
                "The approved CDC PLACES shorthand did not resolve "
                "to exactly one validated measure."
            )

        row = matched_rows.iloc[0]

        return {
            "measure_id": str(
                row["measure_id"]
            ),
            "measure_name": str(
                row["canonical_name"]
            ),
            "category": row.get(
                "category"
            ),
            "unit": row.get(
                "unit"
            ),
            "match_type": "approved_shorthand",
        }

    raise ResolutionError(
        "The requested concept could not be resolved safely "
        "to a CDC PLACES measure."
    )


def resolve_county(
    question_text: str,
    *, catalog: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Resolve a current county and FIPS code conservatively.

    Resolution rules:
    - validated county/location names are accepted;
    - normal punctuation differences are accepted;
    - phrasing such as "Albany County in Wyoming" is accepted;
    - a county name without a state is accepted only when that
      county name uniquely identifies one current county;
    - ambiguous county-only names require the state;
    - unknown or misspelled counties are rejected rather than
      fuzzily mapped to another validated county.
    """
    counties = catalog if catalog is not None else get_counties()

    required_columns = {
        "fips",
        "location_name",
    }

    if counties.empty:
        raise ResolutionError(
            "The county lookup returned no records."
        )

    if not required_columns.issubset(
        counties.columns
    ):
        raise ResolutionError(
            "The county lookup is missing required columns."
        )

    normalized_question = _normalize_text(
        question_text
    )

    matched_rows: list[
        tuple[pd.Series, str]
    ] = []

    county_name_candidates: dict[
        str,
        list[pd.Series],
    ] = {}

    for _, row in counties.iterrows():
        location_name = str(
            row["location_name"]
        ).strip()

        normalized_location = _normalize_text(
            location_name
        )

        aliases = {
            normalized_location,
        }

        # CountyHealth location labels normally have the form:
        #
        # "Albany County (Wyoming)"
        #
        # Add state-qualified natural-language aliases:
        #
        # "Albany County Wyoming"
        # "Albany County in Wyoming"
        match = re.match(
            r"^(.*?)\s*\(([^()]+)\)\s*$",
            location_name,
        )

        if match is not None:
            locality = _normalize_text(
                match.group(1)
            )

            state = _normalize_text(
                match.group(2)
            )

            aliases.update(
                {
                    f"{locality} {state}",
                    f"{locality} in {state}",
                }
            )

            county_name_candidates.setdefault(
                locality,
                [],
            ).append(
                row
            )

        matched_alias = next(
            (
                alias
                for alias in aliases
                if alias
                and alias in normalized_question
            ),
            None,
        )

        if matched_alias is not None:
            matched_rows.append(
                (
                    row,
                    matched_alias,
                )
            )

    # ------------------------------------------------------------
    # First preference:
    # a fully qualified validated county/location match.
    # ------------------------------------------------------------

    if matched_rows:
        longest_length = max(
            len(alias)
            for _, alias in matched_rows
        )

        best_matches = [
            (
                row,
                alias,
            )
            for row, alias in matched_rows
            if len(alias) == longest_length
        ]

        if len(best_matches) != 1:
            names = sorted(
                {
                    str(
                        row["location_name"]
                    )
                    for row, _ in best_matches
                }
            )

            raise ResolutionError(
                "County resolution was ambiguous among "
                "validated locations: "
                + "; ".join(names)
                + ". Please specify the state."
            )

        row, _ = best_matches[0]

        return {
            "fips": str(
                row["fips"]
            ).zfill(5),
            "location_name": str(
                row["location_name"]
            ),
            "match_score": 1.0,
        }

    # ------------------------------------------------------------
    # Second preference:
    # county name without a state.
    #
    # This is allowed only when the normalized county name maps
    # to exactly one current county.
    # ------------------------------------------------------------

    county_only_matches: list[
        tuple[str, list[pd.Series]]
    ] = []

    for (
        locality,
        candidate_rows,
    ) in county_name_candidates.items():
        if (
            locality
            and locality in normalized_question
        ):
            county_only_matches.append(
                (
                    locality,
                    candidate_rows,
                )
            )

    if county_only_matches:
        longest_length = max(
            len(locality)
            for locality, _ in county_only_matches
        )

        best_county_names = [
            (
                locality,
                candidate_rows,
            )
            for locality, candidate_rows
            in county_only_matches
            if len(locality) == longest_length
        ]

        if len(best_county_names) != 1:
            candidate_names = sorted(
                {
                    str(
                        row["location_name"]
                    )
                    for _, rows
                    in best_county_names
                    for row in rows
                }
            )

            raise ResolutionError(
                "County resolution was ambiguous among "
                "validated locations: "
                + "; ".join(candidate_names)
                + ". Please specify the state."
            )

        (
            locality,
            candidate_rows,
        ) = best_county_names[0]

        if len(candidate_rows) == 1:
            row = candidate_rows[0]

            return {
                "fips": str(
                    row["fips"]
                ).zfill(5),
                "location_name": str(
                    row["location_name"]
                ),
                "match_score": 1.0,
            }

        names = sorted(
            str(
                row["location_name"]
            )
            for row in candidate_rows
        )

        raise ResolutionError(
            f"County '{locality}' is ambiguous. "
            "Possible validated matches are: "
            + "; ".join(names)
            + ". Please specify the state."
        )

    raise ResolutionError(
        "No current county could be resolved "
        "from the question."
    )


def _normalize_age_group_name(
    value: str,
) -> str:
    """
    Normalize common natural-language age-range forms to the
    canonical CountyHealth age-group representation.

    Examples:
    - "60-64" -> "60 to 64"
    - "60–64" -> "60 to 64"
    - "60 — 64" -> "60 to 64"
    - "ages 60-64" -> "60 to 64"
    - "age 60 to 64" -> "60 to 64"

    Values that do not match a simple bounded age range are
    returned unchanged so resolution remains fail-closed.
    """
    normalized = _normalize_text(
        value
    )

    match = re.fullmatch(
        (
            r"(?:(?:age|ages)\s+)?"
            r"(\d{1,3})\s+"
            r"(?:to\s+)?"
            r"(\d{1,3})"
        ),
        normalized,
    )

    if match is None:
        return value.strip()

    lower = int(
        match.group(1)
    )

    upper = int(
        match.group(2)
    )

    if lower >= upper:
        return value.strip()

    return f"{lower} to {upper}"


def resolve_demographic_groups(
    classified: ClassifiedQuestion,
) -> dict[str, Any]:
    """
    Resolve demographic names to validated group IDs.

    When the classifier does not explicitly identify a dimension,
    infer it safely from the requested group names.
    """
    entities = classified.extracted_entities

    dimension = entities.get("dimension")

    requested_groups = entities.get(
        "demographic_groups",
        [],
    )

    if not isinstance(requested_groups, list):
        requested_groups = []

    requested_groups = [
        str(group)
        for group in requested_groups
    ]

    if dimension is None:
        race_groups = {
            "Latino, Any race",
            "Non-Latino, Black",
            "Non-Latino, White",
            (
                "Non-Latino, American Indian or "
                "Alaska Native"
            ),
            (
                "Non-Latino, Asian or "
                "Pacific Islander"
            ),
        }

        sex_groups = {
            "Male",
            "Female",
            "Both",
        }

        if requested_groups and all(
            group in race_groups
            for group in requested_groups
        ):
            dimension = "Race / ethnicity"

        elif requested_groups and all(
            group in sex_groups
            for group in requested_groups
        ):
            dimension = "Sex"

    if dimension is None:
        raise ResolutionError(
            "The demographic dimension is unresolved."
        )

    if len(requested_groups) < 2:
        raise ResolutionError(
            "Two demographic groups are required."
        )

    groups = get_disparity_groups(
        str(dimension)
    )

    required_columns = {
        "group_id",
        "group_name",
    }

    if groups.empty:
        raise ResolutionError(
            f"No demographic groups were returned "
            f"for {dimension}."
        )

    if not required_columns.issubset(
        groups.columns
    ):
        raise ResolutionError(
            "The demographic-group lookup is missing "
            "required columns."
        )

    resolved: list[dict[str, Any]] = []

    demographic_aliases = {
        "Race / ethnicity": {
            "black": "Non-Latino, Black",
            "black people": "Non-Latino, Black",
            "african american": "Non-Latino, Black",
            "african americans": "Non-Latino, Black",
            "non-latino black": "Non-Latino, Black",
            "white": "Non-Latino, White",
            "white people": "Non-Latino, White",
            "whites": "Non-Latino, White",
            "non-latino white": "Non-Latino, White",
            "non-latino american indian or alaska native": (
                "Non-Latino, American Indian or Alaska Native"
            ),
            "non-latino asian or pacific islander": (
                "Non-Latino, Asian or Pacific Islander"
            ),
            "latino": "Latino, Any race",
            "latinos": "Latino, Any race",
            "hispanic": "Latino, Any race",
            "hispanics": "Latino, Any race",
        },
        "Sex": {
            "man": "Male",
            "men": "Male",
            "male": "Male",
            "males": "Male",
            "woman": "Female",
            "women": "Female",
            "female": "Female",
            "females": "Female",
        },
    }

    dimension_aliases = (
        demographic_aliases.get(
            str(dimension),
            {},
        )
    )
    
    for requested_name in requested_groups[:2]:
        normalized_requested = (
            requested_name
            .strip()
            .casefold()
        )

        if str(dimension) == "Age group":
            canonical_requested = (
                _normalize_age_group_name(
                    requested_name
                )
            )
        else:
            canonical_requested = (
                dimension_aliases.get(
                    normalized_requested,
                    requested_name,
                )
            )

        match = groups.loc[
            groups["group_name"]
            .astype(str)
            .str.casefold()
            == str(
                canonical_requested
            ).casefold()
        ]

        if len(match) != 1:
            raise ResolutionError(
                "Could not uniquely resolve demographic "
                f"group '{requested_name}'."
            )

        row = match.iloc[0]

        resolved.append(
            {
                "group_id": int(
                    row["group_id"]
                ),
                "group_name": str(
                    row["group_name"]
                ),
            }
        )

    if (
        resolved[0]["group_id"]
        == resolved[1]["group_id"]
    ):
        raise ResolutionError(
            "The two demographic groups must be different."
        )

    return {
        "dimension": str(dimension),
        "group_a_id": resolved[0]["group_id"],
        "group_a_name": resolved[0]["group_name"],
        "group_b_id": resolved[1]["group_id"],
        "group_b_name": resolved[1]["group_name"],
    }

def resolve_plan(
    classified: ClassifiedQuestion,
    plan: AnalysisPlan,
) -> AnalysisPlan:
    """
    Populate resolvable plan parameters using validated lookups.

    The supplied plan is updated in place and returned.

    Human-readable validated context is also stored in
    plan.resolved_context so downstream evidence and narrative
    interpretation can cite county, cause, year, and demographic
    context explicitly.
    """
    if classified.extracted_entities.get("multidimensional_request") is not None:
        if plan.resolved_context.get("resolved_query") is not None and plan.resolved_context.get("availability_receipt") is not None:
            from ai.multidimensional_integration import validate_plan_identity
            validate_plan_identity(plan)
        return plan

    question_text = (
        classified.question.raw_text
    )

    entities = classified.extracted_entities

    county_resolution_text = str(
        entities.get(
            "semantic_county_name",
            question_text,
        )
    )

    cause_resolution_text = str(
        entities.get(
            "semantic_cause_name",
            question_text,
        )
    )

    try:
        if plan.intent == (
            AnalysisIntent.DEMOGRAPHIC_DISPARITY
        ):
            cause = resolve_cause(
                cause_resolution_text,
                disparity=True,
            )

            groups = (
                resolve_demographic_groups(
                    classified
                )
            )

            evidence_domain = (
                plan.resolved_context.get(
                    "evidence_domain"
                )
            )

            places_measure: dict[
                str,
                Any,
            ] | None = None

            if evidence_domain == "PLACES_IHME":
                places_resolution_text = (
                    _extract_places_resolution_text(
                        question_text
                    )
                )

                places_measure = resolve_places_measure(
                    places_resolution_text
                )

                validate_places_ihme_pair(
                    places_measure,
                    cause,
                )

            analysis_year: int | None = None

            for step in plan.steps:
                if (
                    step.operation
                    == "resolve_groups"
                ):
                    step.parameters[
                        "dimension"
                    ] = groups["dimension"]
                elif (
                    step.operation
                    == "places_ihme_demographic_disparity_context"
                ):
                    if places_measure is None:
                        raise ResolutionError(
                            "CDC PLACES measure resolution is required "
                            "for PLACES_IHME demographic disparity."
                        )

                    step.parameters.update(
                        {
                            "dimension": groups["dimension"],
                            "group_a_id": groups["group_a_id"],
                            "group_b_id": groups["group_b_id"],
                            "places_measure_id": places_measure[
                                "measure_id"
                            ],
                            "ihme_cause_id": cause["cause_id"],
                        }
                    )

                    places_year = step.parameters.get(
                        "places_measurement_year"
                    )
                    ihme_year = step.parameters.get(
                        "ihme_year"
                    )

                    if (
                        places_year is not None
                        and ihme_year is not None
                    ):
                        if int(places_year) != int(ihme_year):
                            raise ResolutionError(
                                "Validated demographic disparity "
                                "context requires the CDC PLACES "
                                "measurement year and IHME year to match."
                            )

                        analysis_year = int(
                            places_year
                        )

                elif (
                    step.operation
                    == "county_disparity_ranking"
                ):
                    step.parameters.update(
                        {
                            "cause_id": cause[
                                "cause_id"
                            ],
                            "dimension": groups[
                                "dimension"
                            ],
                            "group_a_id": groups[
                                "group_a_id"
                            ],
                            "group_b_id": groups[
                                "group_b_id"
                            ],
                        }
                    )

                    if (
                        step.parameters.get("year")
                        is not None
                    ):
                        analysis_year = int(
                            step.parameters["year"]
                        )

            plan.assumptions.append(
                "Resolved cause: "
                f"{cause['cause_name']}."
            )

            plan.assumptions.append(
                "Resolved comparison: "
                f"{groups['group_a_name']} versus "
                f"{groups['group_b_name']}."
            )

            plan.resolved_context.update(
                {
                    "dimension": groups[
                        "dimension"
                    ],
                    "group_a_id": groups[
                        "group_a_id"
                    ],
                    "group_a_name": groups[
                        "group_a_name"
                    ],
                    "group_b_id": groups[
                        "group_b_id"
                    ],
                    "group_b_name": groups[
                        "group_b_name"
                    ],
                    "cause_id": cause[
                        "cause_id"
                    ],
                    "cause_name": cause[
                        "cause_name"
                    ],
                }
            )

            if analysis_year is not None:
                plan.resolved_context[
                    "year"
                ] = analysis_year

            if places_measure is not None:
                plan.resolved_context.update(
                    {
                        "places_measure_id": (
                            places_measure["measure_id"]
                        ),
                        "places_measure_name": (
                            places_measure["measure_name"]
                        ),
                        "places_measure_category": (
                            places_measure["category"]
                        ),
                        "places_measure_unit": (
                            places_measure["unit"]
                        ),
                    }
                )

                if analysis_year is not None:
                    plan.resolved_context[
                        "places_measurement_year"
                    ] = analysis_year

                    plan.resolved_context[
                        "ihme_year"
                    ] = analysis_year

                plan.assumptions.append(
                    "Resolved CDC PLACES measure: "
                    f"{places_measure['measure_name']} "
                    f"({places_measure['measure_id']})."
                )

        elif plan.intent == (
            AnalysisIntent.COUNTY_PROFILE
        ):
            county = resolve_county(
                county_resolution_text
            )

            analysis_year: int | None = None

            for step in plan.steps:
                if "fips" in step.parameters:
                    step.parameters["fips"] = (
                        county["fips"]
                    )

                if (
                    step.parameters.get("year")
                    is not None
                    and analysis_year is None
                ):
                    analysis_year = int(
                        step.parameters["year"]
                    )

            plan.assumptions.append(
                "Resolved county: "
                f"{county['location_name']} "
                f"({county['fips']})."
            )

            plan.resolved_context.update(
                {
                    "fips": county["fips"],
                    "location_name": county[
                        "location_name"
                    ],
                }
            )

            if analysis_year is not None:
                plan.resolved_context[
                    "year"
                ] = analysis_year

        elif plan.intent == (
            AnalysisIntent.COUNTY_CAUSE_SNAPSHOT
        ):
            county = resolve_county(
                county_resolution_text
            )

            evidence_domain = plan.resolved_context.get(
                "evidence_domain"
            )

            analysis_year: int | None = None

            if evidence_domain == "PLACES":
                places_measure = resolve_places_measure(
                    question_text
                )

                for step in plan.steps:
                    if (
                        step.operation
                        == "places_county_measure_history"
                    ):
                        step.parameters.update(
                            {
                                "fips": county["fips"],
                                "measure_id": places_measure[
                                    "measure_id"
                                ],
                            }
                        )

                    elif (
                        step.operation
                        == "restrict_measurement_year"
                    ):
                        if (
                            step.parameters.get(
                                "measurement_year"
                            )
                            is not None
                        ):
                            analysis_year = int(
                                step.parameters[
                                    "measurement_year"
                                ]
                            )

                plan.assumptions.append(
                    "Resolved county: "
                    f"{county['location_name']} "
                    f"({county['fips']})."
                )

                plan.assumptions.append(
                    "Resolved CDC PLACES measure: "
                    f"{places_measure['measure_name']} "
                    f"({places_measure['measure_id']})."
                )

                plan.resolved_context.update(
                    {
                        "fips": county["fips"],
                        "location_name": county[
                            "location_name"
                        ],
                        "places_measure_id": places_measure[
                            "measure_id"
                        ],
                        "places_measure_name": places_measure["measure_name"],
                    }
                )

                if analysis_year is not None:
                    plan.resolved_context[
                        "measurement_year"
                    ] = analysis_year

            else:
                cause = resolve_cause(
                    cause_resolution_text
                )

                for step in plan.steps:
                    if (
                        step.operation
                        == "county_cause_snapshot"
                    ):
                        step.parameters.update(
                            {
                                "fips": county["fips"],
                                "cause_id": cause["cause_id"],
                            }
                        )

                        if (
                            step.parameters.get("year")
                            is not None
                        ):
                            analysis_year = int(
                                step.parameters["year"]
                            )

                plan.assumptions.append(
                    "Resolved county: "
                    f"{county['location_name']} "
                    f"({county['fips']})."
                )

                plan.assumptions.append(
                    "Resolved cause: "
                    f"{cause['cause_name']}."
                )

                plan.resolved_context.update(
                    {
                        "fips": county["fips"],
                        "location_name": county[
                            "location_name"
                        ],
                        "cause_id": cause["cause_id"],
                        "cause_name": cause[
                            "cause_name"
                        ],
                    }
                )

                if analysis_year is not None:
                    plan.resolved_context[
                        "year"
                    ] = analysis_year

        elif plan.intent == (
            AnalysisIntent.COUNTY_RANKING
        ):
            cause = resolve_cause(
                cause_resolution_text
            )

            analysis_year: int | None = None

            for step in plan.steps:
                if "cause_id" in step.parameters:
                    step.parameters[
                        "cause_id"
                    ] = cause["cause_id"]

                if (
                    step.parameters.get("year")
                    is not None
                    and analysis_year is None
                ):
                    analysis_year = int(
                        step.parameters["year"]
                    )

            plan.assumptions.append(
                "Resolved cause: "
                f"{cause['cause_name']}."
            )

            plan.resolved_context.update(
                {
                    "cause_id": cause["cause_id"],
                    "cause_name": cause[
                        "cause_name"
                    ],
                }
            )

            if analysis_year is not None:
                plan.resolved_context[
                    "year"
                ] = analysis_year

        elif plan.intent == (
            AnalysisIntent.RURALITY_COMPARISON
        ):
            cause = resolve_cause(
                cause_resolution_text
            )

            places_resolution_text = (
                _extract_places_resolution_text(
                    question_text
                )
            )

            places_measure = resolve_places_measure(
                places_resolution_text
            )

            validate_places_ihme_pair(
                places_measure,
                cause,
            )

            analysis_year: int | None = None

            for step in plan.steps:
                if (
                    step.operation
                    == "places_ihme_rurality_comparison"
                ):
                    step.parameters.update(
                        {
                            "places_measure_id": (
                                places_measure[
                                    "measure_id"
                                ]
                            ),
                            "ihme_cause_id": cause[
                                "cause_id"
                            ],
                        }
                    )

                    places_year = step.parameters.get(
                        "places_measurement_year"
                    )

                    ihme_year = step.parameters.get(
                        "ihme_year"
                    )

                    if (
                        places_year is not None
                        and ihme_year is not None
                    ):
                        if int(places_year) != int(ihme_year):
                            raise ResolutionError(
                                "Validated rurality comparison "
                                "requires the CDC PLACES measurement "
                                "year and IHME year to match."
                            )

                        analysis_year = int(
                            places_year
                        )

            plan.assumptions.append(
                "Resolved CDC PLACES measure: "
                f"{places_measure['measure_name']} "
                f"({places_measure['measure_id']})."
            )

            plan.assumptions.append(
                "Resolved IHME cause: "
                f"{cause['cause_name']}."
            )

            plan.resolved_context.update(
                {
                    "places_measure_id": (
                        places_measure[
                            "measure_id"
                        ]
                    ),
                    "places_measure_name": (
                        places_measure[
                            "measure_name"
                        ]
                    ),
                    "places_measure_category": (
                        places_measure[
                            "category"
                        ]
                    ),
                    "places_measure_unit": (
                        places_measure[
                            "unit"
                        ]
                    ),
                    "cause_id": cause[
                        "cause_id"
                    ],
                    "cause_name": cause[
                        "cause_name"
                    ],
                    "geographic_scope": (
                        "United States"
                    ),
                    "rurality_classification": (
                        "USDA RUCC 2023"
                    ),
                }
            )

            if analysis_year is not None:
                plan.resolved_context[
                    "year"
                ] = analysis_year
                plan.resolved_context[
                    "places_measurement_year"
                ] = analysis_year
                plan.resolved_context[
                    "ihme_year"
                ] = analysis_year

        elif plan.intent == (
            AnalysisIntent.TREND_COMPARISON
        ):
            county = resolve_county(
                county_resolution_text
            )

            cause = resolve_cause(
                cause_resolution_text
            )

            evidence_domain = (
                plan.resolved_context.get(
                    "evidence_domain"
                )
            )

            places_measure: dict[
                str,
                Any,
            ] | None = None

            if evidence_domain == "PLACES_IHME":
                places_resolution_text = (
                    _extract_places_resolution_text(
                        question_text
                    )
                )

                places_measure = (
                    resolve_places_measure(
                        places_resolution_text
                    )
                )

                validate_places_ihme_pair(
                    places_measure,
                    cause,
                )

            first_year: int | None = None
            last_year: int | None = None

            for step in plan.steps:
                if (
                    step.operation
                    == "places_ihme_county_trend"
                ):
                    if places_measure is None:
                        raise ResolutionError(
                            "CDC PLACES measure resolution is required "
                            "for PLACES_IHME trend analysis."
                        )

                    step.parameters.update(
                        {
                            "fips": county["fips"],
                            "places_measure_id": places_measure[
                                "measure_id"
                            ],
                            "ihme_cause_id": cause[
                                "cause_id"
                            ],
                        }
                    )

                elif (
                    step.operation
                    == "cause_trend"
                ):
                    step.parameters[
                        "cause_id"
                    ] = cause["cause_id"]

                    step.parameters[
                        "fips"
                    ] = county["fips"]

                elif step.operation in {
                    "restrict_year_range",
                    "restrict_analysis_year_range",
                }:
                    if (
                        step.parameters.get(
                            "first_year"
                        )
                        is not None
                    ):
                        first_year = int(
                            step.parameters[
                                "first_year"
                            ]
                        )

                    if (
                        step.parameters.get(
                            "last_year"
                        )
                        is not None
                    ):
                        last_year = int(
                            step.parameters[
                                "last_year"
                            ]
                        )

            plan.assumptions.append(
                "Resolved cause: "
                f"{cause['cause_name']}."
            )

            plan.resolved_context.update(
                {
                    "fips": county["fips"],
                    "location_name": county[
                        "location_name"
                    ],
                    "cause_id": cause["cause_id"],
                    "cause_name": cause[
                        "cause_name"
                    ],
                }
            )

            if places_measure is not None:
                plan.resolved_context.update(
                    {
                        "places_measure_id": (
                            places_measure[
                                "measure_id"
                            ]
                        ),
                        "places_measure_name": (
                            places_measure[
                                "measure_name"
                            ]
                        ),
                        "places_measure_category": (
                            places_measure[
                                "category"
                            ]
                        ),
                        "places_measure_unit": (
                            places_measure[
                                "unit"
                            ]
                        ),
                    }
                )

                plan.assumptions.append(
                    "Resolved CDC PLACES measure: "
                    f"{places_measure['measure_name']} "
                    f"({places_measure['measure_id']})."
                )

            if first_year is not None:
                plan.resolved_context[
                    "first_year"
                ] = first_year

            if last_year is not None:
                plan.resolved_context[
                    "last_year"
                ] = last_year

            plan.assumptions.append(
                "Resolved county: "
                f"{county['location_name']} "
                f"({county['fips']})."
            )
            cause = resolve_cause(
                cause_resolution_text
            )

            analysis_year: int | None = None

            for step in plan.steps:
                if "cause_id" in step.parameters:
                    step.parameters[
                        "cause_id"
                    ] = cause["cause_id"]

                if (
                    step.parameters.get("year")
                    is not None
                    and analysis_year is None
                ):
                    analysis_year = int(
                        step.parameters["year"]
                    )

            plan.assumptions.append(
                "Resolved cause: "
                f"{cause['cause_name']}."
            )

            plan.resolved_context.update(
                {
                    "cause_id": cause["cause_id"],
                    "cause_name": cause[
                        "cause_name"
                    ],
                }
            )

            if analysis_year is not None:
                plan.resolved_context[
                    "year"
                ] = analysis_year

    except ResolutionError as exc:
        plan.resolved_context["failure_reason"] = exc.reason
        plan.unresolved_items.append(
            str(exc)
        )

    # Remove duplicated unresolved messages.
    plan.unresolved_items = list(
        dict.fromkeys(
            plan.unresolved_items
        )
    )

    plan.assumptions = list(
        dict.fromkeys(
            plan.assumptions
        )
    )

    return plan

def resolve_multidimensional_request(request, normalized, *, fixture_context=None):
    """Canonical resolution for the new shape, with public activation closed.

    A public planned query can carry a structural preview without fabricated IDs.
    Exact catalogs/availability/plan execution are exercised only in marked fixtures.
    """
    from dataclasses import replace
    import duckdb
    from app.multidimensional import DuplicateAnalyticalKeyError
    from ai.multidimensional_integration import (
        FixtureIntegrationContext, MultidimensionalResolution, query_preview, wire, validate_fixture_availability,
    )
    from ai.multidimensional_request import SemanticCapabilityDecision
    from ai.capabilities import CAPABILITIES, Source, MULTIDIMENSIONAL_RELATIONS
    from ai.query_models import (
        ResolvedQuery, SourceConcept, SourceTime, TimeSpec, TimeAlignment, ReleasePolicy,
        assess_query_contract, DecisionStatus,
    )
    capability = CAPABILITIES[normalized.capability_key]
    def decision(reason, availability, query=None):
        return SemanticCapabilityDecision(normalized.capability_key, capability.state.value, reason,
                                          availability, query, fixture_context is not None)
    draft = {"normalized": wire(normalized), "cause_name": request.cause_name,
             "county_name": request.county_name, "public_executable": False,
             "required_sources": [source.value for source in capability.sources]}
    if fixture_context is None:
        return MultidimensionalResolution(None, draft, decision("activation_pending", "not_checked_activation_pending"))
    if not isinstance(fixture_context, FixtureIntegrationContext):
        raise ValueError("Explicit typed fixture context required before catalog access")
    path = fixture_context.validate()
    connection = duckdb.connect(str(path), read_only=True, config={"enable_external_access": "false"})
    try:
        # Existing canonical catalogs, no model-supplied IDs and no global DB override.
        cause_relation = MULTIDIMENSIONAL_RELATIONS["causes"]
        county_relation = MULTIDIMENSIONAL_RELATIONS["counties"]
        causes = connection.execute(f"SELECT {cause_relation.column('cause_id')}, {cause_relation.column('cause_name')} "
                                    f"FROM {cause_relation.qualified_name}").fetchdf()
        counties = connection.execute(f"SELECT {county_relation.column('fips')}, {county_relation.column('location_name')}, "
                                      f"{county_relation.column('state_fips')} FROM {county_relation.qualified_name}").fetchdf()
    finally:
        connection.close()
    try:
        cause = resolve_cause(request.cause_name, disparity=True, catalog=causes)
        raw_cause = resolve_cause(request.question.raw_text, disparity=True, catalog=causes)
        if raw_cause["cause_id"] != cause["cause_id"]:
            raise ResolutionError("Parsed concept disagrees with the requested health concept")
        geography = normalized.geography
        if request.county_name:
            county = resolve_county(request.county_name, catalog=counties)
            if resolve_county(request.question.raw_text, catalog=counties)["fips"] != county["fips"]:
                raise ResolutionError("Parsed county disagrees with the requested county")
            geography = replace(geography, county_fips=(str(county["fips"]),))
        if normalized.state_name:
            state_candidates = {}
            for _, row in counties.iterrows():
                match = re.search(r"\(([^()]+)\)\s*$", str(row["location_name"]))
                if match:
                    state_candidates.setdefault(_normalize_text(match[1]), set()).add(str(row["state_fips"]))
            matches = state_candidates.get(_normalize_text(normalized.state_name), set())
            if len(matches) != 1:
                raise ResolutionError("State scope is ambiguous or unavailable in the canonical county catalog")
            geography = replace(geography, state_fips=tuple(matches))
        query = ResolvedQuery(capability_key=normalized.capability_key,
            concepts=(SourceConcept(source=Source.IHME, concept_id=cause["cause_id"], name=cause["cause_name"],
                                    dataset_version="unknown"),), stratum=normalized.stratum,
            comparison=normalized.comparison, geography=geography, operation=normalized.operation,
            time=TimeSpec(sources=(SourceTime(source=Source.IHME, years=normalized.years,
                           release_policy=ReleasePolicy.SOURCE_OBSERVATION),), alignment=TimeAlignment.SINGLE_SOURCE),
            assumptions=normalized.assumptions)
        assessed = assess_query_contract(query)
        if assessed.status is not DecisionStatus.PLANNED:
            raise ResolutionError(assessed.explanation)
    except (ResolutionError, ValueError) as exc:
        return MultidimensionalResolution(None, draft, decision("clarification_required", "catalog_unresolved"),
                                         unresolved=(str(exc),), failure_reason=getattr(exc, "reason", None))
    try:
        query, receipt = validate_fixture_availability(query, fixture_context)
    except DuplicateAnalyticalKeyError as exc:
        return MultidimensionalResolution(None, draft, decision("clarification_required", "catalog_ambiguous"),
                                         unresolved=(str(exc),), failure_reason=FailureReason.AMBIGUOUS_DEMOGRAPHIC_VALUE)
    except LookupError as exc:
        return MultidimensionalResolution(query, query_preview(query), decision("data_unavailable", str(exc), query))
    return MultidimensionalResolution(query, query_preview(query), decision("activation_pending", "fixture_only_records_present", query), receipt)
