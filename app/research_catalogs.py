"""Canonical read-only catalogs for human-selected research concepts.

Listings certify selectable labels/observed policy-eligible rows, never complete
analytical coverage. All analytical calls remain in existing data_access APIs.
"""
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
import re
import pandas as pd
from app.data_access import run_query
from ai.capabilities import APPROVED_PLACES_IHME_PAIRS, CAPABILITIES, Source, MEASUREMENT_YEAR_BOUNDS
from ai.request_policy import PLACES_FIRST_YEAR, PLACES_LAST_YEAR
from ai.resolver import resolve_county


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class CountyChoice:
    fips: str
    county: str
    state: str
    abbreviation: str

    @property
    def label(self):
        return f'{self.county}, {self.state}' + (f' ({self.abbreviation})' if self.abbreviation else '')

    @property
    def canonical_name(self):
        return f'{self.county} ({self.state})'


@dataclass(frozen=True)
class MeasureChoice:
    measure_id: str
    label: str


@dataclass(frozen=True)
class PairChoice:
    measure: MeasureChoice
    cause_id: int
    cause_name: str

    @property
    def label(self):
        return f'{self.measure.label} (PLACES) ↔ {self.cause_name} (IHME)'


class YearPolicy(str, Enum):
    TREND = 'trend_history'
    RANKING = 'canonical_ranking'
    METRO = 'canonical_metro'
    ADJACENCY = 'canonical_adjacency'


# Presentation names map exactly to canonical Phase 3/4 groups; no new grouping.
RURALITY_LABELS = MappingProxyType({
    'Metro': 'Metropolitan',
    'Nonmetro': 'Nonmetropolitan',
    'Nonmetro adjacent': 'Nonmetropolitan — adjacent to metro',
    'Nonmetro not adjacent': 'Nonmetropolitan — not adjacent to metro',
})
RUCC_NOTE = ('USDA RUCC 2023 is a fixed geographic classification lens applied to the selected health observation year. '
             'It does not describe historical rural-status change.')
SOURCE_NOTE = ('CDC PLACES: modeled county prevalence and confidence intervals. IHME: YLL burden evidence and '
               'marginal uncertainty intervals; attribution and unit scale remain unknown pending provenance. '
               'RUCC 2023: geographic classification, not a health outcome.')


def places_counties():
    frame = run_query("""SELECT DISTINCT e.geoid AS fips, e.geography_name, e.state_name, e.state_abbr,
            g.location_name AS canonical_county_name
        FROM places.estimates e LEFT JOIN analytics.vw_current_county_lookup g ON g.fips=e.geoid
        WHERE e.geography_level='county' ORDER BY e.state_name, e.geography_name, e.geoid""")
    choices = {}
    for row in frame.itertuples(index=False):
        fips, name, state = str(row.fips), str(row.geography_name).strip(), str(row.state_name).strip()
        if not re.fullmatch(r'\d{5}', fips) or not name or not state or pd.isna(row.state_name) or pd.isna(row.geography_name):
            raise CatalogError('County catalog contains an invalid identity')
        # Prefer canonical county/equivalent names; never invent a County suffix
        # for parishes, independent cities, census areas or municipalities.
        if pd.notna(row.canonical_county_name):
            match = re.fullmatch(r'(.*?)\s*\(([^()]+)\)', str(row.canonical_county_name).strip())
            if match:
                name = match[1].strip()
        choice = CountyChoice(fips, name, state, '' if pd.isna(row.state_abbr) else str(row.state_abbr))
        if fips in choices and choices[fips] != choice:
            raise CatalogError('Conflicting county identities require catalog correction')
        choices[fips] = choice
    if len({c.label for c in choices.values()}) != len(choices):
        raise CatalogError('County labels are not uniquely disambiguated')
    return tuple(sorted(choices.values(), key=lambda c: (c.state, c.county)))


def selected_county(choice, catalog):
    """Validate the explicit selection using the canonical county resolver.

    Search is the selector's presentation job; an unresolved name is never
    converted to a first match. The researcher chooses a state-qualified row.
    """
    if choice is None or choice not in catalog:
        raise CatalogError('Choose a specific county and state')
    frame = pd.DataFrame([{'fips': c.fips, 'location_name': c.canonical_name} for c in catalog])
    resolved = resolve_county(choice.canonical_name, catalog=frame)
    if resolved['fips'] != choice.fips:
        raise CatalogError('County selection disagrees with canonical resolution')
    return resolved['fips']


def places_measures():
    frame = run_query('SELECT measure_id, canonical_name FROM places.measures ORDER BY canonical_name, measure_id')
    if frame['measure_id'].duplicated().any() or frame['canonical_name'].isna().any():
        raise CatalogError('PLACES measure catalog is not unique and complete')
    values = tuple(MeasureChoice(str(r.measure_id), str(r.canonical_name)) for r in frame.itertuples(index=False))
    if len({v.label for v in values}) != len(values):
        raise CatalogError('PLACES measure labels require disambiguation')
    return values


