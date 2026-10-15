"""Opt-in CPU research consumer of existing RSS/body artifacts, never a collector.

Append-only per-window commits, one worker, no AI client, no LIVE/firsts writes.
"""
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
import time

from bct.objective_lock import stamp_export
from .adapters import CPUExtractor, MODEL, MODEL_REVISION
from .cross_industry import reading_result, common_evidence
from .evidence_path import reference
from .free_ai import source_input, APIError
from .reading_quality import coverage
from .store import Ledger, now, sha

VERSION = 'bct-cpu-research-queue-1'


def open_queue(root):
    path = Path(root) / 'v4.sqlite3'
    if path.exists():
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as db:
            try:
                marker = db.execute("SELECT value FROM metadata WHERE key='cpu_queue_format'").fetchone()
            except sqlite3.DatabaseError:
                marker = None
            if marker != (VERSION,):
                raise ValueError('REFUSE_EXISTING_NON_QUEUE_DATABASE')
    ledger = Ledger(root)
    with ledger.db:
        ledger.db.execute("INSERT OR IGNORE INTO metadata VALUES('cpu_queue_format',?)", (VERSION,))
    return ledger


def events(ledger, kind):
    return [json.loads(p) for p, in ledger.db.execute('SELECT payload FROM events WHERE kind=? ORDER BY seq', (kind,))]


def plan(doc):
    # Same strict public-input safety gate, with no outbound transfer. A valid
    # article is not necessarily official primary evidence for event adoption.
    source_input(doc, {'max_input_characters':600, 'max_windows':4}, {})
    body = doc['body']
    from .public_input import LINK, COUNTER
    groups, current = [], []
    for p in re.finditer(r'[^\n]+', body):
        linked = LINK.search(p[0].strip()) or COUNTER.search(p[0]) or re.match(
            r'^(?:this|these|it|its|they|their|the (?:order|contract|agreement|system|facility))\b', p[0].strip(), re.I)
        if current and not linked:
            groups.append(current); current = []
        current.append(p)
    if current: groups.append(current)
    windows, held = [], []
    for group in groups:
        a,b = group[0].start(),group[-1].end()
        item = {'start':a, 'end':b, 'text':body[a:b]}
        if b-a > 1800:
            held.append({'start':a, 'end':b, 'reason':'WHOLE_LINKED_CONTEXT_EXCEEDS_CPU1800'})
        else:
            windows.append(item)
    return windows, held


def body_key(doc):
    return sha([doc['origin_url'], doc['body_sha256'], MODEL, MODEL_REVISION, VERSION])


def enqueue(ledger, doc, raw, upstream):
    if sha(raw) != doc['raw_sha256'] or sha(doc['body'].encode()) != doc['body_sha256']:
        raise ValueError('NATIVE_OR_BODY_HASH_MISMATCH')
    if not doc.get('published_at') or doc.get('provenance') != 'PASS' or doc.get('provenance_verified') is not True:
        raise ValueError('SOURCE_PUBLICATION_OR_PROVENANCE_HELD')
    pub = datetime.fromisoformat(doc['published_at'].replace('Z','+00:00'))
    acquired = datetime.fromisoformat(doc['acquired_at'].replace('Z','+00:00'))
    if pub.date() > acquired.date(): raise ValueError('PUBLICATION_AFTER_ACQUISITION')
    from bct.future_body import extract_document
    if extract_document(raw.decode('utf-8',errors='replace')).get('body')!=doc['body']:
        raise ValueError('NATIVE_TO_BODY_MISMATCH')
    # Retain the existing extractor's source/identity/check contract; do not
    # silently mark media as official, or re-fetch a URL already captured.
    if not doc.get('checks') or not all(v is True for v in doc['checks'].values()):
        raise ValueError('EXISTING_SOURCE_CHECK_NOT_PASS')
    existing = ledger.db.execute('SELECT payload FROM documents WHERE id=?',(doc['document_id'],)).fetchone()
    if existing and any(json.loads(existing[0]).get(k)!=doc.get(k) for k in ('origin_url','body_sha256','raw_sha256')):
        raise ValueError('DOCUMENT_ID_COLLISION')
    windows, held = plan(doc)
    key = body_key(doc)
    known = any(x['body_key']==key for x in events(ledger, 'CPU_QUEUE_DOCUMENT'))
    new_version = not ledger.db.execute('SELECT 1 FROM documents WHERE id=?',(doc['document_id'],)).fetchone()
    if new_version: ledger.capture(doc, raw)
    if known:
        if new_version:
            with ledger.db: ledger.event('CPU_QUEUE_SAME_BODY_VERSION',{'body_key':key,'document_id':doc['document_id'],'raw_sha256':doc['raw_sha256']})
        return 'UNCHANGED_BODY_ALREADY_QUEUED'
    tasks = [{ 'key':sha([key,w]), 'document_id':doc['document_id'], 'body_key':key, 'window':w} for w in windows]
    with ledger.db:
        ledger.event('CPU_QUEUE_DOCUMENT', {'body_key':key,'document_id':doc['document_id'],
            'body_sha256':doc['body_sha256'], 'tasks':tasks, 'held_ranges':held,
            'upstream':upstream, 'at':now(), 'state':'PENDING' if tasks else 'HELD_CONTEXT',
            'primary_source_verified':doc.get('primary_source_verified') is True})
    return 'QUEUED'


