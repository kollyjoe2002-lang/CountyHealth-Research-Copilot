"""Passive capability inventory. No routing, SQL execution, or availability checks.

Version changes describe the inventory, not the data. Legacy executable means
an existing code path, not that this checkout has freshly passed warehouse gates.
Runtime consumers remain unchanged through Phase 3.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

REGISTRY_VERSION = "1.3.0-phase3.1"


class Source(str, Enum):
    IHME = "IHME"
    PLACES = "CDC PLACES"
    RUCC = "USDA RUCC 2023"


class CapabilityState(str, Enum):
    LEGACY_EXECUTABLE = "legacy_executable"
    PLANNED = "planned_non_executable"
    UNSUPPORTED = "unsupported"


class ValidationStatus(str, Enum):
    LEGACY_RECORDED = "legacy_validators_exist_not_freshly_verified"
    PENDING = "pending_validation"
    NOT_SUPPORTED = "not_supported"


class Surface(str, Enum):
    ASSISTANT = "research_assistant_executor"
    DATA_API = "deterministic_data_api"


class GeographyMode(str, Enum):
    COUNTY = "single_county"
    COUNTY_RANKING = "eligible_county_ranking"
    COUNTY_UNIVERSE = "eligible_county_analytical_universe"
    COUNTY_CONTEXT = "county_fips_alignment"
    METRO = "rucc_metro_nonmetro"
    RUCC_CODE = "rucc_codes_1_to_9"
    RUCC_ADJACENCY = "rucc_metro_nonmetro_adjacency"


@dataclass(frozen=True)
class DimensionRule:
    """A single legacy comparison dimension and its exact fixed SQL filters."""
    name: str
    id_column: str
    name_column: str
    fixed_filters: tuple[tuple[str, int], ...]


DIMENSION_RULES = (
    DimensionRule("Race / ethnicity", "race_id", "race_name",
                  (("sex_id", 3), ("age_group_id", 38))),
    DimensionRule("Sex", "sex_id", "sex_name",
                  (("race_id", 1), ("age_group_id", 38))),
    DimensionRule("Age group", "age_group_id", "age_name",
                  (("race_id", 1), ("sex_id", 3))),
)

# Immutable canonical definitions for future consumers. The existing resolver
# constant remains untouched, including its mutable dict/set public API shape.
# The consistency validator proves exact parity without importing the resolver.
APPROVED_PLACES_IHME_PAIRS: Mapping[str, frozenset[int]] = MappingProxyType({
    "DIABETES": frozenset({976}),
    "STROKE": frozenset({494}),
    "CASTHMA": frozenset({515}),
})


# Existing direct data-API code envelopes, NOT observed catalog availability.
# PLACES semantic policy is narrower (2018 onward) and remains unchanged.
MEASUREMENT_YEAR_BOUNDS: Mapping[Source, tuple[int, int]] = MappingProxyType({
    Source.IHME: (2000, 2019),
    Source.PLACES: (2017, 2023),
})


@dataclass(frozen=True)
class SourceRestriction:
    source: Source
    dataset: str
    rules: tuple[str, ...]


SOURCE_RESTRICTIONS = (
    SourceRestriction(Source.IHME, "ihme.burden", (
        "YLL measure_id=4; rate metric_id=3 for demographic burden queries",
        "Legacy county summary/ranking views retain their existing filters",
        "IHME analytical years 2000-2019; observed stratum coverage unverified",
        "Attribution unknown until scoped dataset/import provenance verifies it",
        "Sex/race comparisons use age_group_id=38; age comparisons are age-specific",
    )),
    SourceRestriction(Source.IHME, "ihme.bmi / analytics.vw_county_bmi_summary", (
        "BMI indicators are distinct from YLL outcomes; no inferred attribution",
        "Preserve existing summary view and indicator-specific units",
    )),
    SourceRestriction(Source.PLACES, "places.estimates", (
        "County modeled prevalence; no demographic subgroup prevalence inferred",
        "Releases 2020-2025; release year differs from measurement year",
        "Direct API measurement-year bounds 2017-2023; request policy 2018-2023",
        "Bounds are code limits, not proof of observed measure/year availability",
        "Snapshot/trend APIs retain release and carry-forward metadata",
        "Canonical rankings/rurality/cross-source analyses exclude carry_forward",
        "Age-adjusted prevalence where required; never relabel as YLL burden",
    )),
    SourceRestriction(Source.RUCC, "geography.rucc_2023", (
        "Fixed 2023 county geographic classification; not a health outcome",
        "Metro=1-3; adjacent nonmetro=4,6,8; nonadjacent nonmetro=5,7,9",
        "Missing classifications excluded under existing grouped-analysis rules",
        "Applying RUCC 2023 to prior years does not reconstruct historical rurality",
    )),
)


@dataclass(frozen=True)
class Capability:
    key: str
    operation: str
    state: CapabilityState
    validation: ValidationStatus
    functions: tuple[str, ...]
    sources: tuple[Source, ...]
    surfaces: tuple[Surface, ...]
    comparison_dimensions: tuple[str, ...]
    geography_modes: tuple[GeographyMode, ...]
    restrictions: tuple[str, ...]
    validators: tuple[str, ...]
    fixed_filters: tuple[tuple[str, int], ...] = ()
    approved_pair_policy: bool = False

    @property
    def executable(self) -> bool:
        return self.state is CapabilityState.LEGACY_EXECUTABLE


# An inventory of catalog/status operations, not analytical execution entries.
CATALOG_FUNCTIONS = (
    "get_counties", "get_available_years", "get_causes", "get_county_status",
    "get_disparity_causes", "get_disparity_years", "get_disparity_groups",
)

# Exact assistant callable subset. It is intentionally smaller than the data API.
ASSISTANT_FUNCTIONS = frozenset({
    "get_bmi_summary", "get_top_causes", "get_county_cause_record",
    "get_long_term_change", "get_cause_trend", "get_county_disparity_ranking",
    "get_county_ranking", "get_places_county_measure_trend",
    "get_places_ihme_county_trend_context", "get_places_ihme_rurality_comparison",
    "get_places_ihme_demographic_disparity_context",
})


def _legacy(
    function: str, operation: str, sources: tuple[Source, ...],
    geography: tuple[GeographyMode, ...], validators: tuple[str, ...],
    *, dimensions: tuple[str, ...] = (), restrictions: tuple[str, ...] = (),
    fixed_filters: tuple[tuple[str, int], ...] = (),
) -> Capability:
    cross = Source.IHME in sources and Source.PLACES in sources
    return Capability(
        key=function, operation=operation,
        state=CapabilityState.LEGACY_EXECUTABLE,
        validation=ValidationStatus.LEGACY_RECORDED,
        functions=(function,), sources=sources,
        surfaces=((Surface.DATA_API, Surface.ASSISTANT)
                  if function in ASSISTANT_FUNCTIONS else (Surface.DATA_API,)),
        comparison_dimensions=dimensions, geography_modes=geography,
        restrictions=restrictions + ((
            "Approved concept-pair policy applies at semantic resolution; direct "
            "data APIs do not independently enforce it; separate metrics, "
            "explicit source years, descriptive interpretation only",
        ) if cross else ()),
        validators=validators, fixed_filters=fixed_filters,
        approved_pair_policy=cross,
    )


_I = (Source.IHME,)
_P = (Source.PLACES,)
_PR = (Source.PLACES, Source.RUCC)
_X = (Source.PLACES, Source.IHME, Source.RUCC)
_XT = (Source.PLACES, Source.IHME)
_C = (GeographyMode.COUNTY,)
_R = (GeographyMode.COUNTY_RANKING,)
_DIMS = tuple(rule.name for rule in DIMENSION_RULES)
_DEFAULT_STRATUM = (("race_id", 1), ("sex_id", 3), ("age_group_id", 38))

_ENTRIES = [
    _legacy("get_bmi_summary", "bmi_summary", _I, _C,
            ("check_county_profile",), restrictions=("BMI indicators, not YLL",)),
    *(_legacy(fn, op, _I, _C, ("check_county_profile",),
              restrictions=("Both sexes; Total race; age 20+, age-standardized view",),
              fixed_filters=_DEFAULT_STRATUM)
      for fn, op in (
          ("get_top_causes", "top_causes"),
          ("get_cause_trend", "cause_trend"),
          ("get_county_cause_record", "county_cause_snapshot"),
          ("get_long_term_change", "long_term_change"),
      )),
    _legacy("get_county_ranking", "national_county_ranking", _I, _R,
            ("check_rankings",), fixed_filters=_DEFAULT_STRATUM),
    *(_legacy(fn, op, _I, geo, ("check_disparity_finder",),
              dimensions=_DIMS,
              restrictions=("One comparison dimension; fixed filters in DIMENSION_RULES",))
      for fn, op, geo in (
          ("get_county_disparity_ranking", "county_disparity_ranking", _R),
          ("get_county_disparity_trend", "demographic_disparity_trend", _C),
      )),
    _legacy("get_places_county_snapshot", "places_release_snapshot", _P, _C,
            ("check_places_county_snapshot",),
            restrictions=("Release-year snapshot; crude and adjusted retained",)),
    _legacy("get_places_county_measure_trend", "places_county_measure_history", _P, _C,
            ("check_places_county_measure_trend",),
            restrictions=("Measurement-year trend retains carry-forward flag",)),
    _legacy("get_places_county_measure_ranking", "places_measure_ranking", _P, _R,
            ("check_places_county_measure_ranking",),
            restrictions=("Canonical carry_forward=FALSE; age-adjusted prevalence",)),
    *(_legacy(fn, op, _PR, (geo,), (validator,),
              dimensions=("rurality",),
              restrictions=("Canonical adjusted prevalence; county mean/median",))
      for fn, op, geo, validator in (
          ("get_places_rural_metro_comparison", "places_metro_comparison",
           GeographyMode.METRO, "check_places_rural_metro_comparison"),
          ("get_places_rucc_comparison", "places_rucc_comparison",
           GeographyMode.RUCC_CODE, "check_places_rucc_comparison"),
          ("get_places_rucc_adjacent_comparison", "places_adjacency_comparison",
           GeographyMode.RUCC_ADJACENCY, "check_places_rucc_adjacent_comparison"),
      )),
    *(_legacy(fn, op, _X, geo, (validator,), dimensions=dims,
              fixed_filters=_DEFAULT_STRATUM)
      for fn, op, geo, dims, validator in (
          ("get_places_ihme_county_context", "cross_source_county_context",
           (GeographyMode.COUNTY_CONTEXT,), (), "check_places_ihme_county_context"),
          ("get_places_ihme_rurality_comparison", "places_ihme_rurality_comparison",
           (GeographyMode.RUCC_ADJACENCY,), ("rurality",), "check_places_ihme_rurality_comparison"),
          ("get_places_ihme_positive_deviance", "descriptive_residual_exploration",
           (GeographyMode.COUNTY_CONTEXT, GeographyMode.RUCC_ADJACENCY), (), "check_places_ihme_positive_deviance"),
          ("get_places_ihme_model_diagnostics", "descriptive_model_diagnostics",
           (GeographyMode.COUNTY_CONTEXT, GeographyMode.RUCC_ADJACENCY), (), "check_places_ihme_model_diagnostics"),
      )),
    _legacy("get_places_ihme_county_trend_context", "places_ihme_county_trend",
            _XT, _C, ("check_places_ihme_county_trend_context",),
            restrictions=("Outer year alignment; source availability remains separate",),
            fixed_filters=_DEFAULT_STRATUM),
]

# Existing generic APIs and convenience wrappers; no new multidimensional API.
for _suffix, _dimensions in (
    ("demographic", _DIMS), ("race", ("Race / ethnicity",)),
    ("sex", ("Sex",)), ("age", ("Age group",)),
):
    for _mode in ("context", "ranking", "trend_context"):
        _fn = f"get_places_ihme_{_suffix}_disparity_{_mode}"
        _validator = (f"check_places_ihme_{_suffix}_disparity_{_mode}"
                      if _mode != "trend_context" or _suffix == "demographic"
                      else "check_places_ihme_disparity_trend_wrappers")
        # Generic context is covered by the existing sex/age/race context checks.
        if _suffix == "demographic" and _mode == "context":
            _validator = "check_places_ihme_sex_disparity_context"
        _validators = (("check_places_ihme_sex_disparity_context",
                        "check_places_ihme_age_disparity_context",
                        "check_places_ihme_race_disparity_context")
                       if _suffix == "demographic" and _mode == "context"
                       else (_validator,))
        _ENTRIES.append(_legacy(
            _fn, ("places_ihme_demographic_disparity_context"
                  if _suffix == "demographic" and _mode == "context"
                  else f"cross_source_{_suffix}_disparity_{_mode}"),
            _XT if _mode == "trend_context" else _X,
            _C if _mode == "trend_context" else _R, _validators,
            dimensions=_dimensions,
            restrictions=(
                "IHME one demographic dimension; DIMENSION_RULES fixes others",
                "PLACES is whole-county prevalence context, not subgroup prevalence",
                "Race wrapper fixes Black/White; sex wrapper fixes Male/Female; "
                "age wrapper fixes ages 60-64/80-84 (IDs 17/30)",
            ),
        ))

# Rurality groups use the existing precise three-group RUCC adjacency mode.
# A demographic county universe is not itself a ranking operation.
for _key, _dims, _sources, _geography in (
    ("sex_age", ("Sex", "Age group"), _I, (GeographyMode.COUNTY_UNIVERSE,)),
    ("sex_rurality", ("Sex", "rurality"), (Source.IHME, Source.RUCC),
     (GeographyMode.RUCC_ADJACENCY,)),
    ("age_rurality", ("Age group", "rurality"), (Source.IHME, Source.RUCC),
     (GeographyMode.RUCC_ADJACENCY,)),
):
    _ENTRIES.append(Capability(
        key=_key, operation=_key, state=CapabilityState.PLANNED,
        validation=ValidationStatus.PENDING, functions=(), sources=_sources,
        surfaces=(), comparison_dimensions=_dims,
        geography_modes=_geography, restrictions=("Disabled; requires later validated analytics",),
        validators=("check_capability_registry",),
    ))

for _key in ("forecast", "causal_inference", "hypothesis_testing",
             "arbitrary_demographic_intersections", "composite_cross_source_metric",
             "places_demographic_subgroups", "unapproved_concept_pairs",
             "aggregate_long_term_change"):
    _ENTRIES.append(Capability(
        key=_key, operation=_key, state=CapabilityState.UNSUPPORTED,
        validation=ValidationStatus.NOT_SUPPORTED, functions=(), sources=(),
        surfaces=(), comparison_dimensions=(), geography_modes=(),
        restrictions=("Unavailable in the validated engine; never auto-downgrade",),
        validators=("check_capability_registry",),
    ))

CAPABILITIES: Mapping[str, Capability] = MappingProxyType({c.key: c for c in _ENTRIES})
# Do not retain a mutable construction list as a second inventory.
del _ENTRIES


def executable_capabilities(surface: Surface | None = None) -> tuple[Capability, ...]:
    """Return inventory entries only; this function cannot authorize execution."""
    return tuple(c for c in CAPABILITIES.values()
                 if c.executable and (surface is None or surface in c.surfaces))


@dataclass(frozen=True)
class ExecutorTransform:
    operation: str
    function_name: str
    implementation: str


# Existing in-memory executor special cases, not callable data-access APIs.
EXECUTOR_TRANSFORMS = (
    ExecutorTransform("restrict_year_range", "filter_dataframe", "_filter_dataframe"),
    ExecutorTransform("restrict_measurement_year", "filter_measurement_year_dataframe",
                      "_filter_measurement_year_dataframe"),
    ExecutorTransform("restrict_analysis_year_range", "filter_analysis_year_dataframe",
                      "_filter_analysis_year_dataframe"),
)
RESOLUTION_OPERATIONS = ("resolve_cause", "resolve_county", "resolve_counties", "resolve_groups")