def places_releases(fips, measure_id):
    frame = run_query("""SELECT DISTINCT e.release_year FROM places.estimates e
        INNER JOIN places.releases r ON r.release_year=e.release_year
        INNER JOIN places.measure_versions v ON v.measure_id=e.measure_id AND v.release_year=e.release_year
        WHERE e.geography_level='county' AND e.geoid=? AND e.measure_id=?
          AND e.release_year BETWEEN 2020 AND 2025 ORDER BY e.release_year DESC""", [str(fips), str(measure_id)])
    return tuple(int(y) for y in frame['release_year'])


def _places_year_values(measure_id, policy, *, fips=None, release_for_year=None):
    if not isinstance(policy, YearPolicy):
        raise CatalogError('An explicit canonical year policy is required')
    conditions = ["e.geography_level='county'", 'e.measure_id=?', 'e.measurement_year BETWEEN ? AND ?']
    parameters = [str(measure_id), PLACES_FIRST_YEAR, PLACES_LAST_YEAR]
    if fips is not None:
        conditions.append('e.geoid=?')
        parameters.append(str(fips))
    join = ('INNER JOIN places.measure_versions v ON v.measure_id=e.measure_id AND v.release_year=e.release_year'
            if policy is YearPolicy.TREND else '')
    if policy is not YearPolicy.TREND:
        conditions.extend(['e.carry_forward=FALSE', 'e.age_adjusted_prevalence IS NOT NULL'])
    if policy in {YearPolicy.METRO, YearPolicy.ADJACENCY}:
        join = 'INNER JOIN geography.rucc_2023 r ON r.fips=e.geoid'
        conditions.extend(['r.source_year=2023', 'r.rucc_code BETWEEN 1 AND 9'])
        if policy is YearPolicy.METRO:
            conditions.append("r.metro_status IN ('Metro','Nonmetro')")
    column = 'measurement_year'
    if release_for_year is not None:
        conditions.append('e.measurement_year=?')
        parameters.append(int(release_for_year))
        column = 'release_year'
    frame = run_query('SELECT DISTINCT e.' + column + ' FROM places.estimates e ' + join +
        ' WHERE ' + ' AND '.join(conditions) + ' ORDER BY e.' + column + ' DESC', parameters)
    return tuple(int(y) for y in frame[column])


def places_years(measure_id, policy, *, fips=None):
    return _places_year_values(measure_id, policy, fips=fips)


def rural_releases(measure_id, year, *, adjacency=False):
    policy = YearPolicy.ADJACENCY if adjacency else YearPolicy.METRO
    return _places_year_values(measure_id, policy, release_for_year=year)



def approved_pairs():
    measures = {m.measure_id: m for m in places_measures()}
    causes = run_query('SELECT cause_id, cause_name FROM analytics.dim_cause ORDER BY cause_id')
    if causes['cause_id'].duplicated().any():
        raise CatalogError('IHME cause catalog has duplicate identities')
    names = {int(r.cause_id): str(r.cause_name) for r in causes.itertuples(index=False) if pd.notna(r.cause_name)}
    return tuple(PairChoice(measures[mid], cid, names[cid])
        for mid, ids in APPROVED_PLACES_IHME_PAIRS.items() if mid in measures
        for cid in sorted(ids) if cid in names)


def _pair_year_values(pair, *, release_for_year=None):
    if not isinstance(pair, PairChoice) or pair.cause_id not in APPROVED_PLACES_IHME_PAIRS.get(pair.measure.measure_id, ()):
        raise CatalogError('Only approved source concept pairs are selectable')
    # Catalog availability checks the exact legacy basis and a matched county,
    # not completeness or statistical validity. No estimates are selected.
    cap = CAPABILITIES['get_places_ihme_rurality_comparison']
    ihme_first, ihme_last = MEASUREMENT_YEAR_BOUNDS[Source.IHME]
    clauses = ['i.' + name + '=?' for name, _ in cap.fixed_filters]
    params = [pair.measure.measure_id, pair.cause_id, max(PLACES_FIRST_YEAR, ihme_first), min(PLACES_LAST_YEAR, ihme_last)]
    params.extend(value for _, value in cap.fixed_filters)
    column = 'measurement_year' if release_for_year is None else 'release_year'
    if release_for_year is not None:
        clauses.append('e.measurement_year=?')
        params.append(int(release_for_year))
    frame = run_query('SELECT DISTINCT e.' + column + """ FROM places.estimates e
        INNER JOIN ihme.burden i ON i.fips=e.geoid AND i.year=e.measurement_year
        INNER JOIN geography.rucc_2023 r ON r.fips=e.geoid
        WHERE e.geography_level='county' AND e.measure_id=? AND i.cause_id=?
          AND e.measurement_year BETWEEN ? AND ? AND e.carry_forward=FALSE
          AND e.age_adjusted_prevalence IS NOT NULL AND i.val IS NOT NULL
          AND i.measure_id=4 AND i.metric_id=3 AND r.source_year=2023 AND r.rucc_code BETWEEN 1 AND 9
          AND """ + ' AND '.join(clauses) + ' ORDER BY e.' + column + ' DESC', params)
    return tuple(int(y) for y in frame[column])


def pair_years(pair):
    return _pair_year_values(pair)


def pair_releases(pair, year):
    return _pair_year_values(pair, release_for_year=year)
