"""Resume common Q2 relationship tasks; no models, operating writes or new RSS."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import time
from urllib.parse import urlsplit, parse_qs, urlencode

from bct.objective_lock import stamp_export
from bct.target_acquisition import fetch, verify, now
from bct.v4 import quantitative_counterpart as q
from bct.v4.store import Ledger, sha, file_sha

ROOT=Path('var/v4/quantitative/q2-relations')


def official_searches(tasks,budget,started):
    """Two verified public index interfaces, shared across the research queue.

    These are bounded discovery records, not article evidence. Unsupported
    hosts remain pending; no replacement of a blocked SEC/issuer request.
    """
    folder=ROOT/'official-searches';folder.mkdir(exist_ok=True);calls=0
    for task in tasks:
        if task['scope'].get('official_search'):continue
        host=urlsplit(task['source_identity']['origin_url']).hostname
        product=task['scope'].get('manufacturer_model_proof')or{}
        model=product.get('manufacturer_model')or task['entity_literal']
        if host=='www.aehr.com':
            query='manufacturing facility'if task['facet']=='MANUFACTURER_FACILITY'else re.sub('[®™]','',model).strip()
            url='https://www.aehr.com/wp-json/wp/v2/search?'+urlencode({'search':query,'per_page':20})
            method='VERIFIED_WORDPRESS_SEARCH_PAGE1_MORE_PAGES_UNREAD'
        elif host in {'www.gov.uk','www.gsk.com','ir.halozyme.com'}:
            query=task['entity_literal']
            url='https://www.gov.uk/api/search.json?'+urlencode({'q':query,'count':20})
            method='VERIFIED_UK_GOV_SEARCH_ONLY_NOT_GLOBAL_ABSENCE'
        else:
            task['scope']['official_discovery_hold']='ISSUER_SEARCH_UNAVAILABLE_OR_UNVERIFIED_NEEDS_OTHER_OFFICIAL_INDEX'
            continue
        key=sha(url);p=folder/(key+'.json');native=folder/(key+'.raw')
        if not p.exists():
            if time.monotonic()-started>=90 or not budget.allow(task['event_key'],urlsplit(url).hostname):continue
            budget.charge(task['event_key'],url);calls+=1
            p.write_text(json.dumps({'status':'INTERRUPTED_NO_RETRY','url':url,'urls':[]}))
            try:
                raw,final,status,ctype=fetch(url);native.write_bytes(raw)
                if urlsplit(final).hostname!=urlsplit(url).hostname:raise ValueError('INDEX_REDIRECT_IDENTITY')
                value=json.loads(raw);rows=value if isinstance(value,list)else value.get('results',[])
                urls=[];unrelated=[]
                for row in rows:
                    dest=row.get('url')or('https://www.gov.uk'+row['link']if row.get('link','').startswith('/')else None)
                    if not dest:continue
                    try:q.relation_url(dest)
                    except ValueError:continue
                    if urlsplit(dest).hostname!=urlsplit(url).hostname:continue
                    if 'gov.uk'in url:
                        tokens=[s.casefold()for s in re.findall(r'[\w-]+',query)if len(s)>3 and s.casefold()not in {'site','system','systems','plant','facility'}]
                        if not tokens or tokens[0]not in str(row.get('title','')).casefold():
                            unrelated.append(dest);continue
                    if dest not in urls:urls.append(dest)
                result={'status':'OFFICIAL_INDEX_LEADS_FOUND'if urls else'NO_LEAD_IN_INDEX_RANGE_NOT_GLOBAL_ABSENCE',
                        'url':url,'urls':urls,'raw_sha256':sha(raw),'acquired_at':now(),'method':method,
                        'rows':len(rows),'unread_index_pages':'UNKNOWN','automatic':True,'not_evidence':True}
                result['unrelated_index_results']=unrelated
            except Exception as exc:
                result={'status':'OFFICIAL_INDEX_ACCESS_OR_PARSE_FAILED','url':url,'urls':[],
                        'http_status':getattr(exc,'code',None),'error_type':type(exc).__name__,'method':method}
            p.write_text(json.dumps(result))
        result=json.loads(p.read_text());task['scope']['official_search']=result
        used={x['url']for x in task['urls']}
        for dest in result['urls']:
            if dest not in used:
                task['urls'].append({'url':dest,'via_document_id':'official-index-'+key,
                                    'status':'AUTOMATIC_OFFICIAL_INDEX_LEAD','relation':'UNKNOWN_REVIEW_REQUIRED'});used.add(dest)
    return calls


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
        task['scope']['stored_maker_facility_search']=q.local_relation_pointers(task,list(docs.values()),as_of='2026-10-15')
        did=task['source_identity']['document_id']
        d=docs.get(did)or next((x for x in docs.values()if x['body_sha256']==task['source_identity']['body_sha256']),None)
        if d and d['document_id']in raws:task['urls']=q.relation_links(task,d,raws[d['document_id']])
        task['id']=sha(['q2-relation-state-1',{k:v for k,v in task.items()if k!='id'}])
    return seeds,tasks,docs,raws,protected,rejected


def run(*,network=False,next_round=False,discover=False,official=False):
    ROOT.mkdir(parents=True,exist_ok=True);path=ROOT/'queue.json'
    parents={t['task_id']:t['id']for t in json.loads(Path('docs/v4/quantitative/relation-tasks.json').read_text())['tasks']}
    seeds,tasks,docs,raws,protected,rejected=inventory()
    old=json.loads(path.read_text())if path.exists()else None
    if old:
        previous={r['task_id']:r for r in old['tasks']}
        tasks=[{**r,**{k:previous[r['task_id']][k]for k in ['urls','cursor','checked_sources','search_state','reason']}}
               if r['task_id']in previous else r for r in tasks]
        for task in tasks:
            prior=previous.get(task['task_id'],{})
            for name in ['external_search','official_search','official_discovery_hold']:
                if prior.get('scope',{}).get(name):task['scope'][name]=prior['scope'][name]
        # New verified events append; existing task states/cursors survive.
        tasks += [r for key,r in previous.items()if key not in {t['task_id']for t in tasks}]
    started=time.monotonic();calls=0;results=[]
    budget=q.RelationRound(ROOT/'request-rounds.json',next_round=next_round) if network else None
    cache=ROOT/'captures';cache.mkdir(exist_ok=True)
    held_hosts=json.loads((ROOT/'host-quarantine.json').read_text())if(ROOT/'host-quarantine.json').exists()else{}
    prior_attempts={r['url']:r for t in tasks for r in t['checked_sources']
                    if r['status']not in {'TRIAGED_NOT_SUPPLY_EVIDENCE'}}
    for result in prior_attempts.values():
        if result['status']=='HOST_ACCESS_QUARANTINED_NOT_REQUESTED':
            held_hosts[urlsplit(result['url']).hostname]=result['reason']
    # Exact stored originals outrank a new GET. Re-extraction creates a derived
    # version; it never overwrites frozen documents or upgrades their records.
    needed={u['url']for t in tasks for u in t['urls'][t['cursor']:]}
    existing={d['origin_url']:d for d in docs.values()if d['document_id']in raws}
    def reuse_stored(url):
        key=sha(url);receipt=cache/(key+'.json')
        if receipt.exists():return
        if url not in existing:
            if url in prior_attempts:
                old=prior_attempts[url]
                receipt.write_text(json.dumps({'url':url,'status':'PREVIOUS_ATTEMPT_NO_AUTOMATIC_REFETCH',
                                              'prior_status':old['status'],'published_at':old.get('published_at','UNKNOWN'),
                                              'native_available':False,'source_calls':0}))
            return
        source=existing[url];raw=raws[source['document_id']]
        if sha(raw)!=source['raw_sha256']:raise ValueError('STORED_NATIVE_HASH')
        if raw.startswith(b'%PDF'):
            (cache/(key+'.raw')).write_bytes(raw)
            receipt.write_text(json.dumps({'url':url,'status':'REUSED_STORED_PDF_FORMAT_REVIEW_PENDING','raw_sha256':sha(raw),'published_at':'UNKNOWN','source_calls':0}))
            return
        try:
            d=verify(raw,url,url,source['acquired_at']);d['document_id']='q2-offline-derived-'+sha([url,sha(raw)])
            q.bind_publication(d,raw)
        except Exception as exc:
            receipt.write_text(json.dumps({'url':url,'status':'STORED_ORIGINAL_EXTRACTION_HELD_NO_REFETCH','error_type':type(exc).__name__,'raw_sha256':sha(raw),'published_at':'UNKNOWN','source_calls':0}))
            return
        (cache/(key+'.raw')).write_bytes(raw)
        (cache/(key+'.document.json')).write_text(json.dumps(d,ensure_ascii=False))
        receipt.write_text(json.dumps({'url':url,'status':'REUSED_STORED_ORIGINAL_DERIVED_REVIEW',
                                      'document_id':d['document_id'],'raw_sha256':sha(raw),'body_sha256':d['body_sha256'],
                                      'provenance':d['provenance'],'published_at':d.get('published_at')or'UNKNOWN',
                                      'body_status':d['body_status'],'source_calls':0,'semantic_relation':'UNKNOWN_NOT_ADOPTED'}))
    for url in needed:reuse_stored(url)
    # The already executed public-only search returned unrelated YouTube URLs.
    # Quarantine this provider response; do not treat it as evidence of absence.
    search_probe=json.loads((ROOT/'search-probe.json').read_text())if(ROOT/'search-probe.json').exists()else {}
    irrelevant_hosts={'www.youtube.com','accounts.google.com','play.google.com','en.wikipedia.org'}
    provider_bad=bool(search_probe.get('urls')and all(urlsplit(u).hostname in irrelevant_hosts for u in search_probe['urls']))
    # The old Bing response is quarantined. This explicit alternative was first
    # piloted against official H225M results; snippets never become facts.
    searches=ROOT/'searches';searches.mkdir(exist_ok=True)
    if official and network:calls+=official_searches(tasks,budget,started)
    search_quarantined=((searches/'provider-quarantine.json').exists()or
                        any('CHALLENGE'in t['scope'].get('external_search',{}).get('status','')for t in tasks))
    if discover and not search_quarantined:
        from bct.target_acquisition import Metadata
        official_hosts={urlsplit(t['source_identity']['origin_url']).hostname for t in tasks}
        for task in tasks:
            old_search=task['scope'].get('external_search')
            if old_search:continue
            url='https://html.duckduckgo.com/html/?'+urlencode({'q':task['query']})
            key=sha(url);rp=searches/(key+'.json');rawpath=searches/(key+'.raw')
            if not rp.exists():
                if not network or time.monotonic()-started>=90 or not budget.allow(task['event_key'],urlsplit(url).hostname):continue
                budget.charge(task['event_key'],url);calls+=1
                rp.write_text(json.dumps({'url':url,'status':'INTERRUPTED_NO_RETRY','urls':[]}))
                try:
                    raw,final,status,ctype=fetch(url);rawpath.write_bytes(raw)
                    html=raw.decode('utf-8',errors='replace')
                    if re.search(r'anomaly\.js|anomaly-modal|Unfortunately, bots',html,re.I):
                        (searches/'provider-quarantine.json').write_text(json.dumps({'status':'HUMAN_CHALLENGE_NO_BYPASS','url_sha256':key,'at':now()}))
                        raise ValueError('SEARCH_HUMAN_CHALLENGE')
                    parser=Metadata();parser.feed(html);found=[];seen=set()
                    for href,label in parser.links:
                        dest=parse_qs(urlsplit(href).query).get('uddg',[None])[0]
                        if not dest or dest in seen:continue
                        seen.add(dest);host=urlsplit(dest).hostname or ''
                        try:q.relation_url(dest)
                        except ValueError:continue
                        if host not in official_hosts and not (host.endswith('.gov')or host.endswith('.gov.uk')or host.endswith('.europa.eu')):continue
                        # Full query/result matching nominates URLs only, never
                        # proves the manufacturer, product or independence.
                        found.append(dest)
                    result={'url':url,'status':'OFFICIAL_LEADS_FOUND'if found else'NO_OFFICIAL_LEAD_IN_SEARCH_RANGE',
                            'raw_sha256':sha(raw),'acquired_at':now(),'urls':found,'automatic':True,'not_evidence':True}
                except Exception as exc:
                    result={'url':url,'status':'SEARCH_ACCESS_OR_TRANSPORT_FAILED','http_status':getattr(exc,'code',None),'error_type':type(exc).__name__,'urls':[]}
                rp.write_text(json.dumps(result))
                if (searches/'provider-quarantine.json').exists():
                    task['scope']['external_search']={k:v for k,v in result.items()if k!='url'}
                    break
            result=json.loads(rp.read_text());task['scope']['external_search']={k:v for k,v in result.items()if k!='url'}
            used={x['url']for x in task['urls']}
            for dest in result['urls']:
                if dest not in used:
                    task['urls'].append({'url':dest,'via_document_id':'external-search-'+key,'status':'AUTOMATIC_OFFICIAL_SEARCH_LEAD','relation':'UNKNOWN_REVIEW_REQUIRED'});used.add(dest)
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
        # Re-expand preserved HTML after the narrow SEC query contract changed;
        # no network retry and no discarded future URL behind an old cursor.
        used={x['url']for x in task['urls']}
        for prior in list(task['checked_sources']):
            prior_key=sha(prior['url']);df=cache/(prior_key+'.document.json');rf=cache/(prior_key+'.raw')
            if df.exists()and rf.exists():
                for link in q.relation_links(task,json.loads(df.read_text()),rf.read_bytes()):
                    if link['url']not in used:task['urls'].append(link);used.add(link['url'])
        task['search_state']='PROVIDER_IRRELEVANT_RESPONSE_PENDING_ALTERNATIVE'if provider_bad else'OFFICIAL_CITED_LINK_DISCOVERY'
        if task['scope'].get('external_search'):task['search_state']=task['scope']['external_search']['status']
        if task['scope'].get('official_search'):task['search_state']=task['scope']['official_search']['status']
        # Triage pending links without discarding history. Direct documents lead;
        # menus/other products are marked, not fetched or adopted as evidence.
        pending=task['urls'][task['cursor']:]
        # Resolve non-fetch classifications first so exhausted network quota
        # cannot strand hundreds of menu/law entries behind one direct URL.
        # Actual GETs are still direct-only, newest dated sources first.
        def priority(link):
            match=re.search(r'/(\d{4})[/-](\d{2})',urlsplit(link['url']).path)
            period=int(''.join(match.groups()))if match else 0
            return (q.relation_link_class(task,link['url'])=='DIRECT_DOCUMENT_CANDIDATE',-period)
        pending.sort(key=priority)
        task['urls'][task['cursor']:]=pending
        while network and task['cursor']<len(task['urls']):
            link=task['urls'][task['cursor']];url=link['url'];key=sha(url);receipt=cache/(key+'.json');rawfile=cache/(key+'.raw')
            reuse_stored(url)  # Includes URLs just discovered in this traversal.
            if q.relation_url(url)=='SEC_DISCOVERY_TRANSPORT_REQUIRED':
                # Retain the observed issuer lookup. Existing www.sec.gov403
                # is quarantined; neither a generic-UA fetch nor a retry occurs.
                task['checked_sources'].append({'url':url,'status':'NOT_REQUESTED_PRIOR_SEC_HOST_QUARANTINE','prior_http_status':403,'published_at':'UNKNOWN'})
                task['cursor']+=1;continue
            classification=q.relation_link_class(task,url)
            if url in task['scope'].get('official_search',{}).get('unrelated_index_results',[]):classification='UNRELATED_OFFICIAL_INDEX_RESULT'
            if classification!='DIRECT_DOCUMENT_CANDIDATE':
                task['checked_sources'].append({'url':url,'status':'TRIAGED_NOT_SUPPLY_EVIDENCE','classification':classification,'published_at':'UNKNOWN'})
                task['cursor']+=1;continue
            if not receipt.exists()and urlsplit(url).hostname in held_hosts:
                task['checked_sources'].append({'url':url,'status':'HOST_ACCESS_QUARANTINED_NOT_REQUESTED','reason':held_hosts[urlsplit(url).hostname],'published_at':'UNKNOWN'})
                task['cursor']+=1;continue
            if not receipt.exists():
                if calls>=32 or time.monotonic()-started>=90 or not budget.allow(task['event_key'],urlsplit(url).hostname):break
                # Journal BEFORE network: process death never causes blind retry.
                budget.charge(task['event_key'],url)
                receipt.write_text(json.dumps({'url':url,'event_key':task['event_key'],'status':'ATTEMPT_INTERRUPTED_NO_AUTO_RETRY','at':now()}))
                calls+=1
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
        elif task['scope'].get('external_search')or task['scope'].get('official_search'):task['reason']='SEARCH_EXECUTED_COUNTERPART_FIELDS_REVIEW_PENDING'
        elif not task['checked_sources']and provider_bad:task['reason']='EXTERNAL_SEARCH_NOT_EXECUTED_PROVIDER_IRRELEVANT'
        else:task['reason']='DOCUMENT_FOUND_PUBLICATION_OR_SEMANTIC_RELATION_UNVERIFIED'
        task['id']=sha(['q2-relation-state-1',{k:v for k,v in task.items()if k!='id'}])
        # A crash preserves completed tasks and pending URL cursor atomically.
        packet=stamp_export({'plan_id':'BCT-V4-Q-1.0','tasks':tasks,'S2':0,'S3':0})
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(packet,ensure_ascii=False,indent=2));temp.replace(path)
    if budget:budget.close()
    packet=stamp_export({'plan_id':'BCT-V4-Q-1.0','tasks':tasks,'S2':0,'S3':0,'resume_parent_ids':parents,
                        'request_rounds':budget.state if budget else json.loads((ROOT/'request-rounds.json').read_text())if(ROOT/'request-rounds.json').exists()else None})
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(packet,ensure_ascii=False,indent=2));temp.replace(path)
    l=Ledger(ROOT/'ledger');saved=q.save_relations(l,packet);l.close()
    assert all(file_sha(Path(p))==h for p,h in protected.items())
    report=stamp_export({'seed_records':len(seeds),'document_role_clusters':len({s.get('event_key',s['id'])for s in seeds}),
        'relation_tasks':len(tasks),'facets':dict(Counter(t['facet']for t in tasks)),'new_HTTP_calls_this_batch':calls,
        'round':budget.current if budget else None,'external_searches_executed':sum(bool(t['scope'].get('external_search'))for t in tasks),
        'official_index_requests_covered':sum(bool(t['scope'].get('official_search'))for t in tasks),
        'unique_new_source_results':results,'checked_unique_URLs':len({r['url']for t in tasks for r in t['checked_sources']}),
        'pending_URLs':sum(len(t['urls'])-t['cursor']for t in tasks),'pending_tasks':sum(t['cursor']<len(t['urls'])for t in tasks),
        'observed_SEC_query_links_held':len({u['url']for t in tasks for u in t['urls']if u['status']=='HELD_SEC_INDEX_PRIOR_HOST_QUARANTINE'}),
        'reason_counts':dict(Counter(t['reason']for t in tasks)),'provider_response_irrelevant_not_no_data':provider_bad,
        'explicitly_private_source_evidence':0,'proven_absent_data':0,
        'skipped_unconfirmed_original_records':rejected,'save':saved,'verified_new_world_events':0,'verified_full_scope_demand':0,
        'qualified_capacity':0,'confirmed_delivery':0,'independent_pairs':0,'S2':0,'S3':0,'AI_calls':0,'CPU_windows':0,
        'original_DB_hashes_unchanged':protected})
    (ROOT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--network',action='store_true');parser.add_argument('--next-round',action='store_true');parser.add_argument('--discover',action='store_true');parser.add_argument('--official-discover',action='store_true')
    args=parser.parse_args();run(network=args.network,next_round=args.next_round,discover=args.discover,official=args.official_discover)
