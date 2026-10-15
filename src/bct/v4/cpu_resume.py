"""Source-separated CPU state. Derived research is not a restored original.

Native pages and verbatim contexts never enter this derivative. Exact bodies are
required again for reference replay; stored hashes are not evidence validation.
No collector, inference, stage rule, credential or scheduler lives here.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

from .store import Ledger, sha, file_sha
from .evidence_path import reference

FORMAT = 'bct-source-separated-cpu-1'
QUEUE = 'bct-cpu-research-queue-1'
MODEL = 'fastino/gliner2-base-v1'
REVISION = 'f9634218e53580c56edf0de97ca1a7d3f1c2354e'
LABELS = {'product','specification','industry','subindustry','location','customer','supplier','quantity','date'}
SAFE_KINDS = {'CPU_RESUME_SOURCE','CPU_RESUME_WINDOW','CPU_RESUME_REVIEW','CPU_RESUME_RUN',
              'CPU_RESUME_MANIFEST','CPU_QUEUE_LEGACY_COMPLETE','CPU_QUEUE_IMPORT','CROSS_COMMON_EVIDENCE','CPU_OPERATION_OBSERVATION'}


def rows(db, kind):
    return [json.loads(p) for p, in db.execute('SELECT payload FROM events WHERE kind=? ORDER BY seq', (kind,))]


def key(doc):
    return sha([doc['origin_url'],doc['body_sha256'],MODEL,REVISION,QUEUE])


def url(value):
    p=urlsplit(value)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ValueError('RESUME_URL_NOT_CLEAN')
    return value


def short(value):
    if not isinstance(value,str) or len(value)>120 or len(value.split())>12 or '\n'in value or '@'in value:
        return None
    if re.search(r'ghp_|github_pat_|gsk_|Bearer |-----BEGIN|\b\d{3}[- .]\d{3}[- .]\d{4}\b',value):
        return None
    return value


def bounds(w):
    return {k:w[k] for k in ('start','end')}


def field_ref(ref):
    result={**{k:ref[k] for k in ('document_id','body_sha256','start','end','published_at','acquired_at') if k in ref},
            'quote_sha256':ref.get('quote_sha256',sha(ref.get('quote','').encode())),'source_validation':'SOURCE_VERIFICATION_PENDING'}
    if ref.get('origin_url'):
        try:result['origin_url']=url(ref['origin_url'])
        except ValueError:result['origin_url_sha256']=sha(ref['origin_url'])
    return result


def historical_fact(value):
    """Keep structured judgments, not their narrative/quote serialization."""
    if value is None or type(value)in(int,float,bool):return value
    if isinstance(value,str):
        return value if short(value)is not None else {'withheld_value_sha256':sha(value)}
    if isinstance(value,dict):
        if 'quote'in value:return field_ref(value)
        allowed={'product','specification','region','customer_group','supply_pool','period','quantity','unit',
                 'surface','value','normalized','reference','status','kind','precision','need_time','ready_time',
                 'customer_need_period','physical_quantity','start','end'}
        return {k:historical_fact(v)for k,v in value.items()if k in allowed}
    if isinstance(value,list):return [historical_fact(v)for v in value]
    raise ValueError('UNSUPPORTED_HISTORICAL_FACT_TYPE')


def summarize_window(row, doc):
    w=row['window'];reference(doc,{**w,'quote':w['text']})
    cpu=row['CPU']
    if (cpu.get('model'),cpu.get('revision'))!=(MODEL,REVISION):
        raise ValueError('RESUME_MODEL_VERSION_MISMATCH')
    spans=[]
    for span in cpu.get('spans',[]):
        if span.get('label')not in LABELS:raise ValueError('RESUME_UNREVIEWED_SPAN_TYPE')
        locator=span['locator'];a,b=locator['start'],locator['end']
        reference(doc,{'start':a,'end':b,'quote':span['text']})
        value=short(span['text'])
        spans.append({'label':span['label'],'surface':value,'surface_sha256':sha(span['text'].encode()),
            'surface_withheld':value is None,'confidence':span.get('confidence'),**bounds(locator),
            'semantic_status':span.get('semantic_status','UNKNOWN')})
    return {'key':row['key'],'document_id':doc['document_id'],'body_key':key(doc),
        'source_body_sha256':doc['body_sha256'],'model':MODEL,'revision':REVISION,
        'window':{**bounds(w),'input_sha256':sha(w['text'].encode())},
        'original_record_sha256':sha(row),'original_status':row['status'],
        'actually_read_characters':row.get('actually_read_characters',row.get('actually_model_read_characters',0)),
        'input_sha256':cpu.get('input_sha256'),'CPU_spans':spans,
        'source_validation':'SOURCE_VERIFICATION_PENDING','was_located_before_separation':True}


def source_record(doc, tasks, completed):
    if sha(doc['body'].encode())!=doc['body_sha256']:raise ValueError('RESUME_BODY_HASH_MISMATCH')
    ranges=sorted((t['window']['start'],t['window']['end']) for t in tasks if t['key']in completed)
    covered=set()
    for a,b in ranges:covered.update(range(a,b))
    unread_nonwhite=sum(not c.isspace() and i not in covered for i,c in enumerate(doc['body']))
    return {'document_id':doc['document_id'],'origin_url':url(doc['origin_url']),
        'body_key':key(doc),'body_sha256':doc['body_sha256'],'raw_sha256':doc.get('raw_sha256'),
        'published_at':doc.get('published_at'),'acquired_at':doc.get('acquired_at'),
        'body_characters':len(doc['body']),'model':MODEL,'revision':REVISION,'queue_version':QUEUE,
        'tasks':[{'key':t['key'],'window':{**bounds(t['window']),'input_sha256':sha(t['window']['text'].encode())}} for t in tasks],
        'read_characters':len(covered),'unread_nonwhitespace_characters':unread_nonwhite,
        'complete':unread_nonwhite==0 and all(t['key']in completed for t in tasks),
        'source_state':'WITHHELD_NOT_RESTORED','source_validation':'SOURCE_VERIFICATION_PENDING'}


def export_state(source, destination, *, legacy=None):
    source=Path(source).resolve();destination=Path(destination)
    if destination.exists():raise ValueError('REFUSE_RESUME_OVERWRITE')
    before=file_sha(source)
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)as db:
        if db.execute("SELECT value FROM metadata WHERE key='cpu_queue_format'").fetchone()!=(QUEUE,):
            raise ValueError('RESUME_SOURCE_NOT_CPU_QUEUE')
        # Retain earlier detached history, never repeatedly infer from it.
        preserved=[(k,json.loads(p))for k,p in db.execute('SELECT kind,payload FROM events ORDER BY seq')
                   if k in SAFE_KINDS and (k.startswith('CPU_RESUME_') or k in ('CPU_QUEUE_LEGACY_COMPLETE','CPU_OPERATION_OBSERVATION'))]
        docs={k:json.loads(p)for k,p in db.execute('SELECT id,payload FROM documents')}
        queued=rows(db,'CPU_QUEUE_DOCUMENT');results=rows(db,'CPU_QUEUE_WINDOW_RESULT')
        imports=rows(db,'CPU_QUEUE_IMPORT')
        common=rows(db,'CROSS_COMMON_EVIDENCE')
        runs=[{'id':k,'mode':m,'payload_sha256':sha(json.loads(p)),
               'counts':{n:v for n,v in json.loads(p).items()if type(v)in(int,float,bool) or v is None}}
              for k,m,p in db.execute('SELECT id,mode,payload FROM runs')]
    if legacy:
        with sqlite3.connect(Path(legacy).resolve().as_uri()+'?mode=ro',uri=True)as old:
            old_docs={k:json.loads(p)for k,p in old.execute('SELECT id,payload FROM documents')}
            old_rows=rows(old,'CPU_WINDOW_RESULT')
            allowed={r['document_id']for k,r in preserved if k=='CPU_QUEUE_LEGACY_COMPLETE'}
            for did in sorted(allowed):
                rr=[r for r in old_rows if r['document_id']==did]
                results.extend(rr)
                docs[did]=old_docs[did]
                queued.append({'document_id':did,'tasks':[{'key':r['key'],'window':r['window']}for r in rr]})
            for k,p in old.execute("SELECT kind,payload FROM events WHERE kind IN ('RECOVERY_EXISTING_REVIEWED_EVENT_PRESERVED','RECOVERY_NEW_SOURCE_REPORTED_EVENT_REVIEW')"):
                r=json.loads(p)
                info={n:r[n] for n in ('id','review_id','product','role','actuality','event_status','s_stage','verdict','source_document_id','independent_accuracy_verified','new_independent_performance','references_rechecked')
                      if n in r and (type(r[n])in(int,float,bool) or r[n]is None or short(r[n])is not None)}
                original=r.get('original_review',{})
                info['original_judgment']={n:v for n,v in original.items()if n in (
                    'actuality_in_original','role_in_original','actuality','role','verdict','source_event_id',
                    'original_record_id','review_id','independent_pair','no_new_S_promotions','human_verified',
                    'independent','total_qualified_supply','customer_need_period','need_time','physical_quantity')
                    and (type(v)in(int,float,bool) or v is None or short(v)is not None)}
                refs=original.get('references',r.get('references',[]))
                info['references']=[field_ref(ref)for ref in refs if isinstance(ref,dict)]
                info['original_fields_sha256']=sha(original.get('fields_in_original',original.get('fields',{})))
                info['historical_target']=historical_fact(original.get('target_in_original',{}))
                info['historical_fields']=historical_fact(original.get('fields_in_original',original.get('fields',{})))
                preserved.append(('CPU_RESUME_REVIEW',{'original_kind':k,'original_sha256':sha(r),'historical_fields':info,
                    'source_validation':'SOURCE_VERIFICATION_PENDING','active_stage':'UNKNOWN'}))
    done={r['key']:r for r in results if r['status']in ('REVIEW_PENDING','PASS','PARTIAL_REVIEW')}
    # Existing safe window receipts count as done after rehydration/restart.
    for kind,row in preserved:
        if kind=='CPU_RESUME_WINDOW':done.setdefault(row['key'],row)
    out=Ledger(destination)
    def emit(kind,value):
        digest=sha([kind,value])
        if digest not in emitted:
            out.event(kind,value);emitted.add(digest)
    emitted=set()
    try:
        with out.db:
            out.db.execute("INSERT INTO metadata VALUES('cpu_queue_format',?)",(QUEUE,))
            out.db.execute("INSERT INTO metadata VALUES('cpu_source_separated_format',?)",(FORMAT,))
            for kind,value in preserved:
                value=deepcopy(value);value.pop('source_ledger',None)
                emit(kind,value)
            completed_keys={v['body_key']for k,v in preserved if k=='CPU_QUEUE_LEGACY_COMPLETE'}
            for item in queued:
                doc=docs[item['document_id']];record=source_record(doc,item['tasks'],done)
                emit('CPU_RESUME_SOURCE',record)
                if record['complete'] and record['body_key'] not in completed_keys:
                    emit('CPU_QUEUE_LEGACY_COMPLETE',{'body_key':record['body_key'],'document_id':doc['document_id'],
                        'source_body_sha256':doc['body_sha256'],'windows':len(item['tasks']),
                        'receipt_sha256':sha([done[t['key']]for t in item['tasks']]),'source_state':'WITHHELD_NOT_RESTORED'})
                    completed_keys.add(record['body_key'])
            for row in results:
                if row['key']in done:emit('CPU_RESUME_WINDOW',summarize_window(row,docs[row['document_id']]))
                else:emit('CPU_RESUME_REVIEW',{'original_kind':'UNCOMPLETED_CPU_WINDOW','original_sha256':sha(row),
                    'historical_fields':{'key':row['key'],'status':row['status']},'source_validation':'SOURCE_VERIFICATION_PENDING'})
            for r in imports:
                receipt={k:r[k]for k in ('item_key','document_id','upstream_run_id','at','status','cache_document_sha256','storage_review_sha256')if k in r}
                if r.get('url'):
                    try:receipt['url']=url(r['url'])
                    except ValueError:receipt.update(url_sha256=sha(r['url']),url_withheld=True)
                if r.get('reason'):
                    receipt['reason_sha256']=sha(r['reason'])
                    if re.fullmatch('[A-Z][A-Z0-9_]{1,100}',r['reason']):receipt['reason']=r['reason']
                emit('CPU_QUEUE_IMPORT',receipt)
            for r in common:
                r=deepcopy(r)
                # Preserve existing UI schema, but NOT original quotes/contexts.
                r['references']=[field_ref(ref)for ref in r['references']]
                r['fields']={};r['meaning_status']='SOURCE_VERIFICATION_PENDING'
                r['event_status']='DISCOVERY_ONLY';r['s_stage']='UNKNOWN'
                for target in ('target','source_surface_target'):
                    r[target]={k:short(v)if v is not None else None for k,v in r[target].items()}
                r['sources']=[{k:(url(v)if k in ('url','origin_id')and isinstance(v,str)and v.startswith('https:')else v)
                    for k,v in s.items()if k in ('document_id','url','origin_id','published_at','acquired_at','raw_sha256','body_sha256')}for s in r['sources']]
                emit('CROSS_COMMON_EVIDENCE',r)
            for r in runs:emit('CPU_RESUME_RUN',r)
            emit('CPU_RESUME_MANIFEST',{'version':FORMAT,'source_sqlite_sha256':before,
                'source_raw_bodies_copied':0,'originals_retained':True,'original_DB_fully_restored':False,
                'original_text_required_for_reference_replay':True})
        assert file_sha(source)==before
        return summary(out)
    finally:out.close()


def latest_sources(ledger):
    return {r['body_key']:r for r in rows(ledger.db,'CPU_RESUME_SOURCE')}


def completed(ledger, doc):
    if 'body'not in doc or sha(doc['body'].encode())!=doc.get('body_sha256'):return False
    return any(x['body_key']==key(doc) for x in rows(ledger.db,'CPU_QUEUE_LEGACY_COMPLETE'))


def planned_read(ledger,doc):
    if 'body'not in doc or sha(doc['body'].encode())!=doc.get('body_sha256'):return False
    source=latest_sources(ledger).get(key(doc))
    done={r['key']for r in rows(ledger.db,'CPU_RESUME_WINDOW')}
    return bool(source and source['tasks'] and all(t['key']in done for t in source['tasks']))


def summary(ledger):
    windows={r['key']:r for r in rows(ledger.db,'CPU_RESUME_WINDOW')}
    spans=[s for r in windows.values()for s in r['CPU_spans']]
    sources=latest_sources(ledger)
    return {'format':FORMAT,'detached_sources':len(sources),'completed_body_keys':len({r['body_key']for r in rows(ledger.db,'CPU_QUEUE_LEGACY_COMPLETE')}),
        'CPU_windows_preserved':len(windows),'CPU_spans_preserved':len(spans),
        'CPU_product_proposals_preserved':sum(s['label']=='product'for s in spans),
        'surfaces_withheld':sum(s['surface_withheld']for s in spans),
        'historical_reviews_preserved':len(rows(ledger.db,'CPU_RESUME_REVIEW')),
        'pending_source_replay':len(windows),'partial_documents':sum(not s['complete']for s in sources.values()),
        'awaiting_source_windows':sum(t['key']not in windows for s in sources.values() if not s['complete']for t in s['tasks']),
        'unread_nonwhitespace_characters':sum(s['unread_nonwhitespace_characters']for s in sources.values()),
        'raw_bodies_present':ledger.db.execute('SELECT count(*)FROM documents').fetchone()[0],
        'original_DB_fully_restored':False,'automatic_stage_promotion':False}


def verify(ledger, document_id, ref, *, doc=None):
    known=[s for s in latest_sources(ledger).values()if s['document_id']==document_id]
    if len(known)!=1:raise ValueError('RESUME_SOURCE_IDENTITY_AMBIGUOUS')
    source=known[0]
    if doc is None:return {'status':'HELD_SOURCE_WITHHELD','evidence_validated_now':False}
    if (doc.get('document_id')!=document_id or doc.get('origin_url')!=source['origin_url']
            or doc.get('raw_sha256')!=source['raw_sha256'] or doc.get('body_sha256')!=source['body_sha256']
            or sha(doc.get('body','').encode())!=source['body_sha256']):
        raise ValueError('RESUME_REPLAY_SOURCE_HASH_MISMATCH')
    reference(doc,ref)
    return {'status':'PASS_EXACT_SOURCE_REFERENCE','evidence_validated_now':True}


def transient_allowed(doc, policy):
    r=policy.get('sources',{}).get(doc['document_id'],{})
    if r.get('transient_CPU_read')=='FORBIDDEN':return False
    generic=policy.get('source_separated_transient',{})
    if (generic.get('status')=='PERMITTED_PUBLIC_VERIFIED_LOCAL_ONLY' and generic.get('format')==FORMAT
            and doc.get('provenance')=='PASS' and doc.get('provenance_verified')is True
            and doc.get('checks') and all(v is True for v in doc['checks'].values())
            and not any(doc.get(k)for k in ('confidential','personal_data','api_transfer_forbidden'))):
        return True  # Local reading and BCT facts only; never raw archival permission.
    return (r.get('raw_sha256')==doc.get('raw_sha256') and r.get('body_sha256')==doc.get('body_sha256')
        and r.get('transient_CPU_read')=='PERMITTED' and r.get('derived_state_storage')=='PERMITTED'
        and r.get('privacy_review')=='CLEARED' and bool(r.get('rights_basis')) and bool(r.get('reviewed_by')))


def hydrate(ledger, cache, policy):
    """Only partial sources need input again; exact hashes or safe hold, no fetch."""
    from . import cpu_automation as q
    cache=Path(cache).resolve();result=[]
    complete={v['body_key']for v in rows(ledger.db,'CPU_QUEUE_LEGACY_COMPLETE')}
    known=latest_sources(ledger)
    old={r['key']:r for r in rows(ledger.db,'CPU_RESUME_WINDOW')}
    for bk,source in known.items():
        if bk in complete:continue
        if source['tasks'] and all(t['key']in old for t in source['tasks']):
            result.append({'document_id':source['document_id'],'status':'HELD_UNREAD_CONTEXT_NOT_REPROCESSED'});continue
        candidates=[]
        for p in (cache/'documents').glob('*.json'):
            try:
                d=json.loads(p.read_text())
                if d.get('document_id')==source['document_id'] and d.get('body_sha256')==source['body_sha256']:candidates.append(d)
            except (ValueError,OSError):continue
        if len(candidates)!=1:
            result.append({'document_id':source['document_id'],'status':'HELD_SOURCE_MISSING_OR_AMBIGUOUS'});continue
        d=candidates[0]
        if not transient_allowed(d,policy):
            result.append({'document_id':source['document_id'],'status':'HELD_TRANSIENT_REVIEW'});continue
        rawpath=(cache/'raw'/Path(d['raw_path']).name).resolve()
        if not rawpath.is_relative_to(cache/'raw'):
            raise ValueError('RESUME_RAW_PATH_ESCAPE')
        try:
            if d.get('raw_sha256')!=source['raw_sha256']:raise ValueError('RESUME_NATIVE_VERSION_CHANGED')
            q.enqueue(ledger,d,rawpath.read_bytes(),{'resume':'SOURCE_REHYDRATED_BY_EXACT_HASH'})
            item=next(v for v in q.events(ledger,'CPU_QUEUE_DOCUMENT')if v['body_key']==bk)
            present={v['key']for v in q.events(ledger,'CPU_QUEUE_WINDOW_RESULT')}
            with ledger.db:
                for task in item['tasks']:
                    r=old.get(task['key'])
                    if not r or task['key']in present:continue
                    if sha(task['window']['text'].encode())!=r['window']['input_sha256']:
                        raise ValueError('RESUME_WINDOW_INPUT_CHANGED')
                    spans=[]
                    for s in r['CPU_spans']:
                        text=d['body'][s['start']:s['end']]
                        if sha(text.encode())!=s['surface_sha256']:raise ValueError('RESUME_SPAN_HASH_MISMATCH')
                        spans.append({'text':text,'label':s['label'],'locator':bounds(s),
                                      'confidence':s['confidence'],'document_id':d['document_id'],'body_sha256':d['body_sha256']})
                    ledger.event('CPU_QUEUE_WINDOW_RESULT',{**task,'status':'REVIEW_PENDING',
                        'actually_read_characters':r['actually_read_characters'],
                        'CPU':{'model':MODEL,'revision':REVISION,'spans':spans},
                        'restored_receipt_not_new_inference':True})
            result.append({'document_id':source['document_id'],'status':'SOURCE_REHYDRATED_NO_COMPLETED_WINDOW_RERUN'})
        except (OSError,ValueError,KeyError):
            result.append({'document_id':source['document_id'],'status':'HELD_SOURCE_REHYDRATION_FAILED'})
    return result


def audit(ledger):
    if ledger.db.execute("SELECT value FROM metadata WHERE key='cpu_source_separated_format'").fetchone()!=(FORMAT,):
        raise ValueError('SOURCE_SEPARATED_FORMAT_MISSING')
    for table in ('documents','blobs','captures','readings','runs','firsts'):
        if ledger.db.execute(f'SELECT count(*)FROM {table}').fetchone()[0]:
            raise ValueError('SOURCE_OR_ORIGINAL_READING_PRESENT')
    forbidden={'body','raw','text','quote','context_before','context_after','raw_windows','selected_windows','raw_path'}
    def walk(value):
        if isinstance(value,dict):
            if forbidden.intersection(value):raise ValueError('VERBATIM_SOURCE_FIELD_PRESENT')
            for k,v in value.items():
                if k in ('surface','product') and v is not None and short(v)is None:
                    raise ValueError('UNREVIEWED_ENTITY_SURFACE')
                walk(v)
        elif isinstance(value,list):
            for item in value:walk(item)
    for kind,payload in ledger.db.execute('SELECT kind,payload FROM events'):
        if kind not in SAFE_KINDS:raise ValueError('UNKNOWN_SOURCE_SEPARATED_EVENT')
        walk(json.loads(payload))
    return {'status':'PASS_SOURCE_SEPARATED_SCHEMA','original_DB_fully_restored':False,**summary(ledger)}
