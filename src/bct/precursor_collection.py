"""New-only, source-bound precursor intake and bounded opposite-side acquisition.

Collector state is separate from corpus and prospective state. Frozen discovery
and EARLY/strict/S3 engines are called, never modified. No session creation.
"""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit

from . import precursor_discovery as pd, target_acquisition as acquisition
from . import early_forecast, forecast_discovery, prospective
from .objective_lock import stamp_export
from .future_bottleneck import CHANGE_TARGET
from .future_manual_review import _private_write

UNKNOWN = 'UNKNOWN'
FORMAT = 'bct-new-precursor-collection-v1'
DEFAULT_SEARCH_ENDPOINT = 'https://www.bing.com/search'
FROZEN = (pd, early_forecast, forecast_discovery, prospective)
HINTS = {'DEMAND': 'firm orders backlog offtake reservation customer CAPEX delivery quantities delivery start end',
         'SUPPLY': 'qualified capacity production commissioning ramp qualification completion available substitute supply'}
LABELS = {'product': r'product', 'specification': r'specification|grade|model|standard',
          'region': r'region|market', 'customer_group': r'customer[ _-]group|customers|buyer',
          'supply_pool': r'supply[ _-]pool|qualified suppliers'}


def hashes():
    return {Path(m.__file__).name: acquisition.digest(Path(m.__file__).read_bytes()) for m in FROZEN}


def put(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    _private_write(path,value)


def read(path):
    return json.loads(Path(path).read_text())


def init(root, manifest):
    """Lock collector cutover to a fresh RSS delta, never to its existing corpus."""
    root = Path(root)
    path = root / 'activation.json'
    if path.exists():
        return read(path)
    exclusions=read(Path(__file__).resolve().parents[2]/'config/precursor-baseline-exclusions.json')
    if exclusions['document_count']!=2000:raise ValueError('frozen corpus exclusion manifest invalid')
    started = manifest['collection_started_at']
    if forecast_discovery.clock(started) > forecast_discovery.clock(acquisition.now()):
        raise ValueError('future collection cutover')
    value = {'format': FORMAT, 'activated_at': acquisition.now(), 'new_document_cutover': started,
             'engine_hashes': hashes(), 'excluded_document_ids': sorted(set(manifest.get('preexisting_document_ids', [])) | set(exclusions['document_ids'])),
             'excluded_urls': sorted(set(manifest.get('preexisting_urls', [])) | set(exclusions['urls'])), 'policy': 'New-only; no baseline body loading, screening or LIVE session creation'}
    put(path, value)
    return value


@contextmanager
def lock(root):
    root = Path(root);root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / '.lock').open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(f, fcntl.LOCK_UN)


def scope_fields(body):
    """Explicit assertions only; multiple values are not merged or guessed.

    Reads both colon labels and source prose such as 'grade is X; market is Y'.
    Entity location, publisher domicile and a search query never fill a field.
    """
    out = {}
    for key, labels in LABELS.items():
        pattern = r'(?im)(?:^|[;\n])\s*(?:'+labels+r')\s*(?::|=|\bis\b|\bare\b)\s*([^;\n]+)'
        matches = list(re.finditer(pattern, body))
        values = {m[1].strip().casefold() for m in matches}
        if len(values) != 1:continue
        m = matches[0];value = m[1].strip()
        if not value or value.casefold()==UNKNOWN.casefold():continue
        start=m.start(1)+len(m[1])-len(m[1].lstrip())
        out[key]={'value':value,'locator':{'start':start,'end':start+len(value)}}
    return out