def ingest_delta(ledger, manifest, cache, *, upstream_run_id, reconsider_held=False):
    """Read only existing canonical delta + native cache; never fetch RSS/URLs."""
    if manifest.get('format') != 'bct-new-rss-delta-v1': raise ValueError('RSS_DELTA_CONTRACT')
    cache = Path(cache).resolve()
    # Index metadata once; select only the delta, never the whole cached backlog.
    index = {}
    for p in sorted((cache/'documents').glob('*.json')):
        try:
            d = json.loads(p.read_text())
            index.setdefault((d.get('document_id'),d.get('origin_url')), []).append((p,d))
        except (OSError,ValueError,TypeError,AttributeError):
            # A damaged cached file does not block another source. Its missing
            # delta item will receive a per-document hold below; no refetch.
            continue
    states = []
    known = {x['item_key']:x for x in events(ledger,'CPU_QUEUE_IMPORT')}
    for item in manifest['documents']:
        key = sha([upstream_run_id,item['document_id'],item['url']])
        previous = known.get(key)
        hits = index.get((item['document_id'],item['url']), [])
        changed = len(hits)==1 and sha(hits[0][0].read_bytes())!= (previous or {}).get('cache_document_sha256')
        if previous and not (reconsider_held and previous['status']=='HELD_ISOLATED' and changed):
            states.append({'document_id':item['document_id'],'status':'ALREADY_IMPORTED'}); continue
        receipt = {'item_key':key,'document_id':item['document_id'],'url':item['url'],
                   'upstream_run_id':str(upstream_run_id),'at':now()}
        try:
            hits = index.get((item['document_id'],item['url']), [])
            if not hits: raise ValueError('UPSTREAM_BODY_NOT_AVAILABLE_NO_REFETCH')
            if len(hits)!=1: raise ValueError('UPSTREAM_VERSION_AMBIGUOUS')
            p,doc = hits[0]
            receipt['cache_document_sha256'] = sha(p.read_bytes())
            if previous: receipt['reconsidered_after_new_cache_evidence'] = True
            # Raw path from an artifact may refer to its old runner. Resolve
            # only a basename below raw/, never follow arbitrary artifact paths.
            filename = Path(doc['raw_path']).name
            if not filename.startswith(doc['raw_sha256']+'.'): raise ValueError('RAW_PATH_HASH_IDENTITY')
            rawpath = (cache/'raw'/filename).resolve()
            if not rawpath.is_relative_to(cache/'raw'): raise ValueError('RAW_PATH_ESCAPE')
            receipt['status'] = enqueue(ledger, doc, rawpath.read_bytes(),
                {'run_id':str(upstream_run_id),'manifest_item_sha256':sha(item),
                 'cache_document_sha256':sha(p.read_bytes())})
        except (ValueError,KeyError,TypeError,OSError,APIError) as exc:
            receipt.update(status='HELD_ISOLATED', reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__)
        with ledger.db: ledger.event('CPU_QUEUE_IMPORT',receipt)
        states.append(receipt)
    return states


