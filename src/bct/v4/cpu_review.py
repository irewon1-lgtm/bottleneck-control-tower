"""Source-bound review after verified CPU reading, without semantic promotion.

GLiNER entities remain advisory. A complete, validated read can enter the
existing deterministic event/TARGET/forecast path. This durable attachment is
separate from the sealed manual/AI REVIEW intake and never rewrites its records.
"""
from copy import deepcopy
import json
from pathlib import Path
import re

from bct import precursor_collection as collection, precursor_scope_reader
from bct.objective_lock import require_objective, stamp_export
from .adapters import MODEL, MODEL_REVISION
from .cross_industry import reading_result
from .reading_quality import coverage
from .store import now, sha
from . import official_discovery

KIND = 'CPU_ANALYSIS_RESULT'
FORMAT = 'bct-cpu-source-review-1'
FIELDS = precursor_scope_reader.FIELDS
READ_STATES = {'UNREAD', 'PARTIAL', 'FAILED', 'READ_COMPLETE'}
REVIEW_STATES = {'UNREAD', 'PARTIAL', 'FAILED', 'SOURCE_VERIFICATION_PENDING',
                 'READ_EVIDENCE_HOLD', 'NO_VALIDATED_EVENT', 'RESEARCH_FORECAST_REVIEW'}
REASON_CODES = {'CPU_NOT_READ', 'CPU_READ_INCOMPLETE', 'CPU_WINDOW_VALIDATION_FAILED', 'CPU_CONTEXT_HELD',
                'SOURCE_ORIGINAL_NOT_AVAILABLE', 'SOURCE_VERSION_OR_HASH_MISMATCH', 'SOURCE_PROVENANCE_NOT_VERIFIED',
                'NO_SOURCE_BOUND_EVENT_IN_READ_SCOPE', 'CPU_ENTITY_VALIDATION_REVIEW_PENDING',
                'CPU_ENTITY_ONLY_SEMANTICS_PENDING',
                'TARGET_FIELDS_UNKNOWN', 'QUALIFIED_SUPPLY_SCOPE_UNKNOWN', 'INDEPENDENT_COUNTERPART_NOT_VERIFIED',
                'FORECAST_INPUT_NOT_ELIGIBLE', 'EXISTING_STRICT_FORECAST_CANDIDATE_RESEARCH_ONLY',
                'ANALYSIS_DEPENDENCY_FAILED'}


def _valid_window(doc, task, row):
    """Reject a read receipt whose source, model or actually sent text differs."""
    from .cpu_automation import body_key
    w = task['window']; a, b = w['start'], w['end']
    if (any(row.get(k) != task.get(k) for k in ('key', 'document_id', 'body_key', 'window'))
            or task['document_id'] != doc['document_id'] or task['body_key'] != body_key(doc)
            or task['key'] != sha([task['body_key'], w]) or row['status'] != 'REVIEW_PENDING'
            or type(a) is not int or type(b) is not int or not 0 <= a < b <= len(doc['body'])
            or w['text'] != doc['body'][a:b] or row.get('actually_read_characters') != b-a):
        raise ValueError('CPU_WINDOW_SOURCE_BINDING_MISMATCH')
    cpu = deepcopy(row['CPU'])
    if (cpu.get('model'), cpu.get('revision')) != (MODEL, MODEL_REVISION):
        raise ValueError('CPU_MODEL_OR_REVISION_MISMATCH')
    restored = row.get('restored_receipt_not_new_inference') is True
    if restored:
        # hydrate() already checked the old window input/span hashes against
        # this exact native version. This validation view is not new inference.
        cpu.setdefault('status', 'PASS'); cpu.setdefault('selected_windows', [w])
    if cpu.get('status') not in ('PASS', 'PARTIAL_REVIEW') or cpu.get('selected_windows') != [w]:
        raise ValueError('CPU_TRANSMITTED_WINDOW_MISMATCH')
    if cpu.get('input_sha256') is not None and cpu['input_sha256'] != sha([w]):
        raise ValueError('CPU_INPUT_HASH_MISMATCH')
    for span in cpu.get('spans', []):
        loc = span['locator']
        if span.get('document_id') != doc['document_id'] or not a <= loc['start'] < loc['end'] <= b:
            raise ValueError('CPU_SPAN_OUTSIDE_READ_SOURCE')
    reading_result(doc, cpu)  # Reuse exact existing span/quantity/source guards.
    return cpu, restored


