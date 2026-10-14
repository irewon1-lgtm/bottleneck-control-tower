"""No network: preserved CPU/native → common research facts and fair review queue."""
import json,pathlib,sqlite3,gzip,collections
from urllib.parse import urlsplit
from bct.v4.cross_industry import reading_result,fair_select,source_review,common_evidence,common_structured,deepen
from bct.v4.evidence_path import reference
from bct.v4.public_input import PUBLISHERS,review_native
from bct.v4.store import Ledger,sha,now
from bct.objective_lock import stamp_export
R=pathlib.Path('docs/v4/cross-industry');V=pathlib.Path('var/v4/cross-industry')


def load_inputs():
 rows=json.loads((V/'existing-documents.json').read_text());docs={r['doc']['document_id']:r for r in rows}
 for root in ['docs/v4/stage4-corpus/round2','docs/v4/stage4-corpus/round3','docs/v4/path-comparison/final']:
  for r in json.loads((pathlib.Path(root)/'inputs.json').read_text())['documents']:
   d=r.get('doc')or r.get('document')
   if d:docs.setdefault(d['document_id'],{'doc':d,'raw_path':r.get('raw_path'),'topic_hint':'UNCLASSIFIED_OPEN_DISCOVERY','prior_use':'CONSUMED_NOT_NEW_HOLDOUT'})
 readings={}
 paths=['var/v4/repair/cpu/development-baseline.json','var/v4/repair/cpu/evaluation-baseline.json','docs/v4/stage4-corpus/round2/cpu-baseline.json','docs/v4/stage4-corpus/round3/cpu-baseline.json']
 for name in paths:
  p=pathlib.Path(name)
  if not p.exists():continue
  for cpu in json.loads(p.read_text())['documents']:
   did=cpu.get('document_id')
   if did:readings.setdefault(did,{'CPU':cpu,'evidence':name,'execution':'REUSED_UNCHANGED'})
 for p in pathlib.Path('docs/v4/path-comparison/final/cpu').glob('*.json'):
  cpu=json.loads(p.read_text());readings.setdefault(cpu['document_id'],{'CPU':cpu,'evidence':str(p),'execution':'REUSED_UNCHANGED'})
 return docs,readings


def source_group(doc,row):
 host=urlsplit(doc['origin_url']).hostname
 if host in ('www.airbus.com','www.esa.int'):return 'Defense and space'
 if host=='www.aehr.com':return 'Semiconductor AI datacenter'
 if host=='www.eia.gov':return 'Energy cross-sector (EIA)'
 if host=='www.gevernova.com':return 'Power grid generation'
 if host=='www.energy.gov':return 'Energy and nuclear'
 return row.get('industry_hint','UNCLASSIFIED_OPEN_DISCOVERY')


