#!/usr/bin/env python3
"""Bounded manual SEC/Census batches, using existing typed Q1 private state."""
import argparse,base64,json,os,re,sqlite3,sys,time
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from bct.v4.store import Ledger,sha,now,file_sha
from bct.v4 import quantitative as q,quantitative_private as private
from bct.v4.private_state import _gpg
from bct.v4.quantitative_sources import census_safe,parse_trade,parse_sec_inline
from bct.collectors.sec.transport import SECTransport

R=Path('var/v4/quantitative/q1-source-work');BRIDGE=Path('var/v4/quantitative/q1-source-bridge')
REG=Path('docs/v4/quantitative/source-registry.json')

class StopBatch(Exception):pass
class SourceFailure(Exception):
 def __init__(self,status,reason):self.status=status;self.reason=reason;super().__init__(reason)

class Fetch:
 def __init__(self,ledger):self.start=time.monotonic();self.calls=0;self.ledger=ledger;self.sec=SECTransport(os.environ['BCT_SEC_USER_AGENT']);self.key=os.environ['CENSUS_API_KEY']
 def get(self,url,source):
  folder=R/'native';folder.mkdir(parents=True,exist_ok=True);key=sha(url);data=folder/(key+'.raw');meta=folder/(key+'.json');host=urlsplit(url).hostname
  if meta.exists():
   m=json.loads(meta.read_text())
   if m['status']!=200:raise SourceFailure(m['status'],m['reason'])
   if file_sha(data)!=m['sha256']:raise ValueError('SOURCE_CACHE_HASH')
   return data.read_bytes(),m
  failed=self.ledger.db.execute("select payload from events where kind='QUANTITATIVE_SOURCE_FAILURE'and json_extract(payload,'$.task') in (?,?)limit 1",('source-'+key,'host-'+host)).fetchone()
  if failed:raise SourceFailure('PREVIOUS_FAILURE_QUARANTINED',json.loads(failed[0])['error'])
  if self.calls>=32 or time.monotonic()-self.start>90:raise StopBatch()
  self.calls+=1;status=None;raw=b'';content_type='UNKNOWN';reason='UNKNOWN'
  try:
   if source=='sec':raw=self.sec.get(url);status=200
   else:
    time.sleep(.25)
    # The request's key-bearing URL is memory only and is never emitted or persisted.
    with urlopen(Request(url+'&'+urlencode({'key':self.key}),headers={'User-Agent':'BCT-Q1-free-research/1.0'}),timeout=25)as response:
     status=response.status;content_type=response.headers.get_content_type();raw=response.read(20000001)
    if status!=200:raise SourceFailure(status,'CENSUS_NON200_OR_PENDING')
    if not raw or len(raw)>20000000:raise SourceFailure(status,'CENSUS_EMPTY_OR_SIZE')
    # Inspect only fixed error indicators; error bodies and echoed credentials stay out of logs/cache.
    low=raw.lower()
    if any(s in low for s in [b'invalid key',b'invalid api key',b'key is not valid',b'not been activated']):raise SourceFailure(status,'CENSUS_KEY_REJECTED_OR_UNACTIVATED')
    try:raw,redaction=census_safe(raw,self.key)
    except (ValueError,TypeError,KeyError)as exc:
     safe_reason=str(exc)if str(exc)in {'CENSUS_ARRAY_REQUIRED','CENSUS_COLUMN_ALIGNMENT','CENSUS_UNREVIEWED_CREDENTIAL_ECHO'}else type(exc).__name__
     raise SourceFailure(status,'CENSUS_RESPONSE_'+safe_reason)from None
   if not raw:raise SourceFailure(status,'EMPTY_BODY')
   data.write_bytes(raw);m={'source_id':source,'source_lineage_id':'SEC'if source=='sec'else'US_CENSUS_INTLTRADE','url':url,'status':200,'sha256':sha(raw),'path':str(data),'acquired_at':now(),'published_at':'UNKNOWN','bytes':len(raw)}
   if source!='sec':m['redaction']=redaction
   meta.write_text(json.dumps(m));return raw,m
  except (HTTPError,SourceFailure)as exc:
   status=getattr(exc,'code',getattr(exc,'status',status));reason=exc.reason if isinstance(exc,SourceFailure)else'HTTP_ERROR'
  except Exception as exc:
   reason='TRANSPORT_'+type(exc).__name__
   sec_status=re.fullmatch(r'SEC HTTP (\d{3})',str(exc))if source=='sec'else None
   if sec_status:status=int(sec_status[1])
  m={'status':status or'UNKNOWN','reason':reason,'source_id':source,'url':url,'response_bytes':len(raw),'content_type':content_type,'retried':False,'acquired_at':now(),'diagnostics':{'HTML_response':b'<html'in raw[:3000].lower(),'invalid_key_phrase':b'invalid key'in raw.lower(),'missing_key_phrase':b'missing key'in raw.lower(),'unknown_variable_phrase':b'unknown variable'in raw.lower()}};meta.write_text(json.dumps(m))
  task='host-'+host if status in (202,401,403,429)or reason=='CENSUS_KEY_REJECTED_OR_UNACTIVATED'or reason.startswith('CENSUS_RESPONSE_')else'source-'+key
  with self.ledger.db:self.ledger.event('QUANTITATIVE_SOURCE_FAILURE',{'task':task,'page':1,'error':str(status)+':'+reason,'retry':False,'at':now()})
  raise SourceFailure(status,reason)