def analyze_document(doc, queued, results, *, raw, as_of=None, related_documents=()):
    """Analyze only this bound document; at most three explicit counterpart inputs.

    Unread/failed/held ranges never become a zero-event or zero-pair conclusion.
    Original CPU receipts are retained by the caller independently of this stage.
    """
    if len(related_documents) > 3: raise ValueError('CPU_ANALYSIS_COUNTERPART_CAP_3')
    evaluated_at = as_of or now()
    tasks = queued.get('tasks', []); keys = {t['key'] for t in tasks}
    matching = [r for r in results if r.get('key') in keys]
    rows = {r['key']: r for r in matching}
    valid = []; failures = []; cpu_values = []; restored = 0
    body = doc.get('body', '')
    for task in tasks:
        row = rows.get(task['key'])
        if row is None: continue
        try:
            cpu, old = _valid_window(doc, task, row)
            valid.append(task['window']); cpu_values.append(cpu); restored += old
        except (ValueError, KeyError, TypeError, AttributeError): failures.append(task['key'])
    cov = coverage(body, valid)
    unread_nonwhite = sum(len(re.sub(r'\s', '', body[r['start']:r['end']])) for r in cov['unread_ranges'])
    pending = len(tasks)-len(valid)-len(failures)
    read_state = ('FAILED' if failures else 'PARTIAL' if valid and (pending or unread_nonwhite or queued.get('held_ranges'))
                  else 'UNREAD' if not valid else 'READ_COMPLETE')
    rejected = sum(len(c.get('rejected_spans', [])) for c in cpu_values)
    result = {'format': FORMAT, 'document_id': doc['document_id'], 'body_sha256': doc['body_sha256'],
              'raw_sha256': doc.get('raw_sha256'), 'source_version': doc.get('version') or doc['body_sha256'],
              'model': MODEL, 'revision': MODEL_REVISION, 'body_key': queued['body_key'],
              'window_keys': sorted(keys), 'window_result_sha256': sorted(sha(r) for r in matching),
              'CPU_windows_total': len(tasks), 'CPU_windows_success': len(valid), 'CPU_windows_failed': len(failures),
              'CPU_windows_unread': pending, 'restored_success_windows': restored,
              'new_inference_windows': len(valid)-restored,
              'actually_read_characters': sum(min(max(r.get('actually_read_characters', 0), 0),
                                                   r['window']['end']-r['window']['start']) for r in matching),
              'validated_read_characters': cov['read_characters'], 'body_characters': len(body),
              'unread_nonwhitespace_characters': unread_nonwhite, 'read_ranges': cov['read_ranges'],
              'held_range_count': len(queued.get('held_ranges', [])), 'read_state': read_state,
              'review_state': read_state, 'reason_code': 'CPU_WINDOW_VALIDATION_FAILED' if failures else
                  'CPU_CONTEXT_HELD' if queued.get('held_ranges') else 'CPU_READ_INCOMPLETE' if valid else 'CPU_NOT_READ',
              'source_validation': 'NOT_VERIFIED', 'target_review_performed': False,
              'missing_fields': [], 'source_bound_event_count': None, 'complete_target_events': None,
              'graph_independent_pair_count': None, 'strict_pair_count': None, 'strict_forecast_candidate_count': None,
              'CPU_advisory_product_count': sum(s.get('label') == 'product' for c in cpu_values for s in c.get('spans', [])),
              'CPU_rejected_span_count': rejected, 'event_traces': [], 'pair_traces': [],
              'semantic_review_status': 'PENDING_ATTRIBUTED_REVIEW', 'forecast_mode': 'BACKFILL_RESEARCH',
              'analysis_implementation_sha256': sha(Path(__file__).read_bytes()),
              'dependency_sha256': {name: sha(Path(module.__file__).read_bytes()) for name, module in
                  (('collection', collection), ('scope_reader', precursor_scope_reader),
                   ('graph', official_discovery.graph), ('forecast', official_discovery.forecast),
                   ('official_adapter', official_discovery))},
              'scope_reader_version': precursor_scope_reader.VERSION, 'evaluated_at': evaluated_at,
              'S2': 0, 'S3': 0, 'LIVE_writes': 0}
    native_hash = sha(bytes(raw)) if raw is not None else None
    if raw is None:
        result.update(review_state='SOURCE_VERIFICATION_PENDING', reason_code='SOURCE_ORIGINAL_NOT_AVAILABLE')
    elif (native_hash != doc.get('raw_sha256') or sha(body.encode()) != doc['body_sha256']
          or doc.get('version', doc['body_sha256']) != doc['body_sha256']):
        result.update(review_state='SOURCE_VERIFICATION_PENDING', reason_code='SOURCE_VERSION_OR_HASH_MISMATCH')
    elif (doc.get('provenance') != 'PASS' or doc.get('provenance_verified') is not True
          or not doc.get('checks') or not all(v is True for v in doc['checks'].values())):
        result.update(review_state='SOURCE_VERIFICATION_PENDING', reason_code='SOURCE_PROVENANCE_NOT_VERIFIED')
    else:
        result['source_validation'] = 'EXACT_NATIVE_AND_BODY_HASHES'
        if read_state == 'READ_COMPLETE':
            try:
                structured = collection.structure(doc)
                documents = [structured, *[collection.structure(d) for d in related_documents]]
                q3 = official_discovery.q3_input([], [], as_of=evaluated_at, documents=documents)
                events = structured['precursor_events']
                event_ids = {e['event_id'] for e in events}
                def involves_current(pair):
                    return bool(event_ids & {pair.get('demand_event'), pair.get('supply_event')})
                pair_traces = [p for p in q3['graph_pair_diagnostics'] if involves_current(p)]
                strict_pairs = [p for p in q3['strict_pair_diagnostics'] if involves_current(p)]
                candidates = [p for p in q3['strict_candidate_diagnostics'] if event_ids & set(p['event_ids'])]
                pair_blocks = [p for p in q3['graph_pair_blocks'] if involves_current(p)]
                blocks = {r['event_id']: r for r in q3['graph_blocked_events'] if r.get('event_id')}
                traces = []
                for event in events:
                    block = blocks.get(event['event_id'], {})
                    traces.append({'event_id': event['event_id'], 'document_id': doc['document_id'],
                        'body_sha256': doc['body_sha256'], 'role': event['role'], 'kind': event['kind'],
                        'locator': event['locator'], 'source_quote_sha256': sha(event['source_quote'].encode()),
                        'first_blocker': block.get('first_blocker', block.get('reason')),
                        'missing_fields': block.get('missing_fields', []),
                        'secondary_missing_fields': block.get('secondary_missing_fields', [])})
                missing = [f for f in FIELDS if any(f in t['missing_fields'] for t in traces)]
                state, reason = 'READ_EVIDENCE_HOLD', 'FORECAST_INPUT_NOT_ELIGIBLE'
                if candidates: state, reason = 'RESEARCH_FORECAST_REVIEW', 'EXISTING_STRICT_FORECAST_CANDIDATE_RESEARCH_ONLY'
                elif missing: reason = 'TARGET_FIELDS_UNKNOWN'
                elif pair_blocks: reason = 'QUALIFIED_SUPPLY_SCOPE_UNKNOWN'
                elif not events and rejected: reason = 'CPU_ENTITY_VALIDATION_REVIEW_PENDING'
                elif not events and result['CPU_advisory_product_count']: reason = 'CPU_ENTITY_ONLY_SEMANTICS_PENDING'
                elif not events: state, reason = 'NO_VALIDATED_EVENT', 'NO_SOURCE_BOUND_EVENT_IN_READ_SCOPE'
                elif not pair_traces: reason = 'INDEPENDENT_COUNTERPART_NOT_VERIFIED'
                result.update(review_state=state, reason_code=reason, target_review_performed=True,
                    missing_fields=missing, source_bound_event_count=len(events),
                    complete_target_events=len(event_ids & set(q3['graph_complete_event_ids'])),
                    graph_independent_pair_count=len(pair_traces), strict_pair_count=len(strict_pairs),
                    strict_forecast_candidate_count=len(candidates), event_traces=traces, pair_traces=pair_traces)
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                result.update(review_state='FAILED', reason_code='ANALYSIS_DEPENDENCY_FAILED',
                              analysis_error_type=type(error).__name__)
    if failures:
        result.update(review_state='FAILED', reason_code='CPU_WINDOW_VALIDATION_FAILED')
    identity = [FORMAT, doc['document_id'], doc['body_sha256'], doc.get('raw_sha256'), queued['body_key'],
                result['window_result_sha256'], result['analysis_implementation_sha256'], native_hash,
                [(d['document_id'], d['body_sha256']) for d in related_documents]]
    result['input_binding_sha256'] = sha(identity)
    result = stamp_export(result)
    result['id'] = 'cpu-analysis-'+sha({k: v for k, v in result.items() if k != 'evaluated_at'})
    validate_receipt(result)
    return result


