from __future__ import annotations

import re

from ai.models import (
    AnalysisIntent,
    ClassifiedQuestion,
    ResearchQuestion,
)


# ---------------------------------------------------------------------------
# EpiCounty V1.2 natural-language intent vocabulary
# ---------------------------------------------------------------------------

PROFILE_PATTERNS = [
    r"\bprofile\b",
    r"\boverview\b",
    r"\bsummar(?:y|ize)\b",
    r"\btell me about\b",
    r"\bdescribe\b.*\bcounty\b",
    r"\bhow is\b.*\bcounty\b.*\bdoing\b",
    r"\bhow's\b.*\bcounty\b.*\bdoing\b",
    r"\bwhat is happening in\b.*\bcounty\b",
    r"\bwhat's happening in\b.*\bcounty\b",
    r"\bhealth status\b.*\bcounty\b",
    r"\bhealth picture\b.*\bcounty\b",
]


TREND_PATTERNS = [
    r"\btrend(?:s)?\b",
    r"\bover time\b",
    r"\bover the years\b",
    r"\bthrough the years\b",
    r"\bacross the years\b",

    # Ordinary questions about whether something changed.
    r"\bhow (?:has|have|did)\b.*\bchang(?:e|ed)\b",
    r"\bhas\b.*\bchanged\b",
    r"\bhave\b.*\bchanged\b",
    r"\bdid\b.*\bchange\b",
    r"\bwhat happened to\b.*\bover\b",

    # Ordinary direction-of-change language.
    r"\bhas\b.*\b(?:gone|went)\b.*\b(?:up|down)\b",
    r"\bhave\b.*\b(?:gone|went)\b.*\b(?:up|down)\b",
    r"\b(?:gone|went)\b.*\b(?:up|down)\b",
    r"\bgoing\b.*\bup\b.*\b(?:or|and)\b.*\bdown\b",
    r"\bgoing\b.*\bdown\b.*\b(?:or|and)\b.*\bup\b",
    r"\b(?:rising|falling)\b",
    r"\bgetting (?:better|worse)\b",

    # Explicit temporal change language.
    r"\byear(?:s)?\b.*\bchange",
    r"\bchange(?:d|s)?\b.*\bover time\b",
    r"\bincreas(?:e|ed|ing)\b.*\b(?:since|from|over)\b",
    r"\bdecreas(?:e|ed|ing)\b.*\b(?:since|from|over)\b",
    r"\bris(?:e|en|ing)\b.*\b(?:since|from|over)\b",
    r"\bfall(?:en|ing)?\b.*\b(?:since|from|over)\b",

    # Explicit year ranges.
    r"\bpattern\b.*\b(?:19|20)\d{2}",
    r"\b(?:19|20)\d{2}\b.*\bpattern\b",
    r"\bfrom (?:19|20)\d{2}\s+(?:to|through|-)\s+(?:19|20)\d{2}\b",
    r"\bbetween (?:19|20)\d{2}\s+and\s+(?:19|20)\d{2}\b",
    r"\b(?:19|20)\d{2}\s+(?:to|through|-)\s+(?:19|20)\d{2}\b",
]


RANKING_PATTERNS = [
    r"\bhighest\b",
    r"\blowest\b",
    r"\brank(?:ed|ing|s)?\b",
    r"\btop counties\b",
    r"\bbottom counties\b",
    r"\bworst counties\b",
    r"\bbest counties\b",
    r"\bwhich counties\b.*\b(?:most|least)\b",
    r"\bwhich county\b.*\b(?:most|least)\b",
    r"\bcounties\b.*\b(?:most|least)\b",
    r"\bwhere\b.*\b(?:highest|lowest|worst|best)\b",
    r"\bwhere is\b.*\b(?:most|least)\b",
    r"\bwhere are\b.*\b(?:most|least)\b",
    r"\bwhich counties lead\b",
    r"\blead(?:s)? the nation\b",
    r"\bmost affected counties\b",
    r"\bleast affected counties\b",
    r"\bplaces\b.*\b(?:worst|best|highest|lowest)\b",
]