def state_scope():
 return json.loads(REG.read_text())['sources']


def prepare():
 from bct.v4.cpu_operations import github_guard
 github_guard();R.mkdir(parents=True,exist_ok=False)
 result=private.remote_checkpoint(R/'private-read',R/'prior',os.environ.get('BCT_V4_PRIVATE_STATE_TOKEN',''))
 sealed=private.seal(R/'prior',BRIDGE/'prior/state.gpg',os.environ['BCT_V4_STATE_PASSPHRASE'],result['parent'])
 print('BCT_Q1_PRIOR_JSON='+json.dumps({'private_parent':result['parent'],'typed_restore':result['verified'],'encrypted_handoff':sealed}))


def initialize():
 if (R/'ledger/v4.sqlite3').exists():return
 R.mkdir(parents=True,exist_ok=True)
 prior=private.unseal(BRIDGE/'prior/state.gpg',R/'prior',os.environ['BCT_V4_STATE_PASSPHRASE'])
 private.restore(R/'prior',R/'ledger');(R/'parent.json').write_text(json.dumps(prior))
 bundle=json.loads(_gpg(Path('var/v4/quantitative/q1-source-probe/result.gpg').read_bytes(),os.environ['BCT_V4_STATE_PASSPHRASE'],decrypt=True))
 probe={k:base64.b64decode(v,validate=True)for k,v in bundle.items()};receipt=json.loads(probe['receipt.json']);native=R/'native';native.mkdir()
 if 'sec-original.json'in probe:
  url='https://data.sec.gov/submissions/CIK0001701605.json';raw=probe['sec-original.json'];ident=sha(url);path=native/(ident+'.raw');path.write_bytes(raw)
  (native/(ident+'.json')).write_text(json.dumps({'status':200,'url':url,'source_id':'sec','sha256':sha(raw),'path':str(path),'acquired_at':receipt['at'],'published_at':'UNKNOWN','reused_probe':True}))
 (R/'probe-receipt.json').write_text(json.dumps(receipt))


