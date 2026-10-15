"""Resumable official Q1 JSON batches using existing source/award transports."""
import argparse,json,time,urllib.request,urllib.error,hashlib,os
from pathlib import Path
from bct.v4.adapters import SourceClient
from bct.collectors.usaspending.collector import USAspendingTransport,request_body
from bct.v4.store import Ledger,now,sha
from bct.v4.quantitative import commit_page,cursor,parse_awards,parse_transactions,parse_ted,records
ROOT=Path('var/v4/quantitative/q1');REG=Path('docs/v4/quantitative/source-registry.json')

class Budget:
 def __init__(self):self.start=time.monotonic();self.calls=0
 def check(self):
  if self.calls>=32 or time.monotonic()-self.start>95:raise TimeoutError('BATCH_CHECKPOINT_BUDGET_NO_RETRY')
  self.calls+=1


def request_cache(url,source,body=None,*,budget):
 key=sha([url,body]);folder=ROOT/'requests';folder.mkdir(exist_ok=True);data=folder/(key+'.raw');proof=folder/(key+'.json')
 if proof.exists():
  m=json.loads(proof.read_text())
  if m['status']!=200:raise ValueError('PREVIOUS_FAILURE_QUARANTINED_'+str(m['status']))
  if not data.exists()or sha(data.read_bytes())!=m['sha256']:raise ValueError('CACHED_BODY_CORRUPTED')
  return data.read_bytes(),m
 budget.check();t=time.monotonic()
 try:
  if source=='usaspending'and url.endswith('/search/spending_by_award/'):b=USAspendingTransport(timeout_seconds=25).post(body)
  elif body is not None:
   with urllib.request.urlopen(urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'BCT-Q1-research/1.0'},method='POST'),timeout=25)as r:b=r.read(20000001)
  else:
   b,final,status,content_type=SourceClient().fetch(url)
   if status!=200:raise ValueError('SOURCE_HTTP_'+str(status))
  if not b:raise ValueError('SOURCE_EMPTY_BODY')
  if len(b)>20000000:raise ValueError('MAX_SOURCE_BYTES')
  # These requests contain no API keys/Secret echoes; never persist token-bearing URLs.
  if any(x in url.lower()for x in ['api_key=','token=','secret=','session=']):raise ValueError('SECRET_URL')
  data.write_bytes(b);m={'url':url,'request':body,'source_id':source,'source_lineage_id':source.upper(),'status':200,'sha256':sha(b),'bytes':len(b),'acquired_at':now(),'published_at':'UNKNOWN','path':str(data),'seconds':time.monotonic()-t}
 except Exception as e:
  m={'url':url,'request':body,'source_id':source,'status':getattr(e,'code','FAILED'),'reason':type(e).__name__,'seconds':time.monotonic()-t,'same_request_retry_allowed':False};proof.write_text(json.dumps(m,indent=2));raise
 proof.write_text(json.dumps(m,indent=2));return b,m


def usa(budget):
 spec=json.loads(REG.read_text())['sources']['usaspending']['scope'];ledger=Ledger(ROOT/'ledger');done=[]
 with ledger.worker():
  for keyword in spec['keywords']:
   task='usa-awards-'+keyword;c=cursor(ledger,task)
   while c['next']and c['next']<=spec['max_pages_per_query']:
    body=request_body(keyword,'keyword',spec['page_size']);body['page']=c['next'];body['filters']['time_period']=[{'start_date':spec['start'],'end_date':spec['end']}]
    body['fields']+=['Start Date','End Date','Contract Award Type','NAICS','PSC']
    raw,meta=request_cache('https://api.usaspending.gov/api/v2/search/spending_by_award/','usaspending',body,budget=budget)
    rows,p=parse_awards(raw,meta);has=p['page_metadata']['hasNext'];done.append(commit_page(ledger,task,meta,rows,page=c['next'],has_next=has));c=cursor(ledger,task)
  awards=[r[0]for r in ledger.db.execute("SELECT DISTINCT json_extract(payload,'$.record.entity_or_facility_id') FROM events WHERE kind='QUANTITATIVE_OBSERVATION' AND json_extract(payload,'$.record.source_id')='usaspending' AND json_extract(payload,'$.record.metric')='award_amount' ORDER BY 1")]
  for award in awards:
   task='usa-transactions-'+award;c=cursor(ledger,task)
   while c['next']and c['next']<=10:
    body={'award_id':award,'limit':100,'page':c['next'],'sort':'action_date','order':'asc'}
    try:
     raw,meta=request_cache('https://api.usaspending.gov/api/v2/transactions/','usaspending',body,budget=budget)
     rows,p=parse_transactions(raw,meta,award);done.append(commit_page(ledger,task,meta,rows,page=c['next'],has_next=p['page_metadata']['hasNext']));c=cursor(ledger,task)
    except (TimeoutError,urllib.error.HTTPError):
     raise  # Budget/rate/auth failures stop this source without another call.
    except ValueError as exc:
     if 'CHECKPOINT_'in str(exc) or 'PREVIOUS_FAILURE_QUARANTINED_429'in str(exc):raise
     # A bad cached response or one award's schema must not starve all others.
     with ledger.db:ledger.event('QUANTITATIVE_SOURCE_FAILURE',{'task':task,'page':c['next'],'error':str(exc)[:180],'retry':False,'at':now()})
     break
 ledger.close();return done


def ted(budget):
 spec=json.loads(REG.read_text())['sources']['ted']['scope'];ledger=Ledger(ROOT/'ledger');done=[]
 # Field tokens and date syntax are verified against saved official OpenAPI description.
 fields=['publication-number','publication-date','notice-type','classification-cpv','total-value','total-value-cur','quantity-lot','quantity-unit-lot','result-lot-identifier']
 query='PD >= '+spec['start'].replace('-','')+' AND PD <= '+spec['end'].replace('-','')+' AND PC = ('+' OR '.join(spec['CPV'])+')'
 with ledger.worker():
  c=cursor(ledger,'ted-search');stop=(c['next']or 1)+spec['max_pages_per_batch']
  while c['next']and c['next']<stop:
   body={'query':query,'fields':fields,'page':c['next'],'limit':spec['page_size'],'scope':'ALL','paginationMode':'PAGE_NUMBER','onlyLatestVersions':False}
   raw,meta=request_cache('https://api.ted.europa.eu/v3/notices/search','ted',body,budget=budget)
   rows,p,held=parse_ted(raw,meta);total=p['totalNoticeCount'];has=c['next']*spec['page_size']<total
   done.append(commit_page(ledger,'ted-search',meta,rows,page=c['next'],has_next=has,total=total))
   with ledger.db:ledger.event('QUANTITATIVE_NOTICE_HELD',{'task':'ted-search','page':c['next'],'notices':len(p['notices']),'held':held,'total':total})
   c=cursor(ledger,'ted-search')
 ledger.close();return done

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('source',choices=['usaspending','ted']);a=ap.parse_args();b=Budget()
 try:r=usa(b)if a.source=='usaspending'else ted(b);print(json.dumps({'source':a.source,'results':r,'network_requests':b.calls}))
 except Exception as e:print(json.dumps({'source':a.source,'status':'PARTIAL_OR_BLOCKED','error':type(e).__name__,'reason':str(e)[:200],'network_requests':b.calls}));raise SystemExit(1)
