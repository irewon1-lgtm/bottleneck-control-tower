"""Operational cache-only screening preserves review and immutable versions."""
import hashlib
import json
import sqlite3
from copy import deepcopy

from bct.future_body import cache_body
from bct.future_bottleneck import run


def test_cached_snapshot_screening_clears_pending_without_fetch_or_version_duplication(tmp_path):
    body = 'Orders for power transformers increased.\nQualification of power transformers is delayed.'
    cache = tmp_path / 'cache'
    digest = cache_body(cache, body)
    url, updated = 'https://example.org/a', '2026-10-01T00:00:00+00:00'
    source = hashlib.sha256((url + updated).encode()).hexdigest()
    db = tmp_path / 'db.sqlite3'
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE radar_items(id TEXT,title TEXT,url TEXT,source TEXT,collected_at TEXT,updated_at TEXT,status TEXT)')
        c.execute('INSERT INTO radar_items VALUES(?,?,?,?,?,?,?)', ('doc', 'Title', url, 'source', updated, updated, 'active'))
    metadata = {'body_sha256': digest, 'body_status': 'PARTIAL', 'body_chars': len(body), 'extraction_method': 'ARTICLE'}
    state = {'version': 'body-candidate-v3', 'results': {'doc': {
        'id': 'doc', 'fingerprint': source, 'source_version': source, 'body_status': 'UNAVAILABLE',
        'current_body_sha256': digest, 'versions': {digest: metadata}, 'screening_pending_for': 'pending',
        'acquisition': {'versions': {source: {'latest': {'body_status': 'UNAVAILABLE'}, 'automatic_attempts': 3, 'history': []}}}
    }}, 'hypotheses': {'original': {'history': [{'id': 'first', 'stage': 'S2'}]}}}
    from bct.future_bottleneck import VERSION
    state['version'] = VERSION
    path = tmp_path / 'candidates.json'; path.write_text(json.dumps(state))
    frozen = deepcopy(state['hypotheses'])
    def offline(_):
        raise AssertionError('cache-only screening must not access the network')
    result = run(db, path, cache_dir=cache, document_ids=['doc'], trigger='FILTER_CHANGED', fetcher=offline)
    assert result['results']['doc']['screening_pending_for'] == ''
    assert list(result['results']['doc']['versions']) == [digest]
    assert (cache / (digest + '.txt')).read_text() == body
    assert result['hypotheses'] == frozen
    again = run(db, path, cache_dir=cache, document_ids=['doc'], trigger='FILTER_CHANGED', fetcher=offline)
    assert list(again['results']['doc']['versions']) == [digest]


def test_same_source_history_cache_hash_and_ledger_are_unchanged(tmp_path):
    from bct.future_bottleneck import _acquire_with_cache_snapshot
    body = 'A documented production ramp begins in 2028.'
    digest = cache_body(tmp_path, body)
    snapshot = {'body_status': 'FULL', 'body_sha256': digest, 'body_chars': len(body), 'extraction_method': 'ARTICLE'}
    ledger = {'versions': {'v1': {'automatic_attempts': 3, 'history': [snapshot], 'latest': {'body_status': 'UNAVAILABLE'}}}}
    frozen = deepcopy(ledger)
    result = _acquire_with_cache_snapshot('https://example.org/a', 'v1', ledger, tmp_path,
        lambda _: (_ for _ in ()).throw(AssertionError('no network')), prior_record={}, trigger='FILTER_CHANGED')
    assert result['body'] == body and result['metadata']['body_sha256'] == digest
    assert result['metadata']['body_status'] == 'FULL'
    assert result['ledger'] == ledger == frozen


def test_cache_from_another_source_version_is_not_used(tmp_path):
    from bct.future_bottleneck import _acquire_with_cache_snapshot
    digest = cache_body(tmp_path, 'Old snapshot.')
    prior = {'fingerprint': 'v1', 'current_body_sha256': digest, 'versions': {digest: {'body_sha256': digest, 'body_status': 'FULL'}}}
    r = _acquire_with_cache_snapshot('https://example.org/a', 'v2', {}, tmp_path,
        lambda _: (_ for _ in ()).throw(AssertionError('no network')), prior_record=prior, trigger='FILTER_CHANGED')
    assert r['body'] == '' and r['blocked'] == 'CACHE_UNAVAILABLE'


def test_existing_screening_locations_structured_without_inventing_target_quantity_or_dates():
    from bct.future_bottleneck import screen, _screening_scope_facts
    text = 'The factory plans an expansion.\nCustomers signed a transformer purchase contract.'
    facts = _screening_scope_facts(text, screen(text), [])
    assert facts and {'DEMAND', 'RELIEF'} <= {f['role'] for f in facts}
    assert all(f['quantity'] is None and f['need_date'] is None and f['available_date'] is None for f in facts)
    assert all(f['period'] == 'UNKNOWN' and not f['actual_statement'] and not f['coverage_complete'] for f in facts)
    assert any(f['target'] == 'UNKNOWN' for f in facts)
    assert _screening_scope_facts(text, screen(text), facts) == facts


def test_screening_confirmation_does_not_seed_new_precursor_facts():
    from bct.future_bottleneck import screen, _screening_scope_facts
    text = 'A shortage of power transformers delays orders as demand increases.'
    assert _screening_scope_facts(text, screen(text), []) == []


def test_demand_only_and_supply_only_never_generate_forecast_candidate():
    from bct.forecast_discovery import discover
    from bct.objective_lock import stamp_export
    for role, kind in [('DEMAND', 'committed_order'), ('SUPPLY', 'qualified_capacity')]:
        documents, signals = [], []
        for index in range(2):
            body = f'Origin {index} explicit precursor for this transformer.'
            documents.append({'document_id': str(index), 'body': body, 'body_sha256': hashlib.sha256(body.encode()).hexdigest(),
                'published_at': '2026-01-01T00:00:00Z', 'available_at': '2026-01-02T00:00:00Z',
                'provenance_verified': True, 'origin_id': str(index), 'origin_publisher': str(index),
                'origin_url': f'https://example{index}.org/doc'})
            signals.append({'document_id': str(index), 'target_id': 'transformer', 'target': 'transformer',
                'role': role, 'signal_type': kind, 'specification': 'HV', 'region': 'US', 'supply_pool': 'qualified',
                'period': {'start': '2031-01-01', 'end': '2031-12-31'}, 'locator': {'start': 0, 'end': len(body)},
                'quantity': 'UNKNOWN', 'unit': 'UNKNOWN', 'basis': 'total', 'qualified': True})
        result = discover(stamp_export({'documents': documents, 'signals': signals}), mode='SYNTHETIC', now='2026-10-04T00:00:00Z')
        assert result['candidates'] == [] and result['rejected'] == []
