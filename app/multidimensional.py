"""Isolated deterministic IHME multidimensional reader (Phase 4).

Explicit database path, read-only connection and one read snapshot per call.
No imports into the legacy APIs/assistant; fixture success does not activate
capabilities or verify real coverage, units, or risk-attribution provenance.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from enum import Enum
import math
from pathlib import Path
import re
from statistics import mean, median

import duckdb

from ai.capabilities import (
    DIMENSION_RULES, MULTIDIMENSIONAL_RELATIONS as RELATIONS,
    MULTIDIMENSIONAL_SOURCE_STATUSES, MULTIDIMENSIONAL_YLL_FILTER, Source,
)
from ai.evidence_semantics import (
    Adjustment, AttributionStatus, IHMEYLLSemantics,
)
from ai.query_models import (
    AGE_STANDARDIZED_20_PLUS, DecisionStatus, DemographicStratum, Dimension,
    PopulationValue, QueryOperation, ResolvedQuery, ValueState, assess_query_contract,
)


ANALYTICS_VERSION = "1.3.0-phase4.1"


class MultidimensionalError(ValueError):
    """Invalid request or warehouse data; never reinterpret the research question."""


class DuplicateAnalyticalKeyError(MultidimensionalError):
    """More than one source record for a requested analytical key."""


class ObservationStatus(str, Enum):
    AVAILABLE = "available"
    ABSENT_ROW = "absent_row"
    NULL_ESTIMATE = "null_estimate"
    UNAVAILABLE_COMBINATION = "unavailable_combination"
    SOURCE_SUPPRESSED = "source_declared_suppression"


class GeographyStatus(str, Enum):
    ELIGIBLE = "eligible"
    MISSING_RUCC = "missing_rucc_classification"
    OUTSIDE_FILTER = "outside_requested_rurality"


@dataclass(frozen=True)
class StratumDefinition:
    key: str
    population: DemographicStratum
    catalog_ids: tuple[tuple[str, int], ...]
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class StratumObservation:
    fips: str
    location_name: str
    year: int
    group: str
    rurality_group: str | None
    geography_status: GeographyStatus
    status: ObservationStatus
    value: float | None
    lower: float | None
    upper: float | None


@dataclass(frozen=True)
class StratumValues:
    query: ResolvedQuery
    groups: tuple[StratumDefinition, ...]
    observations: tuple[StratumObservation, ...]
    semantics: tuple[IHMEYLLSemantics, ...]
    source_status_metadata_present: bool
    geography_note: str | None
    warnings: tuple[str, ...]
    version: str = ANALYTICS_VERSION


@dataclass(frozen=True)
class PairedCoverage:
    year: int
    rurality_group: str | None
    candidate_counties: int
    eligible_counties: int
    pre_join_group_a_available: int
    pre_join_group_b_available: int
    group_a_available: int
    group_b_available: int
    complete_paired_counties: int
    excluded_counties: int
    outcome_excluded_counties: int
    missing_rucc_counties: int
    outside_geography_counties: int
    paired_coverage_percent: float | None
    universe_retention_percent: float | None
    # Mutually exclusive primary reasons reconcile to excluded_counties.
    primary_exclusions: tuple[tuple[str, int], ...]
    # A and B status counts are separate and may overlap at county level.
    group_a_status_counts: tuple[tuple[ObservationStatus, int], ...]
    group_b_status_counts: tuple[tuple[ObservationStatus, int], ...]


@dataclass(frozen=True)
class CountyComparison:
    fips: str
    location_name: str
    year: int
    rurality_group: str | None
    group_a_value: float
    group_b_value: float
    group_a_lower: float | None
    group_a_upper: float | None
    group_b_lower: float | None
    group_b_upper: float | None
    signed_gap: float
    absolute_gap_magnitude: float
    relative_gap_percent: float | None
    # No difference interval can be inferred from the marginal intervals.


@dataclass(frozen=True)
class ComparisonResult:
    values: StratumValues
    comparisons: tuple[CountyComparison, ...]
    coverage: tuple[PairedCoverage, ...]
    coverage_by_rurality: tuple[PairedCoverage, ...]


@dataclass(frozen=True)
class RuralityCoverage:
    year: int
    rurality_group: str | None
    candidate_counties: int
    eligible_counties: int
    pre_join_observations_available: int
    observations_available: int
    missing_outcome_observations: int
    missing_rucc_counties: int
    outside_geography_counties: int
    excluded_counties: int
    coverage_percent: float | None
    universe_retention_percent: float | None
    status_counts: tuple[tuple[ObservationStatus, int], ...]
    primary_exclusions: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class RuralitySummary:
    coverage: RuralityCoverage
    county_weighted_mean: float | None
    county_weighted_median: float | None
    estimate_basis: str = "Each available county has equal weight; not population weighted"


@dataclass(frozen=True)
class RuralityResult:
    values: StratumValues
    summaries: tuple[RuralitySummary, ...]
    coverage: tuple[RuralityCoverage, ...]


_DIMENSION_NAMES = {
    Dimension.SEX: "Sex", Dimension.AGE: "Age group", Dimension.RACE_ETHNICITY: "Race / ethnicity",
}


def _validate(query: ResolvedQuery) -> None:
    decision = assess_query_contract(query)
    if query.capability_key not in {"sex_age", "sex_rurality", "age_rurality"} or (
        decision.status is not DecisionStatus.PLANNED
    ):
        raise MultidimensionalError(f"Query is not in the isolated analytical envelope: {decision.reason.value}")
    if len(query.concepts) != 1 or query.concepts[0].source is not Source.IHME:
        raise MultidimensionalError("Phase 4 reads IHME health evidence only, plus RUCC where requested")
    if query.concepts[0].attribution.status is not AttributionStatus.UNKNOWN:
        raise MultidimensionalError("Dataset attribution is not independently verified by this reader; require unknown provenance")


def _population_label(population: DemographicStratum) -> str:
    return "; ".join(f"{dimension.value}={value.value if value.state is ValueState.SUBGROUP else 'Total population'}"
                     for dimension in (Dimension.SEX, Dimension.AGE, Dimension.RACE_ETHNICITY)
                     for value in (population.get(dimension),))


def _catalog_label(value: PopulationValue) -> str:
    if value.state is ValueState.TOTAL:
        labels = {Dimension.SEX: "Both", Dimension.RACE_ETHNICITY: "Total"}
        if value.dimension not in labels:
            raise MultidimensionalError("All-ages total must not substitute for an explicit age basis")
        return labels[value.dimension]
    if value.state is not ValueState.SUBGROUP:
        raise MultidimensionalError("All analytical filters must be explicit")
    if value.dimension is Dimension.AGE:
        if value.value == AGE_STANDARDIZED_20_PLUS:
            return "20 plus, age standardized"
        if value.value.endswith('+'):
            return value.value[:-1] + " plus"
        return value.value.replace('-', ' to ')
    return value.value


def _definitions(connection, query: ResolvedQuery) -> tuple[StratumDefinition, ...]:
    comparison = query.comparison
    if comparison and comparison.dimension in {Dimension.SEX, Dimension.AGE}:
        populations = tuple((key, replace(query.stratum, **{comparison.dimension.value: group}))
                            for key, group in (("A", comparison.group_a), ("B", comparison.group_b)))
    else:
        populations = (("value", query.stratum),)
    definitions = []
    # Resolve only three small existing dimension catalogs, not a warehouse-wide
    # SELECT DISTINCT or hard-coded demographic IDs. Preserve exact filters.
    catalog_cache = {}
    for key, population in populations:
        ids, unavailable = [], []
        for dimension in (Dimension.SEX, Dimension.AGE, Dimension.RACE_ETHNICITY):
            rule = next(rule for rule in DIMENSION_RULES if rule.name == _DIMENSION_NAMES[dimension])
            relation = RELATIONS[dimension.value]
            label = _catalog_label(population.get(dimension))
            cache_key = (dimension, label)
            if cache_key not in catalog_cache:
                rows = connection.execute(
                    f"SELECT {relation.column(rule.id_column)}, {relation.column(rule.name_column)} "
                    f"FROM {relation.qualified_name} WHERE {relation.column(rule.name_column)} = ?",
                    [label],
                ).fetchall()
                if len(rows) > 1:
                    raise DuplicateAnalyticalKeyError(f"Ambiguous dimension catalog entry: {dimension.value}={label}")
                if rows and (type(rows[0][0]) is not int or rows[0][0] < 1):
                    raise MultidimensionalError("Invalid demographic catalog identifier")
                catalog_cache[cache_key] = rows[0][0] if rows else None
            value = catalog_cache[cache_key]
            if value is None:
                unavailable.append(f"No catalog entry for {dimension.value}={label}")
            else:
                ids.append((rule.id_column, value))
        definitions.append(StratumDefinition(key, population, tuple(ids), "; ".join(unavailable) or None))
    signatures = [tuple(sorted(definition.catalog_ids)) for definition in definitions
                  if not definition.unavailable_reason]
    if len(signatures) != len(set(signatures)):
        raise DuplicateAnalyticalKeyError("Distinct requested strata map to the same catalog IDs")
    return tuple(definitions)


def _county_scope(query: ResolvedQuery) -> tuple[str, list]:
    relation = RELATIONS["counties"]
    clauses, parameters = [], []
    for field, selected in (("fips", query.geography.county_fips), ("state_fips", query.geography.state_fips)):
        if selected:
            clauses.append(f"{relation.column(field, 'g')} IN ({','.join('?' for _ in selected)})")
            parameters.extend(selected)
    return (" AND ".join(clauses) if clauses else "TRUE"), parameters


def _counties(connection, query: ResolvedQuery) -> tuple[tuple[str, str], ...]:
    relation = RELATIONS["counties"]
    scope, parameters = _county_scope(query)
    rows = connection.execute(
        f"SELECT {relation.column('fips', 'g')}, {relation.column('location_name', 'g')} "
        f"FROM {relation.qualified_name} AS g WHERE {scope} ORDER BY {relation.column('fips', 'g')}",
        parameters,
    ).fetchall()
    seen = set()
    for fips, name in rows:
        if not isinstance(fips, str) or not re.fullmatch(r"\d{5}", fips) or not isinstance(name, str) or not name:
            raise MultidimensionalError("Invalid county lookup record")
        if fips in seen:
            raise DuplicateAnalyticalKeyError(f"Duplicate eligible county key: {fips}")
        seen.add(fips)
    if query.geography.county_fips and set(query.geography.county_fips) - seen:
        raise MultidimensionalError("An explicitly selected county is outside the eligible county universe")
    return tuple(rows)


def _rucc(connection, query: ResolvedQuery, counties: tuple[tuple[str, str], ...]):
    if not query.geography.requires_rurality:
        return {fips: (None, GeographyStatus.ELIGIBLE) for fips, _ in counties}
    relation = RELATIONS["rucc"]
    lookup = RELATIONS["counties"]
    scope, parameters = _county_scope(query)
    rows = connection.execute(
        f"SELECT {relation.column('fips', 'r')}, {relation.column('rucc_code', 'r')}, "
        f"{relation.column('source_year', 'r')} FROM {relation.qualified_name} AS r "
        f"WHERE {relation.column('fips', 'r')} IN (SELECT {lookup.column('fips', 'g')} "
        f"FROM {lookup.qualified_name} AS g WHERE {scope})", parameters,
    ).fetchall()
    by_fips = {}
    for fips, code, year in rows:
        if fips in by_fips:
            raise DuplicateAnalyticalKeyError(f"Duplicate RUCC key: {fips}")
        if year != 2023 or type(year) is not int:
            raise MultidimensionalError("RUCC evidence must explicitly be the 2023 classification")
        if code is not None and (type(code) is not int or not 1 <= code <= 9):
            raise MultidimensionalError("Invalid RUCC code; do not silently recategorize")
        group = (None if code is None else "Metro" if code <= 3 else
                 "Nonmetro adjacent" if code in {4, 6, 8} else "Nonmetro not adjacent")
        by_fips[fips] = group
    wanted = query.geography.rurality_filter
    selected = ({wanted.value} if wanted.state is ValueState.SUBGROUP else set(query.geography.group_values))
    if query.comparison and query.comparison.dimension is Dimension.RURALITY:
        selected &= {query.comparison.group_a.value, query.comparison.group_b.value}
    return {fips: (by_fips.get(fips), GeographyStatus.MISSING_RUCC if by_fips.get(fips) is None
                   else GeographyStatus.ELIGIBLE if by_fips[fips] in selected else GeographyStatus.OUTSIDE_FILTER)
            for fips, _ in counties}


def _status_column(connection) -> bool:
    relation = RELATIONS["burden"]
    rows = connection.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema=? AND table_name=?",
        [relation.schema, relation.table],
    ).fetchall()
    columns = dict(rows)
    if "source_status" in columns and columns["source_status"] != "VARCHAR":
        raise MultidimensionalError("Optional source_status must use the declared normalized VARCHAR status contract")
    return "source_status" in columns


def _burden_rows(connection, query: ResolvedQuery, definitions: tuple[StratumDefinition, ...],
                 status_present: bool) -> dict:
    relation, lookup = RELATIONS["burden"], RELATIONS["counties"]
    valid = [definition for definition in definitions if not definition.unavailable_reason]
    if not valid:
        return {}
    strata, parameters = [], []
    for definition in valid:
        strata.append("(" + " AND ".join(f"{relation.column(column, 'b')}=?" for column, _ in definition.catalog_ids) + ")")
        parameters.extend(value for _, value in definition.catalog_ids)
    years = query.time.sources[0].years
    conditions = ["(" + " OR ".join(strata) + ")", f"{relation.column('cause_id', 'b')}=?",
                  f"{relation.column('year', 'b')} IN ({','.join('?' for _ in years)})"]
    parameters.extend([query.concepts[0].concept_id, *years])
    for column, value in MULTIDIMENSIONAL_YLL_FILTER:
        conditions.append(f"{relation.column(column, 'b')}=?")
        parameters.append(value)
    scope, scope_parameters = _county_scope(query)
    conditions.append(f"{relation.column('fips', 'b')} IN (SELECT {lookup.column('fips', 'g')} "
                      f"FROM {lookup.qualified_name} AS g WHERE {scope})")
    parameters.extend(scope_parameters)
    fields = ("fips", "year", "sex_id", "age_group_id", "race_id", "val", "lower", "upper")
    select = ", ".join(relation.column(field, 'b') for field in fields)
    select += ", " + (relation.column("source_status", "b") if status_present else "NULL")
    rows = connection.execute(f"SELECT {select} FROM {relation.qualified_name} AS b WHERE "
                              + " AND ".join(conditions), parameters).fetchall()
    keyed = {}
    for row in rows:
        key = tuple(row[:5])
        if key in keyed:
            raise DuplicateAnalyticalKeyError(f"Duplicate IHME analytical key: {key}")
        keyed[key] = row[5:]
    return keyed


def _observed(raw: tuple | None, unavailable: bool):
    if unavailable:
        return ObservationStatus.UNAVAILABLE_COMBINATION, None, None, None
    if raw is None:
        return ObservationStatus.ABSENT_ROW, None, None, None
    value, lower, upper, source_status = raw
    if source_status is not None and source_status not in MULTIDIMENSIONAL_SOURCE_STATUSES:
        raise MultidimensionalError("Unrecognized explicit source_status; no inferred suppression")
    if source_status in {"suppressed", "unavailable"}:
        status = (ObservationStatus.SOURCE_SUPPRESSED if source_status == "suppressed"
                  else ObservationStatus.UNAVAILABLE_COMBINATION)
        return status, None, None, None
    if value is None:
        return ObservationStatus.NULL_ESTIMATE, None, None, None
    for number in (value, lower, upper):
        if number is not None and (type(number) not in (int, float) or not math.isfinite(number)):
            raise MultidimensionalError("Non-finite or invalid outcome/interval value")
    if value < 0 or (lower is not None and lower > value) or (upper is not None and upper < value):
        raise MultidimensionalError("Invalid YLL rate or marginal uncertainty bounds")
    return ObservationStatus.AVAILABLE, float(value), lower, upper


def get_stratum_values(query: ResolvedQuery, *, database_path: Path) -> StratumValues:
    """Read all requested county × year × stratum cells before outcome/geo exclusions.

    Only the three planned shapes are accepted. This is an isolated developer
    API and is deliberately absent from the Research Assistant allowlist.
    """
    _validate(query)
    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError(f"Explicit analytical database does not exist: {path}")
    connection = duckdb.connect(str(path), read_only=True, config={"enable_external_access": "false"})
    try:
        connection.execute("BEGIN TRANSACTION")
        counties = _counties(connection, query)
        definitions = _definitions(connection, query)
        rucc = _rucc(connection, query, counties)
        status_present = _status_column(connection)
        rows = _burden_rows(connection, query, definitions, status_present)
        observations, semantics = [], []
        for year in query.time.sources[0].years:
            for definition in definitions:
                population = definition.population
                age_specific = population.age.age_specific
                semantics.append(IHMEYLLSemantics(
                    dataset_version=query.concepts[0].dataset_version,
                    cause_id=query.concepts[0].concept_id, concept=query.concepts[0].name,
                    population_basis=_population_label(population), unit="unknown",
                    adjustment=Adjustment.AGE_SPECIFIC if age_specific else Adjustment.AGE_STANDARDIZED,
                    measurement_year=year, release_year=query.time.sources[0].release_year,
                    uncertainty_level=None, attribution=query.concepts[0].attribution,
                ))
                ids = dict(definition.catalog_ids)
                for fips, name in counties:
                    raw = (rows.get((fips, year, ids["sex_id"], ids["age_group_id"], ids["race_id"]))
                           if not definition.unavailable_reason else None)
                    status, value, lower, upper = _observed(raw, bool(definition.unavailable_reason))
                    group, geo_status = rucc[fips]
                    observations.append(StratumObservation(fips, name, year, definition.key, group,
                                                           geo_status, status, value, lower, upper))
        note = ("USDA RUCC 2023 geographic classification is a fixed lens applied to the selected IHME year(s); "
                "it does not describe historical rural-status change." if query.geography.requires_rurality else None)
        return StratumValues(query, definitions, tuple(observations), tuple(semantics), status_present, note, (
            "Real-data coverage/uniqueness and provenance activation gates remain pending.",
            "IHME attribution and rate unit scale remain unknown until dataset/import provenance verifies them.",
        ))
    finally:
        # Closing the read-only connection rolls back the read snapshot.
        connection.close()


def _percent(numerator: int, denominator: int) -> float | None:
    return 100.0 * numerator / denominator if denominator else None


def _counts(rows) -> tuple[tuple[ObservationStatus, int], ...]:
    counts = Counter(row.status for row in rows)
    return tuple((status, counts[status]) for status in ObservationStatus)


def _selected_groups(query: ResolvedQuery) -> tuple[str, ...]:
    groups = query.geography.group_values
    selected = query.geography.rurality_filter
    if selected.state is ValueState.SUBGROUP:
        groups = tuple(group for group in groups if group == selected.value)
    if query.comparison and query.comparison.dimension is Dimension.RURALITY:
        wanted = {query.comparison.group_a.value, query.comparison.group_b.value}
        groups = tuple(group for group in groups if group in wanted)
    return groups


def _paired_coverage(a_rows, b_rows, year: int, group: str | None = None) -> PairedCoverage:
    if group is not None:
        a_rows = [row for row in a_rows if row.rurality_group == group]
        b_rows = [row for row in b_rows if row.rurality_group == group]
    b_by_fips = {row.fips: row for row in b_rows}
    eligible_a = [row for row in a_rows if row.geography_status is GeographyStatus.ELIGIBLE]
    eligible_b = [row for row in b_rows if row.geography_status is GeographyStatus.ELIGIBLE]
    paired, reasons = 0, Counter()
    for a in a_rows:
        b = b_by_fips[a.fips]
        if a.geography_status is not GeographyStatus.ELIGIBLE:
            reasons[a.geography_status.value] += 1
        elif a.status is ObservationStatus.AVAILABLE and b.status is ObservationStatus.AVAILABLE:
            paired += 1
        else:
            reason = "|".join(f"{key}:{row.status.value}" for key, row in (("A", a), ("B", b))
                              if row.status is not ObservationStatus.AVAILABLE)
            reasons[reason] += 1
    missing = sum(row.geography_status is GeographyStatus.MISSING_RUCC for row in a_rows)
    outside = sum(row.geography_status is GeographyStatus.OUTSIDE_FILTER for row in a_rows)
    coverage = PairedCoverage(
        year, group, len(a_rows), len(eligible_a),
        sum(row.status is ObservationStatus.AVAILABLE for row in a_rows),
        sum(row.status is ObservationStatus.AVAILABLE for row in b_rows),
        sum(row.status is ObservationStatus.AVAILABLE for row in eligible_a),
        sum(row.status is ObservationStatus.AVAILABLE for row in eligible_b),
        paired, len(a_rows) - paired, len(eligible_a) - paired, missing, outside,
        _percent(paired, len(eligible_a)), _percent(paired, len(a_rows)),
        tuple(sorted(reasons.items())), _counts(eligible_a), _counts(eligible_b),
    )
    if sum(count for _, count in coverage.primary_exclusions) != coverage.excluded_counties:
        raise MultidimensionalError("Paired coverage exclusions do not reconcile")
    return coverage


def compare_strata(query: ResolvedQuery, *, database_path: Path) -> ComparisonResult:
    """County-paired sex/age contrasts, optionally within requested RUCC strata.

    Signed gap A-B; magnitude separately; relative gap (A-B)/B*100, unavailable
    for zero B. Marginal IHME uncertainty bounds are preserved separately.
    """
    _validate(query)
    if query.comparison is None or query.comparison.dimension not in {Dimension.SEX, Dimension.AGE}:
        raise MultidimensionalError("compare_strata requires sex/age pairs; rurality groups contain disjoint counties")
    values = get_stratum_values(query, database_path=database_path)
    comparisons, coverage, grouped = [], [], []
    for year in query.time.sources[0].years:
        a_rows = [row for row in values.observations if row.year == year and row.group == "A"]
        b_rows = [row for row in values.observations if row.year == year and row.group == "B"]
        coverage.append(_paired_coverage(a_rows, b_rows, year))
        for group in _selected_groups(query):
            grouped.append(_paired_coverage(a_rows, b_rows, year, group))
        b_by_fips = {row.fips: row for row in b_rows}
        for a in a_rows:
            b = b_by_fips[a.fips]
            if (a.geography_status is not GeographyStatus.ELIGIBLE
                    or a.status is not ObservationStatus.AVAILABLE or b.status is not ObservationStatus.AVAILABLE):
                continue
            gap = a.value - b.value
            relative = gap / b.value * 100 if b.value != 0 else None
            if not math.isfinite(gap) or (relative is not None and not math.isfinite(relative)):
                raise MultidimensionalError("Non-finite contrast arithmetic")
            comparisons.append(CountyComparison(
                a.fips, a.location_name, year, a.rurality_group, a.value, b.value,
                a.lower, a.upper, b.lower, b.upper, gap, abs(gap), relative,
            ))
    comparisons.sort(key=lambda row: (row.year, -row.signed_gap, row.location_name, row.fips))
    return ComparisonResult(values, tuple(comparisons), tuple(coverage), tuple(grouped))


def _rurality_coverage(rows, year: int, group: str | None = None) -> RuralityCoverage:
    if group is not None:
        rows = [row for row in rows if row.rurality_group == group]
    eligible = [row for row in rows if row.geography_status is GeographyStatus.ELIGIBLE]
    available = sum(row.status is ObservationStatus.AVAILABLE for row in eligible)
    reasons = Counter()
    for row in rows:
        if row.geography_status is not GeographyStatus.ELIGIBLE:
            reasons[row.geography_status.value] += 1
        elif row.status is not ObservationStatus.AVAILABLE:
            reasons[row.status.value] += 1
    coverage = RuralityCoverage(
        year, group, len(rows), len(eligible),
        sum(row.status is ObservationStatus.AVAILABLE for row in rows), available,
        len(eligible) - available,
        sum(row.geography_status is GeographyStatus.MISSING_RUCC for row in rows),
        sum(row.geography_status is GeographyStatus.OUTSIDE_FILTER for row in rows),
        len(rows) - available, _percent(available, len(eligible)), _percent(available, len(rows)),
        _counts(eligible), tuple(sorted(reasons.items())),
    )
    if sum(count for _, count in coverage.primary_exclusions) != coverage.excluded_counties:
        raise MultidimensionalError("Rurality coverage exclusions do not reconcile")
    return coverage


def summarize_by_rurality(query: ResolvedQuery, *, database_path: Path) -> RuralityResult:
    """Equal-county mean/median for a fixed population across RUCC 2023 groups.

    A rurality ComparisonSpec may select two geographic groups; these remain
    disjoint county summaries, never paired contrasts or population estimates.
    """
    _validate(query)
    if query.capability_key not in {"sex_rurality", "age_rurality"} or (
        query.comparison is not None and query.comparison.dimension is not Dimension.RURALITY
    ):
        raise MultidimensionalError("Rurality summaries require a fixed demographic stratum")
    values = get_stratum_values(query, database_path=database_path)
    summaries, coverage = [], []
    for year in query.time.sources[0].years:
        rows = [row for row in values.observations if row.year == year]
        coverage.append(_rurality_coverage(rows, year))
        for group in _selected_groups(query):
            group_coverage = _rurality_coverage(rows, year, group)
            estimates = [row.value for row in rows if row.rurality_group == group
                         and row.geography_status is GeographyStatus.ELIGIBLE
                         and row.status is ObservationStatus.AVAILABLE]
            average = mean(estimates) if estimates else None
            middle = median(estimates) if estimates else None
            if any(number is not None and not math.isfinite(number) for number in (average, middle)):
                raise MultidimensionalError("Non-finite county summary arithmetic")
            summaries.append(RuralitySummary(group_coverage, average, middle))
    return RuralityResult(values, tuple(summaries), tuple(coverage))
