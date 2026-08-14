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
        r"\bcompare\b.*\bblack\b.*\bwhite\b",
        r"\bcompare\b.*\bmale\b.*\bfemale\b",
        r"\brace\b",
        r"\bethnic",
        r"\bsex difference",
        r"\bage group",
    ],
    AnalysisIntent.TREND_COMPARISON: [
        r"\btrend",
        r"\bover time",
        r"\bbetween (?:19|20)\d{2} and (?:19|20)\d{2}",
        r"\bfrom (?:19|20)\d{2} to (?:19|20)\d{2}",
        r"\bchange over",
        r"\bcompare counties",
    ],
    AnalysisIntent.COUNTY_RANKING: [
        r"\bhighest\b",
        r"\blowest\b",
        r"\brank",
        r"\btop counties",
        r"\bworst counties",
        r"\bbest counties",
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


def _extract_entities(text: str) -> dict[str, object]:
    lowered = text.casefold()

    entities: dict[str, object] = {
        "years": _find_years(text),
    }

    if "black" in lowered:
        entities.setdefault(
            "demographic_groups",
            [],
        ).append("Non-Latino, Black")

    if "white" in lowered:
        entities.setdefault(
            "demographic_groups",
            [],
        ).append("Non-Latino, White")

    if "male" in lowered:
        entities.setdefault(
            "demographic_groups",
            [],
        ).append("Male")

    if "female" in lowered:
        entities.setdefault(
            "demographic_groups",
            [],
        ).append("Female")

    if "race" in lowered or "ethnic" in lowered:
        entities["dimension"] = "Race / ethnicity"

    elif "male" in lowered or "female" in lowered:
        entities["dimension"] = "Sex"

    elif "age group" in lowered or "older" in lowered:
        entities["dimension"] = "Age group"

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

    scores: dict[AnalysisIntent, int] = {
        intent: 0
        for intent in AnalysisIntent
        if intent is not AnalysisIntent.UNKNOWN
    }

    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lowered):
                scores[intent] += 1

    best_intent = max(
        scores,
        key=scores.get,
    )

    best_score = scores[best_intent]

    if best_score == 0:
        return ClassifiedQuestion(
            question=question,
            intent=AnalysisIntent.UNKNOWN,
            confidence=0.0,
            extracted_entities=_extract_entities(
                cleaned
            ),
            explanation=(
                "No supported analytical intent could "
                "be identified from the question."
            ),
        )

    total_matches = sum(scores.values())

    confidence = (
        best_score / total_matches
        if total_matches > 0
        else 0.0
    )

    return ClassifiedQuestion(
        question=question,
        intent=best_intent,
        confidence=round(confidence, 3),
        extracted_entities=_extract_entities(
            cleaned
        ),
        explanation=(
            f"Matched {best_score} pattern(s) associated "
            f"with {best_intent.value}."
        ),
    )