def seed_completed(ledger, legacy_path):
    """Reuse exact historical receipts; never call the old 1,210-window worker."""
    path = Path(legacy_path).resolve()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("SELECT value FROM metadata WHERE key='format'").fetchone() != ('bct-v4-ledger-1',):
            raise ValueError('LEGACY_LEDGER_FORMAT')
        docs = {k:json.loads(p) for k,p in db.execute('SELECT id,payload FROM documents')}
        rows = [json.loads(p) for p, in db.execute("SELECT payload FROM events WHERE kind='CPU_WINDOW_RESULT' ORDER BY seq")]
    old = {x['body_key'] for x in events(ledger,'CPU_QUEUE_LEGACY_COMPLETE')}
    done = {}
    for r in rows:
        if r['status'] not in ('PASS','PARTIAL_REVIEW'): continue
        cpu = r.get('CPU',{})
        if cpu.get('model') != MODEL or cpu.get('revision') != MODEL_REVISION: continue
        d = docs[r['document_id']]; w = r['window']
        reference(d, {**w,'quote':w['text']})
        done.setdefault(d['document_id'],[]).append(w)
    added = 0
    for did,windows in done.items():
        doc = docs[did]; key = body_key(doc); scope = coverage(doc['body'],windows)
        nonwhite = sum(len(doc['body'][r['start']:r['end']].strip()) for r in scope['unread_ranges'])
        if nonwhite or key in old: continue
        with ledger.db: ledger.event('CPU_QUEUE_LEGACY_COMPLETE',{'body_key':key,'document_id':did,
            'source_ledger':str(path),'source_body_sha256':doc['body_sha256'],'windows':len(windows),
            'receipt_sha256':sha([r for r in rows if r['document_id']==did]),'coverage':scope})
        added += 1
    return added


def state(ledger):
    docs = events(ledger,'CPU_QUEUE_DOCUMENT')
    completed = {x['key']:x for x in events(ledger,'CPU_QUEUE_WINDOW_RESULT')}
    legacy = {x['body_key'] for x in events(ledger,'CPU_QUEUE_LEGACY_COMPLETE')}
    tasks = [t for d in docs if d['body_key'] not in legacy for t in d['tasks']]
    pending = [t for t in tasks if t['key'] not in completed]
    imports = list({x['item_key']:x for x in events(ledger,'CPU_QUEUE_IMPORT')}.values())
    coverage_rows = []
    for item in docs:
        doc = json.loads(ledger.db.execute('SELECT payload FROM documents WHERE id=?',(item['document_id'],)).fetchone()[0])
        read = [t['window'] for t in item['tasks'] if t['key'] in completed and completed[t['key']]['actually_read_characters']>0]
        cov = coverage(doc['body'],read)
        pending_count = sum(t['key'] not in completed for t in item['tasks'])
        failed_count = sum(completed[t['key']]['status']=='FAILED_ISOLATED' for t in item['tasks'] if t['key'] in completed)
        processing_state = 'PENDING_CPU' if pending_count else 'FAILED_ISOLATED' if failed_count else 'HELD_CONTEXT' if item['held_ranges'] else 'REVIEW_PENDING'
        coverage_rows.append({'document_id':doc['document_id'],'processing_state':processing_state,**cov,
            'unread_nonwhitespace_characters':sum(len(re.sub(r'\s','',doc['body'][g['start']:g['end']])) for g in cov['unread_ranges']),
            'held_ranges':item['held_ranges']})
    return {'documents':len(docs),'tasks':len(tasks),'pending_windows':len(pending),
        'completed_windows':len(tasks)-len(pending),
        'coverage':coverage_rows,
        'actually_read_characters':sum(c['read_characters'] for c in coverage_rows),
        'body_characters':sum(c['body_characters'] for c in coverage_rows),
        'CPU_product_proposals':sum(sum(v['label']=='product' for v in r.get('CPU',{}).get('spans',[])) for r in completed.values()),
        'validated_events':0,'automatic_S1_S2_S3':[0,0,0],
        'failed_windows':sum(x['status']=='FAILED_ISOLATED' for x in completed.values()),
        'isolated_imports':sum(x['status']=='HELD_ISOLATED' for x in imports),
        'legacy_documents_reused':len(legacy),
        'oldest_pending_at':min((d['at'] for d in docs if any(t['key'] not in completed for t in d['tasks']) and d['body_key'] not in legacy),default=None),
        'scheduled':'NOT_RUN_DISABLED','AI_reader':'DISABLED','candidate_promotion':'DISABLED','LIVE_registration':'DISABLED'}


