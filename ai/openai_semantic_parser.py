from __future__ import annotations

import json

from ai.models import (
    AnalysisIntent,
    ResearchQuestion,
    SemanticAnalysisRequest,
)

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover
    OpenAI = None


class SemanticParserError(RuntimeError):
    """
    Raised when semantic parsing cannot produce a valid
    structured analytical request.
    """


class OpenAISemanticParser:
    """
    Translate ordinary natural-language health questions into
    constrained analytical requests.

    This component performs no analytics, executes no SQL, and
    does not access the CountyHealth database.
    """

    def __init__(
        self,
        *,
        model: str = "gpt-5.6",
    ) -> None:
        if OpenAI is None:
            raise SemanticParserError(
                "The openai package is not installed."
            )

        self.model = model
        self.client = OpenAI()

    def parse(
        self,
        question: ResearchQuestion,
    ) -> SemanticAnalysisRequest:
        intent_values = [
            intent.value
            for intent in AnalysisIntent
        ]

        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": intent_values,
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
                "county_name": {
                    "type": ["string", "null"],
                },
                "cause_name": {
                    "type": ["string", "null"],
                },
                "year": {
                    "type": ["integer", "null"],
                },
                "start_year": {
                    "type": ["integer", "null"],
                },
                "end_year": {
                    "type": ["integer", "null"],
                },
                "demographic_dimension": {
                    "type": ["string", "null"],
                    "enum": [
                        "Race / ethnicity",
                        "Sex",
                        "Age group",
                        None,
                    ],
                },
                "demographic_groups": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
                "direction": {
                    "type": ["string", "null"],
                },
                "geographic_scope": {
                    "type": ["string", "null"],
                },
                "needs_clarification": {
                    "type": "boolean",
                },
                "clarification_question": {
                    "type": ["string", "null"],
                },
                "explanation": {
                    "type": "string",
                },
            },
            "required": [
                "intent",
                "confidence",
                "county_name",
                "cause_name",
                "year",
                "start_year",
                "end_year",
                "demographic_dimension",
                "demographic_groups",
                "direction",
                "geographic_scope",
                "needs_clarification",
                "clarification_question",
                "explanation",
            ],
        }

        instructions = """
You are the semantic parsing layer for EpiCounty, a
county-level public-health research system.

Your only task is to determine what analytical question the
user appears to be asking and return the required structured
representation.

You do not perform epidemiological analysis.
You do not calculate results.
You do not generate SQL.
You do not invent database identifiers.
You do not answer the research question.

Interpret ordinary conversational language, including
informal wording, abbreviations, incomplete sentences, and
questions written by users without epidemiology training.

Supported analytical intents:

county_profile:
A general overview of a particular county.

county_cause_snapshot:
The burden or status of a particular disease or cause in a
particular county at one point in time. If no year is stated,
leave year null.

trend_comparison:
How a particular disease or cause changes over time,
especially within a named county.

demographic_disparity:
Comparison of disease burden between demographic groups.

county_ranking:
Questions asking which counties have the highest, lowest,
most, least, or otherwise ranked disease burden.

long_term_change:
Cross-county questions asking which counties improved,
worsened, increased, decreased, or changed most over a
long period.

unknown:
Use only when the analytical meaning genuinely cannot be
mapped to one of the supported intents.

Important distinctions:

"Breast cancer in Milwaukee County, Wisconsin"
is county_cause_snapshot.

"Diabetes in Milwaukee County in 2019"
is county_cause_snapshot.

"Predict diabetes in Milwaukee County in 2035"
is unknown.

"What is the breast cancer burden in Milwaukee County?"
is county_cause_snapshot.

"How has breast cancer changed in Milwaukee County?"
is trend_comparison.

"Which counties have the highest breast cancer burden?"
is county_ranking.

"Which counties improved most since 2000?"
is long_term_change.

"How is Milwaukee County doing?"
is county_profile.

"Compare breast cancer between Black and White people"
is demographic_disparity.

Extract what the user actually said. Do not invent a county,
cause, year, demographic group, direction, or geographic
scope that was not expressed or strongly implied.

If the question is understandable but important information
is genuinely missing, set needs_clarification to true and
provide one short clarification question.

Unsupported analytical operations:

Forecasting, prediction, projection, causal inference, statistical
significance testing, hypothesis testing, and other analytical
operations that are not represented by the supported intents must
return intent = "unknown".

Do not reinterpret or downgrade an unsupported analytical operation
into a supported descriptive one merely because the question also
mentions a county, cause, year, or demographic group.

Examples:

"Predict diabetes rates in Milwaukee County in 2035"
→ unknown

"Forecast breast cancer burden in Albany County next year"
→ unknown

"What will stroke rates be in 2030?"
→ unknown

"Did obesity cause the diabetes increase?"
→ unknown

"Is the Black-White difference statistically significant?"
→ unknown

A future year does not automatically make a question a snapshot.
If the user asks what will happen, requests a prediction, forecast,
projection, or future estimate, use unknown.

The parser may recognize requests that the downstream
analytical engine cannot currently execute. Do not distort
the user's meaning merely to fit available capabilities.

When demographic_dimension is present, use only these exact values:

Race / ethnicity
Sex
Age group

Use geographic_scope only for a geographic scope that is
analytically broader than a specifically named county, such
as a state, region, or national scope.

If a county is named and the state appears only as part of
that county's name, do not separately populate
geographic_scope with that state.
"""

        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=question.raw_text,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "epicounty_semantic_request",
                        "strict": True,
                        "schema": schema,
                    }
                },
            )

            parsed = json.loads(
                response.output_text
            )

        except Exception as exc:
            raise SemanticParserError(
                "Semantic parsing failed: "
                f"{exc}"
            ) from exc

        try:
            intent = AnalysisIntent(
                parsed["intent"]
            )

            return SemanticAnalysisRequest(
                question=question,
                intent=intent,
                confidence=float(
                    parsed["confidence"]
                ),
                county_name=parsed["county_name"],
                cause_name=parsed["cause_name"],
                year=parsed["year"],
                start_year=parsed["start_year"],
                end_year=parsed["end_year"],
                demographic_dimension=(
                    parsed["demographic_dimension"]
                ),
                demographic_groups=list(
                    parsed["demographic_groups"]
                ),
                direction=parsed["direction"],
                geographic_scope=(
                    parsed["geographic_scope"]
                ),
                needs_clarification=bool(
                    parsed["needs_clarification"]
                ),
                clarification_question=(
                    parsed["clarification_question"]
                ),
                explanation=parsed["explanation"],
            )

        except Exception as exc:
            raise SemanticParserError(
                "Semantic parser returned an invalid "
                "structured request."
            ) from exc