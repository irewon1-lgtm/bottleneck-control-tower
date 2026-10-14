"""One bounded round3 source request per invocation/run; no old input retries.

The batch uses the existing shared research API ledger and frozen account caps.
"""
import argparse,gzip,json,pathlib,time
from datetime import datetime,timezone
from bct.v4.free_ai import Router,HTTPAdapter,source_input,VERSION,SYSTEM,QUOTE_SCHEMA
from bct.v4.store import Ledger,sha,now,encode
from v4_scoped_evaluation import verify_freeze
R=pathlib.Path('docs/v4/stage4-corpus/round3')
V=pathlib.Path('var/v4/sequential/api-ledger')


def run(limit):
 freeze=verify_freeze(R);config=json.loads((R/'request-config.json').read_text())
 assert (R/'gold-freeze.json').exists(),'SOURCE_ONLY_TRUTH_MUST_BE_REVIEWED_BEFORE_GROQ'
 gold_freeze=json.loads((R/'gold-freeze.json').read_text())
 assert sha((R/'event-gold.json').read_bytes())==gold_freeze['gold_sha256']
 out=R/'responses';out.mkdir(exist_ok=True);done=0
 for row in json.loads((R/'inputs.json').read_text())['documents']:
  if row['status']!='ELIGIBLE':continue
  if (out/(row['document_id']+'.json')).exists():continue
  verify_freeze(R);ledger=Ledger(V)
  try:
   with ledger.worker():
    router=Router(ledger,config);assert router.request_contract==freeze['request_contract']
    source=source_input({**row['doc'],'api_safe_input_review':row['review']},config,router.env)
    assert source==row['source']
    key=sha([VERSION,SYSTEM,QUOTE_SCHEMA,source,row['body_sha256']])
    if any(a['input_key']==key for a in router.events('API_ATTEMPT')):continue
    before=ledger.db.execute('select coalesce(max(seq),0) from events').fetchone()[0]
    old=router.events('API_ATTEMPT')
    reserve=len(encode(HTTPAdapter({}).request('groq',source,config['max_output_tokens'])[2]).encode())+config['max_output_tokens']
    # Reuse the tested rolling budget: reported tokens when known, full
    # reservations when unknown. Never change the80%/run/account caps.
    if old and router.budget('groq',reserve)=='LOCAL_QUOTA':
     delay=65-(datetime.now(timezone.utc)-datetime.fromisoformat(old[-1]['at'])).total_seconds()
     if delay>0:print(json.dumps({'wait_seconds':round(delay,1),'reason':'MEASURED_ROLLING_FREE_BUDGET'}),flush=True)
     while delay>0:
      time.sleep(min(10,delay));delay=65-(datetime.now(timezone.utc)-datetime.fromisoformat(old[-1]['at'])).total_seconds()
    ledger.capture(row['doc'],gzip.decompress(pathlib.Path(row['raw_path']).read_bytes()))
    with ledger.db:ledger.event('API_SAFE_INPUT_REVIEW',row['review'])
    result=router.read(row['doc'])
    events=[{'seq':seq,'kind':kind,**json.loads(payload)} for seq,kind,payload in ledger.db.execute('select seq,kind,payload from events where seq>? order by seq',(before,))]
    last=lambda k:next((x for x in reversed(events) if x['kind']==k),None)
    item={'at':now(),'document_id':row['document_id'],'body_sha256':row['body_sha256'],'source':source,'attempt':last('API_ATTEMPT'),'response':last('API_RECEIVED'),'error':last('API_ERROR'),'validation':last('API_VALIDATION'),'reading':result,'provider_state':router.state('groq'),'calls':router.calls}
    with (out/(row['document_id']+'.json')).open('x') as f:f.write(json.dumps(item,ensure_ascii=False,indent=2)+'\n')
    done+=1
    print(json.dumps({'document_id':row['document_id'],'generation_received':bool(item['response']),'status':result['status'],'calls':router.calls,'usage':(item['response'] or {}).get('usage'),'failures':result.get('failures',[])}),flush=True)
    if done>=limit or not item['response'] or (router.state('groq') or {}).get('blocked'):break
  finally:ledger.close()
 print(json.dumps({'new_attempted_documents':done,'old_inputs_retried':False}),flush=True)


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--limit',type=int,choices=range(1,21),required=True);run(p.parse_args().limit)
