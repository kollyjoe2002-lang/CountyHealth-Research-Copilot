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
    resolved_context: dict[str, Any] = field(default_factory=dict)


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
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchReport:
    title: str
    question: str
    executive_summary: str
    methods: str
    findings: list[str]
    limitations: list[str]
    evidence: EvidenceBundle

@dataclass(frozen=True)
class EvidenceClaim:
    """
    A deterministic analytical claim derived from validated evidence.

    EvidenceClaim objects are the trusted factual units that may be
    supplied to downstream narrative interpretation.
    """

    claim_id: str
    text: str
    source_function: str
    value: Any = None
    units: str = ""
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class EntailmentLabel(str, Enum):
    ENTAILED = "ENTAILED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"


@dataclass(frozen=True)
class EntailmentJudgment:
    """
    Semantic judgment of whether generated language follows from
    its cited deterministic evidence.
    """

    label: EntailmentLabel
    rationale: str
    
    
@dataclass
class InterpretationInput:
    """
    Evidence-grounded input contract for narrative interpretation.

    The interpretation layer must operate only on these validated
    claims and must not independently execute analytics.
    """

    question: ResearchQuestion
    intent: AnalysisIntent
    claims: list[EvidenceClaim]
    context: dict[str, Any] = field(
        default_factory=dict
    )
    warnings: list[str] = field(
        default_factory=list
    )
    limitations: list[str] = field(
        default_factory=list
    )


@dataclass(frozen=True)
class InterpretationStatement:
    """
    One narrative statement with explicit supporting evidence claims.
    """

    text: str
    supporting_claim_ids: list[str]
    
    
@dataclass(frozen=True)
class GroundedAnswer:
    """
    Direct answer with explicit supporting evidence claims.
    """

    text: str
    supporting_claim_ids: list[str]
    
    
@dataclass
class InterpretationResult:
    """
    Structured narrative interpretation of validated evidence.
    """

    direct_answer: GroundedAnswer
    interpretation: list[InterpretationStatement]
    limitations: list[str]
    follow_up_questions: list[str]
    warnings: list[str] = field(
        default_factory=list
    )
