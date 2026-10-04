import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest


spec = importlib.util.spec_from_file_location(
    'live_document_snapshot',
    Path(__file__).resolve().parents[1] / '.github/scripts/live_document_snapshot.py')
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


def test_source_inputs_preserve_metadata_and_exact_cache(tmp_path):
    db = tmp_path / 'source.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE radar_items (id TEXT, external_id TEXT, url TEXT, '
                     'source TEXT, published_at TEXT, collected_at TEXT, snippet TEXT)')
        conn.execute('INSERT INTO radar_items VALUES (?,?,?,?,?,?,?)',
                     ('doc', 'feed-id', 'https://example.org/article', 'example.org',
                      '2026-10-04', '2026-10-04T10:00:00Z', 'Original feed summary'))
    before = db.read_bytes()
    body = ('Original paragraph.\n' * 500).encode()
    digest = hashlib.sha256(body).hexdigest()
    output = tmp_path / 'artifact'
    (output / 'body-cache').mkdir(parents=True)
    cache = output / 'body-cache' / (digest + '.txt')
    cache.write_bytes(body)
    record = {'id': 'doc', 'body_sha256': digest, 'source_version': 'source-v1',
              'origin_id': None, 'origin_url': None, 'origin_publisher': None,
              'provenance_verified': False, 'publication_verified': False,
              'available_at': '2026-10-04T10:02:00Z', 'versions': {digest: {'body_sha256': digest}}}
    result = {'results': {'doc': record}}
    snapshot.preserve_source_inputs(db, output, result, ['doc'], 'pinned-revision')
    stored = json.loads((output / 'source-inputs.json').read_text())['documents'][0]
    assert stored['upstream_row']['external_id'] == 'feed-id'
    assert stored['upstream_row']['snippet'] == 'Original feed summary'
    assert stored['upstream_row']['url'] == 'https://example.org/article'
    assert stored['snapshot_metadata'] == record
    assert (output / stored['body_path']).read_bytes() == body
    assert db.read_bytes() == before
    cache.write_bytes(b'corrupted cache')
    with pytest.raises(ValueError, match='snapshot body hash mismatch'):
        snapshot.preserve_source_inputs(db, output, result, ['doc'], 'pinned-revision')


def test_collection_retains_existing_feed_id_and_snippet(tmp_path):
    from bct.future_bottleneck import run

    db = tmp_path / 'source.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE radar_items (id, title, url, source, collected_at, '
                     'updated_at, status, external_id, snippet, published_at)')
        conn.execute('INSERT INTO radar_items VALUES (?,?,?,?,?,?,?,?,?,?)',
                     ('doc', 'Original title', 'https://example.org/article', 'example.org',
                      '2026-10-01T10:00:00Z', 'v1', 'active', 'original-feed-id',
                      'Original feed summary', '2026-10-01'))
    before = db.read_bytes()
    result = run(db, tmp_path / 'result.json', limit=1, workers=1,
                 document_ids=['doc'],
                 fetcher=lambda url: '<article><p>Original source paragraph.</p></article>')
    record = result['results']['doc']
    assert record['external_id'] == 'original-feed-id'
    assert record['snippet'] == 'Original feed summary'
    assert record['published_at'] == '2026-10-01'
    assert record['origin_publisher'] is None
    assert record['provenance_verified'] is False
    assert db.read_bytes() == before
