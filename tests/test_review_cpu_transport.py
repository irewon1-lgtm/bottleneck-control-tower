"""Attempt-bound REVIEW input transport, using only public GitHub credentials."""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path

import pytest


def helper():
    spec = importlib.util.spec_from_file_location('review_inputs', '.github/scripts/receive_review_inputs.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def metadata(attempt=2):
    run = {'id': 22, 'run_attempt': attempt, 'head_sha': 'a' * 40, 'head_branch': 'main',
           'head_repository': {'full_name': 'irewon1-lgtm/bottleneck-control-tower'},
           'path': '.github/workflows/precursor-acquisition.yml', 'event': 'workflow_run',
           'conclusion': 'failure', 'created_at': '2026-11-11T12:00:00Z'}
    artifact = {'id': 33, 'name': 'precursor-private-cache-' + str(attempt), 'expired': False,
                'size_in_bytes': 123, 'digest': 'sha256:' + 'b' * 64,
                'workflow_run': {'id': 22, 'head_sha': 'a' * 40, 'head_branch': 'main'}}
    return run, artifact


def test_source_artifact_binds_exact_attempt_run_head_size_digest():
    module = helper(); run, artifact = metadata()
    assert module.select_source_artifact(run, [artifact], 22, 2, 'a' * 40) == artifact
    legacy = deepcopy(artifact); legacy['name'] = 'precursor-private-cache'
    assert module.select_source_artifact(run, [legacy], 22, 2, 'a' * 40) is None
    run1, artifact1 = metadata(1); artifact1['name'] = 'precursor-private-cache'
    assert module.select_source_artifact(run1, [artifact1], 22, 1, 'a' * 40) == artifact1


@pytest.mark.parametrize('field,value', [('size_in_bytes', 0), ('digest', None),
                                       ('workflow_run', {'id': 99, 'head_sha': 'a' * 40, 'head_branch': 'main'})])
def test_invalid_or_ambiguous_source_artifact_is_rejected(field, value):
    module = helper(); run, artifact = metadata(); artifact[field] = value
    with pytest.raises(ValueError): module.select_source_artifact(run, [artifact], 22, 2, 'a' * 40)
    run, artifact = metadata()
    with pytest.raises(ValueError, match='AMBIGUOUS'):
        module.select_source_artifact(run, [artifact, deepcopy(artifact)], 22, 2, 'a' * 40)


def test_rerun_metadata_cannot_adopt_first_attempt_and_wrong_head_is_rejected():
    module = helper(); run, artifact = metadata()
    for expected_attempt, expected_head in ((1, 'a' * 40), (2, 'f' * 40)):
        with pytest.raises(ValueError, match='PRODUCER'):
            module.select_source_artifact(run, [artifact], 22, expected_attempt, expected_head)


def test_existing_and_dangling_destinations_are_never_deleted(tmp_path, monkeypatch):
    from bct import review_artifact
    existing = tmp_path / 'existing'; existing.write_bytes(b'preserve')
    dangling = tmp_path / 'dangling'; dangling.symlink_to(tmp_path / 'absent')
    for path in (existing, dangling):
        with pytest.raises(ValueError, match='DESTINATION_EXISTS'):
            review_artifact.download('owner/repo', '123', 10, path, expected_digest='sha256:' + 'b' * 64)
    assert existing.read_bytes() == b'preserve' and dangling.is_symlink()


def test_download_checks_exact_bytes_and_digest_and_removes_only_own_partial(tmp_path, monkeypatch):
    from bct import review_artifact
    import io
    raw = b'controlled archive bytes'
    class Process:
        stdout = io.BytesIO(raw)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def wait(self): return 0
        def kill(self): pass
    monkeypatch.setattr(review_artifact.subprocess, 'Popen', lambda *a, **k: Process())
    monkeypatch.setattr(review_artifact.shutil, 'disk_usage', lambda path: (10**12, 0, 10**12))
    path = tmp_path / 'archive.zip'
    with pytest.raises(ValueError, match='HASH'):
        review_artifact.download('owner/repo', '123', len(raw), path, expected_digest='sha256:' + '0' * 64)
    assert not path.exists()
    Process.stdout = io.BytesIO(raw)
    assert review_artifact.download('owner/repo', '123', len(raw), path,
                                   expected_digest='sha256:' + hashlib.sha256(raw).hexdigest()) == len(raw)
    assert path.read_bytes() == raw


def test_download_open_race_preserves_foreign_file(tmp_path, monkeypatch):
    from bct import review_artifact
    path = tmp_path / 'archive.zip'; original = Path.open
    monkeypatch.setattr(review_artifact.shutil, 'disk_usage', lambda path: (10**12, 0, 10**12))
    def raced(self, mode='r', *args, **kwargs):
        if self == path and mode == 'xb':
            path.write_bytes(b'foreign owner')
        return original(self, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', raced)
    with pytest.raises(FileExistsError):
        review_artifact.download('owner/repo', '123', 10, path, expected_digest='sha256:' + 'b' * 64)
    assert path.read_bytes() == b'foreign owner'


@pytest.mark.parametrize('pending', ['NONE', 'PRODUCER_IN_PROGRESS', 'SCAN_BOUND'])
def test_every_review_event_catches_up_durable_snapshot_without_attributing_it_to_trigger(tmp_path, monkeypatch, pending):
    from test_v4_public_research import project
    module = helper(); public = project(tmp_path)
    class Transport:
        @staticmethod
        def git_client(): return object()
        @staticmethod
        def read_current(git): return {'research': public, 'cursor': {'artifact_id': 80}}
        @staticmethod
        def api(path): return {'path': module.SOURCE_WORKFLOW}
        @staticmethod
        def catch_up(cursor, research): return research, None, None, pending
    monkeypatch.setattr(module, 'public_transport', lambda path: Transport)
    monkeypatch.chdir(tmp_path)
    result = module.public_inputs(Path('trusted-pin'), 999)
    assert result['public_snapshots'] == 1 and result['catchup_pending_reason'] == pending
    import json
    saved = json.loads(next(Path('var/review-public-inputs').glob('*.json')).read_text())
    assert saved == public and saved['generation']['producer_run_id'] == 103


def test_review_workflow_uses_immutable_receivers_and_separate_cpu_pin():
    import yaml
    text = Path('.github/workflows/review-lead-shadow.yml').read_text()
    workflow = yaml.safe_load(text)
    events = workflow.get('on', workflow.get(True))
    assert events['workflow_run']['workflows'] == ['New precursor evidence acquisition', 'V4 CPU private research consumer']
    steps = workflow['jobs']['shadow']['steps']
    checkouts = [step for step in steps if step.get('uses', '').startswith('actions/checkout@')]
    assert checkouts[0]['with']['ref'] == '${{ github.workflow_sha }}'
    assert checkouts[1]['with']['path'] == 'processor'
    assert checkouts[1]['with']['persist-credentials'] is False
    assert 'processor/src' in text and 'bct.v4.review_cpu_receipts' in text
    assert 'BCT_V4_PRIVATE_STATE_TOKEN' not in text
    assert 'persist_review_shadow.py' in text
    assert 'head -n 1' not in text
