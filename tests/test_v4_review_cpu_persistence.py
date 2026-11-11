"""Local Git persistence preserves classic REVIEW bytes and CPU sidecar dedup."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from bct import review_leads as review
from bct.v4.public_research import seal
from test_v4_review_cpu_receipts import append, prepared, receipts


def git(repo, *args):
    return subprocess.check_output(
        ['git', '-C', str(repo), *args], stderr=subprocess.PIPE)


def state_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob('*')
            if path.is_file() and path.name != '.review-lock'}


def test_existing_writer_restores_append_only_cpu_receipt_and_fresh_process_dedup(tmp_path, monkeypatch):
    project = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        'persist_cpu_receipt_fixture', project / '.github/scripts/persist_review_shadow.py')
    writer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(writer)

    repo = tmp_path / 'publisher'
    root, public = prepared(repo / 'var/review-state', monkeypatch)
    original = state_bytes(root)
    assert not (root / 'cpu-read-receipts').exists()
    remote = tmp_path / 'review-state.git'
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    git(repo, 'init')
    git(repo, 'remote', 'add', 'origin', str(remote))
    monkeypatch.chdir(repo)

    # Persist the real prepared classic state before adding the CPU sidecar.
    baseline = writer.persist(root, '')
    result = append(public, root)
    assert (result['created'], result['duplicate'], result['semantic_status']) == (1, 0, 'PENDING')
    saved, = receipts(root)
    assert saved['queue_binding']['status'] == 'EXACT_QUEUE_VERSION'
    assert saved['semantic_review'] == {'status': 'PENDING', 'completed_by_CPU': False}
    updated = state_bytes(root)
    assert {name: updated[name] for name in original} == original
    sidecar, = set(updated) - set(original)
    assert sidecar.startswith('cpu-read-receipts/')

    persisted = writer.persist(root, baseline)
    assert persisted != baseline
    assert git(repo, 'rev-parse', persisted + '^').decode().strip() == baseline
    assert git(repo, 'diff-tree', '--no-commit-id', '--name-status', '-r', baseline, persisted).decode().strip() == (
        'A\treview-lead-shadow/' + sidecar)
    for name, payload in original.items():
        assert git(repo, 'show', persisted + ':review-lead-shadow/' + name) == payload

    # Restore solely from the local bare remote into a separate Git workspace.
    restored_repo = tmp_path / 'restored'
    restored_repo.mkdir()
    git(restored_repo, 'init')
    git(restored_repo, 'remote', 'add', 'origin', str(remote))
    git(restored_repo, 'fetch', '--no-tags', 'origin', writer.REF)
    assert git(restored_repo, 'rev-parse', 'FETCH_HEAD').decode().strip() == persisted
    restore_parent = restored_repo / 'var/review-state'
    for name in git(restored_repo, 'ls-tree', '-r', '--name-only', persisted).decode().splitlines():
        assert name.startswith('review-lead-shadow/') and '..' not in Path(name).parts
        path = restore_parent / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(git(restored_repo, 'show', persisted + ':' + name))
    restored = restore_parent / 'review-lead-shadow'
    assert state_bytes(restored) == updated
    assert review.sealed_read(restored / sidecar) == saved

    newer = deepcopy(public)
    newer['generation']['ack_sequence'] += 1
    newer['generation']['private_commit'] = '8' * 40
    newer = seal(newer)
    assert newer['snapshot_sha256'] != public['snapshot_sha256']
    snapshot = tmp_path / 'new-generation.json'
    snapshot.write_text(json.dumps(newer))
    duplicate = subprocess.run(
        [sys.executable, '-m', 'bct.v4.review_cpu_receipts',
         '--snapshot', str(snapshot), '--state', str(restored)],
        cwd=restored_repo, env={**os.environ, 'PYTHONPATH': str(project / 'src')},
        capture_output=True, text=True)
    assert duplicate.returncode == 0, duplicate.stderr
    counts = json.loads(duplicate.stdout)
    assert (counts['created'], counts['duplicate'], counts['semantic_status']) == (0, 1, 'PENDING')
    assert state_bytes(restored) == updated
    assert len(receipts(restored)) == 1

    monkeypatch.chdir(restored_repo)
    assert writer.persist(restored, persisted) == persisted
    refs = git(restored_repo, 'ls-remote', '--refs', 'origin').decode().splitlines()
    assert refs == [persisted + '\t' + writer.REF]
    assert state_bytes(root) == updated
