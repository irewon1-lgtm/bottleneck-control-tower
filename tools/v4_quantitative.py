"""Manual bounded Q1 batches. No CPU, AI, cron, candidate or operational writes."""
import argparse,json,hashlib,time,sys,calendar
from pathlib import Path
from collections import Counter
from bct.v4.store import Ledger,now,sha
from bct.v4.quantitative import commit_page,parse_fed,parse_m3,parse_eia,parse_tungsten,records,backup_restore,verify_locator,research_export,quantity_role

ROOT=Path('var/v4/quantitative/q1');REG=Path('docs/v4/quantitative/source-registry.json')

def metadata(name,source,published):
    p=ROOT/'discovery'/(name+'.raw');r=json.loads((ROOT/'discovery'/(name+'.json')).read_text())
    if r.get('status')!=200:raise ValueError('SOURCE_NOT_CAPTURED')
    return dict(r,path=str(p),source_id=source,published_at=published,last_modified=r.get('headers',{}).get('last-modified','UNKNOWN'))

def saved_task(ledger,task):
    return bool(ledger.db.execute("select 1 from events where kind='QUANTITATIVE_PAGE_COMMITTED' and json_extract(payload,'$.task')=?",(task,)).fetchone())

def batch(source):
    registry=json.loads(REG.read_text());scope=registry['sources'][source]['scope'];out=[]
    ledger=Ledger(ROOT/'ledger')
    with ledger.worker():
        if source=='g17':
            for f in ['ip','cap','utl','auto']:
                task='g17-'+f
                if saved_task(ledger,task):out.append({'task':task,'status':'UNCHANGED_COMMITTED_NO_NETWORK'});continue
                meta=metadata(task,source,'2026-09-18');meta['coverage_scope']=scope
                unit,kind,metric=('million vehicles/year SAAR','PHYSICAL','vehicle_assemblies')if f=='auto'else('percent','RATIO','capacity_utilization')if f=='utl'else('2017=100','INDEX','industrial_production'if f=='ip'else'industrial_capacity')
                r=parse_fed(Path(meta['path']).read_bytes(),meta,scope['auto_series']if f=='auto'else scope['series'],unit,kind,metric,*scope['months'])
                out.append({'task':task,**commit_page(ledger,task,meta,r)})
        elif source=='m3':
            for f in scope['metrics']:
                task='m3-'+f
                if saved_task(ledger,task):out.append({'task':task,'status':'UNCHANGED_COMMITTED_NO_NETWORK'});continue
                meta=metadata(task,source,'2026-10-02');meta['coverage_scope']=scope
                r=parse_m3(Path(meta['path']).read_bytes(),meta,scope['series_prefixes'],f,*scope['months'])
                out.append({'task':task,**commit_page(ledger,task,meta,r)})
        elif source=='eia':
            for ym,name in [('2026-07','eia-july'),('2026-08','eia-august')]:
                if saved_task(ledger,name):out.append({'task':name,'status':'UNCHANGED_COMMITTED_NO_NETWORK'});continue
                meta=metadata(name,source,'2026-09-24'if ym=='2026-08'else'UNKNOWN');meta['coverage_scope']=scope
                r,snap=parse_eia(Path(meta['path']).read_bytes(),meta,ym,scope['states'])
                out.append({'task':name,**commit_page(ledger,name,meta,r),'rows_in_native_snapshot':len(snap['records'])})
        elif source=='usgs':
            for path in sorted((ROOT/'discovery').glob('usgs-tungs-*.json')):
                task=path.stem
                if saved_task(ledger,task):out.append({'task':task,'status':'UNCHANGED_COMMITTED_NO_NETWORK'});continue
                meta=metadata(task,source,'UNKNOWN');meta['coverage_scope']=scope
                r,holds=parse_tungsten(Path(meta['path']).read_bytes(),meta,*scope['monthly_periods'])
                out.append({'task':task,**commit_page(ledger,task,meta,r),'schema_holds':holds})
        else:raise ValueError('Use official JSON/XLSX task runner for this source')
    ledger.close();print(json.dumps(out,ensure_ascii=False))


def report():
    ledger=Ledger(ROOT/'ledger');allrows=records(ledger);active=research_export(ledger)['observations'];by={}
    for s in json.loads(REG.read_text())['sources']:
        rows=[x['record']for x in allrows if x['record']['source_id']==s];latest={x['key']:x['record']for x in allrows if x['record']['source_id']==s}
        by[s]={'versioned_observation_records':len(rows),'distinct_observation_keys':len(latest),'actual_numeric':sum(r['value_decimal_or_null']is not None for r in rows),'by_type':dict(Counter(r['measurement_type']for r in rows if r['value_decimal_or_null']is not None)),'with_publication_date':sum(r['published_at']!='UNKNOWN'for r in rows),'periods':sorted(set(r['period_start']for r in rows)),'backtest_unavailable':sum(r['backtest_state'].startswith('BACKTEST_UNAVAILABLE')for r in rows)}
    for source,summary in by.items():
        latest=[x['record']for x in active if x['record']['source_id']==source]
        numeric=[r for r in latest if r['value_decimal_or_null']is not None]
        summary.update(numeric_observations=len(numeric),physical_observations=sum(r['measurement_type']=='PHYSICAL'for r in numeric),
            quantity_roles=dict(Counter(quantity_role(r)for r in latest)),
            physical_customer_order_quantity=0,qualified_supply_quantity=0,lead_time_quantities=0,
            TARGET_specification_region_period_verified=0,
            scope_note='Industrial statistics/trade/nameplate and monetary contracts; not qualified TARGET supply or actual product orders. Role buckets are exclusive within current numeric observations, not additive units.')
    result={'plan_id':'BCT-V4-Q-1.0','step':'Q1','at':now(),'sources':by,'ledger_bytes':ledger.path.stat().st_size,'candidates_created':ledger.db.execute('select count(*)from firsts').fetchone()[0],'AI_calls':0,'CPU_windows':0}
    ledger.close();return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['m3','g17','eia','usgs','report']);a=ap.parse_args()
    if a.action=='report':print(json.dumps(report(),ensure_ascii=False,indent=2))
    else:batch(a.action)
