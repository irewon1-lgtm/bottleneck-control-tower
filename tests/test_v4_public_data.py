"""Durable public-data CAS preserves canonical state and private generation order."""
from copy import deepcopy
import os
from pathlib import Path
import subprocess

import pytest

from bct.v4.public_research import seal
from test_v4_public_research import project


def repository(tmp_path):
    bare = tmp_path / 'remote.git'; repo = tmp_path / 'writer'
    subprocess.run(['git', 'init', '--bare', str(bare)], check=True, capture_output=True)
    subprocess.run(['git', 'init', str(repo)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', str(bare)], check=True)
    def git(*args, input=None, env=None):
        result = subprocess.run(['git', '-C', str(repo), *args], input=input, capture_output=True,
                                env={**os.environ, **(env or {})})
        if result.returncode:
            raise ValueError('PUBLIC_DATA_GIT_FAILED')
        return result.stdout.decode().strip()
    git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid')
    for name in ('canonical.sqlite3', 'state.json', 'precursor-index.json', 'unowned.txt'):
        (repo / name).write_text('original ' + name)
    git('add', '.'); git('commit', '-m', 'Existing canonical state'); git('push', 'origin', 'HEAD:refs/heads/data')
    return repo, bare, git


def version(public, sequence, commit, run_id=None):
    result = deepcopy(public); result['generation']['ack_sequence'] = sequence
    result['generation']['private_commit'] = commit * 40
    if run_id:
        result['generation']['producer_run_id'] = run_id
    return seal(result)


def test_public_cas_preserves_every_unowned_blob_and_rejects_delayed_private_generations(tmp_path):
    from bct.v4.public_data import persist
    _, _, git = repository(tmp_path)
    public = project(tmp_path / 'fixture')
    before = {p: git('rev-parse', 'HEAD:' + p) for p in
              ('canonical.sqlite3', 'state.json', 'precursor-index.json', 'unowned.txt')}
    a = persist(git, research=version(public, 2, 'a'))
    b = persist(git, research=version(public, 4, 'b'))
    assert a['commit'] != b['commit']
    with pytest.raises(ValueError, match='STALE'):
        persist(git, research=version(public, 2, 'a'))
    # An older workflow retry can still publish a genuinely newer private ACK.
    c = persist(git, research=version(public, 6, 'c', run_id=99))
    assert c['research_generation']['ack_sequence'] == 6
    assert persist(git, research=version(public, 6, 'c', run_id=99))['unchanged']
    with pytest.raises(ValueError, match='EQUIVOCATION'):
        persist(git, research=version(public, 6, 'd', run_id=99))
    foreign = version(public, 8, 'd'); foreign['generation']['lineage_root'] = '0' * 40
    with pytest.raises(ValueError, match='LINEAGE'):
        persist(git, research=seal(foreign))
    git('fetch', 'origin', 'refs/heads/data')
    assert {p: git('rev-parse', 'FETCH_HEAD:' + p) for p in before} == before


def test_public_cas_keeps_concurrent_canonical_update_on_retry(tmp_path):
    from bct.v4.public_data import persist
    repo, bare, git = repository(tmp_path)
    other = tmp_path / 'canonical-writer'
    subprocess.run(['git', 'clone', '--branch', 'data', str(bare), str(other)], check=True, capture_output=True)
    changed = False
    def race(*args, **kwargs):
        nonlocal changed
        if args[:2] == ('ls-remote', 'origin') and not changed:
            changed = True
            (other / 'canonical.sqlite3').write_text('new concurrently collected canonical bytes')
            for command in [('config', 'user.name', 'Collector'), ('config', 'user.email', 'collector@example.invalid'),
                            ('add', '.'), ('commit', '-m', 'Concurrent canonical update'), ('push', 'origin', 'data')]:
                subprocess.run(['git', '-C', str(other), *command], check=True, capture_output=True)
        return git(*args, **kwargs)
    result = persist(race, research=project(tmp_path / 'fixture'))
    assert result['attempts'] == 2
    git('fetch', 'origin', 'refs/heads/data')
    assert git('show', 'FETCH_HEAD:canonical.sqlite3') == 'new concurrently collected canonical bytes'


def test_durable_public_file_is_read_without_original_artifact(tmp_path):
    from bct.v4.public_data import persist, read_current
    _, _, git = repository(tmp_path)
    public = project(tmp_path / 'fixture')
    persist(git, research=public)
    # No artifact/API/private repository dependency is involved in this read.
    assert read_current(git)['research'] == public


def test_collection_order_uses_actual_utc_instant_not_iso_text():
    from bct.v4.public_data import _collection_order
    older = {'collection_started_at': '2026-11-11T09:00:00+09:00', 'RSS_run_id': 1,
             'run_id': 2, 'completed_at': '2026-11-11T09:05:00+09:00'}
    newer = {'collection_started_at': '2026-11-11T01:00:00+00:00', 'RSS_run_id': 3,
             'run_id': 4, 'completed_at': '2026-11-11T01:05:00+00:00'}
    assert _collection_order(older) < _collection_order(newer)