LONG_TERM_CHANGE_PATTERNS = [
    r"\blong[- ]term\b",
    r"\bimprov(?:e|ed|ing)\b.*\bmost\b",
    r"\bworsen(?:s|ed|ing)?\b.*\bmost\b",
    r"\bincreas(?:e|ed|ing)\b.*\bmost\b.*\bsince\b",
    r"\bdecreas(?:e|ed|ing)\b.*\bmost\b.*\bsince\b",
    r"\bris(?:e|en|ing)\b.*\bmost\b.*\bsince\b",
    r"\bfall(?:en|ing)?\b.*\bmost\b.*\bsince\b",
    r"\bchanged?\b.*\bmost\b.*\bsince\b",
    r"\bbiggest increase\b.*\bsince\b",
    r"\bbiggest decrease\b.*\bsince\b",
    r"\blargest increase\b.*\bsince\b",
    r"\blargest decrease\b.*\bsince\b",
]


COMPARISON_PATTERNS = [
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bversus\b",
    r"\bvs\.?\b",
    r"\bdiffer(?:s|ed|ence|ences)?\b",
    r"\bdifference\b",
    r"\bdisparit(?:y|ies)\b",
    r"\bgap\b",
    r"\bbetween\b",
    r"\bmore affected\b",
    r"\bless affected\b",
    r"\bmore likely\b",
    r"\bless likely\b",
    r"\bhigher\b.*\bthan\b",
    r"\blower\b.*\bthan\b",
    r"\bworse\b.*\bthan\b",
    r"\bbetter\b.*\bthan\b",
]


RACE_GROUP_PATTERNS: list[tuple[str, str]] = [
    (
        (
            r"\b(?:non[- ]latino\s+)?"
            r"american indians?"
            r"(?:\s+or\s+alaska natives?)?\b"
            r"|\balaska natives?\b"
            r"|\baian\b"
            r"|\bamerican indian(?:s)?\b"
        ),
        "Non-Latino, American Indian or Alaska Native",
    ),
    (
        (
            r"\b(?:non[- ]latino\s+)?"
            r"asian(?:s)?"
            r"(?:\s+or\s+pacific islanders?)?\b"
            r"|\bpacific islanders?\b"
            r"|\baapi\b"
        ),
        "Non-Latino, Asian or Pacific Islander",
    ),
    (
        (
            r"\bblacks?\b"
            r"|\bblack people\b"
            r"|\bblack population\b"
            r"|\bafrican americans?\b"
        ),
        "Non-Latino, Black",
    ),
    (
        (
            r"\bwhites?\b"
            r"|\bwhite people\b"
            r"|\bwhite population\b"
            r"|\bcaucasians?\b"
        ),
        "Non-Latino, White",
    ),
    (
        (
            r"(?<!non-)(?<!non )\blatinos?\b"
            r"|(?<!non-)(?<!non )\bhispanics?\b"
        ),
        "Latino, Any race",
    ),
]


SEX_GROUP_PATTERNS: list[tuple[str, str]] = [
    (
        r"\bmales?\b|\bmen\b|\bmale population\b",
        "Male",
    ),
    (
        r"\bfemales?\b|\bwomen\b|\bfemale population\b",
        "Female",
    ),
]


def _find_years(text: str) -> list[int]:
    return sorted(
        {
            int(value)
            for value in re.findall(
                r"\b((?:19|20)\d{2})\b",
                text,
            )
        }
    )


