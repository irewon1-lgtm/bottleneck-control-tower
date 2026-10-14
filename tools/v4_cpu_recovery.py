"""Offline, append-only window queue. No network clients or model installs."""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import sqlite3
import time
import re

from bct.v4.adapters import CPUExtractor, MODEL, MODEL_REVISION
from bct.v4.reading_quality import plan_pages
from bct.v4.store import Ledger, sha, now

R=Path('docs/v4/cpu-recovery');V=Path('var/v4/cpu-recovery');SOURCE=Path('var/v4/cross-industry/ledger/v4.sqlite3')


def read(path):return json.loads(Path(path).read_text())
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x')as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def ro(path):return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)


def freeze():
    if (R/'freeze.json').exists():return
    c=ro(SOURCE);audit=read('docs/v4/reading-quality/input-coverage-audit.json');config=read('docs/v4/path-comparison/final/config.json')
    docs=[]
    for x in audit['prepared']:
        d= json.loads(c.execute('SELECT payload FROM documents WHERE id=?',(x['document_id'],)).fetchone()[0])
        plan=plan_pages(d,config,{})
        assert sum(p['selected_characters']for p in plan['pages'])==x['prepared_characters']
        docs.append({'document':d,'plan':plan})
    assert len(docs)==38
    tasks=[]
    # Fair queue across sources, no industry-by-industry approval or filtering.
    for page in range(max(len(x['plan']['pages'])for x in docs)):
        for row in docs:
            if page>=len(row['plan']['pages']):continue
            d=row['document']
            for window in row['plan']['pages'][page]['windows']:
                key=sha([MODEL,MODEL_REVISION,d['document_id'],d['body_sha256'],window])
                tasks.append({'key':key,'document_id':d['document_id'],'page':page,'window':window})
    assert len({t['key']for t in tasks})==len(tasks)
    # Protect previous quality evidence, operations, UI, corpus and API ledger.
    protected={str(p):sha(p.read_bytes())for root in ('docs/v4/reading-quality','docs/v4/post-ui','docs/v4/path-comparison/final','.github/workflows','src/bct/v4/dashboard_web') for p in Path(root).rglob('*')if p.is_file()}
    for p in ('src/bct/v4/dashboard.py','docs/index.html','docs/app.js','docs/style.css','docs/view-model.js','var/v4/sequential/api-ledger/v4.sqlite3'):
        protected[p]=sha(Path(p).read_bytes())
    write(R/'inputs.json',{'documents':docs,'scope':'Existing safe38 development documents; not unused holdout'})
    write(R/'freeze.json',{'at':now(),'start_sha':'cc190d429e369580cda5ac5790a9b45b9168baf8','model':MODEL,'revision':MODEL_REVISION,
        'tasks':tasks,'source_DB_sha256':sha(SOURCE.read_bytes()),'protected_files':protected,
        'source_holds':{'provenance':155,'contact':2,'changed':False},'Groq_calls_allowed':0,
        'inputs_sha256':sha((R/'inputs.json').read_bytes()),'criteria':'Preserve all proposals; exact source/relation adoption separate; no S promotion or independent-performance claim.'})
    c.close();print(json.dumps({'documents':38,'windows':len(tasks),'pages':sum(len(x['plan']['pages'])for x in docs),'prepared_characters':sum(t['window']['end']-t['window']['start']for t in tasks)}))


def caches():
    result={}
    paths=list(Path('var/v4/cross-industry/cpu').glob('*.json'))+[Path('docs/v4/reading-quality/live-cpu.json')]
    for p in paths:
        x=read(p);cpu=x.get('CPU',{});did=x.get('document_id');body=x.get('body_sha256')
        if not body and did:
            rows=read(R/'inputs.json')['documents'];body=next((r['document']['body_sha256']for r in rows if r['document']['document_id']==did),None)
        if cpu.get('status')!='PASS' or cpu.get('model')!=MODEL or cpu.get('revision')!=MODEL_REVISION:continue
        for w in cpu.get('selected_windows',[]):
            if 'text' not in w:continue
            spans=[s for s in cpu['spans'] if w['start']<=s['locator']['start']<s['locator']['end']<=w['end']]
            result[sha([MODEL,MODEL_REVISION,did,body,w])]={'status':'PASS','model':MODEL,'revision':MODEL_REVISION,'spans':spans,'selected_windows':[w],'cache_origin':str(p),'raw_model_output':'NOT_AVAILABLE_IN_HISTORICAL_CACHE'}
    return result


