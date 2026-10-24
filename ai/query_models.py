"""Passive Phase 3 query contracts; no parser, resolver, SQL, or execution path.

Normalization accepts canonical structured populations, not natural language.
A ResolvedQuery holds the researcher's normalized intent, including explicit
unresolved/unavailable values. It does not certify observed data availability.
CapabilityDecision is deliberately incapable of authorizing execution here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re

from ai.capabilities import (
    APPROVED_PLACES_IHME_PAIRS, CAPABILITIES, MEASUREMENT_YEAR_BOUNDS, REGISTRY_VERSION,
    CapabilityState, GeographyMode, Source,
)
from ai.evidence_semantics import Attribution, AttributionStatus

QUERY_CONTRACT_VERSION = "1.3.0-phase3.1"
AGE_STANDARDIZED_20_PLUS = "20+, age standardized"


class QueryContractError(ValueError):
    """An internally inconsistent or noncanonical structured query."""


class Dimension(str, Enum):
    SEX = "sex"
    AGE = "age"
    RACE_ETHNICITY = "race_ethnicity"
    RURALITY = "rurality"


class ValueState(str, Enum):
    UNSPECIFIED = "unspecified"
    TOTAL = "total_population"
    SUBGROUP = "subgroup"
    UNAVAILABLE = "unavailable"


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise QueryContractError(f"{name} must be a nonempty string")


def _tuple(value: object, item_type: type, name: str) -> None:
    if not isinstance(value, tuple) or any(not isinstance(x, item_type) for x in value):
        raise QueryContractError(f"{name} must be an immutable tuple of {item_type.__name__}")


def _year(value: int, name: str) -> None:
    if type(value) is not int or not 1900 <= value <= 2200:
        raise QueryContractError(f"{name} must be an integer year")


@dataclass(frozen=True, kw_only=True)
class PopulationValue:
    dimension: Dimension
    state: ValueState
    value: str | None = None
    unavailable_reason: str | None = None
    requested_value: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, Dimension) or not isinstance(self.state, ValueState):
            raise QueryContractError("Explicit Dimension and ValueState enums required")
        if self.state is ValueState.SUBGROUP:
            _text(self.value, "canonical subgroup")
            if self.value != self.value.strip() or self.value.casefold() in {
                "total", "both", "all", "unknown", "unspecified", "unavailable",
            }:
                raise QueryContractError("Use explicit value states, not sentinel subgroup labels")
            if self.dimension is Dimension.SEX and self.value not in {"Female", "Male"}:
                raise QueryContractError("Canonical sex subgroup must be Female or Male")
            if self.dimension is Dimension.AGE and self.value != AGE_STANDARDIZED_20_PLUS:
                match = re.fullmatch(r"(\d{1,3})(?:-(\d{1,3})|(\+))", self.value)
                if not match:
                    raise QueryContractError("Canonical age must be a band, open band or standardized basis")
                first, last = int(match[1]), int(match[2]) if match[2] else 120
                canonical = f"{first}-{last}" if match[2] else f"{first}+"
                if not 0 <= first <= last <= 120 or canonical != self.value:
                    raise QueryContractError("Invalid canonical age band")
            if self.dimension is Dimension.RURALITY and self.value not in {
                "Metro", "Nonmetro", "Nonmetro adjacent", "Nonmetro not adjacent",
                *(str(i) for i in range(1, 10)),
            }:
                raise QueryContractError("Unknown RUCC grouping value")
        elif self.value is not None:
            raise QueryContractError("Only subgroup states may contain a subgroup value")
        if self.state is ValueState.UNAVAILABLE:
            _text(self.unavailable_reason, "unavailable_reason")
            if self.requested_value is not None:
                _text(self.requested_value, "requested unavailable value")
        elif self.requested_value is not None:
            raise QueryContractError("Only unavailable values may retain an unresolved requested value")
        elif self.unavailable_reason is not None:
            raise QueryContractError("Only unavailable values may contain an unavailable reason")

    @classmethod
    def unspecified(cls, dimension: Dimension) -> PopulationValue:
        return cls(dimension=dimension, state=ValueState.UNSPECIFIED)

    @classmethod
    def total(cls, dimension: Dimension) -> PopulationValue:
        # Total age means all ages, NOT the age-standardized 20+ category.
        return cls(dimension=dimension, state=ValueState.TOTAL)

    @classmethod
    def subgroup(cls, dimension: Dimension, value: str) -> PopulationValue:
        return cls(dimension=dimension, state=ValueState.SUBGROUP, value=value)

    @classmethod
    def unavailable(cls, dimension: Dimension, reason: str, *,
                    requested_value: str | None = None) -> PopulationValue:
        return cls(dimension=dimension, state=ValueState.UNAVAILABLE, unavailable_reason=reason,
                   requested_value=requested_value)

    @property
    def age_specific(self) -> bool:
        return (self.dimension is Dimension.AGE and self.state is ValueState.SUBGROUP
                and self.value != AGE_STANDARDIZED_20_PLUS)


@dataclass(frozen=True, kw_only=True)
class DemographicStratum:
    sex: PopulationValue = field(default_factory=lambda: PopulationValue.unspecified(Dimension.SEX))
    age: PopulationValue = field(default_factory=lambda: PopulationValue.unspecified(Dimension.AGE))
    race_ethnicity: PopulationValue = field(default_factory=lambda: PopulationValue.unspecified(
        Dimension.RACE_ETHNICITY))

    def __post_init__(self) -> None:
        for dimension in (Dimension.SEX, Dimension.AGE, Dimension.RACE_ETHNICITY):
            value = self.get(dimension)
            if not isinstance(value, PopulationValue) or value.dimension is not dimension:
                raise QueryContractError(f"{dimension.value} must have its own typed population value")

    def get(self, dimension: Dimension) -> PopulationValue:
        if not isinstance(dimension, Dimension) or dimension not in (
            Dimension.SEX, Dimension.AGE, Dimension.RACE_ETHNICITY
        ):
            raise QueryContractError("Rurality belongs in GeographySpec, not DemographicStratum")
        return getattr(self, dimension.value)


@dataclass(frozen=True, kw_only=True)
class ComparisonSpec:
    dimension: Dimension
    group_a: PopulationValue
    group_b: PopulationValue

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, Dimension):
            raise QueryContractError("Unsupported comparison dimension")
        for group in (self.group_a, self.group_b):
            if not isinstance(group, PopulationValue) or group.dimension is not self.dimension:
                raise QueryContractError("Comparison groups must match the comparison dimension")
            if group.state is not ValueState.SUBGROUP:
                raise QueryContractError("Comparison requires two explicit subgroup values")
        if self.group_a == self.group_b:
            raise QueryContractError("Duplicate comparison group values")
        if self.dimension is Dimension.AGE:
            if not self.group_a.age_specific or not self.group_b.age_specific:
                raise QueryContractError("Age comparison requires age-specific groups")
            def bounds(value: PopulationValue) -> tuple[int, int]:
                parts = value.value.rstrip('+').split('-')
                return int(parts[0]), int(parts[1]) if len(parts) == 2 else 120
            a, b = bounds(self.group_a), bounds(self.group_b)
            if max(a[0], b[0]) <= min(a[1], b[1]):
                raise QueryContractError("Overlapping age comparison groups")
        if self.dimension is Dimension.RURALITY:
            if {self.group_a.value, self.group_b.value} & {"Nonmetro"} and (
                {self.group_a.value, self.group_b.value}
                & {"Nonmetro adjacent", "Nonmetro not adjacent"}
            ):
                raise QueryContractError("Overlapping rurality comparison groups")


def normalize_comparison(
    group_a: DemographicStratum, group_b: DemographicStratum,
) -> tuple[DemographicStratum, ComparisonSpec]:
    """Factor two canonical strata into common filters and one comparison.

    No aliases, catalog IDs, inferred defaults or omitted filters. Reconstructing
    both input strata from the result must preserve every input field exactly.
    """
    if not isinstance(group_a, DemographicStratum) or not isinstance(group_b, DemographicStratum):
        raise QueryContractError("Normalization requires two DemographicStratum contracts")
    dimensions = (Dimension.SEX, Dimension.AGE, Dimension.RACE_ETHNICITY)
    differing = [dim for dim in dimensions if group_a.get(dim) != group_b.get(dim)]
    if not differing:
        raise QueryContractError("Duplicate population groups")
    if len(differing) != 1:
        raise QueryContractError("Only one comparison dimension; never discard differing fixed filters")
    dimension = differing[0]
    comparison = ComparisonSpec(dimension=dimension, group_a=group_a.get(dimension),
                                group_b=group_b.get(dimension))
    fixed = {dim.value: (PopulationValue.unspecified(dim) if dim is dimension
                        else group_a.get(dim)) for dim in dimensions}
    return DemographicStratum(**fixed), comparison


_RURALITY_MODES = frozenset({GeographyMode.METRO, GeographyMode.RUCC_CODE,
                             GeographyMode.RUCC_ADJACENCY})


class MissingGeographyPolicy(str, Enum):
    REPORT_EXCLUSIONS = "report_missing_rucc_as_excluded"


@dataclass(frozen=True, kw_only=True)
class GeographySpec:
    mode: GeographyMode
    county_fips: tuple[str, ...] = ()
    state_fips: tuple[str, ...] = ()
    rurality_filter: PopulationValue = field(default_factory=lambda: PopulationValue.unspecified(
        Dimension.RURALITY))
    classification_year: int | None = None
    missingness_policy: MissingGeographyPolicy = MissingGeographyPolicy.REPORT_EXCLUSIONS
    county_universe: str = field(default="existing_eligible_current_counties", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.mode, GeographyMode):
            raise QueryContractError("Unsupported geography mode")
        if not isinstance(self.missingness_policy, MissingGeographyPolicy):
            raise QueryContractError("Explicit geography missingness policy required")
        for name, width in (("county_fips", 5), ("state_fips", 2)):
            values = getattr(self, name)
            _tuple(values, str, name)
            if len(set(values)) != len(values) or any(not re.fullmatch(rf"\d{{{width}}}", v) for v in values):
                raise QueryContractError(f"{name} requires unique canonical FIPS strings")
        if self.mode is GeographyMode.COUNTY and len(self.county_fips) != 1:
            raise QueryContractError("Single-county geography requires exactly one county")
        if self.state_fips and any(fips[:2] not in self.state_fips for fips in self.county_fips):
            raise QueryContractError("County filters conflict with requested state filters")
        if not isinstance(self.rurality_filter, PopulationValue) or (
            self.rurality_filter.dimension is not Dimension.RURALITY
        ):
            raise QueryContractError("Rurality filter must have the rurality dimension")
        if self.requires_rurality:
            if type(self.classification_year) is not int or self.classification_year != 2023:
                raise QueryContractError("Rurality requires explicit RUCC classification year 2023")
        elif self.classification_year is not None:
            raise QueryContractError("Do not imply RUCC dependency without rurality")
        if (self.rurality_filter.state is ValueState.SUBGROUP and self.group_values
                and self.rurality_filter.value not in self.group_values):
            raise QueryContractError("Rurality filter does not match the grouping mode")

    @property
    def requires_rurality(self) -> bool:
        return self.mode in _RURALITY_MODES or self.rurality_filter.state is not ValueState.UNSPECIFIED

    @property
    def group_values(self) -> tuple[str, ...]:
        if self.mode is GeographyMode.METRO:
            return ("Metro", "Nonmetro")
        if self.mode is GeographyMode.RUCC_CODE:
            return tuple(str(i) for i in range(1, 10))
        if self.mode is GeographyMode.RUCC_ADJACENCY:
            return ("Metro", "Nonmetro adjacent", "Nonmetro not adjacent")
        return ()


class ReleasePolicy(str, Enum):
    SOURCE_OBSERVATION = "source_observation_year"
    CANONICAL_MEASUREMENT = "canonical_non_carry_forward_measurement_year"
    RELEASE_SNAPSHOT = "explicit_release_snapshot"


@dataclass(frozen=True, kw_only=True)
class SourceTime:
    source: Source
    years: tuple[int, ...]
    release_policy: ReleasePolicy
    release_year: int | None = None

    def __post_init__(self) -> None:
        if self.source not in (Source.IHME, Source.PLACES) or not isinstance(self.source, Source):
            raise QueryContractError("RUCC classification time belongs in GeographySpec")
        _tuple(self.years, int, "source years")
        for year in self.years:
            _year(year, "observation year")
        if tuple(sorted(set(self.years))) != self.years:
            raise QueryContractError("Source years must be sorted and unique; no silent truncation")
        if not isinstance(self.release_policy, ReleasePolicy):
            raise QueryContractError("Explicit ReleasePolicy required")
        if self.release_year is not None:
            _year(self.release_year, "release_year")
            if any(year > self.release_year for year in self.years):
                raise QueryContractError("Measurement year cannot follow release year")
        if self.source is Source.IHME and self.release_policy is not ReleasePolicy.SOURCE_OBSERVATION:
            raise QueryContractError("IHME time uses observation years")
        if self.source is Source.PLACES:
            if self.release_policy is ReleasePolicy.SOURCE_OBSERVATION:
                raise QueryContractError("PLACES needs explicit measurement/release selection semantics")
            if self.release_policy is ReleasePolicy.RELEASE_SNAPSHOT and self.release_year is None:
                raise QueryContractError("PLACES release snapshot needs a release year")

    @classmethod
    def year_range(cls, *, source: Source, first: int, last: int,
                   release_policy: ReleasePolicy, release_year: int | None = None) -> SourceTime:
        _year(first, "first")
        _year(last, "last")
        if first > last:
            raise QueryContractError("Reversed year range")
        return cls(source=source, years=tuple(range(first, last + 1)),
                   release_policy=release_policy, release_year=release_year)


class TimeAlignment(str, Enum):
    SINGLE_SOURCE = "single_health_source"
    SAME_YEARS = "same_measurement_years"
    CONTEXTUAL = "distinct_source_years_context_only"


@dataclass(frozen=True, kw_only=True)
class TimeSpec:
    sources: tuple[SourceTime, ...]
    alignment: TimeAlignment
    alignment_note: str = ""

    def __post_init__(self) -> None:
        _tuple(self.sources, SourceTime, "source times")
        if not self.sources or len({item.source for item in self.sources}) != len(self.sources):
            raise QueryContractError("TimeSpec needs unique health sources")
        if not isinstance(self.alignment, TimeAlignment):
            raise QueryContractError("Explicit TimeAlignment required")
        if len(self.sources) == 1:
            if self.alignment is not TimeAlignment.SINGLE_SOURCE:
                raise QueryContractError("One health source requires single-source alignment")
        else:
            if self.alignment is TimeAlignment.SINGLE_SOURCE:
                raise QueryContractError("Cross-source evidence requires explicit alignment")
            same = len({item.years for item in self.sources}) == 1
            if (self.alignment is TimeAlignment.SAME_YEARS) != same:
                raise QueryContractError("Alignment must preserve actual source year selections")
            if self.alignment is TimeAlignment.CONTEXTUAL:
                _text(self.alignment_note, "contextual alignment_note")
            if any(item.release_policy is ReleasePolicy.RELEASE_SNAPSHOT for item in self.sources):
                raise QueryContractError("Cross-source time requires canonical measurement-year evidence")


@dataclass(frozen=True, kw_only=True)
class SourceConcept:
    source: Source
    concept_id: int | str
    name: str
    dataset_version: str
    attribution: Attribution = field(default_factory=Attribution)

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source) or self.source is Source.RUCC:
            raise QueryContractError("A health concept cannot use RUCC as an outcome")
        _text(self.name, "concept name")
        _text(self.dataset_version, "dataset_version")
        if self.source is Source.IHME:
            if type(self.concept_id) is not int or self.concept_id < 1:
                raise QueryContractError("IHME concept requires a canonical positive cause ID")
        elif not isinstance(self.concept_id, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", self.concept_id):
            raise QueryContractError("PLACES concept requires a canonical measure ID")
        if not isinstance(self.attribution, Attribution):
            raise QueryContractError("Explicit Attribution contract required")
        if self.source is Source.PLACES and self.attribution.status is not AttributionStatus.NOT_APPLICABLE:
            raise QueryContractError("PLACES prevalence does not have risk attribution")
        if self.source is Source.IHME and self.attribution.status is AttributionStatus.NOT_APPLICABLE:
            raise QueryContractError("IHME attribution must be explicit unknown or verified")
        if self.attribution.status is AttributionStatus.VERIFIED:
            if self.dataset_version.casefold() in {"unknown", "pending", "provenance-pending"}:
                raise QueryContractError("Verified attribution requires an identified import version")
            if any((ref.dataset, ref.dataset_version) != (self.dataset, self.dataset_version)
                   for ref in self.attribution.provenance):
                raise QueryContractError("Attribution provenance must match the concept dataset/version")

    @property
    def dataset(self) -> str:
        return "ihme.burden" if self.source is Source.IHME else "places.estimates"


class QueryOperation(str, Enum):
    COMPARE_GROUPS = "compare_groups"
    SUMMARIZE_BY_RURALITY = "summarize_by_rurality"


@dataclass(frozen=True, kw_only=True)
class ResolvedQuery:
    capability_key: str
    concepts: tuple[SourceConcept, ...]
    stratum: DemographicStratum
    geography: GeographySpec
    time: TimeSpec
    operation: QueryOperation
    comparison: ComparisonSpec | None = None
    assumptions: tuple[str, ...] = ()
    availability_fingerprint: str | None = None
    registry_version: str = REGISTRY_VERSION
    version: str = field(default=QUERY_CONTRACT_VERSION, init=False)

    def __post_init__(self) -> None:
        _text(self.capability_key, "capability_key")
        _tuple(self.concepts, SourceConcept, "concepts")
        if not self.concepts or len({c.source for c in self.concepts}) != len(self.concepts):
            raise QueryContractError("Query needs unique source-specific concepts")
        for name, kind in (("stratum", DemographicStratum), ("geography", GeographySpec),
                           ("time", TimeSpec), ("operation", QueryOperation)):
            if not isinstance(getattr(self, name), kind):
                raise QueryContractError(f"Explicit {kind.__name__} required")
        _tuple(self.assumptions, str, "assumptions")
        for assumption in self.assumptions:
            _text(assumption, "assumption")
        if self.availability_fingerprint is not None:
            _text(self.availability_fingerprint, "availability_fingerprint")
        if self.registry_version != REGISTRY_VERSION:
            raise QueryContractError("Stale or unknown registry version")
        if {c.source for c in self.concepts} != {item.source for item in self.time.sources}:
            raise QueryContractError("Concept and time sources must match exactly")
        if self.operation is QueryOperation.COMPARE_GROUPS:
            if not isinstance(self.comparison, ComparisonSpec):
                raise QueryContractError("Group comparison requires ComparisonSpec")
        elif self.comparison is not None or not self.geography.group_values:
            raise QueryContractError("Rurality summary requires grouping and no pair comparison")
        if self.comparison is not None:
            dimension = self.comparison.dimension
            fixed = (self.geography.rurality_filter if dimension is Dimension.RURALITY
                     else self.stratum.get(dimension))
            if fixed.state is not ValueState.UNSPECIFIED:
                raise QueryContractError("Conflicting fixed filter and comparison dimension")
            if dimension is Dimension.RURALITY:
                if not self.geography.group_values or any(
                    group.value not in self.geography.group_values
                    for group in (self.comparison.group_a, self.comparison.group_b)
                ):
                    raise QueryContractError("Rurality comparison must match geographic grouping")
        if len(self.concepts) == 2:
            ihme = next(c for c in self.concepts if c.source is Source.IHME)
            places = next(c for c in self.concepts if c.source is Source.PLACES)
            if ihme.concept_id not in APPROVED_PLACES_IHME_PAIRS.get(places.concept_id, frozenset()):
                raise QueryContractError("Unapproved cross-source concept pair")

    @property
    def required_sources(self) -> frozenset[Source]:
        sources = {concept.source for concept in self.concepts}
        if self.geography.requires_rurality:
            sources.add(Source.RUCC)
        return frozenset(sources)


class DecisionStatus(str, Enum):
    PLANNED = "planned_non_executable"
    CLARIFY = "needs_clarification"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    LEGACY_UNVERIFIED = "legacy_requires_validation"


class DecisionReason(str, Enum):
    PLANNED_VALIDATION_PENDING = "planned_validation_pending"
    MISSING_CONSTRAINT = "missing_constraint"
    DATA_UNAVAILABLE = "data_unavailable"
    YEAR_UNAVAILABLE = "year_unavailable"
    COMBINATION_UNSUPPORTED = "demographic_combination_unsupported"
    SOURCE_MISMATCH = "source_dependencies_unsupported"
    GEOGRAPHY_UNSUPPORTED = "geography_mode_unsupported"
    CAPABILITY_UNSUPPORTED = "capability_unsupported"
    LEGACY_REQUIRES_VALIDATION = "legacy_requires_validation"


@dataclass(frozen=True, kw_only=True)
class CapabilityDecision:
    query: ResolvedQuery
    status: DecisionStatus
    reason: DecisionReason
    explanation: str
    missing_constraints: tuple[str, ...] = ()
    alternatives: tuple[ResolvedQuery, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.query, ResolvedQuery) or not isinstance(self.status, DecisionStatus):
            raise QueryContractError("Typed query and decision status required")
        expected = {
            DecisionStatus.PLANNED: {DecisionReason.PLANNED_VALIDATION_PENDING},
            DecisionStatus.CLARIFY: {DecisionReason.MISSING_CONSTRAINT},
            DecisionStatus.UNAVAILABLE: {DecisionReason.DATA_UNAVAILABLE, DecisionReason.YEAR_UNAVAILABLE},
            DecisionStatus.UNSUPPORTED: {DecisionReason.COMBINATION_UNSUPPORTED,
                                        DecisionReason.SOURCE_MISMATCH, DecisionReason.GEOGRAPHY_UNSUPPORTED,
                                        DecisionReason.CAPABILITY_UNSUPPORTED},
            DecisionStatus.LEGACY_UNVERIFIED: {DecisionReason.LEGACY_REQUIRES_VALIDATION},
        }
        if not isinstance(self.reason, DecisionReason) or self.reason not in expected[self.status]:
            raise QueryContractError("Inconsistent capability decision status/reason")
        _text(self.explanation, "decision explanation")
        _tuple(self.missing_constraints, str, "missing constraints")
        for constraint in self.missing_constraints:
            _text(constraint, "missing constraint")
        _tuple(self.alternatives, ResolvedQuery, "alternatives")
        if (self.status is DecisionStatus.CLARIFY) != bool(self.missing_constraints):
            raise QueryContractError("Clarification needs explicit missing constraints")
        cap = CAPABILITIES.get(self.query.capability_key)
        if self.status is DecisionStatus.PLANNED and (cap is None or cap.state is not CapabilityState.PLANNED):
            raise QueryContractError("Planned decision requires a planned registry capability")
        if self.status is DecisionStatus.LEGACY_UNVERIFIED and (cap is None or not cap.executable):
            raise QueryContractError("Legacy decision cannot activate planned capabilities")

    @property
    def executable(self) -> bool:
        # Phase 3 has no execution-authorizing state, including for legacy entries.
        return False


def assess_query_contract(query: ResolvedQuery) -> CapabilityDecision:
    """Describe structural readiness only; preserve the exact requested query.

    No availability lookup, execution, default insertion, filter repair or
    automatic alternative. The multidimensional shape envelope is deliberately
    limited to the three planned capabilities; legacy routing stays untouched.
    """
    if not isinstance(query, ResolvedQuery):
        raise QueryContractError("Typed ResolvedQuery required")

    def decide(status: DecisionStatus, reason: DecisionReason, explanation: str,
               missing: tuple[str, ...] = ()) -> CapabilityDecision:
        return CapabilityDecision(query=query, status=status, reason=reason,
                                  explanation=explanation, missing_constraints=missing)

    def unsupported(explanation: str, reason: DecisionReason = DecisionReason.COMBINATION_UNSUPPORTED):
        return decide(DecisionStatus.UNSUPPORTED, reason, explanation)

    cap = CAPABILITIES.get(query.capability_key)
    if cap is None or cap.state is CapabilityState.UNSUPPORTED:
        return unsupported("The requested capability is unsupported; the query was retained.",
                           DecisionReason.CAPABILITY_UNSUPPORTED)
    stratum, comparison, geography = query.stratum, query.comparison, query.geography
    values = (stratum.sex, stratum.age, stratum.race_ethnicity, geography.rurality_filter)
    if any(value.state is ValueState.UNAVAILABLE for value in values):
        return decide(DecisionStatus.UNAVAILABLE, DecisionReason.DATA_UNAVAILABLE,
                      "A requested fixed population/geography is explicitly unavailable; no filter was removed.")
    dimension = comparison.dimension if comparison else None
    sex_specific = stratum.sex.state is ValueState.SUBGROUP or dimension is Dimension.SEX
    age_specific = stratum.age.age_specific or dimension is Dimension.AGE
    race_specific = stratum.race_ethnicity.state is ValueState.SUBGROUP or dimension is Dimension.RACE_ETHNICITY
    if (sex_specific and age_specific and geography.requires_rurality) or race_specific:
        return unsupported("Unvalidated demographic intersections are not supported; all requested filters were retained.")
    if query.required_sources != frozenset(cap.sources):
        return unsupported("Required health/geography evidence does not match this capability.",
                           DecisionReason.SOURCE_MISMATCH)
    if geography.mode not in cap.geography_modes:
        return unsupported("The requested geography mode is not in this capability's envelope.",
                           DecisionReason.GEOGRAPHY_UNSUPPORTED)
    if cap.state is CapabilityState.LEGACY_EXECUTABLE:
        return decide(DecisionStatus.LEGACY_UNVERIFIED, DecisionReason.LEGACY_REQUIRES_VALIDATION,
                      "Legacy execution is not authorized by Phase 3 contracts; use the unchanged legacy pipeline.")

    # Explicit required defaults are checked, never inserted. Compared fields
    # stay unspecified in fixed filters because ComparisonSpec holds their values.
    requirements: list[tuple[str, PopulationValue, str]] = [
        ("race_ethnicity", stratum.race_ethnicity, "total"),
    ]
    if cap.key == "sex_age":
        if query.operation is not QueryOperation.COMPARE_GROUPS or dimension not in {Dimension.SEX, Dimension.AGE}:
            return unsupported("Sex × age needs exactly one sex/age comparison with the other fixed.")
        requirements.append(("sex", stratum.sex, "subgroup") if dimension is Dimension.AGE
                            else ("age", stratum.age, "age_specific"))
    elif cap.key == "sex_rurality":
        if dimension not in {None, Dimension.SEX, Dimension.RURALITY}:
            return unsupported("Sex × rurality does not permit an age comparison.")
        requirements.append(("age", stratum.age, "standardized"))
        if dimension is not Dimension.SEX:
            requirements.append(("sex", stratum.sex, "subgroup"))
    elif cap.key == "age_rurality":
        if dimension not in {None, Dimension.AGE, Dimension.RURALITY}:
            return unsupported("Age × rurality does not permit a sex comparison.")
        requirements.append(("sex", stratum.sex, "total"))
        if dimension is not Dimension.AGE:
            requirements.append(("age", stratum.age, "age_specific"))
    else:
        return unsupported("This planned capability has no validated contract envelope.")

    missing = []
    for name, value, expected in requirements:
        if value.state is ValueState.UNSPECIFIED:
            missing.append(f"{name}: explicit {expected} selection required")
        elif not {
            "total": value.state is ValueState.TOTAL,
            "subgroup": value.state is ValueState.SUBGROUP,
            "age_specific": value.age_specific,
            "standardized": value.state is ValueState.SUBGROUP and value.value == AGE_STANDARDIZED_20_PLUS,
        }[expected]:
            return unsupported(f"Requested {name} filter does not match the {expected} requirement; it was retained.")
    for source_time in query.time.sources:
        if not source_time.years:
            missing.append(f"{source_time.source.value}: observation years required")
        first, last = MEASUREMENT_YEAR_BOUNDS[source_time.source]
        if any(year < first or year > last for year in source_time.years):
            return decide(DecisionStatus.UNAVAILABLE, DecisionReason.YEAR_UNAVAILABLE,
                          "Requested years exceed the cataloged source bounds; none were silently replaced.")
    if missing:
        return decide(DecisionStatus.CLARIFY, DecisionReason.MISSING_CONSTRAINT,
                      "The request needs explicit selections; no population or time defaults were inserted.",
                      tuple(missing))
    return decide(DecisionStatus.PLANNED, DecisionReason.PLANNED_VALIDATION_PENDING,
                  "The normalized shape is intended for V1.3; analytics and observed coverage remain unvalidated and disabled.")
