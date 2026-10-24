"""Immutable, passive source semantics and controlled semantic claim labels.

Not connected to legacy evidence/report generation in Phase 2. Provenance
records are explicit attestations supplied by a future verified import layer;
this module neither verifies external documents nor infers attribution from IDs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ai.capabilities import APPROVED_PLACES_IHME_PAIRS, Source

SEMANTICS_VERSION = "1.3.0-phase2.1"


class SemanticsError(ValueError):
    """Metadata or a proposed semantic claim exceeds the evidence contract."""


class AttributionStatus(str, Enum):
    UNKNOWN = "unknown_provenance_pending"
    VERIFIED = "verified"
    NOT_APPLICABLE = "not_applicable"


class UncertaintyType(str, Enum):
    IHME_UI = "uncertainty_interval"
    PLACES_CI = "confidence_interval"
    NONE = "not_applicable"


class Adjustment(str, Enum):
    AGE_STANDARDIZED = "age_standardized"
    AGE_SPECIFIC = "age_specific"
    AGE_ADJUSTED = "age_adjusted"
    CRUDE = "crude"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class EvidenceRole(str, Enum):
    YLL_RATE = "yll_rate"
    MODELED_PREVALENCE = "modeled_prevalence"
    CLASSIFICATION = "geographic_classification"


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SemanticsError(f"{name} must be an explicit nonempty string")


def _tuple(value: object, item_type: type, name: str) -> None:
    if not isinstance(value, tuple) or not all(isinstance(x, item_type) for x in value):
        raise SemanticsError(f"{name} must be an immutable tuple of {item_type.__name__}")


def _year(value: int | None, name: str) -> None:
    if value is not None and (type(value) is not int or value < 1900 or value > 2200):
        raise SemanticsError(f"{name} must be an explicit year or None")


@dataclass(frozen=True, kw_only=True)
class ProvenanceReference:
    dataset: str
    dataset_version: str
    reference: str
    verification_note: str

    def __post_init__(self) -> None:
        for name in ("dataset", "dataset_version", "reference", "verification_note"):
            _text(getattr(self, name), name)


@dataclass(frozen=True, kw_only=True)
class Attribution:
    status: AttributionStatus = AttributionStatus.UNKNOWN
    label: str | None = None
    provenance: tuple[ProvenanceReference, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, AttributionStatus):
            raise SemanticsError("Explicit AttributionStatus required")
        _tuple(self.provenance, ProvenanceReference, "attribution provenance")
        if self.status is AttributionStatus.VERIFIED:
            _text(self.label, "verified attribution label")
            if not self.provenance:
                raise SemanticsError("Verified attribution requires dataset/import provenance")
        elif self.label is not None or self.provenance:
            raise SemanticsError("Unknown/not-applicable attribution cannot carry a claim label")


@dataclass(frozen=True, kw_only=True)
class EvidenceSemantics:
    dataset_version: str
    concept: str
    population_basis: str
    unit: str
    adjustment: Adjustment
    measurement_year: int | None
    release_year: int | None
    uncertainty_level: float | None
    provenance: tuple[ProvenanceReference, ...] = ()
    attribution: Attribution = field(default_factory=Attribution)
    version: str = field(default=SEMANTICS_VERSION, init=False)
    source: Source = field(init=False)
    dataset: str = field(init=False)
    measure: str = field(init=False)
    metric: str = field(init=False)
    role: EvidenceRole = field(init=False)
    uncertainty_type: UncertaintyType = field(init=False)

    def __post_init__(self) -> None:
        if type(self) is EvidenceSemantics:
            raise SemanticsError("Use a source-specific evidence contract")
        for name in ("dataset_version", "concept", "population_basis", "unit"):
            _text(getattr(self, name), name)
        if not isinstance(self.adjustment, Adjustment):
            raise SemanticsError("Explicit Adjustment required")
        _year(self.measurement_year, "measurement_year")
        _year(self.release_year, "release_year")
        if self.uncertainty_level is not None and (
            type(self.uncertainty_level) not in (int, float)
            or not 0 < self.uncertainty_level < 1
        ):
            raise SemanticsError("Interval level must be a probability or None (unknown)")
        _tuple(self.provenance, ProvenanceReference, "provenance")
        if not isinstance(self.attribution, Attribution):
            raise SemanticsError("Explicit Attribution contract required")
        for ref in self.provenance + self.attribution.provenance:
            if (ref.dataset, ref.dataset_version) != (self.dataset, self.dataset_version):
                raise SemanticsError("Provenance must match this dataset and version")
        if self.attribution.status is AttributionStatus.VERIFIED:
            if self.dataset_version.casefold() in {"unknown", "pending", "provenance-pending"}:
                raise SemanticsError("Verified attribution requires an identified dataset version")


@dataclass(frozen=True, kw_only=True)
class IHMEYLLSemantics(EvidenceSemantics):
    cause_id: int
    source: Source = field(default=Source.IHME, init=False)
    dataset: str = field(default="ihme.burden", init=False)
    measure: str = field(default="YLLs (Years of Life Lost)", init=False)
    metric: str = field(default="Rate", init=False)
    role: EvidenceRole = field(default=EvidenceRole.YLL_RATE, init=False)
    uncertainty_type: UncertaintyType = field(default=UncertaintyType.IHME_UI, init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if type(self.cause_id) is not int or self.cause_id < 1:
            raise SemanticsError("IHME cause_id must be a positive integer")
        if self.measurement_year is None:
            raise SemanticsError("IHME evidence requires its observation year")
        if self.adjustment not in {
            Adjustment.AGE_STANDARDIZED, Adjustment.AGE_SPECIFIC, Adjustment.UNKNOWN,
        }:
            raise SemanticsError("Unsupported IHME YLL adjustment")
        if self.attribution.status is AttributionStatus.NOT_APPLICABLE:
            raise SemanticsError("IHME attribution must be unknown or verified, not elided")
        if self.unit not in {"unknown", "YLL per 100,000"}:
            raise SemanticsError("IHME YLL unit must be verified YLL scale or explicit unknown")
        # Unit is supplied explicitly, including 'unknown' pending verification.
        # Neither the measure nor the metric IDs prove unit scale or attribution.


@dataclass(frozen=True, kw_only=True)
class PLACESPrevalenceSemantics(EvidenceSemantics):
    measure_id: str
    carry_forward: bool
    source: Source = field(default=Source.PLACES, init=False)
    dataset: str = field(default="places.estimates", init=False)
    measure: str = field(default="Modeled prevalence", init=False)
    metric: str = field(default="Percent", init=False)
    role: EvidenceRole = field(default=EvidenceRole.MODELED_PREVALENCE, init=False)
    uncertainty_type: UncertaintyType = field(default=UncertaintyType.PLACES_CI, init=False)
    attribution: Attribution = field(default_factory=lambda: Attribution(
        status=AttributionStatus.NOT_APPLICABLE))

    def __post_init__(self) -> None:
        super().__post_init__()
        _text(self.measure_id, "PLACES measure_id")
        if self.measure_id != self.measure_id.strip().upper():
            raise SemanticsError("PLACES measure_id must be canonical")
        if self.measurement_year is None or self.release_year is None:
            raise SemanticsError("PLACES measurement and release years must be separate and explicit")
        if self.measurement_year > self.release_year:
            raise SemanticsError("Measurement year cannot follow release year")
        if self.unit != "Percent" or self.adjustment not in {
            Adjustment.AGE_ADJUSTED, Adjustment.CRUDE,
        }:
            raise SemanticsError("PLACES is crude/age-adjusted prevalence in Percent")
        if type(self.carry_forward) is not bool:
            raise SemanticsError("Explicit carry_forward boolean required")
        if self.attribution.status is not AttributionStatus.NOT_APPLICABLE:
            raise SemanticsError("PLACES prevalence has no risk-attribution claim")


@dataclass(frozen=True, kw_only=True)
class RUCCSemantics(EvidenceSemantics):
    classification_year: int = field(default=2023, init=False)
    source: Source = field(default=Source.RUCC, init=False)
    dataset: str = field(default="geography.rucc_2023", init=False)
    measure: str = field(default="Rural-Urban Continuum Code", init=False)
    metric: str = field(default="Geographic classification", init=False)
    role: EvidenceRole = field(default=EvidenceRole.CLASSIFICATION, init=False)
    uncertainty_type: UncertaintyType = field(default=UncertaintyType.NONE, init=False)
    attribution: Attribution = field(default_factory=lambda: Attribution(
        status=AttributionStatus.NOT_APPLICABLE))

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.measurement_year is not None or self.release_year is not None:
            raise SemanticsError("RUCC uses classification_year, not health observation/release years")
        if self.unit != "Category" or self.adjustment is not Adjustment.NOT_APPLICABLE:
            raise SemanticsError("RUCC is categorical geography, not a health rate")
        if self.uncertainty_level is not None:
            raise SemanticsError("RUCC classification has no health-outcome interval")
        if self.attribution.status is not AttributionStatus.NOT_APPLICABLE:
            raise SemanticsError("RUCC attribution is not applicable")


class AlignmentMode(str, Enum):
    SAME_YEAR = "same_measurement_year"
    CONTEXTUAL = "different_source_years_context_only"


@dataclass(frozen=True, kw_only=True)
class CrossSourceSemantics:
    """Separate source semantics, never a synthesized epidemiological metric."""
    items: tuple[EvidenceSemantics, ...]
    geography_basis: str
    alignment: AlignmentMode
    alignment_note: str
    interpretation: str = field(default="descriptive_noncausal", init=False)
    version: str = field(default=SEMANTICS_VERSION, init=False)

    def __post_init__(self) -> None:
        _tuple(self.items, EvidenceSemantics, "source items")
        _text(self.geography_basis, "geography_basis")
        _text(self.alignment_note, "alignment_note")
        if not isinstance(self.alignment, AlignmentMode):
            raise SemanticsError("Explicit source time alignment required")
        if any(type(item) not in (IHMEYLLSemantics, PLACESPrevalenceSemantics, RUCCSemantics)
               for item in self.items):
            raise SemanticsError("Bundle items must use the supported source contracts")
        sources = [item.source for item in self.items]
        if len(sources) != len(set(sources)) or set(sources) not in (
            {Source.IHME, Source.PLACES}, {Source.IHME, Source.PLACES, Source.RUCC},
        ):
            raise SemanticsError("Bundle requires separate IHME and PLACES, optionally RUCC")
        ihme = next(item for item in self.items if isinstance(item, IHMEYLLSemantics))
        places = next(item for item in self.items if isinstance(item, PLACESPrevalenceSemantics))
        if ihme.cause_id not in APPROVED_PLACES_IHME_PAIRS.get(places.measure_id, frozenset()):
            raise SemanticsError("Unapproved PLACES-IHME concept pair")
        if places.carry_forward:
            raise SemanticsError("Canonical cross-source evidence excludes carry-forward estimates")
        same = ihme.measurement_year == places.measurement_year
        if (self.alignment is AlignmentMode.SAME_YEAR) != same:
            raise SemanticsError("Time alignment must reflect the actual source years")


class ClaimKind(str, Enum):
    YLL = "yll_rate"
    ATTRIBUTED_YLL = "attributed_yll_rate"
    BURDEN = "yll_burden"
    PREVALENCE = "modeled_prevalence"
    CLASSIFICATION = "geographic_classification"


def semantic_claim_label(
    evidence: EvidenceSemantics, kind: ClaimKind, *,
    required_attribution: str | None = None,
) -> str:
    """Controlled labels only, not free-text interpretation or numerical claims.

    All attribution-dependent labels pass the same provenance gate. Supplying
    an attribution requirement with ANY claim kind cannot bypass the gate.
    """
    if not isinstance(kind, ClaimKind):
        raise SemanticsError("Explicit ClaimKind required")
    if not isinstance(evidence, (IHMEYLLSemantics, PLACESPrevalenceSemantics, RUCCSemantics)):
        raise SemanticsError("A supported source-specific contract is required")
    attribution = evidence.attribution
    if kind is ClaimKind.ATTRIBUTED_YLL or required_attribution is not None:
        if attribution.status is not AttributionStatus.VERIFIED:
            raise SemanticsError("Attribution-dependent claims require verified provenance")
        if not isinstance(evidence, IHMEYLLSemantics):
            raise SemanticsError("Attribution-dependent YLL claims require IHME evidence")
        if required_attribution is not None and required_attribution != attribution.label:
            raise SemanticsError("Requested attribution is not supported by verified provenance")
    if isinstance(evidence, IHMEYLLSemantics):
        if kind not in {ClaimKind.YLL, ClaimKind.ATTRIBUTED_YLL, ClaimKind.BURDEN}:
            raise SemanticsError("IHME YLL cannot be relabeled as prevalence/classification")
        suffix = (f"; attributable to {attribution.label}"
                  if attribution.status is AttributionStatus.VERIFIED
                  else "; attribution unknown, provenance pending")
        return f"IHME YLL rate for {evidence.concept}{suffix}"
    if isinstance(evidence, PLACESPrevalenceSemantics):
        if kind is not ClaimKind.PREVALENCE:
            raise SemanticsError("PLACES modeled prevalence is not YLL burden")
        return f"CDC PLACES modeled prevalence of {evidence.concept}"
    if kind is not ClaimKind.CLASSIFICATION:
        raise SemanticsError("RUCC is a geographic classification, not a health outcome")
    return f"USDA RUCC {evidence.classification_year} geographic classification"
