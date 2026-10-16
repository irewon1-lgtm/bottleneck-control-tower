import os
import json,sqlite3,pathlib,ast,re
from collections import Counter
from bct.v4 import evidence_path as ep
from bct import precursor_scope_reader as sr,forecast_discovery as strict,precursor_evidence_graph as graph
from bct.objective_lock import stamp_export
from types import SimpleNamespace
ROOT=pathlib.Path(__file__).resolve().parents[1];S=pathlib.Path(os.environ.get('BCT_AUDIT_SOURCE_ROOT',ROOT/'audit-source'));O=pathlib.Path(__file__).resolve().parent
con=sqlite3.connect('file:'+str(pathlib.Path(os.environ.get('BCT_AUDIT_DB',ROOT/'audit-db/reading-quality.sqlite3')))+'?mode=ro',uri=True);docs=[json.loads(x[0]) for x in con.execute('select payload from documents')]
miss=[]
for doc,name,needle in [(docs[0],'FOX-XP','One new ultra-high-power FOX-XP'),(docs[1],'Sonoma','The initial order includes multiple Aehr Sonoma')]:
 line=next(l for l in sr.sentences(doc,sr.allowed_lines(doc)[0]) if needle in l['quote'])
 choices=sr._products(doc,line);picked=sr.bound_product(line,choices)
 assert not picked or name.casefold() not in picked['value'].casefold()
 miss.append({'document_id':doc['document_id'],'url':doc['origin_url'],'body_sha256':doc['body_sha256'],'locator':{'start':line['start'],'end':line['end']},'source_product_present':name,'source_product_offset':doc['body'].index(name,line['start'],line['end']),'parser_candidates':[{'value':v['value'],'locator':v['locator']} for v in choices],'bound_product':picked['value'] if picked else None,'first_cause':'EXTRACTION_FAILURE','status':'CONFIRMED_CURRENT_GRAPH_REPLAY_ONLY','scope':'Stored article body; not newly fetched publisher verification, not actual pair','code':'src/bct/precursor_scope_reader.py:_products/bound_product'})
# Execute exact q3_input with actual event scalars. No restored prose documents
# available in current official packet; absence is explicit, not a full run replica.
def exact(path,names,env):
 tree=ast.parse((S/path).read_text());exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),str(S/path),'exec'),env);return env
q=exact('src/bct/v4/quantitative_targets.py',['comparable'],{'target_key':ep.target_key})
q3=exact('src/bct/v4/official_discovery.py',['q3_input'],{'Counter':Counter,'q3':SimpleNamespace(comparable=q['comparable']),'graph':graph,'forecast':strict,'stamp_export':stamp_export})['q3_input']
auto=json.load(open(S/'docs/v4/quantitative/OFFICIAL_AUTO_RESULTS.json'))
r=q3(auto['events'],[],as_of='2026-10-16T15:10:00+00:00',documents=[])
assert r['reasons']=={'LINKAGE_NO_VERIFIED_OPPOSITE_SIDE':18}
# Control: a supplied, complete synthetic typed pair passes comparable but is
# not forwarded by q3_input when prose graph has no supporting documents.
t={k:{'normalized':v}for k,v in zip(ep.TARGET,['test device','grade a','region a','buyer a','pool a'])}
d={'target':t,'role':'DEMAND','state':'SOURCE_BOUND_EVENT','lineage':'buyer','unit':'units','period':'2028','actuality':'ACTUAL','quantity':10,'source_hash':'buyerhash'}
s={**d,'role':'SUPPLY','lineage':'supplier','quantity':5,'source_hash':'supplierhash','qualified':True,'coverage_complete':True}
latent=q3([d,s],[],as_of='2026-10-16T15:10:00+00:00',documents=[])
# Timing representation in the old research pair builder (synthetic only).
def synthetic_doc(did,role,time_field,time_value):
 body='testdevice gradeA regionA buyerA poolA '+time_value
 doc={'document_id':did,'body':body,'body_sha256':ep.sha(body.encode()),'origin_url':'https://'+did+'.example/test','origin_publisher':did,'origin_id':did,'published_at':'2026-01-01','acquired_at':'2026-01-02'}
 def field(v):a=body.index(v);return {'value':v,'reference':{'start':a,'end':a+len(v),'quote':v}}
 p={'reference':{'start':0,'end':len(body),'quote':body},'product':field('testdevice'),'role':role,'actuality':'ACTUAL','fields':{k:field(v) for k,v in zip(ep.TARGET[1:],['gradeA','regionA','buyerA','poolA'])},'independent_review':{'type':'SOURCE_ONLY_AI','exposed_to_target_outputs':False}}
 p['fields'][time_field]=field(time_value);return doc,p
dd,dp=synthetic_doc('buyer','DEMAND_INCREASE','need_time','2028-06-30');sd,sp=synthetic_doc('supplier','SUPPLY_DELAY','ready_time','2028-09-01')
rdates=ep.analyze([dd,sd],{'buyer':[dp],'supplier':[sp]},enabled=True,reviewed=True)
sd2,sp2=synthetic_doc('supplier','SUPPLY_DELAY','ready_time','2028-06-30');requal=ep.analyze([dd,sd2],{'buyer':[dp],'supplier':[sp2]},enabled=True,reviewed=True)
assert len(rdates['pairs'])==0 and len(requal['pairs'])==1
result={'actual_extraction_misses':miss,'actual_event_only_Q3_diagnostic':r,'actual_event_only_limit':'No official raw documents restored; not exact replay of original complete run','synthetic_typed_pair_precheck':q['comparable']({**d,'source_verified':True,'measurement_type':'PHYSICAL'},{**s,'source_verified':True,'measurement_type':'PHYSICAL'}),'synthetic_typed_pair_Q3_result':latent,'synthetic_legacy_time_filter':{'different_need_ready_dates_pairs':len(rdates['pairs']),'equal_need_ready_dates_pairs':len(requal['pairs']),'not_actual_pairs':True},'real_complete_pairs_found':0}
(O/'additional-reproduction-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
