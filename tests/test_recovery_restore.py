from hashlib import sha256
import pytest
from bct.recovery_restore import verify_restored


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