def sec(ledger,fetch):
 spec=state_scope()['sec']['scope'];ciks=json.loads(Path('config/v4-sources.json').read_text())['ciks']
 for cik in ciks:
  cik=str(cik).zfill(10);url='https://data.sec.gov/submissions/CIK'+cik+'.json'
  try:raw,meta=fetch.get(url,'sec');listing=json.loads(raw)
  except SourceFailure:continue
  recent=listing['filings']['recent'];length=len(recent['accessionNumber'])
  required=['accessionNumber','form','filingDate','primaryDocument']
  if any(len(recent[k])!=length for k in required):raise ValueError('SEC_SUBMISSION_ARRAY_LENGTH')
  for i in range(length):
   form=recent['form'][i];day=recent['filingDate'][i]
   if not(spec['start']<=day<=spec['end'])or form.removesuffix('/A')not in {'10-K','10-Q','8-K','20-F','6-K'}:continue
   accession=recent['accessionNumber'][i];filename=recent['primaryDocument'][i]
   if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',accession)or not re.fullmatch(r'[A-Za-z0-9._-]{1,200}',filename)or'..'in filename:raise ValueError('SEC_ACCESSION_OR_FILENAME')
   task='sec-filing-'+accession
   if q.cursor(ledger,task)['next']is None:continue
   if ledger.db.execute("select 1 from events where kind='QUANTITATIVE_DOCUMENT'and json_extract(payload,'$.accession')=?and json_extract(payload,'$.status')='SOURCE_BODY_BLOCKED'limit 1",(accession,)).fetchone():continue
   filingurl=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-","")}/{filename}'
   pub=recent.get('acceptanceDateTime',[None]*length)[i]or day
   try:
    body,m=fetch.get(filingurl,'sec');m['published_at']=pub
    rows,detail=parse_sec_inline(body,m,cik,accession)
    q.commit_page(ledger,task,m,rows)
    with ledger.db:ledger.event('QUANTITATIVE_DOCUMENT',{'source_id':'sec','document_id':m['sha256'],'url':filingurl,'published_at':pub,'filing_date':day,'accession':accession,'form':form,'cik':cik,'detail':detail,'status':'EXACT_INLINE_EXTRACTION_SEMANTICS_PENDING'})
   except SourceFailure as e:
    with ledger.db:ledger.event('QUANTITATIVE_DOCUMENT',{'source_id':'sec','document_id':sha([cik,accession]),'url':filingurl,'published_at':pub,'filing_date':day,'accession':accession,'form':form,'cik':cik,'detail':{'error':e.reason},'status':'SOURCE_BODY_BLOCKED'})


def census(ledger,fetch):
 spec=state_scope()['census_trade'];months=spec['scope']['months'];maps=spec['annual_mapping']['records']
 # Export is a distinct, schema-verified request, never a replay of the old failed imports query.
 for direction in ['exports','imports']:
  for item in maps:
   if item['direction']!=('export'if direction=='exports'else'import'):continue
   year=item['year'];start=max(months[0],year+'-01');end=min(months[1],year+'-12')
   if start>end:continue
   code=item['code'];task='census-country-detail-v2-'+direction+'-'+year+'-'+code
   if q.cursor(ledger,task)['next']is None:continue
   fields='E_COMMODITY_LDESC,ALL_VAL_MO,QTY_1_MO,QTY_2_MO,UNIT_QY1,UNIT_QY2'if direction=='exports'else'I_COMMODITY_LDESC,GEN_QY1_MO,CON_QY1_MO,GEN_VAL_MO,CON_VAL_MO,UNIT_QY1'
   # CTY_CODE is optional/default displayed in the official schema.
   # The old guessed world code 0000 produced 188 empty responses. Query
   # explicit country detail instead; preserve every returned geography.
   params={'get':fields+',CTY_NAME','time':'from '+start+' to '+end,('E_COMMODITY'if direction=='exports'else'I_COMMODITY'):code}
   url='https://api.census.gov/data/timeseries/intltrade/'+direction+'/hs?'+urlencode(params)
   try:
    raw,meta=fetch.get(url,'census_trade');rows=parse_trade(raw,meta,direction,'VERIFIED_ANNUAL_CODE_UNIT')
    for row in rows:
     if row['measurement_type']=='PHYSICAL'and row['unit_original'].lower().replace(' ','')!=item['unit_original'].lower().replace(' ',''):
      row.update(quality_state='HELD_CODE_UNIT_CHANGED',unknown_reason='API unit differs from same-year official primary unit; secondary quantities not treated as primary')
    for row in rows:q.verify_locator(row,raw)
    q.commit_page(ledger,task,meta,rows)
   except (ValueError,KeyError)as e:
    # A local parser/schema error must not discard other-source progress.
    # Preserve safe diagnostics, stop this path; never relax duplicate checks.
    with ledger.db:ledger.event('QUANTITATIVE_SOURCE_FAILURE',{'task':'source-'+sha(url),'page':1,'error':'LOCAL_PARSER_'+type(e).__name__+':'+str(e)[:100],'retry':False,'at':now()})
    return
   except SourceFailure as e:
    # A common empty response before any data stops the path. Once
    # actual country data exists, isolate individual no-data code years.
    if e.status==204 and not ledger.db.execute("select 1 from events where kind='QUANTITATIVE_PAGE_COMMITTED'and json_extract(payload,'$.task')like 'census-country-detail-v2-%'limit 1").fetchone():return
    if e.status in (202,401,403,429)or e.reason=='CENSUS_KEY_REJECTED_OR_UNACTIVATED'or e.reason.startswith('CENSUS_RESPONSE_'):return


