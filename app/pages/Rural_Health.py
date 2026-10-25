from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import research_catalogs as catalog
from app import research_controls as controller
from app.research_widgets import selector, rural_labels, show_provenance, infrastructure_message
from ai.capabilities import REGISTRY_VERSION, SOURCE_RESTRICTIONS, Source

st.set_page_config(page_title='Rural Health', page_icon='🌎', layout='wide')


def main():
    st.title('Rural Health')
    st.info(catalog.RUCC_NOTE)
    st.caption(catalog.SOURCE_NOTE)
    st.caption('Group means and medians weight counties equally; they are not population-weighted national estimates. Catalog listings do not certify complete coverage.')
    analysis = st.selectbox('Analysis', ['Metro vs nonmetro prevalence', 'Three rurality groups', 'Detailed rurality categories', 'PLACES + IHME rurality comparison'])
    try:
        metadata = {'RUCC classification year': 2023, 'Registry version': REGISTRY_VERSION,
                    'RUCC definitions': next(r.rules for r in SOURCE_RESTRICTIONS if r.source is Source.RUCC)}
        if analysis == 'PLACES + IHME rurality comparison':
            pairs = catalog.approved_pairs()
            pair = selector('Approved health concept relationship', pairs, key='rural_pair', formatter=lambda p: p.label)
            years = catalog.pair_years(pair) if pair else ()
            year = selector('Matched observation year (PLACES and IHME)', years, key='rural_pair_year')
            st.info('CDC PLACES prevalence and IHME YLL burden are separate metrics. Attribution and IHME unit scale remain unknown pending verified provenance.')
            if not pairs:
                st.warning('No approved concept relationship is available in the checked catalogs. Arbitrary source pairing is disabled.')
            elif pair and not years:
                st.warning('This approved relationship has no matched year satisfying the canonical source/geography policy. Execution is disabled.')
            if st.button('Run cross-source rurality comparison', type='primary', disabled=pair is None or year is None):
                frame = rural_labels(controller.cross_source_summary(pair, year))
                if frame.empty:
                    st.warning('No matched observations were returned for this exact relationship and year.')
                else:
                    left, right = st.columns(2)
                    with left:
                        st.subheader('CDC PLACES prevalence')
                        st.bar_chart(frame.set_index('rurality_group')[['median_places_prevalence']])
                    with right:
                        st.subheader('IHME YLL rate — unit scale unverified')
                        st.bar_chart(frame.set_index('rurality_group')[['median_ihme_yll_rate']])
                    st.dataframe(frame[['rurality_group','counties','mean_places_prevalence',
                        'median_places_prevalence','mean_ihme_yll_rate','median_ihme_yll_rate']], hide_index=True, width='stretch')
                metadata.update({'PLACES measure ID': pair.measure.measure_id, 'IHME cause ID': pair.cause_id,
                    'PLACES measurement year': year, 'PLACES eligible release years': list(catalog.pair_releases(pair, year)), 'IHME observation year': year,
                    'Capability': 'get_places_ihme_rurality_comparison', 'Carry-forward policy': 'Excluded'})
                show_provenance(metadata)
        else:
            measures = catalog.places_measures()
            if not measures:
                st.warning("No PLACES health measures are listed in the checked catalog. Execution is disabled.")
            measure = selector('Health measure', measures, key='rural_measure', formatter=lambda m: m.label)
            adjacency = analysis == 'Three rurality groups'
            detailed = analysis == 'Detailed rurality categories'
            policy = catalog.YearPolicy.ADJACENCY if adjacency or detailed else catalog.YearPolicy.METRO
            years = catalog.places_years(measure.measure_id, policy) if measure else ()
            year = selector('PLACES observation measurement year', years, key='rural_year')
            if measure and not years:
                st.warning('No measurement years satisfy the selected measure and rurality policy. Execution is disabled.')
            st.caption('Age-adjusted prevalence; carry-forward observations excluded. Missing RUCC classifications are not assigned to another group.')
            if st.button('Run rurality summary', type='primary', disabled=measure is None or year is None):
                frame = rural_labels(controller.rural_summary(measure, year, adjacency=adjacency, detailed=detailed))
                if frame.empty:
                    st.warning('No matching rurality observations were returned.')
                else:
                    group = 'rucc_description' if detailed else 'rurality_group' if adjacency else 'metro_status'
                    st.bar_chart(frame.set_index(group)[['median_prevalence']])
                    st.dataframe(frame[[group,'counties_with_estimate','mean_prevalence','median_prevalence']], hide_index=True, width='stretch')
                metadata.update({'PLACES measure ID': measure.measure_id, 'Measurement year': year,
                    'PLACES eligible release years': list(catalog.rural_releases(measure.measure_id, year, adjacency=adjacency or detailed)), 'Carry-forward policy': 'Excluded',
                    'Capability': 'get_places_rucc_comparison' if detailed else 'get_places_rucc_adjacent_comparison' if adjacency else 'get_places_rural_metro_comparison'})
                show_provenance(metadata)
    except catalog.CatalogError as exc:
        st.warning(str(exc))
    except Exception:
        infrastructure_message()
        st.button('Analysis unavailable', disabled=True)
    st.caption('Descriptive comparisons do not establish causation. Fixed-sex and fixed-age rurality capabilities remain planned, not activated.')


main()