def structure(document):
    d=deepcopy(document);events=pd.extract_events(d);global_scope=scope_fields(d['body'])
    for e in events:
        e['scope'].update(global_scope)
        # A literal local assertion overrides document context; retain real offsets.
        for k,f in scope_fields(e['source_quote']).items():
            e['scope'][k]={**f,'locator':{q:v+e['locator']['start'] for q,v in f['locator'].items()}}
        if 'product' not in e['scope']:
            anchors=list(CHANGE_TARGET.finditer(e['source_quote']))
            if len(anchors)==1:
                m=anchors[0];value=m['name'].strip()
                start=e['locator']['start']+m.start('name')+len(m['name'])-len(m['name'].lstrip())
                if value and not re.search(r'\b(?:shares|stock|dollars|revenue|cash)\b',value,re.I):
                    e['scope']['product']={'value':value,'locator':{'start':start,'end':start+len(value)}}
        values=pd._validate(d,e)
        e['missing_scope']=[k for k,v in values.items() if v==UNKNOWN]
        window=early_forecast._window(d,e['window']) if e.get('window') else None
        e['future_period']={'start':window['start'],'end':window['end'],'precision':window['precision'],'reference':deepcopy(e['window'])} if window else {'start':UNKNOWN,'end':UNKNOWN}
        # Preserve unsupported exact/relative dates without turning them into years.
        e['raw_period_references']=[{'text':m.group(),'locator':{'start':e['locator']['start']+m.start(),'end':e['locator']['start']+m.end()}}
            for m in re.finditer(r'\b(?:20\d{2}-\d{2}-\d{2}|next year|through 20\d{2}|over the next \d+ months|(?:first|second) half of 20\d{2})\b',e['source_quote'],re.I)]
    d['retained_collection_events']=events
    # Requoted external claims are leads until their actual origin is captured.
    d['precursor_events']=[e for e in events if not re.search(r'\b(?:according to|told|via a syndicated|reported by|provided by|originally published)\b',e['source_quote'],re.I)]
    return d


def stored_documents(root):
    docs=[]
    for path in sorted((Path(root)/'documents').glob('*.json')):
        d=read(path)
        if d.get('provenance')=='PASS':
            if acquisition.digest(d['body'])!=d['body_sha256'] or d['version']!=d['body_sha256']:
                raise ValueError('stored original body/version changed')
            raw=(Path(root)/'raw'/(d['raw_sha256']+'.html')).read_bytes()
            if acquisition.digest(raw)!=d['raw_sha256']:raise ValueError('stored original HTML changed')
            proof=acquisition.verify(raw,d['origin_url'],d['origin_url'],d['acquired_at'])
            fields=('origin_id','origin_url','origin_publisher','published_at','publication_precision','body_sha256','version')
            if proof['provenance']!='PASS' or any(proof[k]!=d[k] for k in fields):
                raise ValueError('stored provenance no longer bound to original HTML')
            docs.append(d)
    return docs


