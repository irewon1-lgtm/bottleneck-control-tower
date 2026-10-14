"""Offline report, explicit source review and storage proof. No API/client."""
from collections import Counter,defaultdict
import gzip,json,pathlib,re,sqlite3,subprocess,sys,time
from bct.v4.exploration import save,source_review
from bct.v4.reading_quality import coverage
from bct.v4.evidence_path import reference
from bct.v4.store import Ledger,sha,now
from bct.objective_lock import stamp_export
R=pathlib.Path('docs/v4/cpu-recovery');V=pathlib.Path('var/v4/cpu-recovery');SOURCE=pathlib.Path('var/v4/cross-industry/ledger/v4.sqlite3')
def read(p):return json.loads(pathlib.Path(p).read_text())
def write(p,x):
 with pathlib.Path(p).open('x')as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def ro(p):return sqlite3.connect(pathlib.Path(p).resolve().as_uri()+'?mode=ro',uri=True)

def paragraph(doc,phrase):
 found=[m for m in re.finditer(r'[^\n]+',doc['body'])if phrase in m[0]]
 assert len(found)==1,(phrase,len(found));m=found[0];return {'start':m.start(),'end':m.end(),'quote':m[0]}
def part(ref,word):
 positions=[m.start()for m in re.finditer(re.escape(word),ref['quote'])];assert len(positions)==1,(word,positions)
 a=ref['start']+positions[0];return {'start':a,'end':a+len(word),'quote':word}
def field(ref,word):return {'surface':word,'reference':part(ref,word)}

def table_digest(path):
 c=ro(path);out={}
 for table in ('metadata','blobs','documents','captures','readings','runs','firsts','events'):
  rows=c.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
  out[table]={'rows':len(rows),'sha256':sha([[v.hex()if isinstance(v,bytes)else v for v in row]for row in rows])}
 c.close();return out

