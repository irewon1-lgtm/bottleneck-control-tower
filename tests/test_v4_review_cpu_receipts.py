"""Append-only CPU read pointers, never classic semantic-review completion."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess

import pytest

from bct import review_leads as review, review_shadow as shadow
from bct.v4.public_research import APPROVED_MODEL, seal
from test_review_shadow import initialized
from test_v4_public_research import DOC, project


def prepared(tmp_path, monkeypatch):
    root, bundle, _, _ = initialized(tmp_path, monkeypatch)
    doc = bundle['documents'][0]
    doc.update(document_id=DOC, raw_sha256='b' * 64)
    shadow.run(bundle, root)
    public = project(tmp_path / 'public')
    public['trace'][0].update(body_sha256=doc['body_sha256'], source_version=doc['version'],
                              model=APPROVED_MODEL[0], revision=APPROVED_MODEL[1])
    return root, seal(public)


def append(public, root):
    from bct.v4.review_cpu_receipts import append_snapshot
    return append_snapshot(public, root)


def receipts(root):
    return [review.sealed_read(path) for path in sorted((root / 'cpu-read-receipts').glob('*.json'))]


def test_existing_intake_queue_gets_source_bound_pointer_without_mutation(tmp_path, monkeypatch):
    root, public = prepared(tmp_path, monkeypatch)
    before = shadow.snapshot(root)
    result = append(public, root)
    assert result['created'] == 1 and result['duplicate'] == 0
    saved, = receipts(root)
    assert saved['queue_binding']['status'] == 'EXACT_QUEUE_VERSION'
    assert saved['source']['document_id'] == DOC
    assert saved['source']['body_sha256'] == public['trace'][0]['body_sha256']
    assert saved['read']['read_state'] == 'READ_COMPLETE'
    assert saved['read']['review_state'] == 'READ_EVIDENCE_HOLD'
    assert saved['read']['missing_fields'] == ['supply_pool']
    assert saved['semantic_review'] == {'status': 'PENDING', 'completed_by_CPU': False}
    assert saved['generation'] == public['generation']
    assert not saved['EARLY_success'] and saved['LIVE_writes'] == 0
    assert all((root / name).read_bytes() and shadow.snapshot(root)[name] == value for name, value in before.items())
    encoded = json.dumps(saved)
    assert 'synthetic.example' not in encoded and 'Facility PX-1' not in encoded
    assert 'source_document' not in encoded
    assert (saved['read']['model'], saved['read']['revision']) == APPROVED_MODEL
    assert saved['read']['analysis_sha256'] == public['trace'][0]['analysis_sha256']
    assert saved['read']['window_binding_sha256'] == public['trace'][0]['window_binding_sha256']


def test_duplicate_survives_new_process_and_new_snapshot_generation(tmp_path, monkeypatch):
    root, public = prepared(tmp_path, monkeypatch)
    append(public, root)
    newer = deepcopy(public)
    newer['generation']['ack_sequence'] += 1
    newer['generation']['private_commit'] = '8' * 40
    newer = seal(newer)
    path = tmp_path / 'public.json'; path.write_text(json.dumps(newer))
    run = subprocess.run([os.environ.get('PYTHON', '/workspace/bottleneck-control-tower/.venv/bin/python'),
                          '-m', 'bct.v4.review_cpu_receipts', '--snapshot', str(path), '--state', str(root)],
                         env={**os.environ, 'PYTHONPATH': str(Path('src').resolve())}, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)['duplicate'] == 1
    assert len(receipts(root)) == 1


@pytest.mark.parametrize('change,status', [
    ({'body_sha256': '2' * 64, 'source_version': '2' * 64}, 'QUEUE_VERSION_PENDING'),
    ({'raw_sha256': '3' * 64}, 'QUEUE_VERSION_PENDING'),
    ({'document_id': '955f7732-e05f-4832-b421-0a84e0ca736b'}, 'QUEUE_UNMATCHED'),
])
def test_wrong_version_and_unmatched_are_explicit(tmp_path, monkeypatch, change, status):
    root, public = prepared(tmp_path, monkeypatch)
    public['trace'][0].update(change)
    append(seal(public), root)
    saved, = receipts(root)
    assert saved['queue_binding']['status'] == status
    assert saved['semantic_review']['status'] == 'PENDING'


def test_queue_race_appends_new_binding_without_rewriting_unmatched(tmp_path, monkeypatch):
    root, public = prepared(tmp_path, monkeypatch)
    queue = next((root / 'queue').glob('*.json'))
    content = queue.read_bytes(); queue.unlink()
    append(public, root)
    first = next((root / 'cpu-read-receipts').glob('*.json')); before = first.read_bytes()
    queue.write_bytes(content)
    append(public, root)
    assert first.read_bytes() == before
    assert {row['queue_binding']['status'] for row in receipts(root)} == {'QUEUE_UNMATCHED', 'EXACT_QUEUE_VERSION'}


def test_failed_unread_and_partial_are_distinct_progress_receipts(tmp_path, monkeypatch):
    root, public = prepared(tmp_path, monkeypatch)
    for state, read, reason, windows in [
        ('UNREAD', 'UNREAD', 'CPU_NOT_READ', {'total': 2, 'success': 0, 'failed': 0, 'unread': 2}),
        ('FAILED', 'FAILED', 'CPU_WINDOW_VALIDATION_FAILED', {'total': 2, 'success': 0, 'failed': 1, 'unread': 1}),
        ('PARTIAL', 'PARTIAL', 'CPU_READ_INCOMPLETE', {'total': 2, 'success': 1, 'failed': 0, 'unread': 1}),
    ]:
        public['trace'][0].update(review_state=state, read_state=read, reason_code=reason, window_counts=windows)
        public['analysis']['states'] = {state: 1}
        append(seal(public), root)
    assert {row['read']['read_state'] for row in receipts(root)} == {'UNREAD', 'FAILED', 'PARTIAL'}


def test_invalid_snapshot_and_absent_trace_never_create_inferred_results(tmp_path, monkeypatch):
    root, public = prepared(tmp_path, monkeypatch)
    public['trace'][0]['read_state'] = 'COMPLETE'
    with pytest.raises(ValueError): append(seal(public), root)
    assert not receipts(root)
    public['trace'] = []; public['analysis'].update(states={}, trace_total=0)
    assert append(seal(public), root)['created'] == 0
    assert not receipts(root)


def test_symlink_and_uninitialized_state_are_rejected(tmp_path, monkeypatch):
    root, public = prepared(tmp_path, monkeypatch)
    outside = tmp_path / 'outside'; outside.mkdir()
    (root / 'cpu-read-receipts').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='SYMLINK'): append(public, root)
    with pytest.raises(ValueError, match='INITIALIZED'): append(public, tmp_path / 'empty' / 'review-lead-shadow')


def test_complete_read_requires_successful_window_evidence(tmp_path, monkeypatch):
    root, public = prepared(tmp_path, monkeypatch)
    public['trace'][0]['window_counts'] = {'total': 2, 'success': 1, 'failed': 0, 'unread': 1}
    with pytest.raises(ValueError, match='COMPLETE_WINDOW_COUNTS'): append(seal(public), root)
    assert not receipts(root)


def test_conflicting_duplicate_source_identity_is_rejected_before_any_append(tmp_path, monkeypatch):
    root, public = prepared(tmp_path, monkeypatch)
    other = deepcopy(public['trace'][0]); other['missing_fields'] = ['quantity']
    public['trace'].append(other)
    public['analysis'].update(states={'READ_EVIDENCE_HOLD': 2}, trace_total=2)
    with pytest.raises(ValueError, match='AMBIGUOUS'): append(seal(public), root)
    assert not receipts(root)


def test_actual_capture_loader_queue_can_be_linked_without_source_recopy(tmp_path, monkeypatch):
    from bct import precursor_collection as collection
    from test_precursor_collection import html, manifest
    cache = tmp_path / 'capture-cache'; delta = manifest([DOC]); url = delta['documents'][0]['url']
    raw = html(DOC, 'The customer signed firm orders for 100 units in 2031. Facility PX-1 is commissioning.')
    monkeypatch.setattr(collection.acquisition, 'fetch', lambda u: (raw, u, 200, 'text/html'))
    monkeypatch.setattr(collection.acquisition, 'now', lambda: '2026-10-05T03:00:00+00:00')
    root = tmp_path / 'review-lead-shadow'
    monkeypatch.setattr(review, 'now', lambda: '2026-10-05T02:00:00+00:00'); shadow.initialize(root)
    activation = collection.init(cache, delta)
    collection.capture(cache, url, DOC, activation, collected_at=delta['documents'][0]['collected_at'])
    before = shadow.snapshot(cache)
    path = tmp_path / 'delta.json'; path.write_text(json.dumps(delta))
    bundle = shadow.handoff(path, cache, tmp_path / 'handoff')
    monkeypatch.setattr(review, 'now', lambda: '2026-10-05T04:00:00+00:00'); shadow.run(bundle, root)
    public = project(tmp_path / 'public'); doc, = bundle['documents']
    public['trace'][0].update(document_id=doc['document_id'], body_sha256=doc['body_sha256'],
                              source_version=doc['version'], raw_sha256=doc['raw_sha256'])
    append(seal(public), root)
    assert receipts(root)[0]['queue_binding']['status'] == 'EXACT_QUEUE_VERSION'
    assert shadow.snapshot(cache) == before


def test_source_model_read_producer_is_preserved_separately_from_ack_writer(tmp_path, monkeypatch):
    root, public = prepared(tmp_path, monkeypatch)
    original = {'run_id': 91, 'run_attempt': 2, 'execution_sha': '3' * 40, 'workflow_sha': '4' * 40}
    public['trace'][0]['model_read_producer'] = original
    append(seal(public), root)
    saved, = receipts(root)
    assert saved['read']['model_read_producer'] == original
    assert saved['generation']['producer_run_id'] != original['run_id']
    assert saved['snapshot_last_read_batch']['consumer_run_id'] != original['run_id']
    assert saved['semantic_review']['status'] == 'PENDING'


def test_legacy_and_unknown_model_read_producer_remain_null_and_deduplicate(tmp_path, monkeypatch):
    root, public = prepared(tmp_path, monkeypatch)
    public['trace'][0].pop('model_read_producer', None)
    append(seal(public), root)
    saved, = receipts(root)
    assert saved['read']['model_read_producer'] is None
    public['trace'][0]['model_read_producer'] = None
    assert append(seal(public), root)['duplicate'] == 1
    assert len(receipts(root)) == 1


def test_pre_attribution_receipt_is_not_relabelled_or_duplicated(tmp_path, monkeypatch):
    from bct.v4 import review_cpu_receipts as module
    root, public = prepared(tmp_path, monkeypatch)
    with monkeypatch.context() as before:
        before.setattr(module, 'READ_FIELDS', tuple(key for key in module.READ_FIELDS if key != 'model_read_producer'))
        append(public, root)
    path = next((root / 'cpu-read-receipts').glob('*.json')); original = path.read_bytes()
    assert 'model_read_producer' not in receipts(root)[0]['read']
    assert append(public, root)['duplicate'] == 1
    assert path.read_bytes() == original and len(receipts(root)) == 1