def evidence_plan(documents):
    """Complete side is not reacquired; same-source pairs do not complete a side."""
    prepared=pd.synthesize(stamp_export({'documents':documents,'signals':[]}),mode='LIVE')
    docs={d['document_id']:d for d in documents};requests={};blocked=[]
    source_leads=[e for d in documents for e in d.get('retained_collection_events',d.get('precursor_events',[]))]
    validated_ids={e['event_id'] for e in prepared['retained_precursor_events']}
    for e in source_leads:
        if e['kind']=='CONFIRMATION' or forecast_discovery.PUBLIC_CONFIRMATION.search(docs[e['document_id']]['body']):continue
        values=pd._validate(docs[e['document_id']],e)
        product=values['product']
        if product==UNKNOWN:
            blocked.append({'event_id':e['event_id'],'reason':'PRODUCT_UNKNOWN_NO_TARGETED_QUERY'});continue
        scope_id=forecast_discovery.digest(values)
        matching=[other for other in source_leads if pd._validate(docs[other['document_id']],other)==values]
        independent=[other for other in matching if forecast_discovery.independent(
            {**docs[e['document_id']],'excerpt_sha256':acquisition.digest(e['source_quote'])},
            {**docs[other['document_id']],'excerpt_sha256':acquisition.digest(other['source_quote'])})]
        def future_event(x):
            if not x.get('window'):return False
            w=early_forecast._window(docs[x['document_id']],x['window'])
            return bool(w.get('start') and w['end']>acquisition.now()[:10])
        for role in ('DEMAND','SUPPLY'):
            usable=[x for x in ([e]+independent) if x['role']==role and future_event(x)
                    and x['event_id'] in validated_ids and not x.get('missing_scope') and not forecast_discovery.PUBLIC_CONFIRMATION.search(docs[x['document_id']]['body'])]
            if role=='SUPPLY':usable=[x for x in usable if x.get('pending') or (x.get('qualified') and (x.get('quantity') not in (None,UNKNOWN) or x.get('sufficiency_verified')))]
            if role=='DEMAND':usable=[x for x in usable if x.get('incremental') and x.get('demand_status') in ('COMMITTED','CONFIRMED_PLAN')]
            if usable:continue
            missing=[k for k,v in values.items() if v==UNKNOWN]
            req_id=forecast_discovery.digest([scope_id,role])
            if req_id not in requests:
                hints=' '.join('"'+values[k]+'"' for k in pd.SCOPE if values[k]!=UNKNOWN)
                requests[req_id]={'request_id':req_id,'target':product,'scope':values,'role':role,'query':hints+' '+HINTS[role]+' official',
                     'missing_fields':missing+['future_start_end','independent_original_'+role.lower()],'seed_document_ids':[]}
            requests[req_id]['seed_document_ids']=sorted(set(requests[req_id]['seed_document_ids']+[e['document_id']]))
    # Both sides can exist while exact need/readiness or comparable amounts remain
    # missing. Acquire these fields neutrally; a sufficient/refuted scope is not
    # searched again merely to manufacture a gap.
    for target in prepared['synthesized_targets']:
        missing=target['missing_core_conditions']
        if ('EXPLICIT_FUTURE_TIMING_OR_QUANTITY_TENSION' not in missing
                or any(k in missing for k in ('DEMAND_WITH_FUTURE_WINDOW','SUPPLY_RAMP_WITH_FUTURE_WINDOW','INDEPENDENT_ORIGINS'))
                or any(e.get('sufficiency_verified') or e['kind']=='DEMAND_CHANGE' for e in target['events'])):continue
        for role in ('DEMAND','SUPPLY'):
            scoped=[e for e in target['events'] if e['role']==role]
            # Fully explicit comparable quantity facts are already a resolved
            # comparison, even if they do not show any gap.
            if all(e.get('quantity') not in (None,UNKNOWN) and e.get('unit')!=UNKNOWN and e.get('basis')!=UNKNOWN for e in scoped):continue
            rid=forecast_discovery.digest([target['target_id'],role,'NEED_READINESS_OR_COMPARABLE_QUANTITY'])
            requests[rid]={'request_id':rid,'target':target['scope']['product'],'scope':target['scope'],'role':role,
                'query':' '.join('"'+target['scope'][k]+'"' for k in pd.SCOPE)+' '+HINTS[role]+' official',
                'missing_fields':['explicit_need_or_qualified_readiness_date','comparable_quantity_unit_basis_coverage'],
                'seed_document_ids':sorted({e['document_id'] for e in target['events']})}
    return {'requests':list(requests.values()),'blocked':blocked,'targets':prepared['synthesized_targets']}


def cited_urls(request,documents):
    """One hop, product-specific links only; independent origins preferred."""
    urls=[]
    for d in documents:
        if d['document_id'] not in request['seed_document_ids'] or not d.get('raw_path'):continue
        raw=Path(d['raw_path']).read_bytes()
        if acquisition.digest(raw)!=d['raw_sha256']:raise ValueError('stored original HTML changed')
        parser=acquisition.Metadata();parser.feed(raw.decode('utf-8',errors='replace'))
        for href,label in parser.links:
            url=urljoin(d['origin_url'],href);context=(url+' '+label).casefold()
            if request['target'].casefold() not in context or not re.search(acquisition.WORDS[request['role']],context,re.I):continue
            try:acquisition.public_url(url)
            except ValueError:continue
            if urlsplit(url).hostname==urlsplit(d['origin_url']).hostname:continue
            urls.append(url)
    return list(dict.fromkeys(urls))[:3]


def capture(root,url,document_id,activation,*,collected_at=None):
    root=Path(root);key=acquisition.digest(url);path=root/'captures'/(key+'.json')
    if path.exists():return read(path)
    if document_id in activation['excluded_document_ids'] or url in activation['excluded_urls']:
        return {'status':'EXISTING_CORPUS_EXCLUDED','url':url}
    if collected_at and forecast_discovery.clock(collected_at)<forecast_discovery.clock(activation['new_document_cutover']):
        return {'status':'BEFORE_NEW_COLLECTION_CUTOVER','url':url}
    record={'document_id':document_id,'origin_url':url,'collected_at':collected_at or acquisition.now()}
    try:
        raw,final,status,ctype=acquisition.fetch(url);at=acquisition.now()
        record.update(acquisition.verify(raw,url,final,at,status,ctype))
        raw_path=root/'raw'/(acquisition.digest(raw)+'.html');raw_path.parent.mkdir(parents=True,exist_ok=True)
        if not raw_path.exists():raw_path.write_bytes(raw)
        record['raw_path']=str(raw_path);record['status']='CAPTURED' if record['provenance']=='PASS' else 'PROVENANCE_BLOCKED'
        if record['provenance']=='PASS':
            record=structure(record)
            # Body versions deduplicate before independent origins can be counted.
            dest=root/'documents'/(record['body_sha256']+'.json')
            if dest.exists():record['status']='DUPLICATE_BODY_EXCLUDED'
            else:
                try:put(dest,record)
                except FileExistsError:record['status']='DUPLICATE_BODY_EXCLUDED'
    except Exception as exc:
        record.update(status=acquisition.error_status(exc),error=str(exc),provenance='BLOCKED')
    put(path,record)
    return record


