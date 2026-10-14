"""Bounded free research sweep; existing feeds/native corpus retained; no AI API."""
import json,pathlib,gzip,collections,sqlite3
from urllib.parse import urlsplit
from bct.v4.cross_industry import feed_sources,collect
from bct.v4.store import sha,now
R=pathlib.Path('docs/v4/cross-industry');V=pathlib.Path('var/v4/cross-industry')

def inventory():
 sources,disabled=feed_sources();docs=[];summary=[]
 for name in ['native-source-records','recovered-source-records']:
  p=pathlib.Path('var/v4/stage4-recovery')/(name+'.json')
  for row in json.loads(p.read_text()):
   doc=dict(row.get('BCT_original_source_document')or{'origin_url':row['url'],'origin_id':row['url'],'origin_publisher':'UNKNOWN','provenance':'BLOCKED','provenance_blockers':['NATIVE_ORIGINAL_UNAVAILABLE'],'body_status':row['body_status'],'acquired_at':None});body=pathlib.Path(row['body_path']).read_text();assert sha(body.encode())==row['body_sha256']
   doc.update(document_id=row['document_id'],body=body,body_sha256=row['body_sha256'],published_at=row.get('published_at'),raw_sha256=row['raw_sha256'])
   rawpath=pathlib.Path(row.get('raw_path')or'ABSENT');native=rawpath.is_file()
   if native:assert sha(rawpath.read_bytes())==row['raw_sha256']
   docs.append({'doc':doc,'raw_path':str(rawpath)if native else None,'topic_hint':row.get('topic_hint','UNCLASSIFIED_OPEN_DISCOVERY'),'body_path':row['body_path'],'prior_use':'CONSUMED_OR_COLLECTION_ONLY_NOT_NEW_HOLDOUT'})
   summary.append({'document_id':doc['document_id'],'url':row['url'],'body_sha256':row['body_sha256'],'native_available':native,'body_status':row['body_status'],'published_at':doc['published_at'],'topic_hint':row.get('topic_hint','UNKNOWN')})
 (V/'existing-documents.json').write_text(json.dumps(docs,ensure_ascii=False,indent=2)+'\n')
 indexes=json.loads(pathlib.Path('config/v4-research-intake.json').read_text())['sources']
 for row in indexes:sources.append({'kind':'INDEX','name':row['index_url'],'url':row['index_url'],'article_prefix':row['article_prefix'],'industry_hint':{'www.airbus.com':'Defense and space','www.gevernova.com':'Power grid generation','www.energy.gov':'Energy and nuclear'}.get(urlsplit(row['index_url']).hostname,'UNCLASSIFIED_OPEN_DISCOVERY')})
 # Persistent old isolated index/article failures are not silently retried.
 blocked=set()
 for p in [pathlib.Path('var/v4/sequential/research-runtime/v4.sqlite3')]:
  if p.is_file():
   c=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True)
   for kind,t in c.execute("SELECT kind,payload FROM events WHERE kind IN ('INTAKE_INDEX_FAILURE','INTAKE_FETCH_RESULT','INTAKE_REFRESH_RESULT')"):
    x=json.loads(t)
    if kind=='INTAKE_INDEX_FAILURE'or x.get('status')=='FAILED':blocked.add(x['url'])
   c.close()
 active=[s for s in sources if s['url']not in blocked]
 result={'at':now(),'base_sha':'0e9cdb1e899c836dfdac68ef76e61a45cc86b269','RSS_active':len(sources)-len(indexes),'RSS_disabled_preserved':disabled,'source_sections':dict(collections.Counter(s['industry_hint']for s in sources)),'official_indexes':len(indexes),'old_failures_isolated':sorted(blocked),'selected_sources':active,'preserved_materials':summary,'source_hint_not_fact':True,'AI_API':'DISABLED','runtime_status_tool':'Configuration changed response twice; readiness UNKNOWN. Local policy unrestricted; actual Git read success. No config/key changes.'}
 (R/'inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return active,docs,blocked

if __name__=='__main__':
 R.mkdir(exist_ok=True);V.mkdir(exist_ok=True);sources,docs,blocked=inventory()
 x=collect(V/'ledger',sources,article_limit=24,workers=6,known_urls={r['doc']['origin_url']for r in docs}|blocked|{(r.get('doc')or r.get('document')or{}).get('origin_url')for p in ['docs/v4/stage4-corpus/round2/inputs.json','docs/v4/stage4-corpus/round3/inputs.json','docs/v4/path-comparison/final/inputs.json']for r in json.loads(pathlib.Path(p).read_text())['documents']})
 (R/('collection-'+x['run_id']+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'sources':x['sources_executed'],'parsed':sum(s['status']=='PARSED'for s in x['source_results']),'captured':len(x['captured']),'pending':x['pending_unattempted']}))
