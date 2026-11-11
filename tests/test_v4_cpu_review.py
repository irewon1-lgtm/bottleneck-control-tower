"""Synthetic CPU/source transport tests; never live inference performance."""
from copy import deepcopy
import json
import subprocess
import sys

import pytest

from bct.v4 import cpu_automation as queue
from bct.v4.adapters import MODEL, MODEL_REVISION
from bct.v4.store import sha
from test_precursor_source_pipeline import doc
from test_v4_q3_linkage_trace import timing_documents

AS_OF = '2026-10-08T17:30:00+00:00'


def analyzer():
    import importlib.util
    assert importlib.util.find_spec('bct.v4.cpu_review'), 'CPU analysis is not delivered to REVIEW'
    from bct.v4 import cpu_review
    return cpu_review


def source(document=None):
    d = deepcopy(document or doc('Signed firm new orders for tungsten; delivery required in 2028.'))
    raw = ('<html><body><article>'+''.join('<p>'+p+'</p>' for p in d['body'].split('\n'))+'</article></body></html>').encode()
    d.update(raw_sha256=sha(raw), checks={'http_success': True}, version=d['body_sha256'])
    return d, raw


def receipts(d, windows=None):
    windows = windows or [{'start': 0, 'end': len(d['body']), 'text': d['body']}]
    key = queue.body_key(d)
    tasks = [{'key': sha([key, w]), 'body_key': key, 'document_id': d['document_id'], 'window': w} for w in windows]
    results = [{**t, 'status': 'REVIEW_PENDING', 'actually_read_characters': t['window']['end']-t['window']['start'],
                'CPU': {'model': MODEL, 'revision': MODEL_REVISION, 'status': 'PASS',
                        'selected_windows': [t['window']], 'input_sha256': sha([t['window']]), 'spans': []}}
               for t in tasks]
    return {'body_key': key, 'document_id': d['document_id'], 'tasks': tasks, 'held_ranges': []}, results


def test_complete_read_reaches_source_bound_target_hold_without_fake_semantic_completion():
    module = analyzer(); d, raw = source(); planned, results = receipts(d); before = deepcopy((d, results))
    result = module.analyze_document(d, planned, results, raw=raw, as_of=AS_OF)
    assert result['read_state'] == 'READ_COMPLETE' and result['review_state'] == 'READ_EVIDENCE_HOLD'
    assert result['reason_code'] == 'TARGET_FIELDS_UNKNOWN'
    assert result['source_bound_event_count'] == 1
    assert result['missing_fields'] == ['specification', 'region', 'customer_group', 'supply_pool']
    event, = result['event_traces']
    assert event['document_id'] == d['document_id'] and event['body_sha256'] == d['body_sha256']
    assert event['first_blocker'] == 'NO_SOURCE_BOUND_SPECIFICATION'
    assert result['strict_pair_count'] == result['strict_forecast_candidate_count'] == 0
    assert result['semantic_review_status'] == 'PENDING_ATTRIBUTED_REVIEW'
    assert result['S2'] == result['S3'] == 0 and (d, results) == before


def test_valid_complete_read_without_source_event_is_explicit_no_validated_event():
    module = analyzer(); d, raw = source(doc('The company held its annual general meeting.'))
    planned, results = receipts(d)
    result = module.analyze_document(d, planned, results, raw=raw, as_of=AS_OF)
    assert result['review_state'] == 'NO_VALIDATED_EVENT'
    assert result['CPU_windows_success'] == 1 and result['source_bound_event_count'] == 0
    assert result['reason_code'] == 'NO_SOURCE_BOUND_EVENT_IN_READ_SCOPE'
    assert result['strict_pair_count'] == 0
    assert result['semantic_review_status'] == 'PENDING_ATTRIBUTED_REVIEW'


def test_entity_only_read_is_pending_semantics_instead_of_completed_no_event():
    module = analyzer(); d, raw = source(doc('The catalogue lists Xena sampling modules.'))
    planned, results = receipts(d); a = d['body'].index('Xena sampling modules')
    results[0]['CPU']['spans'] = [{'text': 'Xena sampling modules', 'label': 'product',
        'document_id': d['document_id'], 'body_sha256': d['body_sha256'], 'locator': {'start': a, 'end': a+21}}]
    result = module.analyze_document(d, planned, results, raw=raw, as_of=AS_OF)
    assert result['review_state'] == 'READ_EVIDENCE_HOLD'
    assert result['reason_code'] == 'CPU_ENTITY_ONLY_SEMANTICS_PENDING'
    assert result['semantic_review_status'] == 'PENDING_ATTRIBUTED_REVIEW'


