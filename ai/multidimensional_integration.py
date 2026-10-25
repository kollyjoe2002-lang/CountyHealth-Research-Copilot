"""Guarded integration utilities used by the canonical assistant pipeline.

No orchestration entry point lives here. Synthetic fixture access cannot be
selected by parser JSON, environment variables, or public capability metadata.
"""
from __future__ import annotations

from ai.conversation_contracts import FailureReason

from dataclasses import asdict, dataclass, is_dataclass, replace
from enum import Enum
import hashlib
import json
from pathlib import Path
import tempfile

import duckdb

from ai.capabilities import CAPABILITIES, MULTIDIMENSIONAL_RELATIONS as RELATIONS, MULTIDIMENSIONAL_YLL_FILTER
from ai.multidimensional_request import SemanticCapabilityDecision
from ai.query_models import DecisionStatus, ResolvedQuery, assess_query_contract


@dataclass(frozen=True)
class FixtureIntegrationContext:
    database_path: Path
    allow_execution: bool = False

    def validate(self, *, execution=False) -> Path:
        path = Path(self.database_path).resolve()
        from app.data_access import DB_FILE
        if (type(self.allow_execution) is not bool or (execution and not self.allow_execution)
            or not path.is_file() or not path.is_relative_to(Path(tempfile.gettempdir()).resolve())
            or path == DB_FILE.resolve() or path.stat().st_size > 16 * 1024 * 1024):
            raise ValueError("An explicit small temporary synthetic fixture is required; public activation is disabled")
        connection = duckdb.connect(str(path), read_only=True)
        try:
            marker = connection.execute("SELECT marker FROM analytics.multidimensional_fixture_marker").fetchall()
            if marker != [("synthetic_structural_fixture_only",)]:
                raise ValueError("Fixture marker does not prove this is a synthetic integration fixture")
        finally:
            connection.close()
        return path


def wire(value):
    """JSON-safe, complete representation; no mutable alias of the typed query."""
    if is_dataclass(value):
        return wire(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): wire(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, frozenset, set)):
        return [wire(item) for item in value]
    return value


def query_digest(query: ResolvedQuery) -> str:
    return hashlib.sha256(json.dumps(wire(query), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def query_preview(query: ResolvedQuery) -> dict:
    return {"query": wire(query), "required_sources": sorted(source.value for source in query.required_sources),
            "public_executable": False, "query_digest": query_digest(query)}


@dataclass(frozen=True)
class AvailabilityReceipt:
    database_digest: str
    query_digest: str
    fixture_only: bool = True


@dataclass(frozen=True)
class MultidimensionalResolution:
    query: ResolvedQuery | None
    preview: dict
    decision: SemanticCapabilityDecision
    receipt: AvailabilityReceipt | None = None
    unresolved: tuple[str, ...] = ()
    failure_reason: FailureReason | None = None


def validate_fixture_availability(query: ResolvedQuery, context: FixtureIntegrationContext) -> tuple[ResolvedQuery, AvailabilityReceipt]:
    """Catalog/existence validation only; no estimates are executed or returned."""
    if not isinstance(context, FixtureIntegrationContext):
        raise ValueError("Explicit typed fixture context required")
    path = context.validate()
    from app.multidimensional import _definitions, _county_scope
    connection = duckdb.connect(str(path), read_only=True)
    try:
        connection.execute("BEGIN TRANSACTION")
        definitions = _definitions(connection, query)
        if any(item.unavailable_reason for item in definitions):
            raise LookupError("Requested demographic combination is unavailable in the fixture catalogs")
        relation, counties = RELATIONS["burden"], RELATIONS["counties"]
        scope, scope_parameters = _county_scope(query)
        for definition in definitions:
            for year in query.time.sources[0].years:
                conditions = [f"{relation.column(name, 'b')}=?" for name, _ in definition.catalog_ids]
                parameters = [value for _, value in definition.catalog_ids]
                conditions.extend([f"{relation.column('cause_id', 'b')}=?", f"{relation.column('year', 'b')}=?"])
                parameters.extend([query.concepts[0].concept_id, year])
                for column, value in MULTIDIMENSIONAL_YLL_FILTER:
                    conditions.append(f"{relation.column(column, 'b')}=?")
                    parameters.append(value)
                conditions.append(f"{relation.column('fips', 'b')} IN (SELECT {counties.column('fips', 'g')} "
                                  f"FROM {counties.qualified_name} AS g WHERE {scope})")
                parameters.extend(scope_parameters)
                exists = connection.execute(f"SELECT 1 FROM {relation.qualified_name} AS b WHERE "
                                             + " AND ".join(conditions) + " LIMIT 1", parameters).fetchone()
                if exists is None:
                    raise LookupError("Exact cause/year/stratum has no fixture records")
        if query.geography.requires_rurality:
            # Schema/classification validation does not assert full join coverage.
            rucc = RELATIONS["rucc"]
            years = connection.execute(f"SELECT DISTINCT {rucc.column('source_year')} FROM {rucc.qualified_name}").fetchall()
            if any(year != (2023,) for year in years):
                raise LookupError("RUCC fixture classification year is unavailable")
    finally:
        connection.close()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    query = replace(query, availability_fingerprint="synthetic-fixture:" + digest)
    return query, AvailabilityReceipt(digest, query_digest(query))


def plan_function(query: ResolvedQuery) -> tuple[str, str]:
    from ai.query_models import Dimension
    if query.comparison and query.comparison.dimension in {Dimension.SEX, Dimension.AGE}:
        return "multidimensional_compare", "compare_strata"
    return "multidimensional_summary", "summarize_by_rurality"


def validate_plan_identity(plan) -> ResolvedQuery:
    context = plan.resolved_context
    query = context.get("resolved_query")
    if not isinstance(query, ResolvedQuery) or assess_query_contract(query).status is not DecisionStatus.PLANNED:
        raise ValueError("A valid planned multidimensional query is required")
    if context.get("interpreted_query") != query_preview(query) or tuple(plan.assumptions) != query.assumptions:
        raise ValueError("Preview/resolved-query/plan identity mismatch")
    operation, function = plan_function(query)
    if len(plan.steps) != 1 or (plan.steps[0].operation, plan.steps[0].function_name) != (operation, function):
        raise ValueError("Multidimensional plan is not an explicit approved operation")
    if plan.steps[0].parameters != {"query": query}:
        raise ValueError("Executor parameters differ from the preview/resolved query")
    receipt = context.get("availability_receipt")
    if not isinstance(receipt, AvailabilityReceipt) or receipt.fixture_only is not True or receipt.query_digest != query_digest(query):
        raise ValueError("Availability receipt is missing or does not match the query")
    return query


def validate_execution(plan, context: FixtureIntegrationContext | None) -> ResolvedQuery:
    query = validate_plan_identity(plan)
    if not isinstance(context, FixtureIntegrationContext):
        raise ValueError("Public multidimensional execution is awaiting real-data activation")
    path = context.validate(execution=True)
    receipt = plan.resolved_context["availability_receipt"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != receipt.database_digest:
        raise ValueError("Fixture changed after availability validation")
    if CAPABILITIES[query.capability_key].executable:
        raise ValueError("Fixture execution is not a substitute for a real activation workflow")
    return query
