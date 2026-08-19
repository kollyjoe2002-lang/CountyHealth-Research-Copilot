from __future__ import annotations

import re

from ai.models import (
    AnalysisIntent,
    ClassifiedQuestion,
    ResearchQuestion,
)


INTENT_PATTERNS = {
    AnalysisIntent.DEMOGRAPHIC_DISPARITY: [
        r"\bdisparit",
        r"\bdiffer(?:ence|ences)?\b.*\bbetween\b",
        r"\bcompare\b.*\bblack\b.*\bwhite\b",
        r"\bcompare\b.*\blatino\b.*\bwhite\b",
        r"\bcompare\b.*\bamerican indian\b.*\bwhite\b",
        r"\bcompare\b.*\balaska native\b.*\bwhite\b",
        r"\bcompare\b.*\basian\b.*\bwhite\b",
        r"\bcompare\b.*\bpacific islander\b.*\bwhite\b",
        r"\bcompare\b.*\bmale(?:s)?\b.*\bfemale(?:s)?\b",
        r"\bcompare\b.*\bmen\b.*\bwomen\b",
        r"\bcompare\b.*\bwomen\b.*\bmen\b",
        r"\bcompare\b.*\bage(?:s)?\b.*\band\b",
        r"\brace\b",
        r"\bethnic",
        r"\bsex difference",
        r"\bage group",
    ],
    AnalysisIntent.TREND_COMPARISON: [
        r"\btrend",
        r"\bover time",
        r"\bpattern\b.*\b(?:19|20)\d{2}",
        r"\b(?:19|20)\d{2}\b.*\bpattern\b",
        r"\bbetween (?:19|20)\d{2} and (?:19|20)\d{2}",
        r"\bfrom (?:19|20)\d{2} to (?:19|20)\d{2}",
        r"\bfrom (?:19|20)\d{2} through (?:19|20)\d{2}",
        r"\b(?:19|20)\d{2} through (?:19|20)\d{2}",
        r"\bchange(?:d)?\b.*\bover time\b",
        r"\bhow (?:has|did)\b.*\bchange",
        r"\bcompare counties",
    ],
    AnalysisIntent.COUNTY_RANKING: [
        r"\bhighest\b",
        r"\blowest\b",
        r"\brank",
        r"\btop counties",
        r"\bworst counties",
        r"\bbest counties",
        r"\blead(?:s)? the nation\b",
        r"\bwhich counties lead\b",
        r"\bwhere\b.*\bhighest\b",
    ],
    AnalysisIntent.LONG_TERM_CHANGE: [
        r"\blong-term",
        r"\blong term",
        r"\bimproved most",
        r"\bworsened most",
        r"\bincrease since",
        r"\bdecrease since",
    ],
    AnalysisIntent.COUNTY_PROFILE: [
        r"\bprofile\b",
        r"\btell me about\b.*\bcounty\b",
        r"\bsummarize\b.*\bcounty\b",
        r"\bcounty overview",
        r"\boverview\b.*\bcounty\b",
        r"\boverview of\b.*\bcounty\b",
    ],
}


def _find_years(
    text: str,
) -> list[int]:
    """
    Extract explicit four-digit years from a research question.

    Years outside the supported analytical period are still
    extracted so they can be rejected with a precise validation
    message later.
    """
    return sorted(
        {
            int(value)
            for value in re.findall(
                r"\b((?:19|20)\d{2})\b",
                text,
            )
        }
    )


def _append_group(
    entities: dict[str, object],
    group_name: str,
) -> None:
    """
    Append a demographic group without creating duplicates.
    """
    groups = entities.setdefault(
        "demographic_groups",
        [],
    )

    if not isinstance(groups, list):
        groups = []
        entities["demographic_groups"] = groups

    if group_name not in groups:
        groups.append(
            group_name
        )


def _extract_age_groups(
    text: str,
) -> list[str]:
    """
    Extract validated age-group labels from question text.

    Examples:
    - "ages 40 to 44 and 65 to 69"
    - "50 to 54 versus 70 to 74"
    """
    age_groups = []

    matches = re.findall(
        r"\b("
        r"(?:20|25|30|35|40|45|50|55|60|65|70|75|80)"
        r")\s+to\s+("
        r"(?:24|29|34|39|44|49|54|59|64|69|74|79|84)"
        r")\b",
        text.casefold(),
    )

    for start, end in matches:
        label = (
            f"{start} to {end}"
        )

        if label not in age_groups:
            age_groups.append(
                label
            )

    if re.search(
        r"\b85\s*(?:plus|\+)\b",
        text.casefold(),
    ):
        age_groups.append(
            "85 plus"
        )

    return age_groups


