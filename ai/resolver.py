from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

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
)


class ResolutionError(ValueError):
    """Raised when an analytical entity cannot be resolved safely."""


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
) -> dict[str, Any]:
    """
    Resolve a cause name and ID against the validated lookup.

    Cause resolution is intentionally conservative:
    - exact validated cause names are accepted;
    - approved shorthand aliases are accepted;
    - unknown causes are rejected rather than fuzzily mapped
      to a different validated cause.
    """
    causes = (
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


def resolve_county(
    question_text: str,
) -> dict[str, Any]:
    """
    Resolve a current county and FIPS code.
    """
    counties = get_counties()

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

    county_names = (
        counties["location_name"]
        .dropna()
        .astype(str)
        .tolist()
    )

    matched_name, score = _best_text_match(
        question_text,
        county_names,
        minimum_score=0.62,
    )

    if matched_name is None:
        raise ResolutionError(
            "No current county could be resolved "
            "from the question."
        )

    matched_rows = counties.loc[
        counties["location_name"]
        .astype(str)
        .str.casefold()
        == matched_name.casefold()
    ]

    if len(matched_rows) != 1:
        raise ResolutionError(
            f"County resolution was ambiguous for "
            f"'{matched_name}'."
        )

    row = matched_rows.iloc[0]

    return {
        "fips": str(row["fips"]).zfill(5),
        "location_name": str(
            row["location_name"]
        ),
        "match_score": round(
            float(score),
            3,
        ),
    }


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

    for requested_name in requested_groups[:2]:
        match = groups.loc[
            groups["group_name"]
            .astype(str)
            .str.casefold()
            == requested_name.casefold()
        ]

        if len(match) != 1:
            raise ResolutionError(
                f"Could not uniquely resolve demographic "
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
    """
    question_text = (
        classified.question.raw_text
    )

    try:
        if plan.intent == (
            AnalysisIntent.DEMOGRAPHIC_DISPARITY
        ):
            cause = resolve_cause(
                question_text,
                disparity=True,
            )

            groups = (
                resolve_demographic_groups(
                    classified
                )
            )

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
                    "dimension": groups["dimension"],
                    "group_a_id": groups["group_a_id"],
                    "group_a_name": groups["group_a_name"],
                    "group_b_id": groups["group_b_id"],
                    "group_b_name": groups["group_b_name"],
                    "cause_id": cause["cause_id"],
                    "cause_name": cause["cause_name"],
                }
            )

        elif plan.intent == (
            AnalysisIntent.COUNTY_PROFILE
        ):
            county = resolve_county(
                question_text
            )

            for step in plan.steps:
                if "fips" in step.parameters:
                    step.parameters["fips"] = (
                        county["fips"]
                    )

            plan.assumptions.append(
                "Resolved county: "
                f"{county['location_name']} "
                f"({county['fips']})."
            )

        elif plan.intent == (
            AnalysisIntent.TREND_COMPARISON
        ):
            try:
                county = resolve_county(
                    question_text
                )
            except ResolutionError:
                county = None

            cause = resolve_cause(
                question_text
            )

            for step in plan.steps:
                if (
                    step.operation
                    == "cause_trend"
                ):
                    step.parameters[
                        "cause_id"
                    ] = cause["cause_id"]

                    if county is not None:
                        step.parameters[
                            "fips"
                        ] = county["fips"]

            plan.assumptions.append(
                "Resolved cause: "
                f"{cause['cause_name']}."
            )

            if county is None:
                plan.unresolved_items.append(
                    "A county must be supplied before "
                    "the trend plan can execute."
                )
            else:
                plan.assumptions.append(
                    "Resolved county: "
                    f"{county['location_name']} "
                    f"({county['fips']})."
                )

        elif plan.intent == (
            AnalysisIntent.COUNTY_RANKING
        ):
            cause = resolve_cause(
                question_text
            )

            for step in plan.steps:
                if "cause_id" in step.parameters:
                    step.parameters[
                        "cause_id"
                    ] = cause["cause_id"]

            plan.assumptions.append(
                "Resolved cause: "
                f"{cause['cause_name']}."
            )

    except ResolutionError as exc:
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