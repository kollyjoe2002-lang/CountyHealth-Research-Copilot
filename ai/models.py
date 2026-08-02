from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AnalysisIntent(str, Enum):
    COUNTY_PROFILE = "county_profile"
    TREND_COMPARISON = "trend_comparison"
    DEMOGRAPHIC_DISPARITY = "demographic_disparity"
    COUNTY_RANKING = "county_ranking"
    LONG_TERM_CHANGE = "long_term_change"
    UNKNOWN = "unknown"


class DemographicDimension(str, Enum):
    RACE_ETHNICITY = "Race / ethnicity"
    SEX = "Sex"
    AGE_GROUP = "Age group"


@dataclass(frozen=True)
class ResearchQuestion:
    raw_text: str


@dataclass
class ClassifiedQuestion:
    question: ResearchQuestion
    intent: AnalysisIntent
    confidence: float
    extracted_entities: dict[str, Any] = field(
        default_factory=dict
    )
    explanation: str = ""


@dataclass
class AnalysisStep:
    step_number: int
    operation: str
    function_name: str
    parameters: dict[str, Any]
    purpose: str


@dataclass
class AnalysisPlan:
    question: ResearchQuestion
    intent: AnalysisIntent
    steps: list[AnalysisStep]
    assumptions: list[str] = field(default_factory=list)
    unresolved_items: list[str] = field(default_factory=list)


@dataclass
class EvidenceItem:
    evidence_type: str
    title: str
    data: Any
    source_function: str
    parameters: dict[str, Any]
    interpretation_note: str = ""


@dataclass
class EvidenceBundle:
    question: ResearchQuestion
    intent: AnalysisIntent
    items: list[EvidenceItem]
    warnings: list[str] = field(default_factory=list)


@dataclass
class ResearchReport:
    title: str
    question: str
    executive_summary: str
    methods: str
    findings: list[str]
    limitations: list[str]
    evidence: EvidenceBundle