def work(ledger, *, extractor=None, max_windows=24, seconds=45):
    if type(max_windows) is not int or not 1<=max_windows<=24 or not 1<=seconds<=60:
        raise ValueError('CPU_BUDGET_WINDOW24_SECONDS60')
    start,cpu_start = time.monotonic(),time.process_time()
    before = state(ledger); done = {x['key']:x for x in events(ledger,'CPU_QUEUE_WINDOW_RESULT')}
    legacy = {x['body_key'] for x in events(ledger,'CPU_QUEUE_LEGACY_COMPLETE')}
    queues = [[t for t in d['tasks'] if t['key'] not in done] for d in events(ledger,'CPU_QUEUE_DOCUMENT') if d['body_key'] not in legacy]
    tasks = [q[i] for i in range(max(map(len,queues),default=0)) for q in queues if i<len(q)]
    # Lazy CPUExtractor: no data/only cached windows -> no model initialization.
    extractor = extractor or CPUExtractor('var/v4/repair/cpu/runtime')
    outputs = []
    for task in tasks[:max_windows]:
        if time.monotonic()-start >= seconds: break
        doc = json.loads(ledger.db.execute('SELECT payload FROM documents WHERE id=?',(task['document_id'],)).fetchone()[0])
        with ledger.db: ledger.event('CPU_QUEUE_WINDOW_ATTEMPT',{**task,'at':now()})
        clock = time.monotonic(); cc = time.process_time()
        reading = None
        input_read = False
        try:
            reading = extractor.extract_windows(doc,[task['window']],diagnostic=True)
            if reading['status'] not in ('PASS','PARTIAL_REVIEW'): raise ValueError('CPU_READING_NOT_COMPLETE')
            if reading['model']!=MODEL or reading['revision']!=MODEL_REVISION or reading['selected_windows']!=[task['window']]:
                raise ValueError('CPU_MODEL_OR_WINDOW_MISMATCH')
            input_read = True
            # Reuse exact original validation + advisory-only masking.
            result = reading_result(doc,reading)
            output = {**task,'status':'REVIEW_PENDING','CPU':reading,'result':result,
                      'actually_read_characters':len(task['window']['text']), 'at':now()}
        except Exception as exc:
            output = {**task,'status':'FAILED_ISOLATED','reason':type(exc).__name__,
                      'actually_read_characters':len(task['window']['text']) if input_read else 0,'at':now()}
            if reading is not None: output['CPU_original_rejected_by_validation'] = reading
        output.update(wall_seconds=time.monotonic()-clock,cpu_seconds=time.process_time()-cc)
        # One atomic commit for receipt + raw reading + common UI records.
        with ledger.db:
            ledger.event('CPU_QUEUE_WINDOW_RESULT',output)
            if reading is not None:
                retained = reading if output['status']=='REVIEW_PENDING' else {'CPU_original':reading,'validation_status':'FAILED_ISOLATED'}
                ledger.db.execute('INSERT OR IGNORE INTO readings VALUES(?,?,?)',
                    (sha([task['key'],retained]),doc['document_id'],json.dumps(retained,ensure_ascii=False)))
            if output['status']=='REVIEW_PENDING':
                for record in result['records']:
                    ledger.event('CROSS_COMMON_EVIDENCE',common_evidence(record,doc,'CPU_QUEUE_DISCOVERY_NOT_VALIDATED_FACT'))
            outputs.append(output)
    # Checkpoint committed windows only. Interruption after an attempt can re-run
    # only that uncommitted local CPU window; never completed windows or an API.
    after = state(ledger)
    if not outputs: return {'new_windows':0,'model_loaded':False,'before':before,'after':after,'API_calls':0}
    run_id = 'cpu-queue-'+sha([o['key'] for o in outputs])
    result = stamp_export({'version':VERSION,'run_id':run_id,'scope':'RESEARCH_ONLY_NO_LIVE',
        'new_windows':len(outputs),'actually_read_characters':sum(o['actually_read_characters'] for o in outputs),
        'CPU_reading':{'windows':len(outputs)},'before':before,'after':after,
        'wall_seconds':time.monotonic()-start,'CPU_seconds':time.process_time()-cpu_start,
        'API_calls':0,'API_tokens':0,'API_cost_KRW':0,'candidates':[],
        'validated_events':0,'S1':0,'S2':0,'S3':0,'promotion_enabled':False})
    return ledger.save_run(run_id,result,'RESEARCH_CPU')
