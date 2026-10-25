"""Read-only real-data activation assessment. Never activates a registry entry.

A caller must supply a development warehouse explicitly. Test-fixture reports
are intrinsically non-activating; neither file existence nor passing sampled
queries certifies an entire public analytical envelope.
"""
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import perf_counter
import math
import re
import duckdb
from ai.capabilities import Source, GeographyMode, REGISTRY_VERSION, MULTIDIMENSIONAL_RELATIONS as REL
from ai.multidimensional_integration import wire
from ai.query_models import (ResolvedQuery, SourceConcept, SourceTime, TimeSpec, TimeAlignment,
    ReleasePolicy, DemographicStratum, PopulationValue as V, Dimension as D,
    ComparisonSpec, GeographySpec, QueryOperation, AGE_STANDARDIZED_20_PLUS, assess_query_contract, DecisionStatus)
from app.multidimensional import compare_strata, summarize_by_rurality


@dataclass(frozen=True)
class CoverageAcceptance:
    minimum_eligible_counties: int
    minimum_paired_percent: float
    minimum_rural_percent: float
    review_reference: str

    def __post_init__(self):
        if type(self.minimum_eligible_counties) is not int or self.minimum_eligible_counties < 1:
            raise ValueError('Explicit positive county acceptance is required')
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0 < v <= 100
               for v in (self.minimum_paired_percent,self.minimum_rural_percent)):
            raise ValueError('Explicit finite coverage percentages in (0,100] are required')
        if not self.review_reference.strip():
            raise ValueError('A scientific acceptance review reference is required')


@dataclass(frozen=True)
class ActivationProfile:
    years: tuple[int,...] = (2000,2010,2019)
    ages: tuple[str,...] = ('40-44','60-64','80-84')
    acceptance: CoverageAcceptance | None = None
    scope: str = 'actual_development'

    def __post_init__(self):
        if not isinstance(self.years,tuple) or not isinstance(self.ages,tuple):
            raise ValueError('Immutable tuples required for sample profile')
        if self.acceptance is not None and not isinstance(self.acceptance,CoverageAcceptance):
            raise ValueError('Explicit typed coverage acceptance required')
        if self.scope not in {'actual_development','structural_fixture_only'}:
            raise ValueError('Explicit actual-development or structural-fixture scope required')
        if len(set(self.years)) != len(self.years) or not self.years or any(type(y) is not int or not 2000<=y<=2019 for y in self.years):
            raise ValueError('Unique IHME observation years required')
        if not {'40-44','60-64','80-84'}.issubset(self.ages) or len(set(self.ages))!=len(self.ages):
            raise ValueError('Representative ages must include 40-44,60-64,80-84')
        for age in self.ages:
            V.subgroup(D.AGE,age)


def check(name,status,reason,**details):
    return dict(gate=name,status=status,reason=reason,details=wire(details))


def query_cases(cause_id,cause_name,profile):
    """Independent orientations on exact canonical population contracts."""
    total,both=V.total(D.RACE_ETHNICITY),V.total(D.SEX)
    female,male=V.subgroup(D.SEX,'Female'),V.subgroup(D.SEX,'Male')
    agevals=[V.subgroup(D.AGE,a) for a in profile.ages]
    std=V.subgroup(D.AGE,AGE_STANDARDIZED_20_PLUS)
    def query(key,sex,age,comparison=None,rural=False,group=None):
        return ResolvedQuery(capability_key=key,
            concepts=(SourceConcept(source=Source.IHME,concept_id=cause_id,name=cause_name,dataset_version='unknown'),),
            stratum=DemographicStratum(sex=sex,age=age,race_ethnicity=total),comparison=comparison,
            geography=GeographySpec(mode=GeographyMode.RUCC_ADJACENCY if rural else GeographyMode.COUNTY_UNIVERSE,
                classification_year=2023 if rural else None,
                rurality_filter=V.subgroup(D.RURALITY,group) if group else V.unspecified(D.RURALITY)),
            operation=QueryOperation.COMPARE_GROUPS if comparison else QueryOperation.SUMMARIZE_BY_RURALITY,
            time=TimeSpec(sources=(SourceTime(source=Source.IHME,years=profile.years,release_policy=ReleasePolicy.SOURCE_OBSERVATION),),alignment=TimeAlignment.SINGLE_SOURCE))
    for sex in (female,male):
        for a,b in zip(agevals,agevals[1:]):
            yield f'age_{a.value}_vs_{b.value}_fixed_{sex.value}',query('sex_age',sex,V.unspecified(D.AGE),ComparisonSpec(dimension=D.AGE,group_a=a,group_b=b))
    for age in agevals:
        yield f'sex_comparison_fixed_{age.value}',query('sex_age',V.unspecified(D.SEX),age,ComparisonSpec(dimension=D.SEX,group_a=female,group_b=male))
    for sex in (female,male):
        yield f'{sex.value}_rural_summary',query('sex_rurality',sex,std,rural=True)
    for age in agevals:
        yield f'{age.value}_rural_summary',query('age_rurality',both,age,rural=True)
    for group in ('Metro','Nonmetro adjacent','Nonmetro not adjacent'):
        yield f'sex_comparison_in_{group}',query('sex_rurality',V.unspecified(D.SEX),std,
            ComparisonSpec(dimension=D.SEX,group_a=female,group_b=male),True,group)
        yield f'age_comparison_in_{group}',query('age_rurality',both,V.unspecified(D.AGE),
            ComparisonSpec(dimension=D.AGE,group_a=agevals[0],group_b=agevals[1]),True,group)