def counters(result,prepared):
    docs={d['document_id']:d for d in prepared['documents']};pairs=[];common=[]
    for target in prepared['synthesized_targets']:
        for de in (e for e in target['events'] if e['role']=='DEMAND' and e.get('incremental') and e.get('demand_status') in ('COMMITTED','CONFIRMED_PLAN')):
            for se in (e for e in target['events'] if e['role']=='SUPPLY'):
                if any(forecast_discovery.PUBLIC_CONFIRMATION.search(docs[e['document_id']]['body']) for e in (de,se)):continue
                origins=[{**docs[e['document_id']],'excerpt_sha256':acquisition.digest(e['source_quote'])} for e in (de,se)]
                if not forecast_discovery.independent(*origins):continue
                pair={'target_id':target['target_id'],'demand_event':de['event_id'],'supply_event':se['event_id']};pairs.append(pair)
                if de.get('window') and se.get('window'):
                    dw=early_forecast._window(docs[de['document_id']],de['window']);sw=early_forecast._window(docs[se['document_id']],se['window'])
                    if dw['start'] and sw['start'] and max(dw['start'],sw['start'])<=min(dw['end'],sw['end']) and min(dw['end'],sw['end'])>acquisition.now()[:10]:common.append(pair)
    return {'scope_complete_events':sum(e['extraction_status']=='SCOPED_EVENT' for e in prepared['retained_precursor_events']),
            'independent_demand_supply_pairs':pairs,'common_future_window_pairs':common,
            'synthesized_targets':len(prepared['synthesized_targets']),'early_preflight':len(result['candidates'])}


def freeze(root,batch,result,stats,store,activation):
    if not result['candidates']:return {'state':'NO_EARLY_CANDIDATE','frozen':0}
    eligible={p['target_id'] for p in stats['common_future_window_pairs']}
    tids=set()
    for candidate in result['candidates']:
        dw,sw=candidate.get('future_demand_window'),candidate.get('known_supply_window')
        if (candidate['target_id'] in eligible and isinstance(dw,dict) and isinstance(sw,dict)
                and dw.get('start') and sw.get('start') and max(dw['start'],sw['start'])<=min(dw['end'],sw['end'])
                and min(dw['end'],sw['end'])>acquisition.now()[:10]):
            tids.add(candidate['target_id'])
    if not tids:return {'state':'NO_COMMON_FUTURE_WINDOW','frozen':0}
    if store is None:return {'state':'EXISTING_LIVE_STORE_NOT_CONFIGURED','frozen':0,'pending_target_ids':sorted(tids)}
    if activation['engine_hashes']!=hashes():raise ValueError('frozen engine hash changed')
    store=Path(store)
    if not (store/'session.json').is_file():raise ValueError('existing LIVE session required; no creation')
    prospective._session(store)
    selected=deepcopy(batch)
    # Source event scope hashes, never topic strings, select compatible new targets.
    for d in selected['documents']:
        d['precursor_events']=[e for e in d['precursor_events'] if UNKNOWN not in (s:=pd._validate(d,e)).values() and pd._target(s)[0] in tids]
    before={str(p):p.read_bytes() for p in store.rglob('*.json')}
    run=prospective.run(store,selected,early=True)
    if any(Path(p).read_bytes()!=raw for p,raw in before.items()):raise RuntimeError('existing LIVE history changed')
    first=[]
    for p in (store/'candidates').glob('*.json'):
        saved=prospective._read(p)
        if saved['target_id'] in tids:first.append({'target_id':saved['target_id'],'path':str(p),'sha256':acquisition.digest(p.read_bytes()),'first_detected_at':saved['candidate_first_detected_at']})
    return {'state':run.get('state',run.get('engine_state')),'frozen':len(first),'first_records':first}