def validate_receipt(value):
    """Source-separated persistence contract; no source text may enter it."""
    require_objective(value)
    allowed = {'format', 'id', 'document_id', 'body_sha256', 'raw_sha256', 'source_version', 'model', 'revision', 'body_key',
        'window_keys', 'window_result_sha256', 'CPU_windows_total', 'CPU_windows_success', 'CPU_windows_failed',
        'CPU_windows_unread', 'restored_success_windows', 'new_inference_windows', 'actually_read_characters',
        'validated_read_characters', 'body_characters', 'unread_nonwhitespace_characters', 'read_ranges', 'held_range_count',
        'read_state', 'review_state', 'reason_code', 'source_validation', 'target_review_performed', 'missing_fields',
        'source_bound_event_count', 'complete_target_events', 'graph_independent_pair_count', 'strict_pair_count',
        'strict_forecast_candidate_count', 'CPU_advisory_product_count', 'CPU_rejected_span_count', 'event_traces',
        'pair_traces', 'semantic_review_status', 'forecast_mode', 'analysis_implementation_sha256', 'dependency_sha256',
        'scope_reader_version', 'evaluated_at', 'S2', 'S3', 'LIVE_writes', 'input_binding_sha256', 'analysis_error_type',
        'objective_version', 'objective_sha256', 'delivery'}
    if set(value)-allowed: raise ValueError('CPU_ANALYSIS_FIELDS_NOT_ALLOWED')
    if value.get('id') != 'cpu-analysis-'+sha({k: v for k, v in value.items() if k not in ('id', 'evaluated_at', 'delivery')}):
        raise ValueError('CPU_ANALYSIS_RECEIPT_HASH_MISMATCH')
    if value.get('format') != FORMAT or value.get('read_state') not in READ_STATES or value.get('review_state') not in REVIEW_STATES:
        raise ValueError('CPU_ANALYSIS_STATE_INVALID')
    if value.get('reason_code') not in REASON_CODES or set(value.get('missing_fields', []))-set(FIELDS):
        raise ValueError('CPU_ANALYSIS_REASON_INVALID')
    if value.get('model') != MODEL or value.get('revision') != MODEL_REVISION or value.get('S2') != 0 or value.get('S3') != 0:
        raise ValueError('CPU_ANALYSIS_PROMOTION_FORBIDDEN')
    if value.get('semantic_review_status') != 'PENDING_ATTRIBUTED_REVIEW': raise ValueError('CPU_ENTITY_IS_NOT_SEMANTIC_COMPLETION')
    counts = [value[k] for k in ('CPU_windows_total', 'CPU_windows_success', 'CPU_windows_failed', 'CPU_windows_unread')]
    if any(type(n) is not int or n < 0 for n in counts) or counts[0] != sum(counts[1:]):
        raise ValueError('CPU_ANALYSIS_WINDOW_COUNTS_INVALID')
    if (len(value['window_keys']) != counts[0] or len(value['window_result_sha256']) > counts[0]
            or value['restored_success_windows']+value['new_inference_windows'] != counts[1]):
        raise ValueError('CPU_ANALYSIS_WINDOW_IDENTITY_INVALID')
    if value['read_state'] == 'READ_COMPLETE' and (not counts[0] or counts[1] != counts[0]
            or value['unread_nonwhitespace_characters'] or value['held_range_count']):
        raise ValueError('CPU_ANALYSIS_INCOMPLETE_READ')
    if value['target_review_performed'] and (value['read_state'] != 'READ_COMPLETE'
            or value['source_validation'] != 'EXACT_NATIVE_AND_BODY_HASHES'):
        raise ValueError('CPU_ANALYSIS_REVIEW_WITHOUT_VERIFIED_READ')
    if not value['target_review_performed'] and any(value[k] is not None for k in
            ('strict_pair_count', 'strict_forecast_candidate_count', 'source_bound_event_count')):
        raise ValueError('CPU_ANALYSIS_UNREAD_IS_NOT_ZERO_RESULT')
    for field in ('body_sha256', 'raw_sha256', 'source_version', 'body_key', 'analysis_implementation_sha256', 'input_binding_sha256'):
        if not isinstance(value.get(field), str) or not re.fullmatch('[0-9a-f]{64}', value[field]):
            raise ValueError('CPU_ANALYSIS_SOURCE_HASH_INVALID')
    for field in ('source_bound_event_count', 'complete_target_events', 'graph_independent_pair_count',
                  'strict_pair_count', 'strict_forecast_candidate_count'):
        if value[field] is not None and (type(value[field]) is not int or value[field] < 0):
            raise ValueError('CPU_ANALYSIS_REVIEW_COUNTS_INVALID')
    for field in ('window_keys', 'window_result_sha256'):
        if any(not isinstance(v, str) or not re.fullmatch('[0-9a-f]{64}', v) for v in value[field]):
            raise ValueError('CPU_ANALYSIS_WINDOW_HASH_INVALID')
    forbidden = {'body', 'raw', 'text', 'quote', 'source_quote', 'selected_windows', 'raw_windows', 'context_before', 'context_after'}
    def walk(item):
        if isinstance(item, dict):
            if forbidden.intersection(item): raise ValueError('CPU_ANALYSIS_SOURCE_TEXT_FORBIDDEN')
            for child in item.values(): walk(child)
        elif isinstance(item, list):
            for child in item: walk(child)
    walk(value)
    return True