def process(only_trade=False):
 initialize();ledger=Ledger(R/'ledger');fetch=Fetch(ledger);done=False
 try:
  with ledger.worker():
   if not only_trade:sec(ledger,fetch)
   census(ledger,fetch);done=True
 except StopBatch:pass
 finally:ledger.close()
 print('BCT_Q1_SOURCE_BATCH_JSON='+json.dumps({'HTTP_requests_this_batch':fetch.calls,'all_unblocked_tasks_visited':done,'AI_calls':0,'CPU_windows':0}))
 return 0 if done else 75


def finish():
 ledger=Ledger(R/'ledger');active=q.research_export(ledger)['observations'];by={}
 for source in sorted(private.SOURCES):
  rows=[r['record']for r in active if r['record']['source_id']==source];by[source]={'numeric':sum(r['value_decimal_or_null']is not None for r in rows),'physical':sum(r['value_decimal_or_null']is not None and r['measurement_type']=='PHYSICAL'for r in rows),'held':sum(r['quality_state'].startswith('HELD')for r in rows),'money':sum(r['value_decimal_or_null']is not None and r['measurement_type']=='MONEY'for r in rows),'publication_UNKNOWN':sum(r['published_at']=='UNKNOWN'for r in rows)}
 docs=[json.loads(p)for p, in ledger.db.execute("select payload from events where kind='QUANTITATIVE_DOCUMENT'")];failures=[json.loads(p)for p, in ledger.db.execute("select payload from events where kind='QUANTITATIVE_SOURCE_FAILURE'")]
 native=[json.loads(p.read_text())for p in (R/'native').glob('*.json')];report={'by_source':by,'SEC_documents':docs,'SEC_filings_seen':len({d['accession']for d in docs}),'SEC_bodies_extracted':sum(d['status'].startswith('EXACT')for d in docs),'failures':failures,'requests_including_reused_probe_receipts':len(native),'response_diagnostics':[m for m in native if m['status']!=200],'bindings':{'SEC_present':bool(os.environ.get('BCT_SEC_USER_AGENT')),'Census_present':bool(os.environ.get('CENSUS_API_KEY')),'Census_40hex_format':bool(re.fullmatch('[0-9a-fA-F]{40}',os.environ.get('CENSUS_API_KEY','')))},'Q2_report':json.loads((R/'q2-report.json').read_text())if(R/'q2-report.json').exists()else None,'firsts':ledger.db.execute('select count(*)from firsts').fetchone()[0],'AI_calls':0,'CPU_windows':0}
 report['new_source_samples']={}
 for source in ['sec','census_trade']:
  rows=[x['record']for x in active if x['record']['source_id']==source and x['record']['value_decimal_or_null']is not None]
  report['new_source_samples'][source]=[{k:r[k]for k in ['product_or_classification','metric','value_original','value_normalized_or_null','unit_original','geography','period_start','period_end','published_at','source_url','raw_or_safe_payload_hash','source_locator','quality_state']}for r in (rows[:2]+rows[-2:]if len(rows)>2 else rows)]
 report['total_numeric']=sum(x['record']['value_decimal_or_null']is not None for x in active)
 report['Census_periods']=sorted({x['record']['period_start'][:7]for x in active if x['record']['source_id']=='census_trade'})
 report['source_scope']='SEC fixed30days/two configured issuers; Census fixed36months/annual mapped codes; country rows never summed as independent sources'
 report['source_task_counts']={prefix:ledger.db.execute("select count(*)from events where kind='QUANTITATIVE_PAGE_COMMITTED'and json_extract(payload,'$.task')like ?",(prefix+'%',)).fetchone()[0]for prefix in ['sec-filing-','census-country-detail-v2-']}
 with ledger.worker():private.checkpoint(ledger,R/'checkpoint')
 ledger.close();parent=json.loads((R/'parent.json').read_text())['parent']
 private.seal(R/'checkpoint',BRIDGE/'result/state.gpg',os.environ['BCT_V4_STATE_PASSPHRASE'],parent,report=report)
 print('BCT_Q1_SOURCES_REPORT_JSON='+json.dumps(report))