def lineage_audit(connection):
    """Import linkage, not evidence of High BMI or a known rate denominator."""
    report={'attribution':'UNKNOWN','unit_scale':'UNKNOWN','dataset_version':'UNKNOWN',
        'source_identity':'UNKNOWN','import_linkage':'BLOCKED',
        'note':'Filenames, IDs and legacy wording cannot establish attribution or rate scale.'}
    columns={r[0] for r in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='ihme' AND table_name='burden'").fetchall()}
    logcols={r[0] for r in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='ihme' AND table_name='import_log'").fetchall()}
    if not {'source_file','imported_at'}.issubset(columns) or not {'file_name','dataset_type','status','completed_at'}.issubset(logcols):
        return report
    duplicate=connection.execute('SELECT COUNT(*) FROM (SELECT file_name FROM ihme.import_log GROUP BY file_name HAVING COUNT(*)>1)').fetchone()[0]
    missing=connection.execute("""SELECT COUNT(*) FROM ihme.burden b LEFT JOIN ihme.import_log l ON l.file_name=b.source_file
        WHERE b.measure_id=4 AND b.metric_id=3 AND
        (b.source_file IS NULL OR trim(b.source_file)='' OR b.imported_at IS NULL OR l.file_name IS NULL OR
         l.status IS DISTINCT FROM 'SUCCESS' OR l.dataset_type IS DISTINCT FROM 'BURDEN' OR l.completed_at IS NULL)""").fetchone()[0]
    selected=connection.execute('SELECT COUNT(*) FROM ihme.burden WHERE measure_id=4 AND metric_id=3').fetchone()[0]
    report.update(import_linkage='PASS' if selected>0 and missing==0 and duplicate==0 else 'FAIL',
                  yll_rows=selected,unlinked_rows=missing,duplicate_import_keys=duplicate)
    return report


def _process_memory():
    try:
        import resource
        import sys
        return {'process_max_rss':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'units':'bytes' if sys.platform=='darwin' else 'KiB',
                'scope':'process lifetime peak, not a query-specific allocation delta'}
    except ImportError:
        return {'scope':'Unavailable on this platform; no estimated memory figure substituted'}


def assess_warehouse(database_path=None, *, profile=None):
    profile=profile or ActivationProfile()
    output={'scope':profile.scope,'profile':wire(profile),'registry_version':REGISTRY_VERSION,'public_activation_performed':False,
        'capabilities':{},'checks':[], 'semantics':{'attribution':'UNKNOWN','unit_scale':'UNKNOWN','dataset_version':'UNKNOWN'}}
    for key in ('sex_age','sex_rurality','age_rurality'):
        output['capabilities'][key]={'status':'BLOCKED','data_gate_ready':False,'registry_state':'PLANNED'}
    if database_path is None:
        output['checks'].append(check('explicit_warehouse','BLOCKED','No actual development warehouse was supplied; no production access attempted'))
        return output
    path=Path(database_path)
    if not path.is_file():
        output['checks'].append(check('explicit_warehouse','BLOCKED','The explicitly supplied warehouse does not exist'))
        return output
    before=(path.stat().st_size,path.stat().st_mtime_ns)
    output['warehouse_identity']={'bytes':before[0],'mtime_ns':before[1],
        'identity_limit':'Metadata snapshot only; no filename-derived scientific provenance or implicit full-file checksum'}
    per_cap={key:[] for key in output['capabilities']}
    started=perf_counter()
    try:
        connection=duckdb.connect(str(path),read_only=True,config={"enable_external_access":"false"})
        try:
            connection.execute('BEGIN TRANSACTION')
            marker=connection.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='analytics' AND table_name='multidimensional_fixture_marker'").fetchone()[0]
            if marker and profile.scope=='actual_development':
                output['checks'].append(check('real_data_identity','FAIL','Synthetic fixture marker prohibits a real-data activation pass'))
                raise ValueError('Synthetic source cannot enter real-data gate')
            output['checks'].append(check('real_data_identity','PASS' if profile.scope=='actual_development' else 'BLOCKED',
                'Explicitly supplied development source; not a proof of scientific provenance' if profile.scope=='actual_development' else 'Structural fixture cannot establish real-data activation'))
            output['semantics']=lineage_audit(connection)
            output['checks'].append(check('import_linkage',output['semantics']['import_linkage'],'Import linkage only; scientific attribution/unit/version remain UNKNOWN'))
            causes_relation=REL['causes']
            causes=connection.execute(f"SELECT cause_id,cause_name FROM {causes_relation.qualified_name}").fetchall()
            ids={}
            for cid,name in causes:
                if name in ids:
                    raise ValueError('Duplicate cause catalog label')
                ids[name]=cid
            required=('Ischemic heart disease','Stroke')
            for label in required:
                output['checks'].append(check('cause_catalog_'+label,'PASS' if label in ids else 'FAIL','Exact representative cause catalog resolution'))
            available=[n for n in (*required,'Diabetes mellitus type 2') if n in ids]
            if 'Diabetes mellitus type 2' not in ids:
                output['checks'].append(check('optional_type2_diabetes','BLOCKED','Not in the supplied cause catalog; do not substitute a different diabetes concept'))
            if len(profile.years)<2:
                output['checks'].append(check('representative_year_profile','BLOCKED','At least two distinct representative years are needed for activation'))
            if profile.acceptance is None:
                output['checks'].append(check('coverage_acceptance','BLOCKED','No reviewed quantitative coverage acceptance was supplied; percentages will be measured, not guessed'))
            # RUCC integrity is a dependency only of the two rural capabilities.
            for key in ('sex_rurality','age_rurality'):
                try:
                    duplicate=connection.execute('SELECT COUNT(*) FROM (SELECT fips FROM geography.rucc_2023 GROUP BY fips HAVING COUNT(*)>1)').fetchone()[0]
                    invalid=connection.execute("SELECT COUNT(*) FROM geography.rucc_2023 WHERE fips IS NULL OR NOT regexp_full_match(fips,'[0-9]{5}') OR source_year IS DISTINCT FROM 2023").fetchone()[0]
                    item=check(key+'/rucc_key_integrity','FAIL' if duplicate or invalid else 'PASS','Global RUCC FIPS uniqueness and fixed-year integrity',duplicate_keys=duplicate,invalid_rows=invalid)
                except Exception as exc:
                    item=check(key+'/rucc_key_integrity','FAIL','RUCC dependency cannot be validated',error_type=type(exc).__name__)
                output['checks'].append(item)
                per_cap[key].append(item)
            # Benchmark the exact catalog projection used by Streamlit. Failure
            # belongs to compatibility, not to scientific absence.
            from ai.capability_conversation import load_capability_catalog_path
            tick=perf_counter()
            try:
                timings=[]
                for _ in range(3):
                    refresh_start=perf_counter()
                    catalog=load_capability_catalog_path(path)
                    timings.append(perf_counter()-refresh_start)
                output['checks'].append(check('streamlit_catalog_refresh','PASS','Exact read-only UI refresh including connection overhead; three uncached repeats measured',seconds=perf_counter()-tick,repeat_seconds=timings,catalog_fingerprint=catalog.fingerprint))
            except Exception as exc:
                output['checks'].append(check('streamlit_catalog_refresh','FAIL','Canonical UI catalog compatibility check failed',error_type=type(exc).__name__,seconds=perf_counter()-tick))
        finally:
            connection.close()
        for cause in available:
            for name,query in query_cases(ids[cause],cause,profile):
                tick=perf_counter()
                try:
                    if assess_query_contract(query).status is not DecisionStatus.PLANNED:
                        raise ValueError('Query does not preserve the approved envelope')
                    result=(compare_strata(query,database_path=path) if query.comparison else summarize_by_rurality(query,database_path=path))
                    coverage=(result.coverage if query.comparison else result.coverage+tuple(s.coverage for s in result.summaries))
                    errors=[]
                    if any(d.unavailable_reason for d in result.values.groups): errors.append('unavailable requested demographic catalog label')
                    for item in coverage:
                        if item.eligible_counties<=0: errors.append('empty eligible county universe/stratum')
                        count=getattr(item,'complete_paired_counties',getattr(item,'observations_available',0))
                        if count<=0: errors.append('no complete paired/observed counties')
                        percent=getattr(item,'paired_coverage_percent',getattr(item,'coverage_percent',None))
                        if profile.acceptance:
                            floor=(profile.acceptance.minimum_paired_percent if query.comparison else profile.acceptance.minimum_rural_percent)
                            if percent is None or percent<floor: errors.append('coverage below reviewed acceptance')
                            if item.rurality_group is None and not query.geography.rurality_filter.value and item.eligible_counties<profile.acceptance.minimum_eligible_counties: errors.append('county universe below reviewed acceptance')
                    if query.geography.requires_rurality and not query.geography.rurality_filter.value:
                        if {c.rurality_group for c in coverage if c.rurality_group is not None}!={'Metro','Nonmetro adjacent','Nonmetro not adjacent'}:
                            errors.append('not all three RUCC groups represented')
                    row=check(query.capability_key+'/'+cause+'/'+name,'FAIL' if errors else 'PASS',
                        '; '.join(sorted(set(errors))) or 'Deterministic key, bounds and coverage checks passed for sampled query',
                        seconds=perf_counter()-tick,coverage=coverage,
                        observations_returned=len(result.values.observations),
                        analytic_rows_returned=len(result.comparisons) if query.comparison else len(result.summaries),
                        source_rows_read='not instrumented; no fabricated scan count',
                        peak_memory=_process_memory(),memory_concern='Dense county/stratum result footprint; process peak is not a per-query allocation delta')
                except Exception as exc:
                    row=check(query.capability_key+'/'+cause+'/'+name,'FAIL','Deterministic sample rejected; no deduplication or alternate population used',error_type=type(exc).__name__,seconds=perf_counter()-tick)
                output['checks'].append(row)
                per_cap[query.capability_key].append(row)
        # Prove rejected triple intersections remain rejected, independent of data.
        sample=next(query_cases(494,'Stroke',profile))[1]
        triple=replace(sample,geography=GeographySpec(mode=GeographyMode.RUCC_ADJACENCY,classification_year=2023))
        output['checks'].append(check('triple_intersection_guard','PASS' if assess_query_contract(triple).status is DecisionStatus.UNSUPPORTED else 'FAIL','Unvalidated sex × age × rurality remains rejected'))
    except Exception as exc:
        output['checks'].append(check('warehouse_schema_or_query','FAIL','Explicit warehouse could not satisfy read-only compatibility checks',error_type=type(exc).__name__))
    finally:
        output['duration_seconds']=perf_counter()-started
        output['read_only_file_unchanged']=(before==(path.stat().st_size,path.stat().st_mtime_ns))
    if not output.get('read_only_file_unchanged',False):
        output['checks'].append(check('warehouse_snapshot_integrity','FAIL','Warehouse identity changed during the audit; results cannot authorize activation'))
    shared=[c for c in output['checks'] if not c['gate'].startswith(tuple(per_cap)) and c['gate'] not in {'optional_type2_diabetes','streamlit_catalog_refresh'}]
    for key,rows in per_cap.items():
        failures=any(r['status']=='FAIL' for r in rows+shared)
        blocked=any(r['status']=='BLOCKED' for r in rows+shared) or profile.scope!='actual_development' or not rows
        status='FAIL' if failures else 'BLOCKED' if blocked else 'PASS'
        output['capabilities'][key].update(status=status,data_gate_ready=status=='PASS',sample_cases=len(rows))
    # An observation-only report cannot change executable state or satisfy live
    # parser/entailment/full-regression gates. Activation requires separate review.
    return output
