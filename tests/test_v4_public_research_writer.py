"""The public artifact comes from fetched private ACK bytes in a fresh process."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

from bct.v4 import cpu_operations as op
from bct.v4.private_state import PRIVATE_URL
from test_v4_public_research import input_state

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_writer', ROOT / 'tools/v4_public_research_snapshot.py')
writer = importlib.util.module_from_spec(spec); spec.loader.exec_module(writer)


def private_ack(tmp_path):
    path, result, _, producer = input_state(tmp_path)
    from bct.v4.store import Ledger
    ledger = Ledger(path.parent)
    checkpoint = tmp_path / 'checkpoint'
    proof = op.checkpoint(ledger, checkpoint); ledger.close()
    repo = tmp_path / 'private'; repo.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL).decode().strip()
    git('init'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid')
    git('remote', 'add', 'origin', PRIVATE_URL)
    for name in ('checkpoint.json', 'checkpoint.sqlite3.gz'):
        (repo / name).write_bytes((checkpoint / name).read_bytes())
    git('add', '.'); git('commit', '-m', 'Fixture checkpoint')
    checkpoint_commit = git('rev-parse', 'HEAD')
    result['persistence_receipt'].update(checkpoint_commit=checkpoint_commit, sqlite_sha256=proof['sqlite_sha256'])
    (repo / 'private-persistence.json').write_text(json.dumps(result['persistence_receipt']))
    git('add', '.'); git('commit', '-m', 'Fixture acknowledged restore')
    result['commit'] = git('rev-parse', 'HEAD')
    git('fetch', '.', result['commit'])
    published = tmp_path / 'published.json'; published.write_text(json.dumps(result))
    return repo, published, producer, git, result


def test_public_writer_reads_fetched_commit_and_emits_only_small_public_files(tmp_path):
    repo, published, producer, _, result = private_ack(tmp_path)
    receipt = writer.emit(repo, published, tmp_path / 'public', producer)
    files = {p.name for p in (tmp_path / 'public').iterdir()}
    assert files == {'snapshot.json', 'manifest.json'}
    public = json.loads((tmp_path / 'public/snapshot.json').read_text())
    assert public['generation']['private_commit'] == result['commit']
    assert receipt['source_originals_exported'] == 0
    assert 'PRIVATE ORIGINAL' not in (tmp_path / 'public/snapshot.json').read_text()
    assert sum(p.stat().st_size for p in (tmp_path / 'public').iterdir()) < 192 * 1024


def test_public_writer_refuses_stale_fetched_generation(tmp_path):
    repo, published, producer, git, result = private_ack(tmp_path)
    git('fetch', '.', result['persistence_receipt']['checkpoint_commit'])
    with pytest.raises(ValueError, match='FETCHED_GENERATION'):
        writer.emit(repo, published, tmp_path / 'public', producer)
    assert not (tmp_path / 'public').exists()


def test_public_writer_refuses_foreign_private_repository(tmp_path):
    repo, published, producer, git, _ = private_ack(tmp_path)
    git('remote', 'set-url', 'origin', 'https://example.invalid/unrelated.git')
    with pytest.raises(ValueError, match='REPOSITORY'):
        writer.emit(repo, published, tmp_path / 'public', producer)
    assert not (tmp_path / 'public').exists()
