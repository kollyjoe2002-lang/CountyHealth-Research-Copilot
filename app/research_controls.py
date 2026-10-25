"""Thin controllers for existing deterministic pages, with fail-closed selections."""
from app import data_access as data
from app import research_catalogs as catalog


def require_choice(value, options, label):
    if value is None or value not in options:
        raise catalog.CatalogError(f'Choose an available {label}; no substitute was selected')
    return value


def places_snapshot(county, measure, release):
    fips = catalog.selected_county(county, catalog.places_counties())
    require_choice(measure, catalog.places_measures(), 'health measure')
    require_choice(release, catalog.places_releases(fips, measure.measure_id), 'release year')
    # The original release-snapshot API remains unchanged; this is display selection.
    result = data.get_places_county_snapshot(fips, release)
    return result.loc[result['measure_id'] == measure.measure_id].copy()


def places_trend(county, measure, years):
    fips = catalog.selected_county(county, catalog.places_counties())
    require_choice(measure, catalog.places_measures(), 'health measure')
    allowed = catalog.places_years(measure.measure_id, catalog.YearPolicy.TREND, fips=fips)
    if not years or any(y not in allowed for y in years):
        raise catalog.CatalogError('Select observed measurement years; no substitute was selected')
    result = data.get_places_county_measure_trend(fips, measure.measure_id)
    # Limit the visible history only; keep release, CI and carry-forward metadata.
    return result.loc[result['measurement_year'].isin(years)].copy()


def places_ranking(measure, year, limit):
    require_choice(measure, catalog.places_measures(), 'health measure')
    require_choice(year, catalog.places_years(measure.measure_id, catalog.YearPolicy.RANKING), 'measurement year')
    return data.get_places_county_measure_ranking(measure.measure_id, year, limit)


def rural_summary(measure, year, *, adjacency=False, detailed=False):
    require_choice(measure, catalog.places_measures(), 'health measure')
    if adjacency and detailed:
        raise catalog.CatalogError('Choose one validated rurality grouping')
    policy = catalog.YearPolicy.ADJACENCY if adjacency or detailed else catalog.YearPolicy.METRO
    require_choice(year, catalog.places_years(measure.measure_id, policy), 'measurement year')
    if detailed:
        return data.get_places_rucc_comparison(measure.measure_id, year)
    if adjacency:
        return data.get_places_rucc_adjacent_comparison(measure.measure_id, year)
    return data.get_places_rural_metro_comparison(measure.measure_id, year)


def cross_source_summary(pair, year):
    require_choice(pair, catalog.approved_pairs(), 'approved concept pair')
    require_choice(year, catalog.pair_years(pair), 'matched observation year')
    return data.get_places_ihme_rurality_comparison(pair.measure.measure_id, year, pair.cause_id, year)
