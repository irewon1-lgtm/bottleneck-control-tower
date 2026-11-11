"""Preserving input bytes never manufactures a new Gate proof."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile
from types import SimpleNamespace
import shutil

import yaml

import pytest


def helper():
    path = Path(__file__).parents[1] / '.github/scripts/recovery_artifacts.py'
    assert path.is_file(), 'no authenticated preserved-input restore route exists'
    spec = importlib.util.spec_from_file_location('recovery_artifacts', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def descriptor(payload=b'original saved ZIP'):
    return {'artifact_id': 10, 'run_id': 20, 'head_sha': 'a' * 40,
            'name': 'bct-recovery-checkpoint-20', 'bytes': len(payload),
            'sha256': hashlib.sha256(payload).hexdigest()}


def wrapper(path, d, *, payload=b'original saved ZIP', change=None):
    proof = {'format': 'bct-input-preservation-1', 'original': d,
             'new_gate_execution': False, 'release_proof_renewed': False}
    if change == 'gate': proof['new_gate_execution'] = True
    if change == 'identity': proof['original'] = {**d, 'run_id': 21}
    with zipfile.ZipFile(path, 'w') as saved:
        saved.writestr('input.zip', payload)
        saved.writestr('preservation.json', json.dumps(proof))
        if change == 'extra': saved.writestr('../escape', b'forbidden')


def test_preserved_original_bytes_restore_without_claiming_gate_renewal(tmp_path):
    module = helper(); d = descriptor(); archive = tmp_path / 'preserved.zip'
    wrapper(archive, d)
    restored = tmp_path / 'original.zip'
    proof = module.unwrap(archive, restored, d)
    assert restored.read_bytes() == b'original saved ZIP'
    assert proof['original'] == d
    assert proof['new_gate_execution'] is proof['release_proof_renewed'] is False


@pytest.mark.parametrize('change', ['payload', 'gate', 'identity', 'extra'])
def test_wrong_original_or_false_gate_claim_is_rejected_before_input_use(tmp_path, change):
    module = helper(); d = descriptor(); archive = tmp_path / 'preserved.zip'
    wrapper(archive, d, payload=b'changed' if change == 'payload' else b'original saved ZIP', change=change)
    destination = tmp_path / 'original.zip'
    with pytest.raises(ValueError): module.unwrap(archive, destination, d)
    assert not destination.exists()


def test_existing_file_is_never_removed_when_unwrap_refuses(tmp_path):
    module = helper(); archive = tmp_path / 'preserved.zip'; d = descriptor()
    wrapper(archive, d); destination = tmp_path / 'keep'; destination.write_bytes(b'keep')
    with pytest.raises(ValueError): module.unwrap(archive, destination, d)
    assert destination.read_bytes() == b'keep'


def test_wrapped_input_reserves_space_for_inner_copy_before_creating_it(tmp_path, monkeypatch):
    module = helper(); archive = tmp_path / 'preserved.zip'; d = descriptor()
    wrapper(archive, d)
    monkeypatch.setattr(module.shutil, 'disk_usage', lambda path: SimpleNamespace(free=module.DISK_RESERVE + d['bytes'] - 1))
    destination = tmp_path / 'original.zip'
    with pytest.raises(ValueError, match='DISK_RESERVE_FOR_INNER_COPY'):
        module.unwrap(archive, destination, d)
    assert not destination.exists()


def test_expiry_requires_new_actual_gates_not_an_archive_copy():
    module = helper()
    state = module.expiry({'expired': False, 'expires_at': '2026-11-12T01:47:21Z'},
                          now=module.instant('2026-11-11T12:00:00Z'))
    assert state['status'] == 'EXPIRES_SOON'
    assert state['days_remaining'] < 1
    state = module.expiry({'expired': False, 'expires_at': '2026-11-12T01:47:21Z'},
                          now=module.instant('2026-11-13T00:00:00Z'))
    assert state['status'] == 'EXPIRED'


def test_shipped_successful_resume_origin_matches_current_proof_and_archive():
    root = Path(__file__).parents[1]
    request = json.loads((root / '.github/bct-recovery-request.json').read_text())
    release = json.loads((root / 'config/bct-operating-release.json').read_text())
    assert helper().resume_origin(request, release) == request['resume_archive']


def test_successful_source_cannot_be_older_or_different_from_active_proof():
    module = helper(); entry = descriptor()
    release = {'gate_run_id': 20, 'validated_code_sha': entry['head_sha'],
               'artifact_id': entry['artifact_id'], 'artifact_sha256': entry['sha256']}
    request = {'resume_run_id': '20', 'resume_archive': entry}
    assert module.resume_origin(request, release) == entry
    for change in [{'run_id': 19}, {'head_sha': 'b'*40}, {'sha256': 'b'*64}, {'artifact_id': 11}]:
        with pytest.raises(ValueError):
            module.resume_origin({**request, 'resume_archive': {**entry, **change}}, release)
    newer = {**entry, 'run_id': 21, 'name': 'bct-recovery-checkpoint-21'}
    with pytest.raises(ValueError): module.resume_origin({**request, 'resume_archive': newer}, release)
    partial = {**request, 'resume_run_id': '21', 'resume_archive': newer, 'resume_input_only': True}
    assert module.resume_origin(partial, release) == newer
    with pytest.raises(ValueError): module.resume_origin({**partial, 'resume_run_id': '22'}, release)
    with pytest.raises(ValueError): module.resume_origin({**request, 'resume_input_only': True}, release)


def test_observer_reports_real_proof_due_and_only_copies_small_recovery_automatically(monkeypatch):
    module = helper(); entry = descriptor(); fixed_now = module.instant('2026-11-11T12:00:00Z')
    actual_expiry = module.expiry
    monkeypatch.setattr(module, 'expiry', lambda value: actual_expiry(value, now=fixed_now))
    metadata = {'id': 10, 'name': entry['name'], 'size_in_bytes': entry['bytes'],
                'digest': 'sha256:'+entry['sha256'], 'expired': False, 'expires_at': '2026-11-12T01:47:21Z',
                'workflow_run': {'id': 20, 'head_sha': entry['head_sha']}}
    class FakeAPI:
        def read(self, suffix):
            if suffix == '/actions/artifacts/10': return metadata
            if suffix == '/actions/runs/20':
                return {'id': 20, 'status': 'completed', 'head_sha': entry['head_sha'],
                        'path': '.github/workflows/bct-recovery.yml',
                        'head_repository': {'full_name': module.REPOSITORY}}
            if suffix.startswith('/actions/artifacts?'): return {'total_count': 0, 'artifacts': []}
            raise AssertionError(suffix)
    release = {'gate_run_id': 20, 'validated_code_sha': entry['head_sha'],
               'artifact_id': 10, 'artifact_sha256': entry['sha256']}
    report = module.inspect(FakeAPI(), {'recovery': entry, 'legacy-source': entry}, release, 'recovery')
    assert report['preservation_due']
    assert report['recorded_release_artifact']['actual_Gates_and_receipt_renewal_due']
    assert not report['recorded_release_artifact']['current_code_Gates_revalidated']
    assert report['archives']['recovery']['automatic_copy_allowed']
    assert not report['archives']['legacy-source']['automatic_copy_allowed']
    metadata['expires_at'] = '2027-01-01T00:00:00Z'
    assert not module.inspect(FakeAPI(), {'recovery': entry}, release, 'recovery')['preservation_due']
    assert module.inspect(FakeAPI(), {'recovery': entry}, release, 'recovery', requested=True)['preservation_due']


def test_original_metadata_cannot_change_head_digest_or_origin_even_with_copy_transport():
    module = helper(); entry = descriptor()
    original = {'id': entry['artifact_id'], 'name': entry['name'], 'size_in_bytes': entry['bytes'],
                'digest': 'sha256:'+entry['sha256'], 'workflow_run': {'id': 20, 'head_sha': entry['head_sha']}}
    for change in [{'digest': 'sha256:'+'b'*64}, {'workflow_run': {'id': 21, 'head_sha': entry['head_sha']}},
                   {'workflow_run': {'id': 20, 'head_sha': 'b'*40}}]:
        class FakeAPI:
            def read(self, suffix): return {**original, **change}
        with pytest.raises(ValueError, match='ORIGINAL_BINDING'): module.original_metadata(FakeAPI(), entry)


def test_automatic_maintenance_refuses_large_copy_without_explicit_request(monkeypatch):
    module = helper(); entry = {**descriptor(), 'bytes': module.MAX_AUTOMATIC_COPY+1}
    metadata = {'expired': True, 'expires_at': '2026-01-01T00:00:00Z'}
    monkeypatch.setattr(module, 'original_metadata', lambda *args: metadata)
    monkeypatch.setattr(module, 'copies', lambda *args: [])
    class FakeAPI:
        def read(self, suffix): return None
    release = {'artifact_id': 10}
    report = module.inspect(FakeAPI(), {'recovery': entry}, release, 'recovery')
    assert report['archives']['recovery']['preservation_needed']
    assert not report['archives']['recovery']['automatic_copy_allowed']
    assert not report['preservation_due']
    assert module.inspect(FakeAPI(), {'recovery': entry}, release, 'recovery', requested=True)['preservation_due']


def test_failed_copy_producer_does_not_hide_a_later_verified_copy():
    module = helper(); entry = descriptor()
    base = {'name': module.copy_name(entry), 'size_in_bytes': 200, 'digest': 'sha256:'+'b'*64,
            'expired': False, 'expires_at': '2099-01-01T00:00:00Z'}
    bad = {**base, 'id': 50, 'workflow_run': {'id': 51}}
    good = {**base, 'id': 60, 'workflow_run': {'id': 61}}
    class FakeAPI:
        def read(self, suffix):
            if suffix.startswith('/actions/artifacts?'): return {'total_count': 2, 'artifacts': [bad, good]}
            return {'id': int(suffix.rsplit('/', 1)[1]), 'path': '.github/workflows/bct-recovery.yml',
                    'head_branch': 'main', 'head_repository': {'full_name': module.REPOSITORY},
                    'event': 'workflow_dispatch', 'status': 'completed',
                    'conclusion': 'failure' if suffix.endswith('/51') else 'success'}
    assert [a['id'] for a in module.copies(FakeAPI(), entry)] == [60]


def test_expired_original_restores_verified_journal_and_cache_via_preserved_bytes(tmp_path, monkeypatch):
    from bct.recovery_restore import verify_restored
    module = helper(); root = tmp_path/'original'; root.mkdir()
    checkpoint = {'run_id': '20', 'code_sha': 'a'*40}
    (root/'checkpoint.json').write_text(json.dumps(checkpoint))
    (root/'source-recovery-attempts.jsonl').write_text('')
    body = b'SYNTHETIC retained source bytes'; cache = root/'private-source-cache'; cache.mkdir()
    (cache/(hashlib.sha256(body).hexdigest()+'.txt')).write_bytes(body)
    pins = {name: module.digest(root/name) for name in ('checkpoint.json', 'source-recovery-attempts.jsonl')}
    inventory = verify_restored(root, pins)['cache_inventory_sha256']
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w') as saved:
        for path in root.rglob('*'):
            if path.is_file(): saved.write(path, path.relative_to(root).as_posix())
    raw = payload.getvalue(); entry = descriptor(raw); saved_wrapper = tmp_path/'preserved.zip'
    wrapper(saved_wrapper, entry, payload=raw)
    preserved = {'id': 60, 'name': module.copy_name(entry), 'size_in_bytes': saved_wrapper.stat().st_size,
                 'digest': 'sha256:'+module.digest(saved_wrapper), 'expired': False,
                 'expires_at': '2099-01-01T00:00:00Z', 'workflow_run': {'id': 61}}
    class FakeAPI:
        def read(self, suffix):
            if suffix == '/actions/artifacts/10': return None  # Expired/deleted original transport.
            if suffix.startswith('/actions/artifacts?'): return {'total_count': 1, 'artifacts': [preserved]}
            if suffix == '/actions/runs/61':
                return {'id': 61, 'path': '.github/workflows/bct-recovery.yml', 'head_branch': 'main',
                        'head_repository': {'full_name': module.REPOSITORY}, 'event': 'workflow_dispatch',
                        'status': 'completed', 'conclusion': 'success'}
            raise AssertionError(suffix)
    def download(meta, destination, maximum):
        assert meta['id'] == 60 and saved_wrapper.stat().st_size <= maximum
        shutil.copyfile(saved_wrapper, destination)
    monkeypatch.setattr(module, 'download', download)
    request = {'resume_run_id': '20', 'resume_file_sha256': pins, 'resume_cache_inventory_sha256': inventory}
    destination = tmp_path/'restored'
    result = module.restore(FakeAPI(), entry, request, destination)
    assert result['original_run_id'] == 20 and result['transport']['source'] == 'preserved'
    assert result['restore']['verified_cache_files']['private-source-cache'] == 1
    assert (destination/'checkpoint.json').read_bytes() == (root/'checkpoint.json').read_bytes()
    assert not result['new_gate_execution'] and not result['release_proof_renewed']
    with pytest.raises(ValueError, match='DESTINATION_EXISTS'):
        module.restore(FakeAPI(), entry, request, destination)


def test_wrapper_and_inner_space_checked_before_any_download(tmp_path, monkeypatch):
    module = helper(); entry = descriptor()
    copy = {'id': 60, 'size_in_bytes': 200, 'workflow_run': {'id': 61}}
    monkeypatch.setattr(module, 'original_metadata', lambda api, expected: None)
    monkeypatch.setattr(module, 'copies', lambda api, expected: [copy])
    monkeypatch.setattr(module.shutil, 'disk_usage', lambda path: SimpleNamespace(
        free=module.DISK_RESERVE + copy['size_in_bytes'] + entry['bytes'] - 1))
    monkeypatch.setattr(module, 'download', lambda *args: pytest.fail('download must not begin'))
    with pytest.raises(ValueError, match='WRAPPER_AND_INNER'):
        module.materialize(None, entry, tmp_path/'input.zip')
    assert not (tmp_path/'input.zip').exists()


def test_maintenance_hook_never_runs_storage_gates_and_never_expands_large_history():
    root = Path(__file__).parents[1]
    workflow = yaml.safe_load((root/'.github/workflows/bct-recovery.yml').read_text())
    triggers = workflow.get('on', workflow.get(True))
    assert triggers['workflow_run']['workflows'] == ['Future bottleneck body candidates']
    assert workflow['jobs']['storage']['if'] == "${{ github.event_name != 'workflow_run' && !inputs.preserve_resume_only }}"
    job = workflow['jobs']['preserve-input']
    assert job['permissions'] == {'contents': 'read', 'actions': 'read'}
    commands = '\n'.join(s.get('run', '') for s in job['steps'])
    assert 'bct_storage_recovery.py' not in commands and 'bct_queue_recovery.py' not in commands
    assert 'bct_local_reader_probe.py' not in commands and 'pip install' not in commands
    assert 'requested+=(--preserve-requested)' in commands
    assert job['env']['ARCHIVE_KEY'] == "${{ inputs.archive_key || 'recovery' }}"
    upload = next(s for s in job['steps'] if s.get('id') == 'preserved')
    assert upload['with']['compression-level'] == 0 and upload['with']['retention-days'] == 90


def gate_fixture(tmp_path, module, monkeypatch, *, partial=False, wrong_head=False):
    root = tmp_path/'checkout'; (root/'src').mkdir(parents=True); (root/'.github/scripts').mkdir(parents=True)
    (root/'config').mkdir(); (root/'src/engine.py').write_text('preserved_engine = 1\n')
    actual = Path(__file__).parents[1]/'.github/scripts/bct_release_guard.py'
    shutil.copyfile(actual, root/'.github/scripts/bct_release_guard.py')
    active = {'gate_run_id': 1, 'validated_code_sha': 'b'*40, 'artifact_id': 2, 'artifact_sha256': 'c'*64}
    previous = {'resume_run_id': '1', 'resume_file_sha256': {'checkpoint.json': 'd'*64,
                'source-recovery-attempts.jsonl': 'e'*64}, 'reader_batch_limit': 50}
    (root/'config/bct-operating-release.json').write_text(json.dumps(active))
    (root/'.github/bct-recovery-request.json').write_text(json.dumps(previous))
    code = 'a'*40; run_id = 20
    checkpoint = {'run_id': str(run_id), 'code_sha': 'b'*40 if wrong_head else code,
                  'status': 'FAIL' if partial else 'PASS', **{'gate'+str(i): 'PASS' for i in range(7)}}
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w') as saved:
        saved.writestr('checkpoint.json', json.dumps(checkpoint))
        saved.writestr('source-recovery-attempts.jsonl', '')
        if not partial:
            saved.writestr('e2e-recovery.json', '{"status":"PASS"}')
            saved.writestr('e2e-original-230/operating-report.json', '{"mode":"SYNTHETIC_FIXTURE"}')
    raw = payload.getvalue(); identity = hashlib.sha256(raw).hexdigest()
    artifact = {'id': 30, 'name': 'bct-recovery-checkpoint-20', 'size_in_bytes': len(raw),
                'digest': 'sha256:'+identity, 'expired': False, 'expires_at': '2099-01-01T00:00:00Z',
                'workflow_run': {'id': run_id, 'head_sha': code}}
    spec = importlib.util.spec_from_file_location('fixture_guard', actual)
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    tree = []
    for path in root.rglob('*'):
        name = path.relative_to(root).as_posix()
        if path.is_file() and guard.code_path(name):
            body = path.read_bytes(); tree.append({'type': 'blob', 'path': name,
                'sha': hashlib.sha1(f'blob {len(body)}\0'.encode()+body).hexdigest()})
    resources = {
        '/actions/runs/20': {'id': run_id, 'head_sha': code, 'head_branch': 'main', 'status': 'completed',
            'conclusion': 'failure' if partial else 'success', 'path': '.github/workflows/bct-recovery.yml',
            'head_repository': {'full_name': module.REPOSITORY}},
        '/actions/runs/20/jobs': {'jobs': [{'name': 'storage', 'steps': [
            {'name': name, 'conclusion': 'success'} for name in guard.REQUIRED]}]},
        '/actions/runs/20/artifacts?per_page=100': {'artifacts': [artifact]},
        '/actions/artifacts/30': artifact,
        '/git/commits/'+code: {'tree': {'sha': 'tree'}},
        '/git/trees/tree?recursive=1': {'tree': tree, 'truncated': False},
    }
    class FakeAPI:
        def read(self, suffix): return resources[suffix]
    def download(meta, destination, maximum):
        assert meta['digest'] == 'sha256:'+hashlib.sha256(raw).hexdigest()
        assert len(raw) <= maximum
        Path(destination).write_bytes(raw)
    monkeypatch.setattr(module, 'download', download)
    return root, FakeAPI(), code, active, previous


def test_genuine_success_rolls_release_and_latest_journal_pins_forward_together(tmp_path, monkeypatch):
    module = helper(); root, api, code, active, previous = gate_fixture(tmp_path, module, monkeypatch)
    destination = tmp_path/'receipts'
    result = module.prepare_receipts(api, 20, code, root, destination)
    release = json.loads((destination/'bct-operating-release.json').read_text())
    request = json.loads((destination/'bct-recovery-request.json').read_text())
    assert release['gate_run_id'] == int(request['resume_run_id']) == 20
    assert request['resume_archive']['head_sha'] == code
    assert request['resume_file_sha256']['checkpoint.json'] != previous['resume_file_sha256']['checkpoint.json']
    assert request['reader_batch_limit'] == 50 and request['resume_input_only'] is False
    assert result['release_receipt_prepared'] and result['source_journals_and_completed_readings_rolled_forward']
    assert module.resume_origin(request, release) == request['resume_archive']
    assert json.loads((root/'config/bct-operating-release.json').read_text()) == active


def test_newer_partial_checkpoint_only_prepares_input_never_release_proof(tmp_path, monkeypatch):
    module = helper(); root, api, code, active, previous = gate_fixture(tmp_path, module, monkeypatch, partial=True)
    destination = tmp_path/'resume'
    result = module.prepare_receipts(api, 20, code, root, destination, partial=True)
    assert not (destination/'bct-operating-release.json').exists()
    request = json.loads((destination/'bct-recovery-request.json').read_text())
    assert request['resume_input_only'] is True and module.resume_origin(request, active) == request['resume_archive']
    assert not result['release_receipt_prepared']
    with pytest.raises(ValueError): module.prepare_receipts(api, 0, code, root, tmp_path/'older', partial=True)


def test_wrong_payload_head_or_unsuccessful_run_cannot_prepare_genuine_receipt(tmp_path, monkeypatch):
    module = helper(); root, api, code, _, _ = gate_fixture(tmp_path, module, monkeypatch, wrong_head=True)
    with pytest.raises(ValueError, match='CHECKPOINT_NOT_PASS'):
        module.prepare_receipts(api, 20, code, root, tmp_path/'wrong')
    assert not (tmp_path/'wrong').exists()
    failed_root, failed_api, failed_code, _, _ = gate_fixture(tmp_path/'failed', module, monkeypatch, partial=True)
    with pytest.raises(ValueError): module.prepare_receipts(failed_api, 20, failed_code, failed_root, tmp_path/'proof')
    assert not (tmp_path/'proof').exists()
    partial_root, partial_api, partial_code, _, _ = gate_fixture(
        tmp_path/'partial', module, monkeypatch, partial=True, wrong_head=True)
    with pytest.raises(ValueError, match='CHECKPOINT_NOT_PASS'):
        module.prepare_receipts(partial_api, 20, partial_code, partial_root, tmp_path/'wrongpartial', partial=True)
    assert not (tmp_path/'wrongpartial').exists()
