"""Bounded artifact transport leaves the activated review judgment unchanged."""
import hashlib
import json
from pathlib import Path
import zipfile

import pytest


def test_current_capture_and_original_survive_without_expanding_unrelated_cache(tmp_path):
    from bct.review_artifact import extract_archive

    raw = b'current original'
    raw_hash = hashlib.sha256(raw).hexdigest()
    current = {'acquired_at': '2026-11-08T17:00:00Z', 'raw_sha256': raw_hash}
    old = {'acquired_at': '2026-10-08T17:00:00Z', 'raw_sha256': 'a' * 64}
    archive = tmp_path / 'cache.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as saved:
        saved.writestr('captures/current.json', json.dumps(current))
        saved.writestr('captures/old.json', json.dumps(old))
        saved.writestr('raw/' + raw_hash + '.html', raw)
        saved.writestr('raw/' + 'a' * 64 + '.html', b'old original')
        # This unrelated member exceeds the entire permitted extraction budget.
        saved.writestr('evaluations/huge.json', b'x' * 100_000)
    before = archive.read_bytes()
    destination = tmp_path / 'selected'
    receipt = extract_archive(archive, destination, '2026-11-08T16:30:49Z', max_expanded=4096)
    assert (destination / 'captures/current.json').read_text() == json.dumps(current)
    assert (destination / ('raw/' + raw_hash + '.html')).read_bytes() == raw
    assert not (destination / 'evaluations').exists()
    assert not (destination / 'captures/old.json').exists()
    assert not (destination / ('raw/' + 'a' * 64 + '.html')).exists()
    assert archive.read_bytes() == before
    assert receipt['selected_captures'] == 1 and receipt['selected_raw_files'] == 1


def test_budget_failure_leaves_existing_source_and_destination_untouched(tmp_path):
    from bct.review_artifact import extract_archive

    archive = tmp_path / 'cache.zip'
    with zipfile.ZipFile(archive, 'w') as saved:
        saved.writestr('captures/current.json', json.dumps({'acquired_at': '2026-11-08T17:00:00Z'}))
    destination = tmp_path / 'selected'
    with pytest.raises(ValueError, match='EXPANDED_LIMIT'):
        extract_archive(archive, destination, '2026-11-08T16:30:49Z', max_expanded=1)
    assert not destination.exists() and archive.is_file()
    destination.mkdir()
    original = destination / 'existing'
    original.write_bytes(b'preserved')
    with pytest.raises(ValueError, match='DESTINATION_EXISTS'):
        extract_archive(archive, destination, '2026-11-08T16:30:49Z')
    assert original.read_bytes() == b'preserved'


def test_duplicate_selected_member_and_archive_traversal_are_rejected(tmp_path):
    from bct.review_artifact import extract_archive

    archive = tmp_path / 'cache.zip'
    with zipfile.ZipFile(archive, 'w') as saved:
        saved.writestr('captures/../escape.json', '{}')
    with pytest.raises(ValueError, match='UNSAFE_CAPTURE_PATH'):
        extract_archive(archive, tmp_path / 'selected', '2026-11-08T16:30:49Z')
    assert not (tmp_path / 'selected').exists()


def test_download_is_blocked_before_network_when_disk_reserve_is_missing(tmp_path, monkeypatch):
    from bct import review_artifact

    monkeypatch.setattr(review_artifact.shutil, 'disk_usage', lambda path: (1000, 999, 1))
    with pytest.raises(ValueError, match='INSUFFICIENT_DISK'):
        review_artifact.download('owner/repo', '123', 500, tmp_path / 'cache.zip')
    assert not (tmp_path / 'cache.zip').exists()


def test_subset_handoff_matches_existing_full_cache_source_verification(tmp_path, monkeypatch):
    from bct import precursor_collection as collection, review_shadow as shadow
    from bct.review_artifact import extract_archive
    from test_precursor_collection import html, manifest

    cache = tmp_path / 'source'
    delta = manifest(['buyer'])
    url = delta['documents'][0]['url']
    raw = html('buyer', 'The customer signed firm orders for 100 units in 2031. Facility PX-1 is commissioning.')
    monkeypatch.setattr(collection.acquisition, 'fetch', lambda u: (raw, u, 200, 'text/html'))
    monkeypatch.setattr(collection.acquisition, 'now', lambda: '2026-10-05T03:00:00+00:00')
    activation = collection.init(cache, delta)
    capture = collection.capture(cache, url, 'buyer', activation,
                                 collected_at=delta['documents'][0]['collected_at'])
    assert capture['provenance'] == 'PASS'
    archive = tmp_path / 'cache.zip'
    with zipfile.ZipFile(archive, 'w') as saved:
        for path in cache.rglob('*'):
            if path.is_file():
                saved.write(path, path.relative_to(cache))
        saved.writestr('evaluations/huge.json', b'x' * 100_000)
    original_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    selected = tmp_path / 'selected'
    extract_archive(archive, selected, delta['collection_started_at'])
    delta_path = tmp_path / 'delta.json'
    delta_path.write_text(json.dumps(delta))
    complete = shadow.handoff(delta_path, cache, tmp_path / 'complete-handoff')
    bounded = shadow.handoff(delta_path, selected, tmp_path / 'bounded-handoff')
    assert complete['documents'] == bounded['documents']
    assert len(bounded['documents']) == 1 and bounded['skipped'] == complete['skipped'] == []
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == original_hash
