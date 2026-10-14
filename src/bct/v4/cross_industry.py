"""Research sweep over the existing open source network; no AI/API or operating writes.

Industry hints are accounting labels, never selection or event proof. A common
source queue and evidence schema are used for every industry and unknown topics.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import json,re,socket,uuid
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit
import yaml

from bct.collectors.rss.collector import parse_feed,RSSTransport
from bct.target_acquisition import public_url
from bct.objective_lock import stamp_export
from .adapters import SourceClient
from .research_intake import discover
from .public_input import PUBLISHERS
from .evidence_path import analyze as connect, relation_check, ROLES
from .store import Ledger,sha,now

VERSION='bct-cross-industry-1'


def feed_sources(path='rss_feeds.yaml'):
    text=Path(path).read_text();data=yaml.safe_load(text);scope='UNCLASSIFIED_OPEN_DISCOVERY';scopes={}
    for line in text.splitlines():
        if line.startswith('disabled_feeds:'):break
        if line.startswith('  # '):scope=line[4:].strip()
        if line.startswith('  ')and not line.lstrip().startswith('#')and ': https://'in line:
            label=line.strip().split(': https://')[0];scopes[label]=scope
    return [{'kind':'RSS','name':name,'url':url,'industry_hint':scopes.get(name,'UNCLASSIFIED_OPEN_DISCOVERY'),
             'hint_status':'SOURCE_SECTION_NOT_VERIFIED_INDUSTRY'}for name,url in data['feeds'].items()],data.get('disabled_feeds',{})


def classify_error(exc):
    code=getattr(exc,'code',None)
    if code in (401,403,451):return 'A_ACCESS_RESTRICTED'
    if code==429 or code and code>=500:return 'B_COMMUNICATION_OR_LIMIT'
    if isinstance(exc,(TimeoutError,socket.timeout,URLError)):return 'B_COMMUNICATION_OR_LIMIT'
    if code in (404,410):return 'A_ENDPOINT_UNAVAILABLE'
    return 'C_EXTRACTION_OR_VALIDATION'


def safe_url(url):
    public_url(url);p=urlsplit(url)
    if re.search(r'(?:token|auth|session|password|secret|key)=',p.query,re.I):raise ValueError('CREDENTIAL_QUERY_BLOCKED')
    return url


def fair_select(items,limit):
    """Breadth first by source section, host second; UNKNOWN is an equal section."""
    groups=defaultdict(list)
    for x in items:groups[x.get('industry_hint','UNCLASSIFIED_OPEN_DISCOVERY')].append(x)
    out=[];hosts=Counter()
    while groups and len(out)<limit:
        for k in list(groups):
            xs=groups[k];xs.sort(key=lambda x:hosts[urlsplit(x['url']).hostname]);x=xs.pop(0)
            out.append(x);hosts[urlsplit(x['url']).hostname]+=1
            if not xs:del groups[k]
            if len(out)>=limit:break
    return out


def prior_attempts(ledger,phase):
    return {json.loads(p)['url']for p, in ledger.db.execute("SELECT payload FROM events WHERE kind=?",('CROSS_'+phase+'_ATTEMPT',))}


def collect(root,sources,*,article_limit=24,workers=6,feed_limit=4,client=None,feed_transport=None,known_urls=()):
    if not 1<=workers<=8 or not 1<=article_limit<=100:raise ValueError('BOUNDED_RESEARCH_BATCH')
    ledger=Ledger(root);client=client or SourceClient();feed_transport=feed_transport or RSSTransport(timeout_seconds=10)
    rid='cross-'+uuid.uuid4().hex;receipts=[];captured=[]
    def fetch_index(s):
        raw=None
        try:
            if s['kind']=='RSS':
                raw=feed_transport.get(s['url']);leads=[asdict(x)for x in parse_feed(raw,feed_limit)]
            else:
                raw,final,status,_=client.fetch(s['url'])
                if final!=s['url']or status!=200:raise ValueError('INDEX_IDENTITY')
                leads=[{'url':u}for u in discover(raw,{**s,'index_url':s['url']})[:100]]
            return s,raw,leads,None
        except Exception as e:return s,raw,[],{'category':classify_error(e),'type':type(e).__name__,'http_status':getattr(e,'code',None),'parser_reason':str(e)if str(e)in ('invalid feed XML','unsupported feed format','feed has no entries','invalid feed date','feed DTD is not allowed')else None}
    try:
        with ledger.worker():
            old=prior_attempts(ledger,'SOURCE');todo=[]
            source_attempts={json.loads(t)['url']:json.loads(t)for t, in ledger.db.execute("SELECT payload FROM events WHERE kind='CROSS_SOURCE_ATTEMPT' ORDER BY seq")}
            last_sources={json.loads(t)['source']['url']:json.loads(t)for t, in ledger.db.execute("SELECT payload FROM events WHERE kind='CROSS_SOURCE_RESULT' ORDER BY seq")}

            for source in sources:
                safe_url(source['url'])
                if any(x['url']==source['url']for x in todo):continue
                previous=last_sources.get(source['url'])
                if source['url']in old:
                    if not previous or previous['status']!='PARSED':continue
                    if source_attempts[source['url']]['at']>previous['at']:continue
                    age=(datetime.fromisoformat(now())-datetime.fromisoformat(previous['at'])).total_seconds()
                    if age<86400:continue

                with ledger.db:ledger.event('CROSS_SOURCE_ATTEMPT',{'url':source['url'],'run_id':rid,'at':now(),'source':source,'automatic_retries':0})
                todo.append(source)
            with ThreadPoolExecutor(max_workers=workers)as pool:
                futures=[pool.submit(fetch_index,s)for s in fair_select(todo,len(todo))]
                for future in as_completed(futures):
                    s,raw,leads,error=future.result();receipt={'source':s,'at':now(),'status':'FAILED_ISOLATED'if error else'PARSED','error':error,'leads':len(leads)}
                    with ledger.db:
                        if raw is not None:
                            receipt['raw_sha256']=sha(raw);ledger.db.execute('INSERT OR IGNORE INTO blobs VALUES(?,?)',(sha(raw),raw))
                        previous=last_sources.get(s['url'])
                        if previous and raw is not None and previous.get('raw_sha256')!=sha(raw):
                            ledger.event('CROSS_SOURCE_VERSION',{'url':s['url'],'before_raw_sha256':previous.get('raw_sha256'),'after_raw_sha256':sha(raw),'at':now(),'scope':'FEED_OR_INDEX_VERSION_ONLY_NOT_SUPPLY_CHANGE'})
                        ledger.event('CROSS_SOURCE_RESULT',receipt)
                        for item in leads:
                            try:safe_url(item['url'])
                            except ValueError:continue
                            ledger.event('CROSS_DISCOVERED',{**item,'industry_hint':s['industry_hint'],'source_url':s['url'],'discovered_at':now(),'source_raw_sha256':sha(raw),'publication_verified':False})
                    receipts.append(receipt)
            all_leads={};prior=prior_attempts(ledger,'ARTICLE')|set(known_urls)
            prior.update(x[0]for x in ledger.db.execute('SELECT url FROM documents'))
            for text, in ledger.db.execute("SELECT payload FROM events WHERE kind='CROSS_DISCOVERED' ORDER BY seq"):
                x=json.loads(text)
                if x['url']not in prior:all_leads.setdefault(x['url'],x)
            # One stale managed source gets a refresh slot; pending new URLs
            # retain the rest. Failed URLs never refresh automatically.
            last_articles={json.loads(t)['url']:json.loads(t)for t, in ledger.db.execute("SELECT payload FROM events WHERE kind='CROSS_ARTICLE_RESULT' ORDER BY seq")}
            article_attempts={json.loads(t)['url']:json.loads(t)for t, in ledger.db.execute("SELECT payload FROM events WHERE kind='CROSS_ARTICLE_ATTEMPT' ORDER BY seq")}
            stale=[x for x in last_articles.values()if x['status']=='CAPTURED'and article_attempts[x['url']]['at']<=x['at']and(datetime.fromisoformat(now())-datetime.fromisoformat(x['at'])).total_seconds()>=86400]
            refresh=min(stale,key=lambda x:x['at'])if stale else None
            batch=fair_select(list(all_leads.values()),article_limit-int(bool(refresh)))
            if refresh:batch.append({**refresh,'refresh':True})
            def article(x):
                try:
                    doc,raw,views=client.document(x['url']);return x,doc,raw,None
                except Exception as e:return x,None,None,{'category':classify_error(e),'type':type(e).__name__,'http_status':getattr(e,'code',None)}
            for x in batch:
                with ledger.db:ledger.event('CROSS_ARTICLE_ATTEMPT',{'url':x['url'],'at':now(),'run_id':rid,'automatic_retries':0})
            with ThreadPoolExecutor(max_workers=workers)as pool:
                futures=[pool.submit(article,x)for x in batch]
                for future in as_completed(futures):
                    x,doc,raw,error=future.result();receipt={'url':x['url'],'industry_hint':x['industry_hint'],'at':now(),'status':'FAILED_ISOLATED'if error else'CAPTURED','error':error}
                    if doc is not None:
                        doc['primary_source_verified']=urlsplit(doc['origin_url']).hostname in PUBLISHERS and doc.get('provenance')=='PASS'
                        doc['primary_source_basis']='EXISTING_OFFICIAL_REGISTRY_AND_ORIGINAL_METADATA'if doc['primary_source_verified']else'UNKNOWN_RESEARCH_DISCOVERY_ONLY'
                        previous=last_articles.get(x['url'])
                        added=ledger.capture(doc,raw,{'collection_origin':'CROSS_INDUSTRY','AI':'DISABLED'})
                        if previous and previous.get('body_sha256')!=doc['body_sha256']:
                            with ledger.db:ledger.event('CROSS_ARTICLE_CHANGE',{'url':x['url'],'previous_document_id':previous['document_id'],'document_id':doc['document_id'],'before_body_sha256':previous.get('body_sha256'),'after_body_sha256':doc['body_sha256'],'at':now(),'meaning':'BODY_VERSION_CHANGE_REQUIRES_FACT_REVIEW_NOT_AUTOMATIC_S_PROMOTION'})
                        receipt.update(document_id=doc['document_id'],body_status=doc['body_status'],body_characters=len(doc['body']),provenance=doc['provenance'],body_sha256=doc['body_sha256'])
                        if added:captured.append(doc['document_id'])
                    with ledger.db:ledger.event('CROSS_ARTICLE_RESULT',receipt)
            result=stamp_export({'version':VERSION,'run_id':rid,'at':now(),'sources_executed':len(todo),'source_results':receipts,
                'previous_source_attempts_not_retried':len(old),'eligible_unique_pending_before_batch':len(all_leads),
                'article_attempts':len(batch),'captured':captured,'pending_unattempted':max(0,len(all_leads)-len(batch)+int(bool(refresh))),'managed_daily_refresh_slots':int(bool(refresh)),
                'AI_calls':0,'operational_integration_enabled':False,'candidates':[],'forecast_performance':'NOT_RUN'})
            return ledger.save_run(rid,result,'BACKFILL')
    finally:ledger.close()


def proposals_from_cpu(doc,reading):
    """CPU entities + transmitted paragraphs → strict shared relation check.

    No industry/product dictionary. Event hints are not semantic truth. All
    accepted literals remain research limited checks, never S2/S3 proof.
    """
    spans=reading.get('spans',[]);windows=reading.get('selected_windows',[]);out=[];seen=set()
    body=doc['body']
    for span in spans:
        if span['label']!='product':continue
        c,d=span['locator']['start'],span['locator']['end']
        w=next((w for w in windows if w['start']<=c<d<=w['end']),None)
        if not w:continue
        a,b=w['start'],w['end'];quote=body[a:b]
        actual='NEGATED'if re.search(r'\b(?:did not|cancelled|canceled)\b',quote,re.I)else'PLAN'if re.search(r'\b(?:will|plans?|expected|may|could|intends?)\b',quote,re.I)else'ACTUAL'
        product={'surface':span['text'],'reference':{'start':c,'end':d,'quote':body[c:d]}}
        # Test shared relations for ALL CPU products; no old parser event gate.
        for role in sorted(ROLES):
            ok,_=relation_check(product,{'start':a,'end':b,'quote':quote},role,actual)
            if ok:
                out.append({'reference':{'start':a,'end':b,'quote':quote},'product':{'value':span['text'],'reference':{'start':c,'end':d,'quote':body[c:d]}},'role':role,'actuality':actual,'fields':{},'origin':'CPU_LITERAL_ENTITY_AND_SHARED_LIMITED_RELATION_NOT_AI_OR_GOLD'})
    # Physical entities with no recognized event stay exploration records.
    for span in spans:
        if span['label']!='product':continue
        c,d=span['locator']['start'],span['locator']['end']
        if any(p['product']['reference']['start']==c for p in out):continue
        w=next((w for w in windows if w['start']<=c<d<=w['end']),None)
        if w:out.append({'reference':{'start':w['start'],'end':w['end'],'quote':body[w['start']:w['end']]},'product':{'value':span['text'],'reference':{'start':c,'end':d,'quote':body[c:d]}},'role':'UNKNOWN','actuality':'UNKNOWN','fields':{},'origin':'CPU_DISCOVERY_ONLY'})
    return out


def source_review(doc,raw):
    """Missing metadata holds this document, never stops another industry."""
    from .public_input import review_native
    if not isinstance(doc.get('published_at'),str)or not doc['published_at']:
        return {'status':'BLOCKED','reasons':['PUBLICATION_UNKNOWN']}
    try:
        return review_native(doc,raw,{'url':doc['origin_url'],'final_url':doc['origin_url'],'raw_sha256':doc['raw_sha256'],'body_sha256':doc['body_sha256'],'published_at':doc['published_at']})
    except (ValueError,KeyError,TypeError,AttributeError)as e:
        return {'status':'BLOCKED','reasons':['METADATA_INVALID_'+type(e).__name__]}


def reading_result(doc,reading):
    if sha(doc['body'].encode())!=doc['body_sha256']:raise ValueError('BODY_HASH_MISMATCH')
    for s in reading.get('spans',[]):
        a,b=s['locator']['start'],s['locator']['end']
        if s.get('body_sha256')!=doc['body_sha256']or doc['body'][a:b]!=s['text']:raise ValueError('CPU_SOURCE_MISMATCH')
    for w in reading.get('selected_windows',[]):
        if not 0<=w['start']<w['end']<=len(doc['body']):raise ValueError('CPU_WINDOW_INVALID')
        if 'text'in w and doc['body'][w['start']:w['end']]!=w['text']:raise ValueError('CPU_WINDOW_TEXT_MISMATCH')
    ps=proposals_from_cpu(doc,reading)
    review=doc.get('native_source_review')or{}
    excerpt=(review.get('status')=='PASS'and all(review.get(k)==doc.get(k)for k in ('document_id','body_sha256','raw_sha256','origin_url','published_at')))
    allowed=bool(doc.get('published_at'))and ((doc.get('provenance')=='PASS'and doc.get('primary_source_verified')is True)or excerpt)
    result=connect([doc],{doc['document_id']:ps},enabled=True)
    # Literal CPU entities and broad verb checks are advisory, not semantic proof.
    # Keep raw downstream proposals, but do not auto-adopt or manufacture S1.
    from copy import deepcopy
    result['limited_relation_diagnostic']=deepcopy(result)
    for record in result['records']:
        record.update(event_status='DISCOVERY_ONLY',meaning_status='CPU_RELATION_REVIEW_PENDING'if allowed else'SOURCE_VERIFICATION_PENDING',s_stage='UNKNOWN')
    result['counts'].update(events=0,S1=0,S2=0,S3=0)
    result['pairs']=[]
    result.update(original_provenance_preserved=doc.get('provenance'),source_validation_scope='VERIFIED_PUBLIC_EXCERPT_ONLY'if excerpt else'ORIGINAL_DOCUMENT_PROVENANCE',source_gate='PASS'if allowed else'HELD_PRIMARY_SOURCE_PUBLICATION_OR_PROVENANCE',CPU_reading=reading,
        CPU_products=sum(s['label']=='product'for s in reading.get('spans',[])),
        read_characters=sum(w['end']-w['start']for w in reading.get('selected_windows',[]))if reading.get('status')=='PASS'else 0,
        body_characters=len(doc['body']),proposals=ps,unread_policy='Not model FN or no-bottleneck evidence',
        priority='COUNTERPART_EVIDENCE_REVIEW'if result['counts']['S1']else'SOURCE_OR_PRODUCT_REVIEW'if ps else'NO_OBSERVED_SIGNAL_IN_READ_SCOPE')
    return result


def common_evidence(record,doc,origin):
    """One envelope for discovery/reviewed narrative facts; original stays intact."""
    return {'event_id':sha(['common-1',origin,record['id']]),'evidence_kind':'NARRATIVE',
        'origin_kind':origin,'original_record_id':record['id'],
        'target':{k:v['normalized']if v else None for k,v in record['target'].items()},
        'source_surface_target':{k:v['surface']if v else None for k,v in record['target'].items()},
        'role':record['role'],'actuality':record['actuality'],'event_status':record['event_status'],
        'meaning_status':record['meaning_status'],'s_stage':record['s_stage'],
        'fields':record.get('fields',{}),'references':[record['context'],record['product']['reference']],
        'sources':[{'document_id':doc['document_id'],'url':doc['origin_url'],'origin_publisher':doc.get('origin_publisher'),'origin_id':doc.get('origin_id'),'published_at':doc.get('published_at'),
                    'acquired_at':doc.get('acquired_at'),'raw_sha256':doc.get('raw_sha256'),'body_sha256':doc['body_sha256']}],
        'total_qualified_supply':'UNKNOWN','independence':'UNKNOWN','future_gap':'UNKNOWN','research_only':True}


def common_structured(event,source_documents=None):
    """Same target/status envelope, different row/cell reference format only."""
    f=event['after']['fields'];surface={'product':f.get('Technology'),'specification':None,'region':f.get('Plant State'),'customer_group':None,'supply_pool':None}
    return {'event_id':sha(['common-1','EIA_REPORTED_CHANGE',event['id']]),'original_record_id':event['id'],
        'evidence_kind':'STRUCTURED','origin_kind':'REUSED_EIA_REPORTED_CHANGE',
        'target':{k:v.strip().casefold()if isinstance(v,str)else None for k,v in surface.items()},
        'source_surface_target':surface,'role':event['role'],'actuality':'REPORTED_STATUS_NOT_PHYSICALLY_VERIFIED',
        'event_status':'REPORTED_CHANGE_UNVERIFIED','meaning_status':'QUALIFIED_SUPPLY_UNKNOWN','s_stage':'UNKNOWN','fields':{},
        'references':[event['before'],event['after']],
        'sources':[{'url':r['url'],'raw_sha256':r['raw_sha256'],'published_at':'UNKNOWN','acquired_at':(source_documents or{}).get(r['url'],{}).get('acquired_at','UNKNOWN'),'reporting_period':r['period']}for r in (event['before'],event['after'])],
        'total_qualified_supply':'UNKNOWN','independence':'UNKNOWN','future_gap':'UNKNOWN','research_only':True}


def deepen(record,documents,common_records,*,limit=3):
    """Bounded actual-source retrieval, never same-name proof of equivalent TARGET.

    Whole stored documents are searched locally. Matches are pointers for review,
    not new interpreted facts or inferred need dates. No network/AI calls.
    """
    if not 1<=limit<=3:raise ValueError('COUNTERPART_SOURCE_CAP_3')
    product=record['source_surface_target']['product'];matches=[];seen=set()
    for doc in documents:
        if doc['document_id']==record['sources'][0].get('document_id'):continue
        if doc['body_sha256']in seen:continue
        positions=[{'start':m.start(),'end':m.end(),'quote':m.group()}for m in re.finditer(r'(?<!\w)'+re.escape(product)+r'(?!\w)',doc['body'],re.I)]
        if not positions:continue
        seen.add(doc['body_sha256']);publisher=doc.get('origin_publisher')
        original_publisher=record['sources'][0].get('origin_publisher')
        independence='NOT_ESTABLISHED'if not publisher or publisher=='UNKNOWN'or not original_publisher or original_publisher=='UNKNOWN'or publisher==original_publisher else'DIFFERENT_PUBLISHER_ONLY_EVENT_ORIGIN_UNVERIFIED'
        matches.append({'document_id':doc['document_id'],'url':doc['origin_url'],'body_sha256':doc['body_sha256'],'published_at':doc.get('published_at'),'provenance':doc.get('provenance'),'independence':independence,'literal_positions':positions,'scope_equivalence':'UNKNOWN_NOT_NAME_ONLY','read_scope':'Exact-name search only, no whole-document semantic interpretation'})
    matches.sort(key=lambda x:(x['independence']=='NOT_ESTABLISHED',x['published_at']or'9999',x['url']))
    related=[]
    for x in common_records:
        if x['event_id']==record['event_id']or x['target'].get('product')!=record['target']['product']:continue
        if x['origin_kind']!='REUSED_SOURCE_ONLY_AI_REVIEW_NOT_NEW_DISCOVERY':continue
        complete=all(record['target'].values())and all(x['target'].values())
        related.append({'event_id':x['event_id'],'role':x['role'],'actuality':x['actuality'],'TARGET_equivalence':'FIVE_LITERAL_FIELDS_MATCH'if complete and x['target']==record['target']else'UNPROVEN_SCOPE','independence':'UNKNOWN','need_ready_period_comparable':False,'supply_quantity_comparable':False})
    return {'review_id':sha(['deep-1',record['event_id'],[(d['document_id'],d['body_sha256'])for d in matches[:limit]],related]),'source_event_id':record['event_id'],'product':product,'source_cap':limit,'selected_source_documents':matches[:limit],'additional_matching_documents_not_read':max(0,len(matches)-limit),'related_reviewed_records':related,'missing':['CUSTOMER_NEED_PERIOD','SUPPLIER_READY_PERIOD','TOTAL_QUALIFIED_SUPPLY','RESIDUAL_DEMAND','INDEPENDENT_COMPARABLE_COUNTERPART'],'result':'INSUFFICIENT_EVIDENCE_NO_PROMOTION','S2':False,'S3':False,'new_AI_calls':0,'source_search_not_accuracy_or_forecast':True}


def alternative_body_view(doc,raw,*,views=None):
    """Existing HTML alternative only for empty bodies; never replace an original."""
    from copy import deepcopy
    from .adapters import html_views
    import importlib.metadata
    if doc.get('body_status')!='UNAVAILABLE'or doc['body']:return None
    if sha(raw)!=doc['raw_sha256']or sha(doc['body'].encode())!=doc['body_sha256']:raise ValueError('ORIGINAL_SOURCE_HASH_MISMATCH')
    text_html=raw.decode('utf-8',errors='replace')
    if re.search(r'class=[\"\'][^\"\']*\bgsd-paywall\b',text_html,re.I)or re.search(r'[\"\']isAccessibleForFree[\"\']\s*:\s*false',text_html,re.I):
        raise ValueError('EXPLICIT_ACCESS_RESTRICTION_MARKER')
    parsed=views if views is not None else html_views(raw);text=parsed.get('trafilatura')or''
    if not text.strip():return None
    d=deepcopy(doc);d.update(document_id='cross-view-'+sha([doc['document_id'],sha(text.encode()),'trafilatura-derived-1']),body=text,body_sha256=sha(text.encode()),version=sha(text.encode()),body_status='PARTIAL',provenance='BLOCKED',provenance_verified=False,provenance_blockers=['ALTERNATIVE_EXTRACTION_FULLNESS_AND_SOURCE_RELATION_UNVERIFIED'],source_snapshot_kind='DERIVED_EXTRACTION_VIEW',original_document_id=doc['document_id'],original_body_sha256=doc['body_sha256'],extraction={'name':'trafilatura','version':importlib.metadata.version('trafilatura'),'source_raw_sha256':doc['raw_sha256'],'text_not_rewritten':True,'fullness':'UNVERIFIED_PARTIAL','not_a_new_source_or_supply_event':True})
    return d