def record_analysis(ledger, doc, *, as_of=None, related_documents=()):
    """Append one immutable versioned attachment; never update old REVIEW files."""
    from .cpu_automation import body_key
    key = body_key(doc)
    queued_rows = [json.loads(p) for p, in ledger.db.execute(
        "SELECT payload FROM events WHERE kind='CPU_QUEUE_DOCUMENT' AND json_extract(payload,'$.body_key')=? ORDER BY seq", (key,))]
    if len(queued_rows) != 1: raise ValueError('CPU_ANALYSIS_QUEUE_BINDING_NOT_UNIQUE')
    rows = [json.loads(p) for p, in ledger.db.execute(
        "SELECT payload FROM events WHERE kind='CPU_QUEUE_WINDOW_RESULT' AND json_extract(payload,'$.body_key')=? ORDER BY seq", (key,))]
    native = ledger.db.execute('SELECT b.data FROM documents d JOIN blobs b ON b.id=d.raw_id WHERE d.id=?', (doc['document_id'],)).fetchone()
    result = analyze_document(doc, queued_rows[0], rows, raw=native[0] if native else None,
                              as_of=as_of, related_documents=related_documents)
    existing = ledger.db.execute("SELECT payload FROM events WHERE kind=? AND json_extract(payload,'$.id')=?", (KIND, result['id'])).fetchone()
    if existing: return {**json.loads(existing[0]), 'delivery': 'DUPLICATE'}
    ledger.event(KIND, result)
    return {**result, 'delivery': 'NEW_ANALYSIS'}