def _normalized_text(text: str) -> str:
    normalized = text.casefold()

    normalized = (
        normalized
        .replace("–", "-")
        .replace("—", "-")
        .replace("’", "'")
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized.strip()


def _matches_any(
    text: str,
    patterns: list[str],
) -> bool:
    return any(
        re.search(pattern, text) is not None
        for pattern in patterns
    )


def _match_count(
    text: str,
    patterns: list[str],
) -> int:
    return sum(
        1
        for pattern in patterns
        if re.search(pattern, text) is not None
    )


def _extract_age_groups(text: str) -> list[str]:
    lowered = _normalized_text(text)

    age_groups: list[str] = []

    matches = re.findall(
        (
            r"\b("
            r"20|25|30|35|40|45|50|55|60|65|70|75|80"
            r")\s*(?:to|-)\s*("
            r"24|29|34|39|44|49|54|59|64|69|74|79|84"
            r")\b"
        ),
        lowered,
    )

    for start, end in matches:
        label = f"{start} to {end}"

        if label not in age_groups:
            age_groups.append(label)

    if re.search(
        r"\b85\s*(?:plus|\+)\b",
        lowered,
    ):
        age_groups.append("85 plus")

    return age_groups


def _extract_pattern_groups(
    text: str,
    patterns: list[tuple[str, str]],
) -> list[str]:
    lowered = _normalized_text(text)

    matches: list[tuple[int, str]] = []

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
            groups.append(group_name)

    return groups


def _extract_race_groups(text: str) -> list[str]:
    return _extract_pattern_groups(
        text,
        RACE_GROUP_PATTERNS,
    )


def _extract_sex_groups(text: str) -> list[str]:
    return _extract_pattern_groups(
        text,
        SEX_GROUP_PATTERNS,
    )


def _extract_entities(
    text: str,
) -> dict[str, object]:
    lowered = _normalized_text(text)

    entities: dict[str, object] = {
        "years": _find_years(text),
    }

    race_groups = _extract_race_groups(text)
    sex_groups = _extract_sex_groups(text)
    age_groups = _extract_age_groups(text)

    if race_groups:
        entities["demographic_groups"] = race_groups
        entities["dimension"] = "Race / ethnicity"

    elif sex_groups:
        entities["demographic_groups"] = sex_groups
        entities["dimension"] = "Sex"

    elif age_groups:
        entities["demographic_groups"] = age_groups
        entities["dimension"] = "Age group"

    elif (
        "race" in lowered
        or "racial" in lowered
        or "ethnic" in lowered
    ):
        entities["dimension"] = "Race / ethnicity"

    elif (
        "sex" in lowered
        or "gender" in lowered
    ):
        entities["dimension"] = "Sex"

    elif (
        "age group" in lowered
        or "older" in lowered
        or re.search(
            r"\bages?\b",
            lowered,
        )
    ):
        entities["dimension"] = "Age group"

    return entities


def _score_intents(
    text: str,
    entities: dict[str, object],
) -> dict[AnalysisIntent, int]:
    scores: dict[AnalysisIntent, int] = {
        intent: 0
        for intent in AnalysisIntent
        if intent is not AnalysisIntent.UNKNOWN
    }

    scores[
        AnalysisIntent.COUNTY_PROFILE
    ] += _match_count(
        text,
        PROFILE_PATTERNS,
    )

    trend_count = _match_count(
        text,
        TREND_PATTERNS,
    )

    scores[
        AnalysisIntent.TREND_COMPARISON
    ] += trend_count

    ranking_count = _match_count(
        text,
        RANKING_PATTERNS,
    )

    scores[
        AnalysisIntent.COUNTY_RANKING
    ] += ranking_count

    long_term_change_count = _match_count(
        text,
        LONG_TERM_CHANGE_PATTERNS,
    )

    demographic_groups = entities.get(
        "demographic_groups",
        [],
    )

    if not isinstance(
        demographic_groups,
        list,
    ):
        demographic_groups = []

    comparison_count = _match_count(
        text,
        COMPARISON_PATTERNS,
    )

    if len(demographic_groups) >= 2:
        scores[
            AnalysisIntent.DEMOGRAPHIC_DISPARITY
        ] += 4

        scores[
            AnalysisIntent.DEMOGRAPHIC_DISPARITY
        ] += comparison_count

    elif entities.get(
        "dimension"
    ) is not None:
        scores[
            AnalysisIntent.DEMOGRAPHIC_DISPARITY
        ] += comparison_count

        if _matches_any(
            text,
            [
                r"\bdisparit(?:y|ies)\b",
                r"\bdifference\b",
                r"\bgap\b",
            ],
        ):
            scores[
                AnalysisIntent.DEMOGRAPHIC_DISPARITY
            ] += 2

    years = entities.get(
        "years",
        [],
    )

    if (
        isinstance(years, list)
        and len(years) >= 2
    ):
        scores[
            AnalysisIntent.TREND_COMPARISON
        ] += 3

    if (
        long_term_change_count == 0
        and re.search(
            r"\bcount(?:y|ies)\b",
            text,
        )
        and re.search(
            (
                r"\b(?:highest|lowest|most|least|"
                r"worst|best|top|bottom)\b"
            ),
            text,
        )
    ):
        scores[
            AnalysisIntent.COUNTY_RANKING
        ] += 2

    if (
        "county" in text
        and _matches_any(
            text,
            [
                r"\btell me\b",
                r"\bhow is\b",
                r"\bhow's\b",
                r"\bdescribe\b",
                r"\boverview\b",
                r"\bsummar",
            ],
        )
    ):
        scores[
            AnalysisIntent.COUNTY_PROFILE
        ] += 2

    national_long_term_request = (
        long_term_change_count > 0
        and (
            re.search(
                r"\bwhich count(?:y|ies)\b",
                text,
            )
            is not None
            or re.search(
                r"\bwhat count(?:y|ies)\b",
                text,
            )
            is not None
            or re.search(
                r"\bwhere\b",
                text,
            )
            is not None
        )
    )

    is_specific_county_temporal = (
        long_term_change_count > 0
        and "county" in text
        and not national_long_term_request
    )

    if national_long_term_request:
        scores[
            AnalysisIntent.TREND_COMPARISON
        ] = 0

        scores[
            AnalysisIntent.COUNTY_RANKING
        ] = 0

        scores[
            AnalysisIntent.LONG_TERM_CHANGE
        ] = 0

    elif is_specific_county_temporal:
        scores[
            AnalysisIntent.TREND_COMPARISON
        ] += 4

    return scores


def _select_intent(
    scores: dict[AnalysisIntent, int],
) -> tuple[AnalysisIntent, int]:
    priority = [
        AnalysisIntent.DEMOGRAPHIC_DISPARITY,
        AnalysisIntent.TREND_COMPARISON,
        AnalysisIntent.COUNTY_RANKING,
        AnalysisIntent.COUNTY_PROFILE,
    ]

    best_intent = AnalysisIntent.UNKNOWN
    best_score = 0

    for intent in priority:
        score = scores.get(
            intent,
            0,
        )

        if score > best_score:
            best_intent = intent
            best_score = score

    return (
        best_intent,
        best_score,
    )


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

    normalized = _normalized_text(
        cleaned
    )

    entities = _extract_entities(
        cleaned
    )

    scores = _score_intents(
        normalized,
        entities,
    )

    (
        best_intent,
        best_score,
    ) = _select_intent(
        scores
    )

    if (
        best_intent is AnalysisIntent.UNKNOWN
        or best_score == 0
    ):
        return ClassifiedQuestion(
            question=question,
            intent=AnalysisIntent.UNKNOWN,
            confidence=0.0,
            extracted_entities=entities,
            explanation=(
                "No supported analytical intent could "
                "be identified from the question."
            ),
        )

    positive_scores = [
        score
        for score in scores.values()
        if score > 0
    ]

    total_positive_score = sum(
        positive_scores
    )

    confidence = (
        best_score / total_positive_score
        if total_positive_score > 0
        else 0.0
    )

    return ClassifiedQuestion(
        question=question,
        intent=best_intent,
        confidence=round(
            confidence,
            3,
        ),
        extracted_entities=entities,
        explanation=(
            "Deterministic natural-language routing selected "
            f"{best_intent.value} with score {best_score}."
        ),
    )
