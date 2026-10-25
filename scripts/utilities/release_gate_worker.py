"""Run a legacy gate on an explicitly supplied development DB, forced read-only.

The worker never discovers or opens a production location. Archive/test DBs must
be supplied separately in a future audited gate; they are not silently remapped.
"""
from pathlib import Path
import runpy
import json
import builtins
import sys
import tempfile
import duckdb
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))


class BlockedPrerequisite(RuntimeError):
    pass


def main():
    target,db_path=sys.argv[1:3]
    extra=sys.argv[3:]
    explicit=Path(db_path).resolve()
    if not explicit.is_file(): raise SystemExit('BLOCKED: explicit development warehouse missing')
    targets={'countyhealth.duckdb':explicit}
    if extra and extra[0]!='-':
        declared=json.loads(Path(extra[0]).read_text())
        allowed={f'places_{year}_test.duckdb' for year in range(2020,2026)}
        if not set(declared).issubset(allowed):
            raise SystemExit('BLOCKED: unrecognized auxiliary database identity')
        for name,value in declared.items():
            path=Path(value).resolve()
            if not path.is_file(): raise SystemExit('BLOCKED: explicitly declared auxiliary database missing')
            targets[name]=path
    if len(extra)>1 and extra[1]!='-':
        geo=Path(extra[1]).resolve()
        if not geo.is_file(): raise SystemExit('BLOCKED: explicitly declared GeoJSON missing')
        targets['counties.geojson']=geo
    original_exists,original_is_file=Path.exists,Path.is_file
    def alias(path):
        return targets.get(str(path).replace('\\','/').rsplit('/',1)[-1])
    Path.exists=lambda self: original_exists(alias(self) or self)
    Path.is_file=lambda self: original_is_file(alias(self) or self)
    original_open=builtins.open
    def open_declared(file,mode='r',*args,**kwargs):
        if not isinstance(file,int) and str(file).replace('\\','/').rsplit('/',1)[-1]=='counties.geojson':
            if 'counties.geojson' not in targets or any(c in mode for c in 'wa+'):
                raise BlockedPrerequisite('GeoJSON input was not explicitly supplied for a read-only audit')
            file=targets['counties.geojson']
        return original_open(file,mode,*args,**kwargs)
    builtins.open=open_declared
    original=duckdb.connect
    temporary_owned=set()
    def connect(database=':memory:',*args,**kwargs):
        name=str(database).replace('\\','/')
        path=Path(name).resolve()
        chosen=explicit if path==explicit else targets.get(name.rsplit('/',1)[-1])
        if chosen is not None:
            if args:
                args=(True,)+args[1:]
                kwargs.pop('read_only',None)
            else:
                kwargs['read_only']=True
            config=dict(kwargs.get('config') or {})
            config['enable_external_access']='false'
            kwargs['config']=config
            return original(str(chosen),*args,**kwargs)
        if name==':memory:':
            return original(database,*args,**kwargs)
        if path.is_relative_to(Path(tempfile.gettempdir()).resolve()) and (not path.exists() or path in temporary_owned):
            temporary_owned.add(path)
            return original(database,*args,**kwargs)
        raise BlockedPrerequisite('An auxiliary database was not explicitly supplied; no automatic external access')
    duckdb.connect=connect
    import app.data_access as data
    data.DB_FILE=explicit
    sys.modules.setdefault('data_access',data)
    # Analytical gates may not create/persist operational events while auditing.
    import ai.research_assistant as assistant
    assistant.persist_research_telemetry=lambda *args,**kwargs: None
    try:
        sys.argv=[target]+(['--warehouse',str(explicit)] if Path(target).stem=='check_v1_3_live_semantics' else [])
        runpy.run_path(str(ROOT/target),run_name='__main__')
    except BlockedPrerequisite:
        print('BLOCKED: auxiliary database input is not explicitly supplied')
        raise SystemExit(2)


if __name__=='__main__': main()