def main():
 if(R/'RESULTS.json').exists():print('EXISTING_REPORT_NO_REPROCESS');return
 frozen=read(R/'freeze.json');inputs=read(R/'inputs.json');docs={r['document']['document_id']:r['document']for r in inputs['documents']}
 windows=[read(p)for p in sorted((V/'windows').glob('*.json'))];tasks=frozen['tasks']+read(R/'cpu-remainder.json')['tasks']
 assert len(windows)==len(tasks)==1210 and {x['key']for x in windows}=={x['key']for x in tasks}
 grouped=defaultdict(list)
 for x in windows:grouped[x['document_id']].append(x)
 ledger=Ledger(V/'ledger');c=ro(SOURCE);reports=[];diagnostics=[];counts=Counter();all_discoveries=[]
 with ledger.worker():
  for did,d in docs.items():
   rows=sorted(grouped[did],key=lambda x:x['window']['start']);success=[x for x in rows if x['status']in('PASS','PARTIAL_REVIEW')]
   allread=coverage(d['body'],[x['window']for x in success]);prior=coverage(d['body'],[x['window']for x in success if x['cache_reused']]);fresh=coverage(d['body'],[x['window']for x in success if not x['cache_reused']])
   before=time.monotonic();result=save(ledger,d,[x['CPU']for x in success]);discovery=result['discoveries'];all_discoveries.extend(discovery)
   hints=result['CPU_validation']['limited_relation_diagnostic']['records']
   diagnostics.extend({'document_id':did,'record':r,'status':'ADVISORY_ONLY_NOT_ADOPTED'}for r in hints if r['event_status']=='ADOPTED_RESEARCH_EVENT')
   unseen_nonwhite=sum(not z.isspace()for r in allread['unread_ranges']for z in d['body'][r['start']:r['end']])
   products=[x for x in discovery if x['origin']=='CPU'and x['product_candidate']]
   counts.update(products=len(products),source_valid_products=sum(x['source_status'].startswith('EXACT')for x in products),source_held_products=sum(x['source_status']=='HELD'for x in products))
   report={'document_id':did,'origin_url':d['origin_url'],'published_at':d['published_at'],'body_sha256':d['body_sha256'],
    'primary_source_verified':d.get('primary_source_verified'),'actual_CPU_coverage':allread,'fresh_CPU_characters':fresh['read_characters'],
    'previous_CPU_cache_characters':prior['read_characters'],'first_CPU_document':not bool(prior['read_characters']),
    'completed_windows':len(success),'failed_windows':[x for x in rows if x['status']not in('PASS','PARTIAL_REVIEW')],
    'unread_nonwhitespace_characters':unseen_nonwhite,'unread_reason':'ONLY_ORIGINAL_PARAGRAPH_OR_SENTENCE_WHITESPACE'if not unseen_nonwhite else'UNREAD_OR_FAILED_CONTEXT',
    'CPU_seconds_including_initializations':sum(x.get('cpu_seconds_including_load',0)for x in rows),
    'model_wall_seconds_including_initializations':sum(x['wall_seconds']for x in rows),'downstream_seconds':time.monotonic()-before,
    'CPU_all_label_proposals_retained':len([x for x in discovery if x['origin']=='CPU']),
    'CPU_product_proposals_retained':len(products),'limited_event_hypotheses':sum(x['event_status']=='ADOPTED_RESEARCH_EVENT'for x in hints),
    'source_gate':result['CPU_validation']['source_gate'],'actual_event_adoption':0,'s_stage':'UNKNOWN'}
   reports.append(report)
  # Restore original six CPU/AI outputs to the same research storage, no rerun.
  old=pathlib.Path('docs/v4/path-comparison/final')
  for row in read(old/'inputs.json')['documents']:
   d=row['doc'];cpu=read(old/'cpu'/(d['document_id']+'.json'));ai=json.loads(read(old/'responses'/(d['document_id']+'.json'))['receipt']['response']['text'])['extractions']
   ledger.capture(d,gzip.decompress(pathlib.Path(row['raw_path']).read_bytes()));save(ledger,d,[cpu],ai)
  # Reuse14 source reviews exactly, not newly discovered events or independent truth.
  reused=read(R/'reviewed14-regression.json')
  review_docs={ref['document_id']for item in reused['events']for ref in item['original_review']['references']}
  for did in review_docs:
   d=json.loads(c.execute('SELECT payload FROM documents WHERE id=?',(did,)).fetchone()[0])
   existing=ledger.db.execute('SELECT payload FROM documents WHERE id=?',(did,)).fetchone()
   if existing:assert json.loads(existing[0])['body_sha256']==d['body_sha256']
   else:
    raw=c.execute('SELECT data FROM blobs WHERE id=?',(d['raw_sha256'],)).fetchone()
    ledger.capture(d,raw[0]if raw else None)
  for item in reused['events']:
   ledger.event('RECOVERY_EXISTING_REVIEWED_EVENT_PRESERVED',item)
  by_suffix=lambda suffix:next(d for did,d in docs.items()if did.endswith(suffix))
  specifications=[
   ('a30168db','test aircraft','DEMAND_INCREASE',['Boeing has been selected','Inked at $20 billion'],
    '해군 개발 계약의 시험기 조달 보도. 200억 달러는 개발 계약금액이며 기체 수량은 multiple로만 적혀 있다. 양산 전투기 주문·가동 공급으로 바꾸지 않는다.'),
   ('2f262ae4','40-satellite constellation','DEMAND_INCREASE',['Meanwhile, Finland’s ICEYE'],
    '독일의 40기 위성군 주문 보도. 기사 속 CEO 설명이며 공식 계약 원문 미확인. 신설 공장을 이미 이용 가능한 공급으로 채택하지 않는다.'),
   ('3e29feb0','F-16V Block 70 fighter jets','SUPPLY_INCREASE',['TAITUNG, Taiwan'],
    '2019년 주문66기 중 첫2기 인도 보도. 신규 주문66기 또는 전체 시장 생산능력 증가가 아니다. 대만 인도에 한정한다.'),
   ('c856373a','Tavneos','SUPPLY_DECREASE',['The U.K. has stopped allowing','CSL Vifor holds the marketing','While supply and sale'],
    '영국 신규 환자 공급·판매 제한 보도. 기존 환자는 전환 기간 동안 공급 가능하며 미국 판매도 계속된다. 전 세계 전면 공급 중단으로 확대하지 않는다.'),
   ('a3ae5a64','subcutaneous Keytruda','SUPPLY_DECREASE',['A Dutch court has blocked','The court found Merck’s drug','Decisions are pending'],
    '특정 피하주사 제형과8개 유럽 국가의 제조·판매 제한 보도. 모든 Keytruda 제형/세계 공급으로 확대하지 않는다. 항소·미국 계류와 독일의 별도 과거 사건을 보존한다.'),
   ('42b65bac','antibiotic plant','SUPPLY_DECREASE',['London-based GSK has invested'],
    '지난2년 중 영국 항생제 공장 폐쇄 보도. 정확 폐쇄일·생산량은 미확인. 신규 펜실베이니아 투자 계획을 현재 공급량으로 사용하지 않는다.')]
  reviewed=[]
  for suffix,name,role,phrases,note in specifications:
   d=by_suffix(suffix);refs=[paragraph(d,s)for s in phrases];pr=next(r for r in refs if name in r['quote']);facts={}
   if suffix=='2f262ae4':facts={'quantity':field(pr,'40'),'unit':field(pr,'satellite')}
   if suffix=='3e29feb0':facts={'quantity':field(pr,'two'),'unit':field(pr,'fighter jets')}
   review={'review_type':'SAME_SESSION_CODEX_SOURCE_REVIEW','independent':False,'human_verified':False,
      'product_reference':part(pr,name),'references':refs,'role':role,'actuality':'ACTUAL','fields':facts,
      'reason_ko':note,'physical_quantity':'UNKNOWN'if not facts else facts['quantity']['surface'],
      'need_time':'UNKNOWN','total_qualified_supply':'UNKNOWN'}
   record=source_review(d,review,[x['window']for x in grouped[d['document_id']]if x['status']in('PASS','PARTIAL_REVIEW')]);reviewed.append(record)
   with ledger.db:ledger.event('RECOVERY_NEW_SOURCE_REPORTED_EVENT_REVIEW',record)
  negative_specs=[
    ('1560942e','Qilimanjaro closed €19.6 million','Closed funding is financing, not a plant/physical supply closure.'),
    ('8a2228dd','BMW opened orders','Opening an order book is not actual received demand or confirmed available supply.'),
    ('1c990e71','once those motors are fully qualified','Partnership and future qualification are not currently qualified supply.'),
    ('d49f5618','Sales of TTR silencer Amvuttra','Sales/guidance shortfall is not physical production decline.'),
    ('0a3b79bb','His closing slide reduced the problem','Reducing a conceptual problem is not reducing equipment supply.'),
    ('e08280b1','Three operating measures will be worth following','Proposed monitoring measures are not realized production/deliveries.'),
    ('3e29feb0','though Washington has been unwilling','Unwillingness to supply other aircraft is not actual delivery of those models.'),
    ('65bde92d','Investigational new drug (IND) applications','Delivering a functional clinical outcome is not shipping physical units.')]
  rejected=[]
  for suffix,phrase,reason in negative_specs:
   d=by_suffix(suffix);ref=paragraph(d,phrase);reference(d,ref)
   rec={'document_id':d['document_id'],'source_reference':ref,'decision':'REJECT_EVENT_KEEP_ORIGINAL_CPU_DISCOVERY','reason':reason,
        'source_hash':d['body_sha256'],'reviewer':'Same-session Codex source review, not independent or human'}
   rejected.append(rec)
   with ledger.db:ledger.event('RECOVERY_EVENT_COUNTEREXAMPLE_REVIEW',rec)
 c.close();ledger.backup(R/'research-snapshot.sqlite3');ledger.close()
 write(R/'document-results.json',{'at':now(),'documents':reports,'raw_windows_archive':'window-results.json.gz','model':'fastino/gliner2-base-v1','API_calls':0})
 write(R/'event-reviews.json',{'at':now(),'new_source_reported_reviews':reviewed,'negative_reviews':rejected,'limited_relation_hypotheses':diagnostics,
      'source_review_method':'Same-session Codex source inspection, not human/independent accuracy; no target-model output generated.',
      'new_official_primary_verified_events':0,'strict_downstream_adoption':0,'new_S1_S2_S3':[0,0,0],
      'existing_reviewed_events_reused':14,'not_quality_scores':True})
 with gzip.GzipFile(filename=str(R/'window-results.json.gz'),mode='wb',mtime=0)as f:f.write(json.dumps(windows,ensure_ascii=False,allow_nan=False).encode())
 original_digest=table_digest(V/'ledger/v4.sqlite3');assert table_digest(R/'research-snapshot.sqlite3')==original_digest
 with gzip.GzipFile(filename=str(R/'research-snapshot.sqlite3.gz'),mode='wb',mtime=0)as f:f.write((R/'research-snapshot.sqlite3').read_bytes())
 restore=V/'restored';restore.mkdir(exist_ok=True);(restore/'v4.sqlite3').write_bytes(gzip.decompress((R/'research-snapshot.sqlite3.gz').read_bytes()))
 assert table_digest(restore/'v4.sqlite3')==original_digest;(R/'research-snapshot.sqlite3').unlink()
 assert sha(SOURCE.read_bytes())==frozen['source_DB_sha256']
 assert all(sha(pathlib.Path(p).read_bytes())==h for p,h in frozen['protected_files'].items())
 assert all(x['unread_nonwhitespace_characters']==0 for x in reports)
 counts=Counter(x['status']for x in windows);bad=[{'key':x['key'],'document_id':x['document_id'],'rejected':x.get('CPU',{}).get('rejected_spans',[])}for x in windows if x['status']=='PARTIAL_REVIEW']
 result={'at':now(),'start_sha':frozen['start_sha'],'documents_processed':len(reports),'first_CPU_documents':sum(x['first_CPU_document']for x in reports),
     'previous_partial_document_expanded':sum(not x['first_CPU_document']for x in reports),
     'body_characters':sum(x['actual_CPU_coverage']['body_characters']for x in reports),
     'actually_CPU_read_characters':sum(x['actual_CPU_coverage']['read_characters']for x in reports),
     'fresh_CPU_read_characters':sum(x['fresh_CPU_characters']for x in reports),'cache_characters':sum(x['previous_CPU_cache_characters']for x in reports),
     'unread_characters':sum(x['actual_CPU_coverage']['unread_characters']for x in reports),'unread_nonwhitespace_characters':0,
     'model_window_results':dict(counts),'new_model_inferences':sum(not x['cache_reused']for x in windows),
     'cache_windows':sum(x['cache_reused']for x in windows),'remaining_windows':0,'failed_windows':0,
     'rejected_source_mentions_preserved':sum(len(x['rejected'])for x in bad),'invalid_mention_details':bad,
     'CPU_all_label_proposals_retained':sum(x['CPU_all_label_proposals_retained']for x in reports),
     'CPU_product_proposals_retained':sum(x['CPU_product_proposals_retained']for x in reports),
     'CPU_model_wall_seconds_including_loads':sum(x['model_wall_seconds_including_initializations']for x in reports),
     'CPU_process_seconds_including_loads':sum(x['CPU_seconds_including_initializations']for x in reports),
     'consumed6_diagnosis':'development-diagnosis.json','existing14_regression':'reviewed14-regression.json',
     'new_source_reported_actual_event_reviews':len(reviewed),'new_official_primary_verified_events':0,'strict_downstream_event_adoptions':0,
     'new_reported_roles':dict(Counter(x['role']for x in reviewed)),'source_primary_pending_documents':38,
     'original_CPU_baseline_preserved':{'TP':16,'FP':13,'FN':9},
     'AI_missing18_recovered_as_CPU_exploration':12,'AI_missing18_remaining_without_CPU':6,'new_AI_reading_errors_fixed':0,
     'AI_quality':'FAIL_UNCHANGED','independent20':'BLOCKED_UNCHANGED','S1_S2_S3_change':[0,0,0],
     'Groq_calls':0,'new_AI_tokens':0,'API_cost_KRW':0,'platform_cost':'UNKNOWN_SEPARATE',
     'source_provenance_held':155,'contact_safety_held':2,'source_holds_changed':False,
     'operations_UI_Actions_main_changed':False,'automation_enabled':False,'forecast_performance':'NOT_RUN',
     'next':'Keep all CPU/AI proposals,14 prior reviewed events and6 source-reported reviews. Verify primary originals and missing need-period/qualified-supply before pairing/promotions. Do not rerun completed CPU windows.'}
 result['CPU_character_coverage']=result['actually_CPU_read_characters']/result['body_characters']
 write(R/'storage-proof.json',{'at':now(),'tables':original_digest,'backup_and_compressed_restore':'PASS_ALL_8_TABLE_DIGESTS',
     'protected_files_unchanged':len(frozen['protected_files']),'source_DB_unchanged':True,'API_ledger_byte_hash_unchanged':True,
     'snapshot_sha256':sha((R/'research-snapshot.sqlite3.gz').read_bytes()),'window_archive_sha256':sha((R/'window-results.json.gz').read_bytes())})
 write(R/'RESULTS.json',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
