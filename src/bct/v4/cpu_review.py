"""Source-bound review after verified CPU reading, without semantic promotion.

GLiNER entities remain advisory. A complete, validated read can enter the
existing deterministic event/TARGET/forecast path. This durable attachment is
separate from the sealed manual/AI REVIEW intake and never rewrites its records.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from bct import precursor_scope_reader
from bct.objective_lock import require_objective, stamp_export
from .cpu_resume import MODEL, REVISION as MODEL_REVISION
from .store import now, sha

KIND = 'CPU_ANALYSIS_RESULT'
FORMAT = 'bct-cpu-source-review-1'
FIELDS = precursor_scope_reader.FIELDS
READ_STATES = {'UNREAD', 'PARTIAL', 'FAILED', 'READ_COMPLETE'}
REVIEW_STATES = {'UNREAD', 'PARTIAL', 'FAILED', 'SOURCE_VERIFICATION_PENDING',
                 'READ_EVIDENCE_HOLD', 'NO_VALIDATED_EVENT', 'RESEARCH_FORECAST_REVIEW', 'GRAPH_CONTEXT_PENDING'}
REASON_CODES = {'CPU_NOT_READ', 'CPU_READ_INCOMPLETE', 'CPU_WINDOW_VALIDATION_FAILED', 'CPU_CONTEXT_HELD',
                'SOURCE_ORIGINAL_NOT_AVAILABLE', 'SOURCE_VERSION_OR_HASH_MISMATCH', 'SOURCE_PROVENANCE_NOT_VERIFIED',
                'NO_SOURCE_BOUND_EVENT_IN_READ_SCOPE', 'CPU_ENTITY_VALIDATION_REVIEW_PENDING',
                'CPU_ENTITY_ONLY_SEMANTICS_PENDING',
                'TARGET_FIELDS_UNKNOWN', 'QUALIFIED_SUPPLY_SCOPE_UNKNOWN', 'INDEPENDENT_COUNTERPART_NOT_VERIFIED',
                'FORECAST_INPUT_NOT_ELIGIBLE', 'EXISTING_STRICT_FORECAST_CANDIDATE_RESEARCH_ONLY',
                'ANALYSIS_DEPENDENCY_FAILED', 'GRAPH_CONTEXT_UNAVAILABLE', 'GRAPH_CONTEXT_LIMIT_EXCEEDED',
                'GRAPH_CONTEXT_VERSION_MISMATCH'}
MAX_GRAPH_CONTEXT_BYTES = 128 * 1024**2


def _known_producer(value):
    return (isinstance(value, dict) and set(value) == {'run_id', 'run_attempt', 'execution_sha', 'workflow_sha'}
            and all(type(value[k]) is int and value[k] > 0 for k in ('run_id', 'run_attempt'))
            and all(isinstance(value[k], str) and re.fullmatch('[0-9a-f]{40}', value[k])
                    for k in ('execution_sha', 'workflow_sha')))


def load_graph_context(cache, manifest, doc):
    """Load exact producer-selected graph dependencies; never choose a top three.

    The receiver already bound the literal bundle manifest to its input artifact.
    This boundary verifies its per-root file/version relationships again. Missing
    old conflicts or relief sources cannot be silently treated as no counterpart.
    """
    proof = {'state': 'PENDING', 'reason_code': 'GRAPH_CONTEXT_UNAVAILABLE',
             'required_source_count': None, 'verified_source_count': 0, 'source_bindings': []}
    if cache is None or not isinstance(manifest, dict): return [], proof
    proof['manifest_sha256'] = sha(manifest)
    if manifest.get('format') != 'bct-cpu-source-delta-1' or manifest.get('graph_context_complete') is not True:
        return [], proof
    root = doc['document_id']; required = manifest.get('required_graph_sources', [])
    try:
        if not isinstance(required, list) or not isinstance(manifest.get('documents'), list):
            raise ValueError('CONTEXT_SCHEMA')
        required = [r for r in required if root in r.get('root_document_ids', [])]
        if any((r.get('body_sha256'), r.get('raw_sha256'), r.get('origin_url')) !=
               (doc['body_sha256'], doc['raw_sha256'], doc.get('origin_url'))
               for r in required if r.get('document_id') == root):
            raise ValueError('CONTEXT_ROOT_VERSION')
        unavailable = manifest.get('unavailable_graph_sources', [])
        if any(not r.get('root_document_ids') or root in r['root_document_ids'] for r in unavailable):
            return [], proof
        contexts = [r for r in required if r['document_id'] != root]
        proof['required_source_count'] = len(contexts)
        if len(contexts) > 3:
            return [], {**proof, 'reason_code': 'GRAPH_CONTEXT_LIMIT_EXCEEDED'}
        identities = [(r['document_id'], r['body_sha256'], r['raw_sha256']) for r in contexts]
        if len(set(identities)) != len(identities) or len({r[0] for r in identities}) != len(identities):
            raise ValueError('CONTEXT_VERSION_AMBIGUOUS')
        entries = manifest['documents']; cache = Path(cache)
        if cache.is_symlink(): raise ValueError('CONTEXT_PATH')
        budget = 0
        def read_member(name, *, family, metadata=False):
            nonlocal budget
            if (not isinstance(name, str) or '\\' in name or PurePosixPath(name).is_absolute()
                    or len(name.split('/')) != 2 or name.split('/')[0] != family
                    or name.split('/')[1] in ('', '.', '..')):
                raise ValueError('CONTEXT_PATH')
            path = cache/name
            if (cache/family).is_symlink() or path.is_symlink() or not path.is_file():
                raise ValueError('CONTEXT_PATH')
            spec = manifest['files'][name]; size = path.stat().st_size; budget += size
            if budget > MAX_GRAPH_CONTEXT_BYTES: raise OverflowError('CONTEXT_LIMIT')
            if type(spec.get('bytes')) is not int or size != spec['bytes']:
                raise ValueError('CONTEXT_SIZE')
            with path.open('rb') as stream:
                if metadata:
                    value = stream.read(size+1); digest = hashlib.sha256(value).hexdigest()
                    if len(value) != size: raise ValueError('CONTEXT_SIZE')
                else:
                    value = None; digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != spec['sha256']: raise ValueError('CONTEXT_HASH')
            return value, digest
        def load(identity):
            hits = [r for r in entries if (r.get('document_id'), r.get('body_sha256'), r.get('raw_sha256')) == identity]
            if len(hits) != 1: raise ValueError('CONTEXT_METADATA_AMBIGUOUS')
            entry = hits[0]
            if entry.get('source_kind') not in ('RSS', 'ACQUISITION_OPPOSITE', 'GRAPH_CONTEXT'):
                raise ValueError('CONTEXT_SOURCE_KIND')
            if identity[0] != root and root not in entry.get('root_document_ids', []):
                raise ValueError('CONTEXT_ROOT_RELATION')
            data, metadata_hash = read_member(entry['document_member'], family='documents', metadata=True)
            if metadata_hash != entry['metadata_sha256']: raise ValueError('CONTEXT_METADATA_HASH')
            value = json.loads(data)
            if ((value.get('document_id'), value.get('body_sha256'), value.get('raw_sha256')) != identity
                    or value.get('origin_url') != entry.get('origin_url')
                    or sha(value['body'].encode()) != identity[1] or value.get('version', identity[1]) != identity[1]
                    or value.get('provenance') != 'PASS' or value.get('provenance_verified') is not True
                    or not value.get('checks') or not all(v is True for v in value['checks'].values())
                    or any(value.get(k) for k in ('confidential', 'personal_data', 'api_transfer_forbidden'))):
                raise ValueError('CONTEXT_SOURCE_BINDING')
            _, native_hash = read_member(entry['native_member'], family='raw')
            if native_hash != identity[2] or not entry['native_member'].split('/')[1].startswith(identity[2]+'.'):
                raise ValueError('CONTEXT_NATIVE_HASH')
            proof['source_bindings'].append({'document_id': identity[0], 'body_sha256': identity[1],
                'raw_sha256': identity[2], 'metadata_sha256': metadata_hash})
            return value
        original = load((root, doc['body_sha256'], doc['raw_sha256']))
        if original['body'] != doc['body'] or original.get('origin_url') != doc.get('origin_url'):
            raise ValueError('CONTEXT_ROOT_BINDING')
        related = [load(identity) for identity in identities]
        if any(value.get('origin_url') != required_row.get('origin_url')
               for value, required_row in zip(related, contexts)):
            raise ValueError('CONTEXT_ORIGIN_BINDING')
        proof.update(state='COMPLETE', reason_code=None, verified_source_count=len(related))
        return related, proof
    except OverflowError:
        return [], {**proof, 'reason_code': 'GRAPH_CONTEXT_LIMIT_EXCEEDED'}
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        return [], {**proof, 'reason_code': 'GRAPH_CONTEXT_VERSION_MISMATCH'}


def _valid_window(doc, task, row):
    """Reject a read receipt whose source, model or actually sent text differs."""
    from .cpu_automation import body_key
    from .cross_industry import reading_result
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


def analyze_document(doc, queued, results, *, raw, as_of=None, related_documents=(), graph_context=None):
    """Analyze only this bound document; at most three explicit counterpart inputs.

    Unread/failed/held ranges never become a zero-event or zero-pair conclusion.
    Original CPU receipts are retained by the caller independently of this stage.
    """
    from bct import precursor_collection as collection
    from . import official_discovery
    from .reading_quality import coverage
    if len(related_documents) > 3: raise ValueError('CPU_ANALYSIS_COUNTERPART_CAP_3')
    evaluated_at = as_of or now()
    tasks = queued.get('tasks', []); keys = {t['key'] for t in tasks}
    matching = [r for r in results if r.get('key') in keys]
    rows = {r['key']: r for r in matching}
    valid = []; failures = []; cpu_values = []; producers = []; restored = 0
    body = doc.get('body', '')
    for task in tasks:
        row = rows.get(task['key'])
        if row is None: continue
        try:
            cpu, old = _valid_window(doc, task, row)
            valid.append(task['window']); cpu_values.append(cpu); restored += old
            producers.append(row.get('inference_producer'))
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
              'model_read_producer': deepcopy(producers[0]) if producers and all(
                  _known_producer(p) and p == producers[0] for p in producers) else None,
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
              'graph_context': graph_context or {'state': 'EXPLICIT_INPUTS', 'reason_code': None,
                  'required_source_count': len(related_documents), 'verified_source_count': len(related_documents), 'source_bindings': []},
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
        if read_state == 'READ_COMPLETE' and result['graph_context']['state'] == 'PENDING':
            result.update(review_state='GRAPH_CONTEXT_PENDING', reason_code=result['graph_context']['reason_code'])
        elif read_state == 'READ_COMPLETE':
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
        'objective_version', 'objective_sha256', 'delivery', 'graph_context', 'derived_reuse_binding_sha256',
        'model_read_producer'}
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
    if value.get('model_read_producer') is not None and not _known_producer(value['model_read_producer']):
        raise ValueError('CPU_ANALYSIS_MODEL_PRODUCER_INVALID')
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
    pointer = value.get('derived_reuse_binding_sha256')
    if pointer is not None and (not isinstance(pointer, str) or not re.fullmatch('[0-9a-f]{64}', pointer)):
        raise ValueError('CPU_ANALYSIS_REUSE_POINTER_INVALID')
    forbidden = {'body', 'raw', 'text', 'quote', 'source_quote', 'selected_windows', 'raw_windows', 'context_before', 'context_after'}
    def walk(item):
        if isinstance(item, dict):
            if forbidden.intersection(item): raise ValueError('CPU_ANALYSIS_SOURCE_TEXT_FORBIDDEN')
            for child in item.values(): walk(child)
        elif isinstance(item, list):
            for child in item: walk(child)
    walk(value)
    return True


def record_analysis(ledger, doc, *, as_of=None, related_documents=(), cache=None, input_manifest=None):
    """Append one immutable versioned attachment; never update old REVIEW files."""
    from .cpu_automation import body_key
    key = body_key(doc)
    queued_rows = [json.loads(p) for p, in ledger.db.execute(
        "SELECT payload FROM events WHERE kind='CPU_QUEUE_DOCUMENT' AND json_extract(payload,'$.body_key')=? AND json_extract(payload,'$.document_id')=? ORDER BY seq", (key, doc['document_id']))]
    if len(queued_rows) != 1: raise ValueError('CPU_ANALYSIS_QUEUE_BINDING_NOT_UNIQUE')
    rows = [json.loads(p) for p, in ledger.db.execute(
        "SELECT payload FROM events WHERE kind='CPU_QUEUE_WINDOW_RESULT' AND json_extract(payload,'$.body_key')=? AND json_extract(payload,'$.document_id')=? ORDER BY seq", (key, doc['document_id']))]
    pointers = {r['derived_reuse_binding_sha256'] for r in rows if r.get('derived_reuse_binding_sha256')}
    pointer = None
    if pointers:
        from .cpu_resume import validate_reuse_binding
        if len(pointers) != 1: raise ValueError('CPU_ANALYSIS_REUSE_BINDING_AMBIGUOUS')
        pointer = next(iter(pointers))
        bindings = [json.loads(p) for p, in ledger.db.execute("SELECT payload FROM events WHERE kind='CPU_INPUT_REUSE_BINDING'")]
        bindings = [b for b in bindings if sha(b) == pointer]
        if len(bindings) != 1: raise ValueError('CPU_ANALYSIS_REUSE_BINDING_MISSING')
        binding = bindings[0]; validate_reuse_binding(binding)
        if any(binding.get(k) != v for k, v in {'document_id': doc['document_id'], 'body_sha256': doc['body_sha256'],
                'raw_sha256': doc['raw_sha256'], 'body_key': key, 'model': MODEL, 'revision': MODEL_REVISION}.items()):
            raise ValueError('CPU_ANALYSIS_REUSE_SOURCE_MISMATCH')
        proof = {w['key']: w for w in binding['windows']}
        if set(proof) != {t['key'] for t in queued_rows[0]['tasks']}: raise ValueError('CPU_ANALYSIS_REUSE_WINDOWS_MISMATCH')
        for row in rows:
            w = proof.get(row['key'], {})
            if (row.get('derived_reuse_binding_sha256') != pointer or row.get('restored_receipt_not_new_inference') is not True
                    or row.get('original_record_sha256') != w.get('original_record_sha256')
                    or row.get('verified_window_input_sha256') != w.get('input_sha256')
                    or sha(row['window']['text'].encode()) != w.get('input_sha256')):
                raise ValueError('CPU_ANALYSIS_REUSE_WINDOW_PROOF_MISMATCH')
    native = ledger.db.execute('SELECT b.data FROM documents d JOIN blobs b ON b.id=d.raw_id WHERE d.id=?', (doc['document_id'],)).fetchone()
    if cache is not None or input_manifest is not None or not related_documents:
        related_documents, context = load_graph_context(cache, input_manifest, doc)
    else:
        context = {'state': 'EXPLICIT_INPUTS', 'reason_code': None, 'required_source_count': len(related_documents),
                   'verified_source_count': len(related_documents), 'source_bindings': []}
    result = analyze_document(doc, queued_rows[0], rows, raw=native[0] if native else None,
                              as_of=as_of, related_documents=related_documents, graph_context=context)
    if pointer is not None:
        result['derived_reuse_binding_sha256'] = pointer
        result['id'] = 'cpu-analysis-'+sha({k: v for k, v in result.items() if k not in ('id', 'evaluated_at')})
        validate_receipt(result)
    existing = ledger.db.execute("SELECT payload FROM events WHERE kind=? AND json_extract(payload,'$.id')=?", (KIND, result['id'])).fetchone()
    if existing: return {**json.loads(existing[0]), 'delivery': 'DUPLICATE'}
    ledger.event(KIND, result)
    return {**result, 'delivery': 'NEW_ANALYSIS'}