def cycle(root,manifest,*,search_endpoint=None,live_store=None,direct_urls=None,request_limit=100):
    """Every URL is attempted once; errors stay durable and never drain old corpus."""
    if not 1<=request_limit<=100:raise ValueError('request limit must be 1..100')
    with lock(root):
        root=Path(root);activation=init(root,manifest)
        if activation['engine_hashes']!=hashes():raise ValueError('frozen engine hash changed')
        receipt=root/'cycles'/(forecast_discovery.digest(manifest)+'.json')
        if receipt.exists():return read(receipt)
        rows={row['url']:row for row in manifest.get('documents',[])[:100] if row['document_id'] not in manifest.get('preexisting_document_ids',[])}
        with ThreadPoolExecutor(max_workers=6) as pool:
            seeds=list(pool.map(lambda row:capture(root,row['url'],row['document_id'],activation,collected_at=row['collected_at']),rows.values()))
        # Preserve unattempted new seeds durably; next cycle takes the next 100.
        for row in manifest.get('documents',[])[100:]:
            path=root/'seed-queue'/(acquisition.digest(row['url'])+'.json')
            if not path.exists():put(path,row)
        for path in sorted((root/'seed-queue').glob('*.json')):
            if len(seeds)>=100:break
            row=read(path)
            if (root/'captures'/(acquisition.digest(row['url'])+'.json')).exists():continue
            seeds.append(capture(root,row['url'],row['document_id'],activation,collected_at=row['collected_at']))
        docs=stored_documents(root)
        # Absolute raw-cache paths are rebound after artifact relocation, not evidence values.
        for d in docs:d['raw_path']=str(root/'raw'/(d['raw_sha256']+'.html'))
        value=evidence_plan(docs);requests=[];provider_block=None
        for req in value['requests']:
            path=root/'requests'/(req['request_id']+'.json')
            if path.exists():continue
            if len(requests)>=request_limit:break
            urls=cited_urls(req,docs)+list((direct_urls or {}).get(req['request_id'],[]))
            r={**req,'attempted_at':acquisition.now()}
            if search_endpoint and not provider_block:
                try:urls+=acquisition.search(req,search_endpoint);r['search_status']='FINISHED'
                except Exception as exc:
                    r.update(search_status=acquisition.error_status(exc),error=str(exc))
                    if r['search_status'] in ('CONNECT_BLOCKED','SITE_HTTP_BLOCKED'):provider_block=r['search_status']
            else:r['search_status']=provider_block or 'SEARCH_PROVIDER_NOT_CONFIGURED'
            r['urls']=list(dict.fromkeys(urls))[:3]
            r['captures']=[capture(root,url,'new-source-'+acquisition.digest(url),activation) for url in r['urls']]
            # Do not mark an unconfigured search as completed forever: keep it pending without fetching again.
            if r['urls'] or r['search_status']!='SEARCH_PROVIDER_NOT_CONFIGURED':put(path,r)
            else:
                pending=root/'pending'/(req['request_id']+'.json')
                if not pending.exists():put(pending,r)
            requests.append(r)
        docs=stored_documents(root);batch=stamp_export({'mode':'LIVE','precursor_discovery':True,'documents':docs,'signals':[]})
        result,prepared=pd.discover(batch,mode='LIVE');stats=counters(result,prepared)
        execution=freeze(root,batch,result,stats,live_store,activation)
        summary={'format':FORMAT,'completed_at':acquisition.now(),'new_seed_attempts':len(seeds),'new_seed_statuses':{k:sum(s['status']==k for s in seeds) for k in sorted({s['status'] for s in seeds})},
                 'new_verified_documents':len(docs),'requests_this_cycle':len(requests),'scope_blocked_events':len(value['blocked']),
                 **stats,'live_execution':execution,'search_statuses':sorted({r['search_status'] for r in requests}),'existing_corpus_reprocessed':0,'engine_hashes':hashes()}
        summary=stamp_export(summary)
        put(receipt,summary)
        put(root/'evaluations'/(forecast_discovery.digest(summary)+'.json'),{'summary':summary,'batch':batch,'result':result})
        return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--search-endpoint',default=DEFAULT_SEARCH_ENDPOINT);parser.add_argument('--live-store',type=Path)
    args=parser.parse_args();print(json.dumps(cycle(args.state,read(args.manifest),search_endpoint=args.search_endpoint,live_store=args.live_store),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