def extend_cpu_scope():
    """CPU-only remainder, without inheriting Groq's 16-page queue ceiling.

    Reuse sentence/context rules and exact cached windows. Linked conditions
    stay intact; at most1800 characters, the existing CPU window bound.
    """
    out=R/'cpu-remainder.json'
    if out.exists():return
    from bct.v4.public_input import LINK,COUNTER
    from bct.precursor_scope_reader import sentences
    old=read(R/'freeze.json');tasks=[];withheld=[]
    for row in read(R/'inputs.json')['documents']:
        d=row['document'];body=d['body'];groups=[];current=[]
        known=[t['window']for t in old['tasks']if t['document_id']==d['document_id']]
        for p in re.finditer(r'[^\n]+',body):
            continuation=re.match(r'^(?:this|these|it|its|they|their|the (?:order|contract|agreement|system|facility))\b',p[0].strip(),re.I)
            if current and (LINK.search(p[0].strip())or COUNTER.search(p[0])or continuation):current.append(p)
            else:
                if current:groups.append(current)
                current=[p]
        if current:groups.append(current)
        for group in groups:
            a,b=group[0].start(),group[-1].end();text=body[a:b]
            dependent=re.search(r'\b(?:it|its|they|their|this|these|those|such|however|whereas|unless|although|if|not|never|subject to|provided that)\b',text,re.I)
            spans=[(a,b)]
            if b-a>1100 and len(group)==1 and not dependent and not COUNTER.search(text):
                spans=[(p['start'],p['end'])for p in sentences(d,[{'quote':text,'start':a,'end':b,'paragraph_start':a}])]
            for a,b in spans:
                if any(w['start']==a and w['end']==b for w in known):continue
                if any(a<w['end']and w['start']<b for w in known):
                    reason='PARTLY_READ_CONTEXT_NOT_CUT'
                elif b-a>1800:reason='WHOLE_LINKED_CONTEXT_EXCEEDS_CPU1800'
                else:reason=None
                if reason:
                    withheld.append({'document_id':d['document_id'],'start':a,'end':b,'reason':reason});continue
                w={'start':a,'end':b,'text':body[a:b]};key=sha([MODEL,MODEL_REVISION,d['document_id'],d['body_sha256'],w])
                tasks.append({'key':key,'document_id':d['document_id'],'page':'CPU_REMAINDER','window':w})
    write(out,{'at':now(),'reason':'CPU does not inherit Groq16-page ceiling; no API limit changed. Existing CPU1800-char bound and complete-context rules retained.',
               'tasks':tasks,'withheld':withheld,'extra_characters':sum(t['window']['end']-t['window']['start']for t in tasks)})
    print(json.dumps({'additional_CPU_windows':len(tasks),'characters':sum(t['window']['end']-t['window']['start']for t in tasks),'withheld_contexts':len(withheld)}))


def work(seconds):
    frozen=read(R/'freeze.json');assert sha((R/'inputs.json').read_bytes())==frozen['inputs_sha256']
    docs={r['document']['document_id']:r['document']for r in read(R/'inputs.json')['documents']}
    receipts=V/'windows';receipts.mkdir(exist_ok=True);l=Ledger(V/'ledger');source=ro(SOURCE)
    cache=caches();extractor=CPUExtractor('var/v4/repair/cpu/runtime');started=time.monotonic();done=0
    try:
        with l.worker():
            prior={json.loads(p)['key']for p, in l.db.execute("SELECT payload FROM events WHERE kind='CPU_WINDOW_ATTEMPT'")}
            completed={json.loads(p)['key']:json.loads(p)for p, in l.db.execute("SELECT payload FROM events WHERE kind='CPU_WINDOW_RESULT'")}
            tasks=frozen['tasks']+(read(R/'cpu-remainder.json')['tasks']if(R/'cpu-remainder.json').exists()else[])
            for task in tasks:
                out=receipts/(task['key']+'.json')
                if out.exists():continue
                if task['key']in completed:
                    write(out,completed[task['key']]);continue
                if task['key']in prior:
                    print(json.dumps({'key':task['key'],'state':'INTERRUPTED_ATTEMPT_HELD_NO_AUTO_RETRY'}));continue
                if time.monotonic()-started>=seconds:break
                d=docs[task['document_id']];w=task['window']
                assert d['body'][w['start']:w['end']]==w['text'] and sha(d['body'].encode())==d['body_sha256']
                if not l.db.execute('SELECT 1 FROM documents WHERE id=?',(d['document_id'],)).fetchone():
                    raw=source.execute('SELECT data FROM blobs WHERE id=?',(d['raw_sha256'],)).fetchone()[0]
                    assert sha(raw)==d['raw_sha256'];l.capture(d,raw)
                with l.db:l.event('CPU_WINDOW_ATTEMPT',{**task,'at':now(),'retry':False})
                at=now();clock=time.monotonic();cpuclock=time.process_time()
                try:
                    cpu=cache.get(task['key']) or extractor.extract_windows(d,[w],diagnostic=True)
                    result={**task,'at':at,'status':cpu['status'],'CPU':cpu,'cache_reused':task['key']in cache,'actually_model_read_characters':len(w['text']),
                            'wall_seconds':time.monotonic()-clock,'cpu_seconds_including_load':time.process_time()-cpuclock}
                except Exception as e:
                    result={**task,'at':at,'status':'FAILED_ISOLATED','reason':str(e) if isinstance(e,ValueError)else type(e).__name__,
                            'actually_model_read_characters':0,'wall_seconds':time.monotonic()-clock,'cpu_seconds_including_load':time.process_time()-cpuclock}
                write(out,result)
                with l.db:l.event('CPU_WINDOW_RESULT',result)
                if 'CPU'in result:l.capture(d,reading={'window_key':task['key'],'CPU':result['CPU']})
                done+=1
                if done%25==0:print(json.dumps({'new_window_results':done,'elapsed_seconds':round(time.monotonic()-started,1),'last_status':result['status']}),flush=True)
    finally:l.close();source.close()
    print(json.dumps({'new_window_results':done,'remaining':sum(not(receipts/(t['key']+'.json')).exists()for t in tasks),'seconds':time.monotonic()-started,'new_API_calls':0}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['freeze','extend','work']);p.add_argument('--seconds',type=int,default=180);a=p.parse_args()
    if a.action=='freeze':freeze()
    elif a.action=='extend':extend_cpu_scope()
    else:
        assert 1<=a.seconds<=300
        work(a.seconds)
