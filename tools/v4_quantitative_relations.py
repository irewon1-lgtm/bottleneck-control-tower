"""Resume common Q2 relationship tasks; no models, operating writes or new RSS."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import time
from urllib.parse import urlsplit

from bct.objective_lock import stamp_export
from bct.target_acquisition import fetch, verify, now
from bct.v4 import quantitative_counterpart as q
from bct.v4.store import Ledger, sha, file_sha

ROOT=Path('var/v4/quantitative/q2-relations')


def inventory():
    docs={};raws={};common={};protected={}
    for path in ['var/v4/cross-industry/ledger/v4.sqlite3','var/v4/supply-linkage/ledger/v4.sqlite3']:
        p=Path(path);protected[path]=file_sha(p)
        with sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True)as db:
            for text, in db.execute('SELECT payload FROM documents'):
                d=json.loads(text);docs[d['document_id']]=d
                native=db.execute('SELECT data FROM blobs WHERE id=?',(d['raw_sha256'],)).fetchone()
                if native:raws[d['document_id']]=native[0]
            for text, in db.execute("SELECT payload FROM events WHERE kind IN ('CROSS_COMMON_EVIDENCE','CROSS_COMMON_EVIDENCE_REVISION') ORDER BY seq"):
                r=json.loads(text);common[r['event_id']]=r
    reviews=json.loads(Path('docs/v4/post-ui/event-reviews.json').read_text())['events']
    approved={r['source_event_id']for r in reviews if r['verdict']in {'DOCUMENTED_ORDER','REPORTED_SUPPLY_CHANGE'}}
    seeds=[];rejected=[]
    for r in common.values():
        if r.get('event_status')!='ADOPTED_RESEARCH_EVENT' or r.get('actuality')!='ACTUAL':continue
        if r.get('origin_kind')!='EXPLICIT_PRIMARY_SOURCE_REVIEW_NOT_AUTOMATIC_DISCOVERY'and r['event_id']not in approved:
            rejected.append({'event_id':r['event_id'],'reason':'NOT_CONFIRMED_BY_CURRENT_SOURCE_REVIEW'});continue
        role={'DEMAND_INCREASE':'DEMAND','SUPPLY_DECREASE':'CONSTRAINT','SUPPLY_DELAY':'CONSTRAINT'}.get(r['role'])
        if not role:continue
        ref=r['sources'][0];did=ref['document_id'];d=docs[did]
        if d['body_sha256']!=ref['body_sha256']:raise ValueError('SEED_SOURCE_VERSION_CHANGED')
        surface=r['source_surface_target'];fields=r.get('fields',{})
        product=surface['product'];facility=bool(re.search(r'\b(?:site|factory|facility|plant)\b',product,re.I))
        seed={'id':r['event_id'],'product':product,'role':role,'entity_kind':'FACILITY'if facility else'PRODUCT',
              'event_key':sha([d['origin_url'],d['published_at'],role]),
              'source':{k:d.get(k)for k in ['document_id','body_sha256','raw_sha256','origin_url','published_at']},
              'fields':{'specification':surface.get('specification'),'region':surface.get('region'),
                        'customer':surface.get('customer_group'),
                        'supplier':(fields.get('reported_supplier')or{}).get('surface')or surface.get('supply_pool'),
                        'quantity':None,'need_window':None,'qualified_supplier_pool':None,'qualified_capacity':None,'delivery':None}}
        seeds.append(seed)
    # Add the exact Q2 typed order fields without discarding earlier proposals.
    products=json.loads(Path('docs/v4/quantitative/product-facts.json').read_text())
    seeds+=q.seeds(products['records'],[])
    proof_path=Path('docs/v4/quantitative/relation-facts.json')
    model_proofs=json.loads(proof_path.read_text()).get('model_identity_proofs',[])if proof_path.exists()else[]
    for seed in seeds:
        proof=next((p for p in model_proofs if p['surface']==seed['product']),None)
        if proof:seed['verified_model_proof']=proof
    tasks=q.relation_tasks(seeds)
    for task in tasks:
        did=task['source_identity']['document_id']
        d=docs.get(did)or next((x for x in docs.values()if x['body_sha256']==task['source_identity']['body_sha256']),None)
        if d and d['document_id']in raws:task['urls']=q.relation_links(task,d,raws[d['document_id']])
        task['id']=sha(['q2-relation-state-1',{k:v for k,v in task.items()if k!='id'}])
    return seeds,tasks,docs,raws,protected,rejected


def run(*,network=False):
    ROOT.mkdir(parents=True,exist_ok=True);path=ROOT/'queue.json'
    seeds,tasks,docs,raws,protected,rejected=inventory()
    old=json.loads(path.read_text())if path.exists()else None
    if old:
        previous={r['task_id']:r for r in old['tasks']}
        tasks=[{**r,**{k:previous[r['task_id']][k]for k in ['urls','cursor','checked_sources','search_state','reason']}}
               if r['task_id']in previous else r for r in tasks]
        # New verified events append; existing task states/cursors survive.
        tasks += [r for key,r in previous.items()if key not in {t['task_id']for t in tasks}]
    started=time.monotonic();calls=0;event_calls=Counter();host_calls=Counter();results=[]
    cache=ROOT/'captures';cache.mkdir(exist_ok=True)
    for previous in cache.glob('*.json'):
        if previous.name.endswith('.document.json'):continue
        saved=json.loads(previous.read_text())
        if saved.get('event_key'):
            event_calls[saved['event_key']]+=1;host_calls[urlsplit(saved['url']).hostname]+=1
    # The already executed public-only search returned unrelated YouTube URLs.
    # Quarantine this provider response; do not treat it as evidence of absence.
    search_probe=json.loads((ROOT/'search-probe.json').read_text())if(ROOT/'search-probe.json').exists()else {}
    irrelevant_hosts={'www.youtube.com','accounts.google.com','play.google.com','en.wikipedia.org'}
    provider_bad=bool(search_probe.get('urls')and all(urlsplit(u).hostname in irrelevant_hosts for u in search_probe['urls']))
    # Recovery uses preserved raw responses, never repeats the old failed GET.
    recovered={}
    for native in cache.glob('*.raw'):
        if not native.read_bytes().startswith(b'%PDF'):continue
        rawid=native.stem;receipt=cache/(rawid+'.json');result=json.loads(receipt.read_text())
        out=cache/(rawid+'.pdf-text.txt')
        if not out.exists():subprocess.run(['pdftotext','-layout',str(native),str(out)],check=True,timeout=20,capture_output=True)
        derived={'url':result['url'],'status':'PDF_RECOVERED_OFFLINE_PARTIAL_DATE_UNKNOWN','raw_sha256':file_sha(native),
                 'text_sha256':file_sha(out),'published_at':'UNKNOWN','extraction':'pdftotext-layout','qualification':'UNKNOWN'}
        (cache/(rawid+'.recovery.json')).write_text(json.dumps(derived));recovered[result['url']]=derived
    for task in tasks:
        if not task.get('party')and task['facet']in {'MANUFACTURER_FACILITY','FACILITY_CAPACITY_READY'}and task['cursor']==0:
            task['urls']=[]
        task['checked_sources']=[recovered.get(x['url'],x)for x in task['checked_sources']]
        task['search_state']='PROVIDER_IRRELEVANT_RESPONSE_PENDING_ALTERNATIVE'if provider_bad else'OFFICIAL_CITED_LINK_DISCOVERY'
        while network and task['cursor']<len(task['urls']):
            link=task['urls'][task['cursor']];url=link['url'];key=sha(url);receipt=cache/(key+'.json');rawfile=cache/(key+'.raw')
            if not receipt.exists():
                if calls>=32 or time.monotonic()-started>=90 or event_calls[task['event_key']]>=3 or host_calls[urlsplit(url).hostname]>=6:break
                # Journal BEFORE network: process death never causes blind retry.
                receipt.write_text(json.dumps({'url':url,'event_key':task['event_key'],'status':'ATTEMPT_INTERRUPTED_NO_AUTO_RETRY','at':now()}))
                calls+=1;event_calls[task['event_key']]+=1;host_calls[urlsplit(url).hostname]+=1
                try:
                    raw,final,status,ctype=fetch(url);rawfile.write_bytes(raw)
                    if raw.startswith(b'%PDF'):
                        out=cache/(key+'.pdf-text.txt');subprocess.run(['pdftotext','-layout',str(rawfile),str(out)],check=True,timeout=20,capture_output=True)
                        result={'url':url,'status':'PDF_RECOVERED_OFFLINE_PARTIAL_DATE_UNKNOWN','raw_sha256':sha(raw),'text_sha256':file_sha(out),
                                'published_at':'UNKNOWN','extraction':'pdftotext-layout','qualification':'UNKNOWN','event_key':task['event_key']}
                        receipt.write_text(json.dumps(result));results.append(result)
                        task['checked_sources'].append(result);task['cursor']+=1;continue
                    d=verify(raw,url,final,now(),status,ctype);d['document_id']='q2-relation-'+sha([url,sha(raw)])
                    q.bind_publication(d,raw)
                    result={'url':url,'status':'CAPTURED','document_id':d['document_id'],'raw_sha256':sha(raw),'body_sha256':d['body_sha256'],
                            'published_at':d.get('published_at')or'UNKNOWN','provenance':d['provenance'],'body_status':d['body_status'],
                            'semantic_relation':'UNKNOWN_NOT_ADOPTED','primary_identity':'UNVERIFIED_UNTIL_SOURCE_REVIEW'}
                    (cache/(key+'.document.json')).write_text(json.dumps(d,ensure_ascii=False))
                except Exception as exc:
                    code=getattr(exc,'code',None)
                    result={'url':url,'status':'ACCESS_BLOCKED'if code in (401,403,451)else'FETCH_FAILED',
                            'http_status':code,'error_type':type(exc).__name__,'retry':False}
                result['event_key']=task['event_key'];receipt.write_text(json.dumps(result,ensure_ascii=False));results.append(result)
            result=json.loads(receipt.read_text());task['checked_sources'].append(result)
            task['cursor']+=1
            # A successful index may point to a separate agency, issuer or a
            # filing attachment; preserve ALL unseen URLs, not just a count.
            docfile=cache/(key+'.document.json')
            if docfile.exists()and rawfile.exists():
                d=json.loads(docfile.read_text());more=q.relation_links(task,d,rawfile.read_bytes())
                used={x['url']for x in task['urls']}
                task['urls'] += [x for x in more if x['url']not in used and not used.add(x['url'])]
        if task['cursor']<len(task['urls']):task['reason']='UNPROCESSED_OFFICIAL_LINKS_PENDING_BATCH_BUDGET'
        elif any(r['status']=='ACCESS_BLOCKED'for r in task['checked_sources']):task['reason']='ACCESS_BLOCKED_NO_ABSENCE_INFERENCE'
        elif not task['checked_sources']and provider_bad:task['reason']='EXTERNAL_SEARCH_NOT_EXECUTED_PROVIDER_IRRELEVANT'
        else:task['reason']='DOCUMENT_FOUND_PUBLICATION_OR_SEMANTIC_RELATION_UNVERIFIED'
        task['id']=sha(['q2-relation-state-1',{k:v for k,v in task.items()if k!='id'}])
        # A crash preserves completed tasks and pending URL cursor atomically.
        packet=stamp_export({'plan_id':'BCT-V4-Q-1.0','tasks':tasks,'S2':0,'S3':0})
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(packet,ensure_ascii=False,indent=2));temp.replace(path)
    packet=stamp_export({'plan_id':'BCT-V4-Q-1.0','tasks':tasks,'S2':0,'S3':0})
    l=Ledger(ROOT/'ledger');saved=q.save_relations(l,packet);l.close()
    assert all(file_sha(Path(p))==h for p,h in protected.items())
    report=stamp_export({'seed_records':len(seeds),'document_role_clusters':len({s.get('event_key',s['id'])for s in seeds}),
        'relation_tasks':len(tasks),'facets':dict(Counter(t['facet']for t in tasks)),'new_HTTP_calls_this_batch':calls,
        'unique_new_source_results':results,'checked_unique_URLs':len({r['url']for t in tasks for r in t['checked_sources']}),
        'pending_URLs':sum(len(t['urls'])-t['cursor']for t in tasks),'pending_tasks':sum(t['cursor']<len(t['urls'])for t in tasks),
        'reason_counts':dict(Counter(t['reason']for t in tasks)),'provider_response_irrelevant_not_no_data':provider_bad,
        'explicitly_private_source_evidence':0,'proven_absent_data':0,
        'skipped_unconfirmed_original_records':rejected,'save':saved,'verified_new_world_events':0,'verified_full_scope_demand':0,
        'qualified_capacity':0,'confirmed_delivery':0,'independent_pairs':0,'S2':0,'S3':0,'AI_calls':0,'CPU_windows':0,
        'original_DB_hashes_unchanged':protected})
    (ROOT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--network',action='store_true');run(network=parser.parse_args().network)