def _extract_race_groups(
    text: str,
) -> list[str]:
    """
    Extract supported race/ethnicity groups in the order
    they appear in the research question.
    """
    lowered = text.casefold()

    matches: list[
        tuple[int, str]
    ] = []

    patterns = [
        (
            (
                r"\b(?:non[- ]latino\s+)?"
                r"american indian(?:\s+or\s+alaska native)?\b"
                r"|\balaska native\b"
                r"|\baian\b"
            ),
            (
                "Non-Latino, American Indian or "
                "Alaska Native"
            ),
        ),
        (
            (
                r"\b(?:non[- ]latino\s+)?"
                r"asian(?:\s+or\s+pacific islander)?\b"
                r"|\bpacific islander\b"
            ),
            (
                "Non-Latino, Asian or "
                "Pacific Islander"
            ),
        ),
        (
            r"\bblack\b",
            "Non-Latino, Black",
        ),
        (
            r"\bwhite\b",
            "Non-Latino, White",
        ),
        (
            r"(?<!non-)(?<!non )\blatino\b",
            "Latino, Any race",
        ),
    ]

    for pattern, group_name in patterns:
        match = re.search(
            pattern,
            lowered,
        )

        if match is not None:
            matches.append(
                (
                    match.start(),
                    group_name,
                )
            )

    matches.sort(
        key=lambda item: item[0]
    )

    groups: list[str] = []

    for _, group_name in matches:
        if group_name not in groups:
            groups.append(
                group_name
            )

    return groups


def _extract_sex_groups(
    text: str,
) -> list[str]:
    """
    Extract supported sex groups in the order they appear
    in the research question.
    """
    lowered = text.casefold()

    matches: list[
        tuple[int, str]
    ] = []

    male_match = re.search(
        r"\bmale(?:s)?\b|\bmen\b",
        lowered,
    )

    if male_match is not None:
        matches.append(
            (
                male_match.start(),
                "Male",
            )
        )

    female_match = re.search(
        r"\bfemale(?:s)?\b|\bwomen\b",
        lowered,
    )

    if female_match is not None:
        matches.append(
            (
                female_match.start(),
                "Female",
            )
        )

    matches.sort(
        key=lambda item: item[0]
    )

    return [
        group_name
        for _, group_name in matches
    ]
    
    
def _extract_entities(
    text: str,
) -> dict[str, object]:
    lowered = text.casefold()

    entities: dict[str, object] = {
        "years": _find_years(text),
    }

    race_groups = _extract_race_groups(
        text
    )

    sex_groups = _extract_sex_groups(
        text
    )

    age_groups = _extract_age_groups(
        text
    )

    if race_groups:
        entities[
            "demographic_groups"
        ] = race_groups

        entities[
            "dimension"
        ] = "Race / ethnicity"

    elif sex_groups:
        entities[
            "demographic_groups"
        ] = sex_groups

        entities[
            "dimension"
        ] = "Sex"

    elif age_groups:
        entities[
            "demographic_groups"
        ] = age_groups

        entities[
            "dimension"
        ] = "Age group"

    elif (
        "race" in lowered
        or "ethnic" in lowered
    ):
        entities[
            "dimension"
        ] = "Race / ethnicity"

    elif (
        "age group" in lowered
        or "older" in lowered
        or re.search(
            r"\bages?\b",
            lowered,
        )
    ):
        entities[
            "dimension"
        ] = "Age group"

    return entities

def classify_question(
    question_text: str,
) -> ClassifiedQuestion:
    cleaned = question_text.strip()

    if not cleaned:
        raise ValueError(
            "The research question cannot be empty."
        )

    question = ResearchQuestion(
        raw_text=cleaned
    )

    lowered = cleaned.casefold()

    scores: dict[
        AnalysisIntent,
        int,
    ] = {
        intent: 0
        for intent in AnalysisIntent
        if intent is not AnalysisIntent.UNKNOWN
    }

    for intent, patterns in (
        INTENT_PATTERNS.items()
    ):
        for pattern in patterns:
            if re.search(
                pattern,
                lowered,
            ):
                scores[
                    intent
                ] += 1

    best_intent = max(
        scores,
        key=scores.get,
    )

    best_score = scores[
        best_intent
    ]

    if best_score == 0:
        return ClassifiedQuestion(
            question=question,
            intent=AnalysisIntent.UNKNOWN,
            confidence=0.0,
            extracted_entities=(
                _extract_entities(
                    cleaned
                )
            ),
            explanation=(
                "No supported analytical intent could "
                "be identified from the question."
            ),
        )

    total_matches = sum(
        scores.values()
    )

    confidence = (
        best_score / total_matches
        if total_matches > 0
        else 0.0
    )

    return ClassifiedQuestion(
        question=question,
        intent=best_intent,
        confidence=round(
            confidence,
            3,
        ),
        extracted_entities=(
            _extract_entities(
                cleaned
            )
        ),
        explanation=(
            f"Matched {best_score} pattern(s) associated "
            f"with {best_intent.value}."
        ),
    )