def test_unread_and_partial_are_not_evaluated_zero_pairs(monkeypatch):
    module = analyzer(); d, raw = source(doc('First paragraph.\nSigned firm new orders for tungsten in 2028.'))
    cut = d['body'].index('\n')
    windows = [{'start': 0, 'end': cut, 'text': d['body'][:cut]},
               {'start': cut+1, 'end': len(d['body']), 'text': d['body'][cut+1:]}]
    planned, results = receipts(d, windows)
    from bct import precursor_collection as collection
    monkeypatch.setattr(collection, 'structure', lambda *a, **k: pytest.fail('unread body must not be analyzed'))
    for supplied, expected in [([], 'UNREAD'), (results[:1], 'PARTIAL')]:
        result = module.analyze_document(d, planned, supplied, raw=raw, as_of=AS_OF)
        assert result['review_state'] == expected
        assert result['strict_pair_count'] is result['strict_forecast_candidate_count'] is None
        assert result['source_bound_event_count'] is None


@pytest.mark.parametrize('change', ['failed_after_read', 'model', 'window', 'source_version'])
def test_failed_or_mismatched_receipt_is_not_a_read_hold(change):
    module = analyzer(); d, raw = source(); planned, results = receipts(d)
    if change == 'failed_after_read': results[0]['status'] = 'FAILED_ISOLATED'
    elif change == 'model': results[0]['CPU']['revision'] = 'foreign-model-version'
    elif change == 'window': results[0]['CPU']['selected_windows'][0] = {'start': 0, 'end': 1, 'text': d['body'][:1]}
    else: results[0]['body_key'] = 'stale-other-body-key'
    result = module.analyze_document(d, planned, results, raw=raw, as_of=AS_OF)
    assert result['review_state'] == 'FAILED'
    assert result['CPU_windows_success'] == 0 and result['CPU_windows_failed'] == 1
    assert result['strict_pair_count'] is None


def test_missing_native_original_keeps_source_verification_pending():
    module = analyzer(); d, _ = source(); planned, results = receipts(d)
    result = module.analyze_document(d, planned, results, raw=None, as_of=AS_OF)
    assert result['review_state'] == 'SOURCE_VERIFICATION_PENDING'
    assert result['reason_code'] == 'SOURCE_ORIGINAL_NOT_AVAILABLE'
    assert result['strict_pair_count'] is None


def test_conflicting_explicit_body_version_is_not_a_verified_source_review():
    module = analyzer(); d, raw = source(); planned, results = receipts(d)
    d['version'] = 'f'*64
    result = module.analyze_document(d, planned, results, raw=raw, as_of=AS_OF)
    assert result['review_state'] == 'SOURCE_VERIFICATION_PENDING'
    assert result['reason_code'] == 'SOURCE_VERSION_OR_HASH_MISMATCH'
    assert result['source_version'] == d['version'] and result['strict_pair_count'] is None


def test_existing_timing_route_is_reached_with_explicit_independent_original():
    module = analyzer(); buyer, supplier = timing_documents(); d, raw = source(buyer)
    planned, results = receipts(d)
    result = module.analyze_document(d, planned, results, raw=raw, related_documents=[supplier], as_of=AS_OF)
    assert result['strict_pair_count'] == result['strict_forecast_candidate_count'] == 1
    assert result['review_state'] == 'RESEARCH_FORECAST_REVIEW'
    assert result['pair_traces'][0]['comparison_state'] == 'POSSIBLE_TIMING_GAP'
    assert result['S2'] == result['S3'] == 0


def test_unrelated_context_pair_cannot_be_attributed_to_the_read_document():
    module = analyzer(); d, raw = source(doc('The company held its annual general meeting.', 'unrelated-root'))
    planned, results = receipts(d)
    result = module.analyze_document(d, planned, results, raw=raw, related_documents=timing_documents(), as_of=AS_OF)
    assert result['source_bound_event_count'] == 0
    assert result['strict_pair_count'] == result['strict_forecast_candidate_count'] == 0
    assert result['complete_target_events'] == result['graph_independent_pair_count'] == 0
    assert result['review_state'] == 'NO_VALIDATED_EVENT' and not result['pair_traces']


def test_restored_exact_window_is_not_a_new_inference():
    module = analyzer(); d, raw = source(); planned, results = receipts(d)
    results[0]['restored_receipt_not_new_inference'] = True
    results[0]['CPU'] = {k: results[0]['CPU'][k] for k in ('model', 'revision', 'spans')}
    result = module.analyze_document(d, planned, results, raw=raw, as_of=AS_OF)
    assert result['CPU_windows_success'] == result['restored_success_windows'] == 1
    assert result['new_inference_windows'] == 0
    assert result['review_state'] == 'READ_EVIDENCE_HOLD'


