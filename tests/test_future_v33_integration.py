import hashlib
import json
import sqlite3

from bct.future_bottleneck import run


def database(path, count=1):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE radar_items(id,title,url,source,collected_at,updated_at,status,source_type)')
        for n in range(count):
            db.execute("INSERT INTO radar_items VALUES(?,?,?,?,?,?,'active','NEWS')",
                       (str(n), 'title', str(n), 'source', f'2026-09-30T00:00:{n:02}', 'v1'))


def test_collection_preserves_every_other_writer_and_old_body_versions(tmp_path):
    db, output = tmp_path / 'db.sqlite3', tmp_path / 'future-candidates.json'
    database(db)
    original_db = hashlib.sha256(db.read_bytes()).hexdigest()
    body = '<article><p>Demand for transformers is growing.</p></article>'
    first = run(db, output, fetcher=lambda _: body)
    old_hash = first['results']['0']['body_sha256']
    first['unknown_root'] = {'keep': 1}
    first['results']['0']['unknown_extension'] = {'keep': 2}
    first['results']['0']['read_progress'] = {'end': 20}
    first['bundles'] = {'fixed': {'documents': [{'document_id': '0', 'body_sha256': old_hash}]}}
    output.write_text(json.dumps(first))
    with sqlite3.connect(db) as sql:
        sql.execute("UPDATE radar_items SET updated_at='v2'")
    original_db = hashlib.sha256(db.read_bytes()).hexdigest()
    second = run(db, output, fetcher=lambda _: '<article><p>Orders were cancelled.</p></article>')
    assert second['unknown_root'] == {'keep': 1}
    assert second['results']['0']['unknown_extension'] == {'keep': 2}
    assert second['results']['0']['read_progress'] == {'end': 20}
    assert old_hash in second['results']['0']['versions']
    assert second['bundles'] == first['bundles']
    assert second['results']['0']['current_body_sha256'] != old_hash
    assert hashlib.sha256(db.read_bytes()).hexdigest() == original_db


def test_filter_change_uses_private_cached_body_and_small_run_does_not_cap_documents(tmp_path):
    db, output = tmp_path / 'db.sqlite3', tmp_path / 'future-candidates.json'
    database(db, 4)
    calls = []
    def fetch(url):
        calls.append(url)
        return '<article><p>Orders grew.</p></article>'
    one = run(db, output, limit=2, fetcher=fetch)
    assert one['summary']['scope_articles'] == 4
    assert one['summary']['pending_due'] == 2
    two = run(db, output, limit=2, fetcher=fetch)
    assert len(two['results']) == 4
    assert len(calls) == 4
    changed = run(db, output, limit=4, filter_version='test-new-filter', fetcher=fetch)
    assert len(calls) == 4
    assert len(changed['results']) == 4
    assert all(r['attempts'] == 1 for r in changed['results'].values())
    assert all('body' not in r and 'body' not in v
               for r in changed['results'].values() for v in r['versions'].values())


def test_unread_and_partial_material_remain_queued_even_without_a_signal(tmp_path):
    db, output = tmp_path / 'db.sqlite3', tmp_path / 'future-candidates.json'
    database(db, 2)
    def fetch(url):
        if url == '0':
            raise TimeoutError('timed out')
        return '<main class="preview"><p>A short incomplete report.</p></main>'
    state = run(db, output, fetcher=fetch)
    assert all(r['material_check_required'] for r in state['results'].values())
    assert all(r.get('queue_entered_at') for r in state['results'].values())
    assert not any(r['candidate'] for r in state['results'].values())
    assert state['results']['0']['decision'] == 'UNREAD_MATERIAL'


def test_collection_envelope_keeps_the_preparation_context(tmp_path):
    db, output = tmp_path / 'db.sqlite3', tmp_path / 'future-candidates.json'
    change = tmp_path / 'collection-change.json'
    database(db)
    original = {'version': 'body-candidate-v3.3', 'results': {}, 'unknown_root': {'keep': 1}}
    output.write_text(json.dumps(original))
    state = run(db, output, patch_output=change,
                fetcher=lambda _: '<article><p>Orders grew.</p></article>')
    envelope = json.loads(change.read_text())
    assert envelope['prepared_document'] == original
    assert '0' in envelope['patch']['results']
    assert 'prepared_document' not in state
    assert state['unknown_root'] == original['unknown_root']


def test_expired_cache_and_exhausted_retry_never_erase_a_positive(tmp_path):
    from bct.future_review import queue_summary
    db, output = tmp_path / 'db.sqlite3', tmp_path / 'future-candidates.json'
    database(db)
    calls = []
    def fetch(url):
        calls.append(url)
        return '<article><p>Demand for transformers is growing.</p></article>'
    state = run(db, output, fetcher=fetch)
    record = state['results']['0']
    original_hash = record['body_sha256']
    original_signals = record['discovery_paths']
    record['attempts'] = 3
    record['acquisition']['versions'][record['source_version']]['automatic_attempts'] = 3
    output.write_text(json.dumps(state))
    for file in (tmp_path / '.future-body-cache').glob('*.txt'):
        file.unlink()
    changed = run(db, output, filter_version='new-filter', fetcher=fetch)
    result = changed['results']['0']
    assert result['candidate'] is True and result['discovery_paths'] == original_signals
    assert result['versions'][original_hash]['candidate'] is True
    assert result['material_check_required'] is True
    assert queue_summary(changed, {})['material_pending'] > 0
    assert len(calls) == 1
    assert run(db, output, filter_version='new-filter', fetcher=fetch)['summary']['processed_this_run'] == 0


def test_registered_target_is_connected_to_real_collection_and_cached_rescreen(tmp_path):
    db, output = tmp_path / 'db.sqlite3', tmp_path / 'future-candidates.json'
    database(db)
    calls = []
    def fetch(url):
        calls.append(url)
        return '<article><p>The Aurora product receives a new specification notice.</p></article>'
    state = run(db, output, fetcher=fetch)
    assert state['results']['0']['candidate'] is False
    tracking = tmp_path / 'future-tracking.json'
    tracking.write_text(json.dumps({'version': 1, 'targets': [{'id': 'aurora', 'target': 'Aurora', 'history': []}]}))
    state = run(db, output, tracking_path=tracking, fetcher=fetch)
    assert state['results']['0']['candidate'] is True
    assert state['results']['0']['tracked_matches'] == ['Aurora']
    assert len(calls) == 1
