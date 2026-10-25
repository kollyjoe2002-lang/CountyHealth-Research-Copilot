from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import research_catalogs as catalog
from app import research_controls as controller
from app.research_widgets import selector, show_provenance, infrastructure_message
from ai.capabilities import REGISTRY_VERSION

st.set_page_config(page_title='CDC PLACES', page_icon='🏥', layout='wide')


def main():
    st.title('CDC PLACES')
    st.caption('Explore modeled county prevalence. Choose a health concept and county; EpiCounty resolves the identifiers.')
    st.info('PLACES confidence intervals describe modeled prevalence. Release year and underlying measurement year are different. Catalog availability does not establish complete coverage.')
    analysis = st.selectbox('Analysis', ['County snapshot', 'County measure trend', 'National county ranking'])
    try:
        measures = catalog.places_measures()
        if not measures:
            st.warning("No PLACES health measures are listed in the checked catalog. Execution is disabled.")
        measure = selector('Health measure', measures, key='places_measure', formatter=lambda m: m.label)
        county = None
        if analysis != 'National county ranking':
            counties = catalog.places_counties()
            if not counties:
                st.warning("No counties are listed in the checked PLACES catalog. Execution is disabled.")
            county = selector('County and state', counties, key='places_county', formatter=lambda c: c.label)
            st.caption('Search by county or state, then choose the state-qualified result. Ambiguous names are never guessed.')
        ready = measure is not None and (county is not None or analysis == 'National county ranking')
        metadata = {'Source': 'CDC PLACES', 'Registry version': REGISTRY_VERSION}
        if measure:
            metadata['PLACES measure ID'] = measure.measure_id
        if county:
            metadata['County FIPS'] = county.fips
        if analysis == 'County snapshot':
            releases = catalog.places_releases(county.fips, measure.measure_id) if ready else ()
            release = selector('PLACES release year', releases, key='places_release')
            st.caption('A release snapshot preserves the source measurement year and carry-forward status of each observation.')
            if ready and not releases:
                st.warning('This county/measure has no available release snapshot. Execution is disabled; no year was substituted.')
            clicked = st.button('Run snapshot', type='primary', disabled=not ready or release is None)
            if clicked:
                frame = controller.places_snapshot(county, measure, release)
                metadata.update({'Capability': 'get_places_county_snapshot', 'Release year': release, 'Measurement years': sorted(frame['measurement_year'].dropna().astype(int).unique().tolist())})
                if frame.empty:
                    st.warning('No matching snapshot records were returned for this exact selection.')
                else:
                    st.subheader(f'{measure.label} — {county.label}')
                    st.dataframe(frame[['release_year','measurement_year','crude_prevalence','crude_ci_lower',
                        'crude_ci_upper','age_adjusted_prevalence','age_adjusted_ci_lower','age_adjusted_ci_upper','carry_forward','missing_reason']],
                        hide_index=True, width='stretch')
                show_provenance(metadata)
        elif analysis == 'County measure trend':
            years = catalog.places_years(measure.measure_id, catalog.YearPolicy.TREND, fips=county.fips) if ready else ()
            # Empty defaults require an explicit year selection, never another year.
            if any(y not in years for y in st.session_state.get('places_trend_years', [])):
                st.session_state['places_trend_years'] = []
            selected = st.multiselect('Observation measurement years', years, key='places_trend_years')
            if ready and not years:
                st.warning('No measurement years satisfy this county/measure policy. Execution is disabled.')
            st.caption('History retains release years and carry-forward flags. Carry-forward observations are not independent new measurements. The page measurement-year policy is 2018–2023.')
            if st.button('Run trend', type='primary', disabled=not ready or not selected):
                frame = controller.places_trend(county, measure, selected)
                if frame.empty:
                    st.warning('No history records were returned for the exact selection.')
                else:
                    st.line_chart(frame.set_index('measurement_year')[['age_adjusted_prevalence']])
                    st.dataframe(frame[['release_year','measurement_year','age_adjusted_prevalence',
                        'age_adjusted_ci_lower','age_adjusted_ci_upper','carry_forward','missing_reason']], hide_index=True, width='stretch')
                metadata.update({'Capability': 'get_places_county_measure_trend', 'Measurement years': list(selected), 'Release years': sorted(frame['release_year'].dropna().astype(int).unique().tolist()),
                    'Carry-forward policy': 'Retained and flagged in history'})
                show_provenance(metadata)
        else:
            years = catalog.places_years(measure.measure_id, catalog.YearPolicy.RANKING) if measure else ()
            year = selector('Observation measurement year', years, key='places_ranking_year')
            limit = st.slider('Number of counties', 5, 100, 25, 5)
            if measure and not years:
                st.warning('No measurement years satisfy the canonical ranking policy for this measure. Execution is disabled.')
            st.caption('Rankings use age-adjusted prevalence and exclude carry-forward observations.')
            if st.button('Run ranking', type='primary', disabled=measure is None or year is None):
                frame = controller.places_ranking(measure, year, limit)
                if frame.empty:
                    st.warning('No matching ranking records were returned.')
                else:
                    st.dataframe(frame[['national_rank','geography_name','state_name','age_adjusted_prevalence',
                        'age_adjusted_ci_lower','age_adjusted_ci_upper']], hide_index=True, width='stretch')
                metadata.update({'Measurement year': year, 'Release years': sorted(frame['release_year'].dropna().astype(int).unique().tolist()),
                    'Carry-forward policy': 'Excluded', 'Capability': 'get_places_county_measure_ranking'})
                show_provenance(metadata)
    except catalog.CatalogError as exc:
        st.warning(str(exc))
    except Exception:
        infrastructure_message()
        st.button('Analysis unavailable', disabled=True)


main()
