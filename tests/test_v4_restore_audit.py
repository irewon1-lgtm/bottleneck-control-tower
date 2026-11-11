"""Read-only recovery proof; fixture generations never touch a remote account."""
import os
from pathlib import Path

import pytest

from bct.v4 import quantitative_private as private
from test_v4_monthly_storage import setup, evolve


def test_latest_child_restore_and_previous_history_are_verified_without_writes(tmp_path, monkeypatch):
    from bct.v4.restore_audit import audit_checkpoint

    for name in ('BCT_V4_PRIVATE_STATE_TOKEN', 'BCT_V4_STATE_PASSPHRASE', 'GH_TOKEN', 'GITHUB_TOKEN'):
        monkeypatch.setenv(name, 'fixture-account-credential-must-not-reach-child')
    registry, monthly, checkpoint, _, seed = setup(tmp_path / 'fixture')
    first = monthly.publish(checkpoint, seed)
    next_checkpoint, _ = evolve(checkpoint, tmp_path / 'next')
    latest = monthly.publish(next_checkpoint, first['storage'])
    monthly.receive(tmp_path / 'received')
    private.restore(tmp_path / 'received', tmp_path / 'current')
    before = {tag: (list(rows), dict(data)) for tag, (rows, data) in registry.stores.items()}
    proof = audit_checkpoint(monthly, tmp_path / 'received', tmp_path / 'current/v4.sqlite3',
                             tmp_path / 'audit')
    assert proof['storage'] == latest['storage']
    assert proof['new_process_restore']['tables'] == 8
    assert proof['child_pid'] != os.getpid()
    assert proof['child_private_credentials_removed'] is True
    assert proof['previous_generation']['generation'] == 0
    assert proof['previous_generation']['existing_history_preserved'] is True
    assert proof['remote_writes'] == proof['source_HTTP_requests'] == 0
    assert {tag: (list(rows), dict(data)) for tag, (rows, data) in registry.stores.items()} == before


def test_stale_input_and_existing_work_directory_fail_without_overwrite(tmp_path):
    from bct.v4.restore_audit import audit_checkpoint

    _, monthly, checkpoint, _, seed = setup(tmp_path / 'fixture')
    first = monthly.publish(checkpoint, seed)
    monthly.receive(tmp_path / 'received')
    private.restore(tmp_path / 'received', tmp_path / 'current')
    next_checkpoint, _ = evolve(checkpoint, tmp_path / 'next')
    monthly.publish(next_checkpoint, first['storage'])
    with pytest.raises(ValueError, match='CURRENT_HEAD_MISMATCH'):
        audit_checkpoint(monthly, tmp_path / 'received', tmp_path / 'current/v4.sqlite3',
                         tmp_path / 'audit')
    assert not (tmp_path / 'audit').exists()
    (tmp_path / 'existing').mkdir()
    (tmp_path / 'existing/keep').write_text('preserved')
    with pytest.raises(ValueError, match='REFUSE_OVERWRITE'):
        audit_checkpoint(monthly, tmp_path / 'received', tmp_path / 'current/v4.sqlite3',
                         tmp_path / 'existing')
    assert (tmp_path / 'existing/keep').read_text() == 'preserved'


def test_first_generation_has_explicit_no_previous_generation(tmp_path):
    from bct.v4.restore_audit import audit_checkpoint

    _, monthly, checkpoint, _, seed = setup(tmp_path / 'fixture')
    monthly.publish(checkpoint, seed)
    monthly.receive(tmp_path / 'received')
    private.restore(tmp_path / 'received', tmp_path / 'current')
    proof = audit_checkpoint(monthly, tmp_path / 'received', tmp_path / 'current/v4.sqlite3',
                             tmp_path / 'audit')
    assert proof['previous_generation'] == {'status': 'NOT_APPLICABLE_INITIAL_GENERATION'}


def test_corrupt_previous_generation_is_not_hidden_by_valid_latest_checkpoint(tmp_path):
    from bct.v4.restore_audit import audit_checkpoint
    from bct.v4 import release_archive as archive
    from test_v4_release_archive import PASSWORD

    registry, monthly, checkpoint, _, seed = setup(tmp_path / 'fixture')
    first = monthly.publish(checkpoint, seed)
    next_checkpoint, _ = evolve(checkpoint, tmp_path / 'next')
    # A forced full checkpoint makes the latest independently recoverable.
    store = monthly.store(first['storage']['tag'])
    archive.publish(store, next_checkpoint, PASSWORD, expected_generation=0, max_deltas=1, at=monthly.at,
                    context={'purpose': 'QUANTITATIVE_RESEARCH_PRIMARY', 'previous_month': None})
    last_checkpoint, _ = evolve(next_checkpoint, tmp_path / 'last')
    archive.publish(store, last_checkpoint, PASSWORD, expected_generation=1, max_deltas=1, at=monthly.at,
                    context={'purpose': 'QUANTITATIVE_RESEARCH_PRIMARY', 'previous_month': None})
    monthly.receive(tmp_path / 'received')
    private.restore(tmp_path / 'received', tmp_path / 'current')
    prior, _ = archive.load_commit(store, 1, PASSWORD)
    rows, data = registry.stores[store.tag]
    old = prior['patches'][0]['id']
    data[old] = b'damaged previous generation'
    with pytest.raises(ValueError, match='CIPHERTEXT_HASH'):
        audit_checkpoint(monthly, tmp_path / 'received', tmp_path / 'current/v4.sqlite3',
                         tmp_path / 'audit')
