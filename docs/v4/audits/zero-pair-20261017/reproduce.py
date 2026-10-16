import os
"""Read-only audit. Exact AST function loading avoids unrelated collector dependencies.
No model/network/operating DB write. Synthetic gates never count as actual pairs.
Run: PYTHONPATH=audit-source/src python3 audit-output/reproduce.py
"""
import ast,json,pathlib,sqlite3,hashlib,re
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace
from bct import precursor_scope_reader as sr,precursor_temporal as temporal,precursor_discovery as pd,early_forecast as early,forecast_discovery as strict,future_bottleneck
from bct.v4 import evidence_path as ep
ROOT=pathlib.Path(__file__).resolve().parents[1];SRC=pathlib.Path(os.environ.get('BCT_AUDIT_SOURCE_ROOT',ROOT/'audit-source'));OUT=pathlib.Path(__file__).resolve().parent
def read(p):return json.loads((SRC/p).read_text())
def exact_functions(path,names,env):
 text=(SRC/path).read_text();tree=ast.parse(text);nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
 assert {n.name for n in nodes}==set(names)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SRC/path),'exec'),env)
 return env
qenv=exact_functions('src/bct/v4/quantitative_targets.py',['comparable'],{'target_key':ep.target_key});comparable=qenv['comparable']
env={'re':re,'deepcopy':deepcopy,'pd':pd,'forecast_discovery':strict,'scope_reader':sr,'temporal':temporal,'early_forecast':early,'CHANGE_TARGET':future_bottleneck.CHANGE_TARGET,'UNKNOWN':'UNKNOWN','LABELS':{'product':r'product','specification':r'specification|grade|model|standard','region':r'region|market','customer_group':r'customer[ _-]group|customers|buyer','supply_pool':r'supply[ _-]pool|qualified suppliers'}}
exact_functions('src/bct/precursor_collection.py',['scope_fields','source_events','structure'],env)
from bct import precursor_evidence_graph as graph
con=sqlite3.connect('file:'+str(pathlib.Path(os.environ.get('BCT_AUDIT_DB',ROOT/'audit-db/reading-quality.sqlite3')))+'?mode=ro',uri=True)
assert con.execute('pragma integrity_check').fetchone()[0]=='ok'
docs=[json.loads(x[0]) for x in con.execute('select payload from documents')]
for d in docs:assert hashlib.sha256(d['body'].encode()).hexdigest()==d['body_sha256']
structured=[env['structure'](d) for d in docs]
g=graph.analyze(structured,now='2026-10-16T15:10:00+00:00',mode='BACKFILL')
(OUT/'structured-graph-replay.json').write_text(json.dumps(g,ensure_ascii=False,indent=2))
auto=read('docs/v4/quantitative/OFFICIAL_AUTO_RESULTS.json');sel=read('docs/v4/quantitative/OFFICIAL_SELECTION_REPAIR_RESULTS.json');sup=read('docs/v4/supply-linkage/engine-results.json')
legacy=sup['engine']['records'];dc=[x for x in legacy if x['role']=='DEMAND_INCREASE'];sc=[x for x in legacy if x['role'] in ('SUPPLY_DECREASE','SUPPLY_DELAY')]
legacy_first=Counter(comparable({'target':d['target']},{'target':s['target']})[1] for d in dc for s in sc)
def fields(e):return [k for k in ep.TARGET if not e['target'].get(k)]
# Synthetic complete scope: only compare dates; no actual source or discovery claim.
target={k:{'normalized':v} for k,v in zip(ep.TARGET,['test device','grade-a','region-a','buyer-a','qualified-pool-a'])}
d={'target':target,'lineage':'buyer','unit':None,'period':'2028','actuality':'ACTUAL','source_verified':True,'measurement_type':'PHYSICAL','quantity':None,'basis':'total','need_date':'2028-06-30'}
s={**d,'lineage':'supplier','basis':'total','qualified':True,'coverage_complete':True,'available_date':'2028-09-01'}
strict_d={**d,'period':{'start':'2028-01-01','end':'2028-12-31'}};strict_s={**s,'period':strict_d['period']}
synthetic={'classification':'SYNTHETIC_DIAGNOSTIC_NOT_REAL_PAIR','quantity_precheck':comparable(d,s),'strict_timing_comparison':strict.comparison(strict_d,strict_s)}
# Actual graph first-block reasons, events not original document counts.
res={'baseline':'23a0615f1a10f2b938cb2b5401706a1995b4d4f2','reading_db':{'documents':len(docs),'body_hashes_verified':len(docs),'table_counts':{t:con.execute('select count(*) from '+t).fetchone()[0] for t, in con.execute("select name from sqlite_master where type='table'")}},'actual_graph':{'structured_events':sum(len(x['precursor_events']) for x in structured),'retained_events':sum(len(x['retained_collection_events']) for x in structured),'observations':len(g['observations']),'complete_target_events':g['complete_target_events'],'independent_pairs':g['independent_pairs'],'comparable_period_pairs':g['comparable_period_pairs'],'blocked_reasons':dict(Counter(x['reason'] for x in g['blocked'])),'reference_checks':g['reference_checks']},'automatic':{'event_rows':len(auto['events']),'event_states':dict(Counter(x['state'] for x in auto['events'])),'demand_missing_fields':dict(Counter(k for e in auto['events'] if e['state']=='SOURCE_BOUND_EVENT' and e['role']=='DEMAND' for k in fields(e))),'Q3':auto['Q3']},'legacy':{'records':len(legacy),'demand_records':len(dc),'supply_constraint_records':len(sc),'cartesian_comparisons':len(dc)*len(sc),'first_reasons':dict(legacy_first),'complete_targets':sum(all(x['target'].values()) for x in legacy),'need_time':sum(bool(x['fields'].get('need_time')) for x in legacy),'ready_time':sum(bool(x['fields'].get('ready_time')) for x in legacy)},'selection':{'contexts':len(sel['context_results']),'event_rows':sum(len(x['events']) for x in sel['context_results']),'product_bound_events':sum(bool(e.get('product')) for x in sel['context_results'] for e in x['events']),'hold_reasons':dict(Counter(e['reason'] for x in sel['context_results'] for e in x['holds']))},'synthetic':synthetic,'new_real_pairs':0,'new_S2_S3':0}
(OUT/'reproduction-results.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps(res,ensure_ascii=False,indent=2))
# Frozen existing-case census, never choose favorable rows.
case_rows=[]
for i,c in enumerate(sup['cases']):
 refs=c['review']['references'];doc=next((d for d in docs if d['document_id']==c['document_id']),None)
 checks=[]
 if doc:
  checks=[doc['body'][r['start']:r['end']]==r['quote'] for r in refs]
  assert all(checks)
 first='SUPPLY_UNKNOWN' if c['status']=='SOURCE_REVIEW_LINKED' else 'EVENT_CLASSIFICATION' if c.get('excluded_reason') else 'UNKNOWN'
 case_rows.append({'audit_id':f'L{i+1:02}','source_case_id':c['id'],'document_id':c['document_id'],'product':c['product'],'role':c['review']['role'],'actuality':c['review']['actuality'],'historical_status':c['status'],'historical_reason':c.get('reason'),'first_cause':first,'cause_status':'CONFIRMED' if first=='EVENT_CLASSIFICATION' else 'LIKELY' if first=='SUPPLY_UNKNOWN' else 'BLOCKED','source_access':'FULL_STORED_BODY_HASH_VERIFIED' if doc else 'SAVED_EXCERPTS_ONLY_NOT_FULL_ORIGINAL','exact_refs_verified_this_audit':len(checks),'missing_target':c.get('missing',[]),'need_period':c.get('need_period'),'total_qualified_supply':c.get('total_qualified_supply'),'review_text':c['review']['reason_ko'],'quotes':refs,'code':'src/bct/v4/supply_linkage.py:prepare; src/bct/v4/evidence_path.py:analyze','source_url':doc['origin_url'] if doc else None})
(OUT/'legacy-cases.json').write_text(json.dumps(case_rows,ensure_ascii=False,indent=2))
