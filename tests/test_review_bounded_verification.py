"""Read-only Actions replay keeps real HOLD intake separate from completion."""
import importlib.util
import hashlib
import json
from pathlib import Path
import zipfile

import pytest
import yaml


def helper():
    path = Path('.github/scripts/verify_bounded_review.py')
    assert path.is_file(), 'bounded actual REVIEW replay helper is missing'
    spec = importlib.util.spec_from_file_location('verify_bounded_review', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metadata(module):
    return ({'id': module.UPSTREAM_RUN_ID, 'path': '.github/workflows/precursor-acquisition.yml',
             'head_branch': 'main', 'head_sha': module.UPSTREAM_SHA, 'event': 'workflow_run',
             'created_at': module.CUTOVER, 'head_repository': {'full_name': module.REPOSITORY}},
            {'artifacts': [{'id': module.ARTIFACT_ID, 'name': 'precursor-private-cache',
                            'size_in_bytes': module.ARTIFACT_SIZE, 'digest': module.ARTIFACT_DIGEST,
                            'expired': False}]})


def test_actual_input_binding_rejects_different_run_fork_and_expired_artifact():
    module = helper()
    run, artifacts = metadata(module)
    assert module.validate_inputs(run, artifacts)['id'] == module.ARTIFACT_ID
    for field, value in [('id', 1), ('head_sha', 'wrong'), ('head_repository', {'full_name': 'other/repo'})]:
        with pytest.raises(ValueError, match='UPSTREAM_BINDING'):
            module.validate_inputs({**run, field: value}, artifacts)
    artifacts['artifacts'][0]['expired'] = True
    with pytest.raises(ValueError, match='ARTIFACT_BINDING'):
        module.validate_inputs(run, artifacts)


def test_snapshot_check_preserves_old_intake_and_detects_changed_bytes(tmp_path):
    module = helper()
    state = tmp_path / 'review-lead-shadow'
    (state / 'store/intake').mkdir(parents=True)
    original = state / 'store/intake/old.json'
    original.write_text('{"status":"HOLD"}')
    before = module.snapshot(state)
    (state / 'store/intake/new.json').write_text('{"status":"HOLD"}')
    assert module.verify_preserved(state, before) == 1
    original.write_text('{"status":"COMPLETED"}')
    with pytest.raises(ValueError, match='EXISTING_REVIEW_FILE_CHANGED'):
        module.verify_preserved(state, before)


def test_hold_and_duplicate_delivery_are_not_new_semantic_completions():
    module = helper()
    result = {'records': [
        {'final_status': 'HOLD', 'semantic_review': {'status': 'PENDING'}},
        {'final_status': 'HOLD', 'semantic_review': {'status': 'PENDING'}, 'delivery': 'DUPLICATE'},
        {'final_status': 'REVIEW_LEAD', 'semantic_review': {'status': 'COMPLETED'}, 'delivery': 'DUPLICATE'}],
        'omitted_backfill': [], 'alerts': []}
    counts = module.stage_counts(result)
    assert counts['intake_records'] == 3 and counts['new_intake_records_in_copy'] == 1
    assert counts['new_HOLD_records_in_copy'] == 1 and counts['duplicate_records'] == 2
    assert counts['new_semantic_completions'] == 0


def test_dev_verification_workflow_is_manual_branch_bound_and_read_only():
    workflow = yaml.safe_load(Path('.github/workflows/bct-isolated-review.yml').read_text())
    assert workflow['permissions'] == {'contents': 'read', 'actions': 'read'}
    job = workflow['jobs'].get('bounded_saved_source')
    assert job, 'manual bounded review validation job is missing'
    guard = job['if']
    assert "github.event_name == 'workflow_dispatch'" in guard
    assert "github.ref == 'refs/heads/codex/bct-v4-integration'" in guard
    assert 'inputs.bounded_current_replay' in guard
    text = str(job)
    assert 'persist_review_shadow' not in text and 'contents: write' not in text
    assert 'verify_bounded_review.py' in text
    upload = next(s for s in job['steps'] if s.get('uses') == 'actions/upload-artifact@v4')
    assert upload['with']['path'].endswith('/review-bounded-verification.json')


def test_historical_date_selection_cannot_claim_the_fixed_corpus(tmp_path):
    module = helper()
    archive = tmp_path/'archive.zip'
    with zipfile.ZipFile(archive, 'w') as saved:
        saved.writestr('documents/one.json', json.dumps({'provenance': 'PASS', 'acquired_at': '2026-10-01T00:00:00Z',
            'document_id': 'one', 'body_sha256': 'a'*64, 'raw_sha256': 'b'*64}))
    with zipfile.ZipFile(archive) as saved: result = module.historical_source_inventory(saved)
    assert result['selected_documents'] == 1 and not result['exact_fingerprint_match']
    assert result['status'] == 'BLOCKED_EXACT_FIXED230_SNAPSHOT_NOT_IDENTIFIED'
    assert not result['Gates_revalidated'] and not result['source_originals_reverified']


def test_exact_historical_hash_vector_only_verifies_present_raw_bytes(tmp_path):
    module = helper()
    archive = tmp_path/'archive.zip'; vector = []
    raw = b'<p>Saved historical source</p>'; body = 'Saved historical source'
    raw_hash = hashlib.sha256(raw).hexdigest(); body_hash = hashlib.sha256(body.encode()).hexdigest()
    with zipfile.ZipFile(archive, 'w') as saved:
        for n in range(230):
            document = {'provenance': 'PASS', 'acquired_at': '2026-10-01T00:00:00Z', 'document_id': str(n),
                        'body_sha256': body_hash, 'raw_sha256': raw_hash, 'body': body}
            saved.writestr('documents/'+str(n).zfill(3)+'.json', json.dumps(document))
            vector.append({k: document[k] for k in ('document_id', 'body_sha256', 'raw_sha256')})
        saved.writestr('raw/'+raw_hash+'.html', raw)
    expected = hashlib.sha256(json.dumps(vector, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    with zipfile.ZipFile(archive) as saved: result = module.historical_source_inventory(saved, expected)
    assert result['status'] == 'EXACT_HISTORICAL_CACHE_BYTES_AVAILABLE'
    assert result['raw_hashes_verified'] == 1 and result['body_hashes_verified']
    assert not result['source_originals_reverified'] and not result['Gates_revalidated']
