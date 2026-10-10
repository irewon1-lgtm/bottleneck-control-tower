from hashlib import sha256
import json
import pytest
from bct.recovery_restore import copy_latest_root_state, verify_restored


def pinned(tmp_path):
    files={'checkpoint.json':b'{"run_id":"1"}', 'source-recovery-attempts.jsonl':b'{"url":"source"}\n'}
    for name,raw in files.items():(tmp_path/name).write_bytes(raw)
    return {name:sha256(raw).hexdigest() for name,raw in files.items()}


def test_restore_binds_checkpoint_journal_and_every_actual_cached_source(tmp_path):
    expected=pinned(tmp_path);body=b'Original retained source bytes.'
    cache=tmp_path/'private-source-cache';cache.mkdir()
    (cache/(sha256(body).hexdigest()+'.txt')).write_bytes(body)
    result=verify_restored(tmp_path,expected)
    assert result['verified_cache_files']['private-source-cache']==1
    (tmp_path/'checkpoint.json').write_text('{"run_id":"other"}')
    with pytest.raises(ValueError,match='checkpoint file'):verify_restored(tmp_path,expected)


def test_changed_private_source_is_never_used_to_resume(tmp_path):
    expected=pinned(tmp_path);cache=tmp_path/'private-source-cache';cache.mkdir()
    (cache/('a'*64+'.txt')).write_bytes(b'changed')
    with pytest.raises(ValueError,match='private source'):verify_restored(tmp_path,expected)


def test_missing_source_cache_cannot_pass_a_pinned_inventory(tmp_path):
    expected=pinned(tmp_path);cache=tmp_path/'private-source-cache';cache.mkdir()
    raw=b'retained';path=cache/(sha256(raw).hexdigest()+'.txt');path.write_bytes(raw)
    inventory=verify_restored(tmp_path,expected)['cache_inventory_sha256']
    path.unlink()
    with pytest.raises(ValueError,match='inventory differs'):
        verify_restored(tmp_path,expected,expected_cache_inventory=inventory)


def test_unpinned_or_path_traversing_restore_is_rejected(tmp_path):
    with pytest.raises(ValueError,match='pinned'):verify_restored(tmp_path,{})
    expected=pinned(tmp_path);expected['../other']='a'*64
    with pytest.raises(ValueError,match='invalid recovery'):verify_restored(tmp_path,expected)


def test_latest_root_journals_survive_an_early_gate_failure(tmp_path):
    source, destination = tmp_path / 'source', tmp_path / 'destination'
    source.mkdir()
    (source / 'source-recovery-attempts.jsonl').write_text('{"url":"kept"}\n')
    (source / 'private-local-reader-execution.jsonl').write_text('{"result":"kept"}\n')
    receipt = copy_latest_root_state(source, destination)
    assert receipt['status'] == 'PASS'
    assert (destination / 'source-recovery-attempts.jsonl').read_bytes() == (source / 'source-recovery-attempts.jsonl').read_bytes()
    assert (destination / 'private-local-reader-execution.jsonl').read_bytes() == (source / 'private-local-reader-execution.jsonl').read_bytes()
    assert copy_latest_root_state(source, destination)['copied_files'] == []


def test_latest_root_journals_never_overwrite_conflicting_bytes(tmp_path):
    source, destination = tmp_path / 'source', tmp_path / 'destination'
    source.mkdir(); destination.mkdir()
    (source / 'source-recovery-attempts.jsonl').write_text('new\n')
    (destination / 'source-recovery-attempts.jsonl').write_text('different\n')
    with pytest.raises(ValueError, match='destination differs'):
        copy_latest_root_state(source, destination)


def test_native_claim_private_results_must_be_pinned_and_preserved(tmp_path):
    from bct.recovery_restore import copy_preserved_caches
    source, destination = tmp_path/'source', tmp_path/'destination'
    source.mkdir()
    expected = pinned(source)
    name = 'private-native-claim/123/response.json'
    private = source/name; private.parent.mkdir(parents=True); private.write_text('{"review":"kept"}')
    history = source/'native-claim-history.json'
    history.write_text(json.dumps([{'private_file_sha256': {name: sha256(private.read_bytes()).hexdigest()}}]))
    with pytest.raises(ValueError, match='history must be pinned'):
        verify_restored(source, expected)
    expected[history.name] = sha256(history.read_bytes()).hexdigest()
    assert verify_restored(source, expected)['verified_cache_files']['private-native-claim'] == 1
    copy_preserved_caches(source, destination)
    assert (destination/name).read_bytes() == private.read_bytes()
    assert copy_preserved_caches(source, destination)['copied_files'] == []
    private.write_text('changed')
    with pytest.raises(ValueError, match='native claim private receipt hash'):
        verify_restored(source, expected)