def main():
 docs,readings=load_inputs();l=Ledger(V/'ledger');fresh={json.loads(t)['url']:json.loads(t)['industry_hint']for t, in l.db.execute("SELECT payload FROM events WHERE kind='CROSS_ARTICLE_RESULT'")}
 excluded_views={json.loads(t)['document_id']for t, in l.db.execute("SELECT payload FROM events WHERE kind='CROSS_BODY_VIEW_QUARANTINED'")}
 for t, in l.db.execute('SELECT payload FROM documents'):
  d=json.loads(t)
  if d['document_id']in excluded_views:continue
  docs.setdefault(d['document_id'],{'doc':d,'industry_hint':fresh.get(d['origin_url'],'UNCLASSIFIED_OPEN_DISCOVERY'),'raw_blob':d.get('raw_sha256'),'prior_use':'NEW_COLLECTION'})
 baseline_products={s['text'].casefold()for r in readings.values()for s in r['CPU'].get('spans',[])if s['label']=='product'}
 baseline_industries={s['text'].casefold()for r in readings.values()for s in r['CPU'].get('spans',[])if s['label']in ('industry','subindustry')}
 for p in (V/'cpu').glob('*.json'):
  r=json.loads(p.read_text());readings.setdefault(r['document_id'],{'CPU':r['CPU'],'evidence':str(p),'execution':'NEW_CPU_NO_API'})
 reports=[];counts=collections.defaultdict(collections.Counter);gaps=[];discoveries=[];records=[];review=[];common=[]
 with l.worker():
  for did,row in docs.items():
   d=dict(row['doc']);group=source_group(d,row);counts[group]['available_documents']+=1
   d['primary_source_verified']=urlsplit(d['origin_url']).hostname in PUBLISHERS and d.get('provenance')=='PASS'
   raw=None
   if row.get('raw_path')and pathlib.Path(row['raw_path']).is_file():
    p=pathlib.Path(row['raw_path']);raw=gzip.decompress(p.read_bytes())if p.suffix=='.gz'else p.read_bytes()
   elif row.get('raw_blob'):
    got=l.db.execute('SELECT data FROM blobs WHERE id=?',(row['raw_blob'],)).fetchone();raw=got[0]if got else None
   if raw is not None:
    assert sha(raw)==d['raw_sha256'];counts[group]['native_available']+=1
    d['native_source_review']=source_review(d,raw)
   if did not in readings:
    counts[group]['CPU_unread_documents']+=1;continue
   cached=readings[did];cpu=cached['CPU']
   try:
    x=reading_result(d,cpu);counts[group]['CPU_evaluated_documents']+=1;counts[group]['reading_documents']+=x['read_characters']>0;counts[group]['read_characters']+=x['read_characters'];counts[group]['body_characters_of_reading_documents']+=len(d['body']);counts[group]['CPU_products']+=x['CPU_products'];counts[group]['event_adoptions']+=x['counts']['events']
    counts[group]['source_gate_held_documents']+=x['source_gate']!='PASS';counts[group]['S1_research_item_counts']+=x['counts']['S1']
    for z in x['records']:
     z['industry_hint']=group;z['source_document']=did;records.append(z);common.append(common_evidence(z,d,'CPU_DISCOVERY_UNVERIFIED'))
     if z['s_stage']=='S1':review.append({'url':d['origin_url'],'record_id':z['id'],'industry_hint':group,'product':z['product']['surface'],'priority':x['priority'],'missing_target_fields':[k for k,v in z['target'].items()if v is None],'need_time':'UNKNOWN','qualified_supply':'UNKNOWN','action':'Find independent counterpart evidence; no forecast promotion','source_published_at':d.get('published_at')})
    if cached['execution']=='NEW_CPU_NO_API':
     for s in cpu.get('spans',[]):
      pool=baseline_products if s['label']=='product'else baseline_industries if s['label']in ('industry','subindustry')else None
      if pool is not None and s['text'].casefold()not in pool:discoveries.append({'kind':s['label'],'surface':s['text'],'document_id':did,'source_group_hint':group,'reference':s['locator'],'body_sha256':d['body_sha256'],'status':'CPU_LITERAL_EXPLORATION_NOT_QUALIFIED_TARGET_OR_VERIFIED_SEMANTICS','novelty_scope':'Not in preserved CPU outputs loaded for this run; not all global/historical BCT targets'})
    l.capture(d,raw,{'cross_industry_result':x,'execution':cached['execution'],'CPU_evidence':cached['evidence']})
    rid='cross-reading-'+sha([did,x,cached['evidence']]);l.save_run(rid,stamp_export({**x,'candidates':[]}), 'BACKFILL')
    reports.append({'document_id':did,'industry_hint':group,'source_gate':x['source_gate'],'original_provenance':d.get('provenance'),'source_review':d.get('native_source_review'),'CPU_execution':cached['execution'],'CPU_evidence':cached['evidence'],'CPU_status':cpu['status'],'counts':x['counts'],'CPU_products':x['CPU_products'],'read_characters':x['read_characters'],'body_characters':x['body_characters'],'result_run_id':rid})
   except Exception as e:
    counts[group]['reading_failed_isolated']+=1;gaps.append({'document_id':did,'industry_hint':group,'type':type(e).__name__,'reason':str(e)[:100]})
  # Only already verified EIA comparison records are imported; no refetch/reparse.
  structured=json.loads(pathlib.Path('docs/v4/path-comparison/structured-results.json').read_text());seen={json.loads(t)['event_id']for t, in l.db.execute("SELECT payload FROM events WHERE kind='CROSS_STRUCTURED_CHANGE'")}
  native_db=sqlite3.connect('file:var/v4/path-comparison/structured-ledger/v4.sqlite3?mode=ro',uri=True)
  structured_sources={json.loads(t)['origin_url']:json.loads(t)for t, in native_db.execute('SELECT payload FROM documents')};native_db.close()
  for e in structured['events']:
   assert all(structured_sources[x['url']]['raw_sha256']==x['raw_sha256']for x in (e['before'],e['after']))
   common.append(common_structured(e,structured_sources))
   row_record={'event_id':e['id'],'evidence_kind':'STRUCTURED_REPORTED_CHANGE','industry_hint':'Power grid generation','target':{'product':e['after']['fields'].get('Technology'),'specification':None,'region':e['after']['fields'].get('Plant State'),'customer_group':None,'supply_pool':None},'role':e['role'],'actuality':'REPORTED_STATUS_NOT_PHYSICALLY_VERIFIED','before':e['before'],'after':e['after'],'s_stage':'UNKNOWN','meaning':'Qualified supply/residual demand/effective date require separate verification','operational_integration_enabled':False}
   if e['id']not in seen:
    with l.db:l.event('CROSS_STRUCTURED_CHANGE',row_record)
  # Reuse validated, separately source-reviewed evidence already stored before
  # this task. This is NOT a CPU/AI automatic event discovery claim.
  origin=pathlib.Path('var/v4/path-comparison/oracle-ledger/v4.sqlite3').resolve()
  old=sqlite3.connect(origin.as_uri()+'?mode=ro',uri=True)
  preserved=json.loads(old.execute('SELECT payload FROM runs ORDER BY at LIMIT 1').fetchone()[0])
  source_docs={json.loads(t)['document_id']:json.loads(t)for t, in old.execute('SELECT payload FROM documents')}
  imported=[]
  seen_imports={json.loads(t)['record_id']for t, in l.db.execute("SELECT payload FROM events WHERE kind='CROSS_REVIEWED_EVENT_REUSED'")}
  for record in preserved['records']:
   did=record['context']['document_id'];d=source_docs[did];reference(d,record['context']);group=source_group(d,{})
   imported.append(record);common.append(common_evidence(record,d,'REUSED_SOURCE_ONLY_AI_REVIEW_NOT_NEW_DISCOVERY'));counts[group]['previously_reviewed_events_reused']+=1
   if record['id']not in seen_imports:
    with l.db:l.event('CROSS_REVIEWED_EVENT_REUSED',{'record_id':record['id'],'record':record,'origin_ledger':str(origin),'origin_result_sha256':sha(preserved),'industry_hint':group,'not_new_discovery':True,'not_human_review':True})
   if record['s_stage']=='S1':review.append({'url':d['origin_url'],'record_id':record['id'],'industry_hint':group,'product':record['product']['surface'],'priority':'COUNTERPART_EVIDENCE_REVIEW','missing_target_fields':[k for k,v in record['target'].items()if v is None],'need_time':record.get('fields',{}).get('need_time')or'UNKNOWN','qualified_supply':'UNKNOWN','action':'Check need period and independent counterpart; no forecast promotion','source_published_at':d.get('published_at'),'evidence_origin':'REUSED_SOURCE_ONLY_AI_REVIEW_NOT_NEW_CPU_DISCOVERY'})
  old.close()
  common_known={json.loads(t)['event_id']:json.loads(t)for t, in l.db.execute("SELECT payload FROM events WHERE kind IN ('CROSS_COMMON_EVIDENCE','CROSS_COMMON_EVIDENCE_REVISION') ORDER BY seq")}
  for entry in common:
   if common_known.get(entry['event_id'])!=entry:
    kind='CROSS_COMMON_EVIDENCE_REVISION'if entry['event_id']in common_known else'CROSS_COMMON_EVIDENCE'
    with l.db:l.event(kind,entry)
  with l.db:l.event('CROSS_DOWNSTREAM_POLICY',{'at':now(),'CPU_source_relations':'ADVISORY_ONLY_NOT_AUTOMATIC_EVENTS','initial_limited_relation_debug_runs':'Preserved in initial-limited-relation-diagnostic.json and ledger history; superseded for adoption by advisory-only downstream policy','automatic_AI_reading':False,'operating_changes':0})
  queue=fair_select(review,len(review))if review else[]
  # Actual bounded offline counterpart review follows the fair accepted-S1 queue.
  common_by_original={x['original_record_id']:x for x in common if x['origin_kind']=='REUSED_SOURCE_ONLY_AI_REVIEW_NOT_NEW_DISCOVERY'}
  deep=[deepen(common_by_original[x['record_id']],[r['doc']for r in docs.values()],common)for x in queue]
  deep_known={json.loads(t)['review_id']for t, in l.db.execute("SELECT payload FROM events WHERE kind='CROSS_DEEP_REVIEW'")}
  for x in deep:
   if x['review_id']not in deep_known:
    with l.db:l.event('CROSS_DEEP_REVIEW',x)
  (R/'deep-reviews.json').write_text(json.dumps({'at':now(),'scope':'Existing corpus exact-name retrieval only, max3 sources per target; not new semantic review/independence proof','reviews':deep},ensure_ascii=False,indent=2)+'\n')
  # Every event retains missing TARGET fields; literal equality isn't a verified pair.
  summary={'at':now(),'scope':'Cross-industry collection and research discovery, not accuracy/lead-performance evaluation','industry_counters':{k:dict(v)for k,v in counts.items()},'automatic_bounded_deep_reviews':len(deep),'common_evidence_records':len(common),'CPU_evaluated_documents':len(reports),'reading_documents':sum(r['read_characters']>0 for r in reports),'reading_failures':gaps,'new_literal_discoveries':discoveries,'research_review_queue':queue,'queue_order':'Category: actual accepted S1 first, fair industry/source order, no new score; unknown period remains unknown','structured_changes_reused':len(structured['events']),'previously_reviewed_events_reused':len(imported),'previously_reviewed_S1_literal_keys':preserved['counts']['S1'],'new_narrative_event_records':sum(z['event_status']=='ADOPTED_RESEARCH_EVENT'for z in records),'new_independent_qualified_demand_supply_pairs':0,'S1_research_unique_products':sorted({z['product']['normalized']for z in records if z['s_stage']=='S1'}),'future_12_36_month_candidates':{'S1':0,'S2':0,'S3':0},'S_stage_note':'Research S1 is a source signal only; no validated need period or total qualified supply, so not a future forecast candidate','automatic_event_adoption_from_CPU':False,'CPU_reused_documents':sum(r['CPU_execution']=='REUSED_UNCHANGED'for r in reports),'CPU_new_documents':sum(r['CPU_execution']=='NEW_CPU_NO_API'for r in reports),'AI_API_calls':0,'automatic_AI_reading':'DISABLED','operational_changes':0,'documents':reports}
  (R/'common-evidence.json').write_text(json.dumps(common,ensure_ascii=False,indent=2)+'\n')
  (R/'analysis.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(R/'located-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
 l.close();print(json.dumps({k:summary[k]for k in ('reading_documents','CPU_reused_documents','CPU_new_documents','new_narrative_event_records','S1_research_unique_products','structured_changes_reused','reading_failures')}))

if __name__=='__main__':main()
