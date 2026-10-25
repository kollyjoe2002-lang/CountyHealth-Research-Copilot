"""Deterministic evidence/claims for the guarded multidimensional operations."""
from __future__ import annotations

import re

from ai.models import EvidenceBundle, EvidenceClaim, EvidenceItem
from ai.multidimensional_integration import wire
from app.multidimensional import ComparisonResult, RuralityResult

LIMITATIONS = (
    "Results are descriptive and do not establish causation.",
    "IHME risk attribution is unknown pending independent dataset/import provenance verification.",
    "The IHME rate unit scale is unknown; no per-population rate scale is established.",
    "Marginal IHME uncertainty bounds are retained separately; no interval for the contrast was derived.",
    "County summaries give each available county equal weight; population-weighted national estimates are not established.",
    "Synthetic integration fixtures do not validate real epidemiological coverage or activate public capabilities.",
)


def evidence_bundle(result, plan) -> EvidenceBundle:
    if result.values.query != plan.resolved_context["resolved_query"]:
        raise ValueError("Deterministic result differs from the resolved query/preview")
    context = wire(plan.resolved_context)
    context["multidimensional"] = True
    context["fixture_only"] = True
    context["attribution_unknown"] = True
    context["unit_unknown"] = True
    context["coverage"] = wire(result.coverage)
    context["semantics"] = wire(result.values.semantics)
    return EvidenceBundle(plan.question, plan.intent, [EvidenceItem(
        "multidimensional", "IHME multidimensional evidence (synthetic development fixture)", result,
        plan.steps[0].function_name, {"query": wire(result.values.query)},
        "Guarded fixture execution; capability remains PLANNED")],
        list(result.values.warnings), context)


def claims(bundle: EvidenceBundle) -> list[EvidenceClaim]:
    result = bundle.items[0].data
    query = result.values.query
    source = bundle.items[0].source_function
    context = (f"IHME YLL rates for {query.concepts[0].name}. Risk attribution is unknown and rate unit scale is unknown. "
               f"Explicit population basis: {result.values.semantics[0].population_basis}. "
               f"Policy assumptions: {'; '.join(query.assumptions) or 'none'}. Synthetic fixture evidence only.")
    if query.geography.requires_rurality:
        context += f" RUCC 2023 grouping; selected rurality filter={query.geography.rurality_filter.value or 'all defined groups'}."
    if query.comparison:
        context += (f" Comparison dimension {query.comparison.dimension.value}; "
                    f"A={query.comparison.group_a.value}; B={query.comparison.group_b.value}.")
    output = [EvidenceClaim("multidimensional.context", context, source,
                            units="unknown", metadata={"interpreted_query": bundle.context["interpreted_query"]})]
    if result.values.geography_note:
        output.append(EvidenceClaim("multidimensional.geography", result.values.geography_note, source))
    for index, coverage in enumerate(result.coverage):
        if isinstance(result, ComparisonResult):
            text = (f"In {coverage.year}, candidate counties={coverage.candidate_counties}; eligible counties={coverage.eligible_counties}; "
                    f"A available={coverage.group_a_available}; B available={coverage.group_b_available}; "
                    f"complete paired counties={coverage.complete_paired_counties}; excluded counties={coverage.excluded_counties}; "
                    f"paired coverage={coverage.paired_coverage_percent} percent (eligible denominator).")
            if query.geography.requires_rurality:
                text += f" Missing RUCC classifications={coverage.missing_rucc_counties}."
        else:
            text = (f"In {coverage.year}, candidate counties={coverage.candidate_counties}; eligible counties={coverage.eligible_counties}; "
                    f"observations available={coverage.observations_available}; missing outcomes={coverage.missing_outcome_observations}; "
                    f"missing RUCC classifications={coverage.missing_rucc_counties}; exclusions={coverage.excluded_counties}; "
                    f"coverage={coverage.coverage_percent} percent (eligible denominator).")
        output.append(EvidenceClaim(f"multidimensional.coverage.{index}", text, source,
                                    metadata=wire(coverage)))
    if isinstance(result, ComparisonResult):
        for index, row in enumerate(result.comparisons):
            text = (f"{row.location_name}, {row.year}: A YLL rate={row.group_a_value}; B YLL rate={row.group_b_value}; "
                    f"signed gap A minus B={row.signed_gap}; magnitude={row.absolute_gap_magnitude}; "
                    f"relative gap using B as denominator={row.relative_gap_percent} percent; rurality group={row.rurality_group or 'not requested'}. "
                    f"Marginal A uncertainty bounds [{row.group_a_lower}, {row.group_a_upper}]; "
                    f"marginal B uncertainty bounds [{row.group_b_lower}, {row.group_b_upper}]. "
                    "Rate unit scale and attribution remain unknown.")
            output.append(EvidenceClaim(f"multidimensional.pair.{index}", text, source, units="unknown", metadata=wire(row)))
    elif isinstance(result, RuralityResult):
        for index, row in enumerate(result.summaries):
            coverage = row.coverage
            text = (f"{coverage.rurality_group}, {coverage.year}: equally weighted county mean YLL rate={row.county_weighted_mean}; "
                    f"county median={row.county_weighted_median}; eligible counties={coverage.eligible_counties}; "
                    f"observations available={coverage.observations_available}; coverage={coverage.coverage_percent} percent. "
                    "These are summaries across disjoint county groups. Rate unit scale and attribution remain unknown.")
            output.append(EvidenceClaim(f"multidimensional.summary.{index}", text, source, units="unknown", metadata=wire(row)))
    return output


def validate_language(text: str) -> None:
    """Additional fail-closed guard for unknown source semantics, never a replacement for entailment."""
    patterns = (r"\bhigh[\s-]*bmi\b", r"\battribut(?:able|ed)\b",
                r"\bper\s+(?:\d|one hundred|capita|person|population|resident)",
                r"\bpopulation[- ]weighted\b", r"\bnational\s+(?:rate|estimate)",
                r"\b(?:gap|difference)\s+(?:confidence|uncertainty)\s+interval")
    if any(re.search(pattern, text, re.I) for pattern in patterns):
        raise ValueError("Multidimensional prose upgrades unknown attribution/units or unsupported weighting/intervals")