def storage():
 initialize();ledger=Ledger(R/'ledger')
 with ledger.worker():
  with ledger.db:ledger.event('QUANTITATIVE_VALIDATION',{'reason':'Actual incremental checkpoint compatibility check; no numerical facts added','originals_modified':False,'policy':{'scope':'Q1 private storage only','source_collection':False,'delete_history':False,'raise_retention_limit':False}})
 ledger.close();finish()


def targets():
 initialize();ledger=Ledger(R/'ledger')
 from bct.v4.quantitative_targets import save
 legacy=json.loads(Path('docs/v4/supply-linkage/next-step-inputs.json').read_text())['records']
 with ledger.worker():result=save(ledger,legacy,as_of='2026-10-15')
 before=file_sha(ledger.path);ledger.close()
 # Actual fresh-process persistence/dedup: no source/network/model execution.
 import subprocess
 code="from bct.v4.store import Ledger;from bct.v4.quantitative_targets import save;from pathlib import Path;import json;L=Ledger('var/v4/quantitative/q1-source-work/ledger');r=save(L,json.loads(Path('docs/v4/supply-linkage/next-step-inputs.json').read_text())['records'],as_of='2026-10-15');L.close();print(json.dumps(r))"
 child=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=60)
 if child.returncode:raise ValueError('Q2_FRESH_PROCESS_RELOAD_FAILED')
 restarted=json.loads(child.stdout)
 if restarted['added_review_records']!=0 or file_sha(R/'ledger/v4.sqlite3')!=before:raise ValueError('Q2_DUPLICATE_RESTART_CHANGED_DB')
 result['actual_fresh_process_noop']={'added':0,'database_hash_unchanged':True,'new_HTTP_requests':0}
 (R/'q2-report.json').write_text(json.dumps(result));finish()


def publish():
 result=private.unseal(BRIDGE/'result/state.gpg',R/'publish-checkpoint',os.environ['BCT_V4_STATE_PASSPHRASE'])
 owner=json.loads(Path('docs/v4/cpu-automation/preflight/connection-results.json').read_text());scope=owner['actual_remote_evidence']['receipts']['BCT_PRIVATE_SCOPE_JSON']['scope']
 receipt=private.publish(R/'private-write',R/'publish-checkpoint',result['parent'],os.environ['BCT_V4_PRIVATE_STATE_TOKEN'],scope)
 print('BCT_Q1_SOURCES_PUBLISH_JSON='+json.dumps({'report':result['report'],'receipt':receipt,'code_SHA':os.environ['GITHUB_SHA']}))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','process','finish','publish','targets','trade','storage']);a=parser.parse_args()
 if a.action in {'process','trade'}:raise SystemExit(process(only_trade=a.action=='trade'))
 else:globals()[a.action]()