@pytest.mark.parametrize('variant', ['same', 'legacy', 'mixed', 'invalid', 'restored'])
def test_model_read_producer_is_known_only_when_every_success_agrees(variant):
    module = analyzer(); d, raw = source(doc('First paragraph.\nSecond paragraph.'))
    cut = d['body'].index('\n')
    windows = [{'start': 0, 'end': cut, 'text': d['body'][:cut]},
               {'start': cut+1, 'end': len(d['body']), 'text': d['body'][cut+1:]}]
    planned, results = receipts(d, windows)
    producer = {'run_id': 123, 'run_attempt': 2, 'execution_sha': 'a'*40, 'workflow_sha': 'b'*40}
    for row in results: row['inference_producer'] = deepcopy(producer)
    if variant == 'legacy': results[1].pop('inference_producer')
    elif variant == 'mixed': results[1]['inference_producer']['run_id'] = 124
    elif variant == 'invalid': results[1]['inference_producer']['run_attempt'] = True
    elif variant == 'restored':
        for row in results: row['restored_receipt_not_new_inference'] = True
    result = module.analyze_document(d, planned, results, raw=raw, as_of=AS_OF)
    assert result['model_read_producer'] == (producer if variant in ('same', 'restored') else None)
    if variant == 'restored': assert result['new_inference_windows'] == 0


def test_model_read_producer_validator_is_strict_but_legacy_optional():
    module = analyzer(); d, raw = source(); planned, results = receipts(d)
    value = module.analyze_document(d, planned, results, raw=raw, as_of=AS_OF)
    for producer in [None, {'run_id': 1, 'run_attempt': 1, 'execution_sha': 'a'*40, 'workflow_sha': 'b'*40}]:
        candidate = {**value, 'model_read_producer': producer}
        candidate['id'] = 'cpu-analysis-'+sha({k: v for k, v in candidate.items() if k not in ('id', 'evaluated_at')})
        assert module.validate_receipt(candidate)
    legacy = {k: v for k, v in value.items() if k != 'model_read_producer'}
    legacy['id'] = 'cpu-analysis-'+sha({k: v for k, v in legacy.items() if k not in ('id', 'evaluated_at')})
    assert module.validate_receipt(legacy)
    for invalid in [{'run_id': True}, {'run_id': 1, 'run_attempt': 0, 'execution_sha': 'a'*40, 'workflow_sha': 'b'*40},
                    {'run_id': 1, 'run_attempt': 1, 'execution_sha': 'bad', 'workflow_sha': 'b'*40}]:
        candidate = {**value, 'model_read_producer': invalid}
        candidate['id'] = 'cpu-analysis-'+sha({k: v for k, v in candidate.items() if k not in ('id', 'evaluated_at')})
        with pytest.raises(ValueError, match='PRODUCER'): module.validate_receipt(candidate)


def test_analysis_is_immutable_source_free_deduplicated_and_readable_after_restart(tmp_path):
    module = analyzer(); d, raw = source(); ledger = queue.open_queue(tmp_path/'queue')
    with ledger.worker():
        queue.enqueue(ledger, d, raw, {})
        planned = queue.events(ledger, 'CPU_QUEUE_DOCUMENT')[0]
        _, results = receipts(d, [t['window'] for t in planned['tasks']])
        with ledger.db:
            for result in results: ledger.event('CPU_QUEUE_WINDOW_RESULT', result)
            first = module.record_analysis(ledger, d, as_of=AS_OF)
            again = module.record_analysis(ledger, d, as_of=AS_OF)
    assert first['id'] == again['id'] and again['delivery'] == 'DUPLICATE'
    stored, = queue.events(ledger, module.KIND)
    assert stored['document_id'] == d['document_id'] and stored['source_version'] == d['version']
    def no_sources(value):
        if isinstance(value, dict):
            assert not {'body', 'raw', 'text', 'quote', 'source_quote', 'selected_windows', 'raw_windows'} & set(value)
            for v in value.values(): no_sources(v)
        elif isinstance(value, list):
            for v in value: no_sources(v)
    no_sources(stored); ledger.close()
    script = ('import json,sys;from bct.v4.cpu_automation import open_queue,events;'
              'q=open_queue(sys.argv[1]);print(json.dumps(events(q,"CPU_ANALYSIS_RESULT")));q.close()')
    restored = json.loads(subprocess.check_output([sys.executable, '-c', script, str(tmp_path/'queue')]))
    assert restored == [stored]


def test_analysis_dependency_failure_is_not_normal_hold_and_can_recover_without_inference(monkeypatch):
    module = analyzer(); d, raw = source(); planned, results = receipts(d)
    from bct.v4 import official_discovery
    real = official_discovery.q3_input
    monkeypatch.setattr(official_discovery, 'q3_input', lambda *a, **k: (_ for _ in ()).throw(ValueError('fixture')))
    failed = module.analyze_document(d, planned, results, raw=raw, as_of=AS_OF)
    assert failed['review_state'] == 'FAILED' and failed['reason_code'] == 'ANALYSIS_DEPENDENCY_FAILED'
    assert failed['CPU_windows_success'] == 1 and failed['strict_pair_count'] is None
    monkeypatch.setattr(official_discovery, 'q3_input', real)
    recovered = module.analyze_document(d, planned, results, raw=raw, as_of=AS_OF)
    assert recovered['review_state'] == 'READ_EVIDENCE_HOLD' and recovered['id'] != failed['id']
    assert recovered['window_result_sha256'] == failed['window_result_sha256']
