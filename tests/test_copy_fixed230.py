"""Synthetic byte-transport tests; production CLI keeps the fixed old hash."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def helper():
    path = Path('.github/scripts/copy_fixed230.py')
    assert path.is_file(), 'exact fixed230 literal-copy helper is missing'
    spec = importlib.util.spec_from_file_location('copy_fixed230', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def synthetic_cache(root, module, monkeypatch):
    (root/'documents').mkdir(parents=True); (root/'raw').mkdir()
    vector = []; selected = {}
    for n in range(230):
        body = 'Historical source '+str(n); raw = ('<p>'+body+'</p>').encode()
        raw_hash = hashlib.sha256(raw).hexdigest(); body_hash = hashlib.sha256(body.encode()).hexdigest()
        document = {'document_id': str(n), 'body': body, 'body_sha256': body_hash,
                    'raw_sha256': raw_hash, 'version': body_hash, 'provenance': 'PASS',
                    'acquired_at': '2026-10-01T00:00:00Z'}
        # Noncanonical whitespace must survive; parsing never rewrites source JSON.
        metadata = ('\n'+json.dumps(document, indent=3)+'\n\n').encode()
        selected['documents/'+str(n).zfill(3)+'.json'] = metadata
        selected['raw/'+raw_hash+'.html'] = raw
        vector.append({k: document[k] for k in ('document_id', 'body_sha256', 'raw_sha256')})
    for name, value in selected.items(): (root/name).write_bytes(value)
    fingerprint = hashlib.sha256(json.dumps(vector, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    # This transport-only fixture has its own identity. No repository golden is edited.
    monkeypatch.setattr(module, 'FIXED230_FINGERPRINT', fingerprint)
    (root/'documents/future.json').write_text(json.dumps({**document, 'acquired_at': '2030-01-01T00:00:00Z'}))
    (root/'documents/unverified.json').write_text(json.dumps({**document, 'provenance': 'BLOCKED'}))
    (root/'documents/malformed.json').write_text('{bad unrelated metadata')
    (root/'raw/unrelated.html').write_bytes(b'unrelated')
    return selected


def test_exact_selection_copies_literal_metadata_and_raw_without_mutating_source(tmp_path, monkeypatch):
    module = helper(); source = tmp_path/'source'; selected = synthetic_cache(source, module, monkeypatch)
    before = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    destination = tmp_path/'fixed230'; result = module.copy_fixed230(source, destination)
    assert {str(p.relative_to(destination)): p.read_bytes() for p in destination.rglob('*') if p.is_file()} == selected
    assert {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()} == before
    assert result['documents'] == result['body_hashes_verified'] == result['raw_hashes_verified'] == 230
    assert result['copied_bytes'] == sum(map(len, selected.values()))
    assert result['source_input_sha256'] == module.FIXED230_FINGERPRINT
    assert not result['source_originals_modified'] and not result['QA_executed']


@pytest.mark.parametrize('change', ['missing', 'identity', 'raw', 'body'])
def test_incomplete_selection_or_changed_hash_fails_before_destination_exists(tmp_path, monkeypatch, change):
    module = helper(); source = tmp_path/'source'; selected = synthetic_cache(source, module, monkeypatch)
    if change == 'missing': (source/'documents/000.json').unlink()
    elif change == 'identity':
        path = source/'documents/000.json'; document = json.loads(path.read_text()); document['document_id'] = 'changed'
        path.write_text(json.dumps(document))
    elif change == 'raw':
        document = json.loads((source/'documents/000.json').read_text())
        (source/'raw'/(document['raw_sha256']+'.html')).write_bytes(b'changed source')
    else:
        path = source/'documents/000.json'; document = json.loads(path.read_text()); document['body'] += 'changed'
        path.write_text(json.dumps(document))
    with pytest.raises(ValueError): module.copy_fixed230(source, tmp_path/'fixed230')
    assert not (tmp_path/'fixed230').exists()


def test_existing_destination_and_byte_budget_fail_without_overwrite(tmp_path, monkeypatch):
    module = helper(); source = tmp_path/'source'; synthetic_cache(source, module, monkeypatch)
    destination = tmp_path/'preserved'; destination.mkdir(); (destination/'original').write_bytes(b'preserved')
    with pytest.raises(ValueError, match='DESTINATION_EXISTS'): module.copy_fixed230(source, destination)
    assert (destination/'original').read_bytes() == b'preserved'
    monkeypatch.setattr(module, 'MAX_COPY_BYTES', 1)
    with pytest.raises(ValueError, match='COPY_LIMIT'): module.copy_fixed230(source, tmp_path/'bounded')
    assert not (tmp_path/'bounded').exists()


def test_destination_cannot_be_inside_original_cache(tmp_path, monkeypatch):
    module = helper(); source = tmp_path/'source'; synthetic_cache(source, module, monkeypatch)
    with pytest.raises(ValueError, match='DESTINATION_INSIDE_SOURCE'): module.copy_fixed230(source, source/'derived')
    assert not (source/'derived').exists()


@pytest.mark.parametrize('where', ['raw', 'metadata', 'destination'])
def test_symlinks_are_not_read_as_source_or_removed_as_destination(tmp_path, monkeypatch, where):
    module = helper(); source = tmp_path/'source'; synthetic_cache(source, module, monkeypatch)
    destination = tmp_path/'fixed230'; original = tmp_path/'preserved'; original.write_bytes(b'preserved')
    if where == 'raw':
        document = json.loads((source/'documents/000.json').read_text())
        path = source/'raw'/(document['raw_sha256']+'.html'); path.unlink(); path.symlink_to(original)
    elif where == 'metadata':
        path = source/'documents/000.json'; path.unlink(); path.symlink_to(original)
    else: destination.symlink_to(tmp_path/'not-created')
    with pytest.raises(ValueError): module.copy_fixed230(source, destination)
    assert original.read_bytes() == b'preserved'
    if where == 'destination': assert destination.is_symlink()
    else: assert not destination.exists()
