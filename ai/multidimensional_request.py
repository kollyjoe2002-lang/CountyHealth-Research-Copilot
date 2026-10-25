"""Untrusted parser vocabulary and deterministic multidimensional policy.

No IDs, SQL, execution tokens or population defaults come from the model.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import re

from ai.capabilities import (
    CAPABILITIES, GeographyMode, Source, MEASUREMENT_YEAR_BOUNDS, MULTIDIMENSIONAL_POLICY_DEFAULTS,
)
from ai.query_models import (
    AGE_STANDARDIZED_20_PLUS, ComparisonSpec, DemographicStratum, Dimension,
    GeographySpec, PopulationValue, QueryOperation, ResolvedQuery, ValueState,
    assess_query_contract, DecisionStatus,
)

POLICY_VERSION = "multidimensional-policy-1"


@dataclass(frozen=True)
class SemanticPopulation:
    sex: str | None = None
    age: str | None = None
    race_ethnicity: str | None = None
    rurality: str | None = None


@dataclass(frozen=True)
class MultidimensionalRequest:
    fixed_sex: str | None = None
    fixed_age: str | None = None
    fixed_race_ethnicity: str | None = None
    comparison_dimension: str | None = None
    group_a: SemanticPopulation | None = None
    group_b: SemanticPopulation | None = None
    rurality_grouping: str | None = None
    rurality_filter: str | None = None
    state_name: str | None = None
    operation: str = "compare_groups"


_GROUP_SCHEMA = {"type": ["object", "null"], "additionalProperties": False,
                 "properties": {f.name: {"type": ["string", "null"]} for f in fields(SemanticPopulation)},
                 "required": [f.name for f in fields(SemanticPopulation)]}
MULTIDIMENSIONAL_SCHEMA = {
    "type": ["object", "null"], "additionalProperties": False,
    "properties": {f.name: ({**_GROUP_SCHEMA} if f.name in {"group_a", "group_b"}
                   else {"type": "string", "enum": ["compare_groups", "summarize_by_rurality", "unsupported"]}
                   if f.name == "operation" else {"type": ["string", "null"]})
                   for f in fields(MultidimensionalRequest)},
    "required": [f.name for f in fields(MultidimensionalRequest)],
}
MULTIDIMENSIONAL_SCHEMA["properties"]["comparison_dimension"]["enum"] = [
    "sex", "age", "race_ethnicity", "rurality", "multiple", None,
]
MULTIDIMENSIONAL_SCHEMA["properties"]["rurality_grouping"]["enum"] = [
    "rucc_adjacency", "metro_nonmetro", "rucc_code", None,
]


def decode_multidimensional(payload) -> MultidimensionalRequest | None:
    if payload is None:
        return None
    if not isinstance(payload, dict) or set(payload) != {f.name for f in fields(MultidimensionalRequest)}:
        raise ValueError("Multidimensional schema keys must match exactly; IDs/functions are forbidden")
    values = dict(payload)
    for name, value in values.items():
        if name in {"group_a", "group_b"}:
            if value is not None:
                if not isinstance(value, dict) or set(value) != {f.name for f in fields(SemanticPopulation)}:
                    raise ValueError("Comparison populations require independent named dimensions")
                if any(v is not None and (not isinstance(v, str) or not v.strip()) for v in value.values()):
                    raise ValueError("Population labels must be nonempty strings or null")
                values[name] = SemanticPopulation(**value)
        elif value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError("Semantic fields require strings or null")
        allowed = MULTIDIMENSIONAL_SCHEMA["properties"][name].get("enum")
        if allowed is not None and value not in allowed:
            raise ValueError(f"Unsupported semantic schema value: {name}")
    return MultidimensionalRequest(**values)


class MultidimensionalPolicyError(ValueError):
    def __init__(self, reason: str, *, clarify: bool = False):
        super().__init__(reason)
        self.clarify = clarify


@dataclass(frozen=True)
class NormalizedMultidimensional:
    capability_key: str
    stratum: DemographicStratum
    comparison: ComparisonSpec | None
    geography: GeographySpec
    operation: QueryOperation
    years: tuple[int, ...]
    state_name: str | None
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class SemanticCapabilityDecision:
    capability_key: str
    state: str
    reason: str
    availability_status: str
    resolved_query: ResolvedQuery | None = None
    fixture_only: bool = False

    @property
    def executable(self) -> bool:
        # No real-data activation has been authorized in this implementation.
        return False


SEX_WORDS = r"\b(?:women|woman|female|females|men|man|male|males)\b"
AGE_PATTERN = r"\b(\d{1,3})\s*(?:-|–|to)\s*(\d{1,3})\b"
RURAL_WORDS = r"\b(?:rurality|rucc|rural|metro|nonmetro|metropolitan)\b"
RACE_WORDS = r"\b(?:(?:black|white)(?!\s+(?:hawk\s+)?county\b)|hispanic|latino|asian|african american)\b"
AMBIGUOUS_AGE = r"\b(?:older|younger|elderly|middle-aged)\b"


def compound_population_requested(text: str) -> bool:
    return sum(bool(re.search(pattern, text, re.I)) for pattern in (SEX_WORDS, AGE_PATTERN + "|" + AMBIGUOUS_AGE, RURAL_WORDS, RACE_WORDS)) >= 2


def _value(dimension: Dimension, text: str | None) -> PopulationValue:
    if text is None:
        return PopulationValue.unspecified(dimension)
    normalized = " ".join(text.casefold().replace('–', '-').split())
    if normalized in {"total", "total population", "both", "both sexes", "all races"}:
        return PopulationValue.total(dimension)
    if dimension is Dimension.SEX:
        aliases = {"women": "Female", "woman": "Female", "female": "Female", "females": "Female",
                   "men": "Male", "man": "Male", "male": "Male", "males": "Male"}
        if normalized not in aliases:
            raise MultidimensionalPolicyError("Ambiguous sex label", clarify=True)
        text = aliases[normalized]
    elif dimension is Dimension.AGE:
        if normalized in {"20 plus, age standardized", "20+, age standardized", "age standardized 20+"}:
            text = AGE_STANDARDIZED_20_PLUS
        else:
            match = re.fullmatch(r"(?:age[sd]?\s+)?(\d+)\s*(?:-|to)\s*(\d+)", normalized)
            if not match:
                raise MultidimensionalPolicyError("Ambiguous or compound age label", clarify=True)
            text = f"{int(match[1])}-{int(match[2])}"
    elif dimension is Dimension.RACE_ETHNICITY:
        raise MultidimensionalPolicyError("Race intersections are not validated")
    else:
        aliases = {"metro": "Metro", "metropolitan": "Metro", "nonmetro adjacent": "Nonmetro adjacent",
                   "nonmetro not adjacent": "Nonmetro not adjacent"}
        if normalized not in aliases:
            raise MultidimensionalPolicyError("Specify a validated RUCC adjacency group", clarify=True)
        text = aliases[normalized]
    return PopulationValue.subgroup(dimension, text)


def normalize_multidimensional(request) -> NormalizedMultidimensional:
    md = request.multidimensional
    if not isinstance(md, MultidimensionalRequest):
        raise MultidimensionalPolicyError("Compound population requires structured semantic fields", clarify=True)
    text = request.question.raw_text
    if re.search(AMBIGUOUS_AGE, text, re.I) and not re.search(AGE_PATTERN, text, re.I):
        raise MultidimensionalPolicyError("An explicit age band is required for this demographic phrase", clarify=True)
    if re.search(r"\b(?:forecast\w*|predict\w*|project\w*|caused|causal|causality|causation|causing|significan\w*|hypothesis|p-value)\b", text, re.I):
        raise MultidimensionalPolicyError("Forecasting, causality and inferential testing are unsupported")
    if re.search(r"\bdid\b.*\bcause\b|\bled to\b|\bbecause of\b", text, re.I):
        raise MultidimensionalPolicyError("Causal inference is unsupported")
    if re.search(r"\b(?:education|income|occupation|insurance|socioeconomic|marital status)\b", text, re.I):
        raise MultidimensionalPolicyError("Additional demographic dimensions are not validated")
    if re.search(r"\b(?:YLDs?|DALYs?|deaths?|mortality|incidence|hospitalizations?)\b", text, re.I):
        raise MultidimensionalPolicyError("The requested health metric is not the validated IHME YLL-rate outcome")
    if request.evidence_domain in {"PLACES", "PLACES_IHME"} or re.search(r"\b(?:PLACES|prevalence)\b", text, re.I):
        raise MultidimensionalPolicyError("Demographic PLACES prevalence and new cross-source intersections are unsupported; no concept remapping is permitted")
    if re.search(RACE_WORDS, text, re.I):
        raise MultidimensionalPolicyError("Race intersections are not validated")
    if md.operation not in {"compare_groups", "summarize_by_rurality"}:
        raise MultidimensionalPolicyError("Unsupported analytical operation")
    if md.comparison_dimension == "multiple":
        raise MultidimensionalPolicyError("Two changing demographic dimensions are not supported")
    ordered_sexes = tuple(dict.fromkeys("Female" if re.fullmatch(r"women|woman|female|females", m, re.I) else "Male"
                          for m in re.findall(SEX_WORDS, text, re.I)))
    sexes = set(ordered_sexes)
    bands = tuple(dict.fromkeys(f"{int(a)}-{int(b)}" for a, b in re.findall(AGE_PATTERN, text, re.I)))
    if len(sexes) == 2 and len(bands) > 1:
        raise MultidimensionalPolicyError("Two changing demographic dimensions are not supported")
    if len(sexes) == 2 and md.comparison_dimension != "sex":
        raise MultidimensionalPolicyError("The parsed comparison discarded a requested sex dimension")
    for field, pattern in (("fixed_race_ethnicity", r"\b(?:total race|total population|all races)\b"),
                           ("fixed_sex", r"\b(?:both sexes|total population)\b"),
                           ("fixed_age", r"\bage.standard|standardized\b")):
        value = getattr(md, field)
        if value and (value.casefold() in {"total", "total population", "both", "both sexes", "all races"}
                      or "standard" in value.casefold()) and not re.search(pattern, text, re.I):
            raise MultidimensionalPolicyError("The parser supplied an unstated population default; deterministic policy must establish it", clarify=True)
    fixed = {dimension: _value(dimension, getattr(md, name)) for dimension, name in (
        (Dimension.SEX, "fixed_sex"), (Dimension.AGE, "fixed_age"), (Dimension.RACE_ETHNICITY, "fixed_race_ethnicity"))}
    comparison = None
    if md.operation == "compare_groups":
        if md.group_a is None or md.group_b is None:
            raise MultidimensionalPolicyError("Two explicit comparison populations are required", clarify=True)
        changes = []
        groups = []
        for dimension in Dimension:
            a = _value(dimension, getattr(md.group_a, dimension.value))
            b = _value(dimension, getattr(md.group_b, dimension.value))
            if a != b:
                changes.append(dimension)
                groups.append((a, b))
            elif a.state is not ValueState.UNSPECIFIED:
                if dimension is Dimension.RURALITY:
                    raise MultidimensionalPolicyError("Put shared rurality in the explicit filter", clarify=True)
                if fixed[dimension].state is not ValueState.UNSPECIFIED and fixed[dimension] != a:
                    raise MultidimensionalPolicyError("Conflicting shared and fixed population filters")
                explicit_pattern = {
                    Dimension.RACE_ETHNICITY: r"\b(?:total race|all races|total population)\b",
                    Dimension.SEX: r"\b(?:both sexes|all sexes|total population)\b",
                    Dimension.AGE: r"\b20\b.*standard|standard.*\b20\b",
                    Dimension.RURALITY: r"\btotal\b",
                }[dimension]
                if (a.state is ValueState.TOTAL or a.value == AGE_STANDARDIZED_20_PLUS) and not re.search(
                    explicit_pattern, text, re.I
                ):
                    raise MultidimensionalPolicyError("Parser supplied an unstated shared population default", clarify=True)
                fixed[dimension] = a
        if len(changes) != 1:
            raise MultidimensionalPolicyError("Exactly one changing comparison dimension is supported")
        dimension = changes[0]
        if md.comparison_dimension != dimension.value:
            raise MultidimensionalPolicyError("Comparison dimension disagrees with its population groups", clarify=True)
        if dimension is not Dimension.RURALITY and fixed[dimension].state is not ValueState.UNSPECIFIED:
            raise MultidimensionalPolicyError("Fixed filter conflicts with the comparison dimension")
        comparison = ComparisonSpec(dimension=dimension, group_a=groups[0][0], group_b=groups[0][1])
        if dimension is Dimension.SEX and len(ordered_sexes) == 2 and (
            comparison.group_a.value, comparison.group_b.value
        ) != ordered_sexes:
            raise MultidimensionalPolicyError("Sex comparison orientation does not preserve the question")
        if dimension is Dimension.AGE and bands and (comparison.group_a.value, comparison.group_b.value) != bands:
            raise MultidimensionalPolicyError("Age comparison orientation does not preserve the question")
    elif md.group_a is not None or md.group_b is not None or md.comparison_dimension is not None:
        raise MultidimensionalPolicyError("A fixed-population summary must not contain a hidden comparison")
    if fixed[Dimension.SEX].state is ValueState.SUBGROUP and fixed[Dimension.SEX].value not in sexes:
        raise MultidimensionalPolicyError("Parsed fixed sex is not supported by the question", clarify=True)
    if fixed[Dimension.AGE].age_specific and fixed[Dimension.AGE].value not in bands:
        raise MultidimensionalPolicyError("Parsed fixed age is not supported by the question", clarify=True)
    rural = bool(md.rurality_grouping or md.rurality_filter or re.search(RURAL_WORDS, text, re.I))
    if md.rurality_grouping not in {None, "rucc_adjacency"}:
        raise MultidimensionalPolicyError("This RUCC grouping is not in the validated contract envelope")
    dimension = comparison.dimension if comparison else None
    age_specific = fixed[Dimension.AGE].age_specific or dimension is Dimension.AGE
    sex_specific = fixed[Dimension.SEX].state is ValueState.SUBGROUP or dimension is Dimension.SEX
    if rural and age_specific and sex_specific:
        raise MultidimensionalPolicyError("Sex × age × rurality is not validated")
    key = ("age_rurality" if age_specific else "sex_rurality") if rural else "sex_age"
    assumptions = []
    if request.evidence_domain is None:
        assumptions.append(f"{POLICY_VERSION}/{key}: source=IHME (only supported new health-evidence envelope)")
    if request.county_name is None and md.state_name is None and request.geographic_scope is None:
        assumptions.append(f"{POLICY_VERSION}/{key}: scope=eligible current-county universe (no county/state specified)")
    def default(dimension, value, explanation):
        if fixed[dimension].state is ValueState.UNSPECIFIED:
            fixed[dimension] = value
            assumptions.append(f"{POLICY_VERSION}/{key}: {explanation}")
    for field, label in MULTIDIMENSIONAL_POLICY_DEFAULTS[key]:
        default_dimension = Dimension(field)
        display = "race" if default_dimension is Dimension.RACE_ETHNICITY else default_dimension.value
        default(default_dimension, _value(default_dimension, label), f"{display}={label} (required envelope)")
    if rural and md.rurality_grouping is None:
        assumptions.append(f"{POLICY_VERSION}/{key}: RUCC 2023 adjacency grouping (explicit policy)")
    observation_text = re.sub(r"\b(?:RUCC(?:\s+classification)?\s+2023|2023\s+RUCC)\b", "", text, flags=re.I)
    raw_years = {int(value) for value in re.findall(r"\b\d{4}\b", observation_text)}
    supplied = [value for value in (request.year, request.start_year, request.end_year) if value is not None]
    first_year, last_year = MEASUREMENT_YEAR_BOUNDS[Source.IHME]
    if any(type(value) is not int or value < first_year or value > last_year for value in [*supplied, *raw_years]):
        raise MultidimensionalPolicyError("Unsupported IHME observation year")
    if set(supplied) != raw_years:
        raise MultidimensionalPolicyError("Parser supplied an unstated year", clarify=True)
    if request.year is not None and (request.start_year is not None or request.end_year is not None):
        raise MultidimensionalPolicyError("Conflicting point-year and time-range selections")
    if request.start_year is not None or request.end_year is not None:
        if request.start_year is None or request.end_year is None or request.start_year > request.end_year:
            raise MultidimensionalPolicyError("An ordered complete year range is required", clarify=True)
        years = tuple(range(request.start_year, request.end_year + 1))
    else:
        years = (request.year,) if request.year is not None else (last_year,)
        if request.year is None:
            assumptions.append(f"{POLICY_VERSION}/{key}: year={last_year} (IHME code envelope; observed availability still required)")
    state_name = md.state_name
    if request.geographic_scope and request.geographic_scope.casefold() not in {"united states", "us", "usa", "national"}:
        if state_name and state_name.casefold() != request.geographic_scope.casefold():
            raise MultidimensionalPolicyError("Conflicting state/geographic scope labels", clarify=True)
        state_name = state_name or request.geographic_scope
    geography = GeographySpec(mode=GeographyMode.RUCC_ADJACENCY if rural else GeographyMode.COUNTY_UNIVERSE,
        classification_year=2023 if rural else None,
        rurality_filter=_value(Dimension.RURALITY, md.rurality_filter))
    stratum = DemographicStratum(**{dimension.value: value for dimension, value in fixed.items()})
    if comparison and comparison.dimension is Dimension.RURALITY and md.rurality_filter:
        raise MultidimensionalPolicyError("Fixed rurality filter conflicts with rurality comparison")
    # Check the intended envelope without inventing a cause ID: shape-only checks
    # are repeated with the actual canonical cause in the resolver/executor.
    if key == "sex_age" and (dimension not in {Dimension.SEX, Dimension.AGE} or
        (dimension is Dimension.AGE and stratum.sex.state is not ValueState.SUBGROUP) or
        (dimension is Dimension.SEX and not stratum.age.age_specific)):
        raise MultidimensionalPolicyError("Sex × age requires an independent fixed sex/age selection", clarify=True)
    if key == "sex_rurality" and dimension is not Dimension.SEX and stratum.sex.state is not ValueState.SUBGROUP:
        raise MultidimensionalPolicyError("Fixed sex is required for sex-rurality summaries", clarify=True)
    if key == "age_rurality" and dimension is not Dimension.AGE and not stratum.age.age_specific:
        raise MultidimensionalPolicyError("Fixed age is required for age-rurality summaries", clarify=True)
    if state_name and state_name.casefold() not in text.casefold():
        raise MultidimensionalPolicyError("Parsed state scope was not stated", clarify=True)
    if not request.cause_name:
        raise MultidimensionalPolicyError("A health concept is required", clarify=True)
    return NormalizedMultidimensional(key, stratum, comparison, geography, QueryOperation(md.operation), years,
                                      state_name, tuple(assumptions))
