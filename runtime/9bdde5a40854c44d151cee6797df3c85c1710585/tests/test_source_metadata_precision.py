"""Boundary and common-path checks using the recovered official EIA snapshot."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import pytest

from bct import early_forecast, forecast_discovery
from bct.future_body import acquire_document, discovery_document, verified_source_metadata
from bct.future_bottleneck import run
from bct.objective_lock import stamp_export

FIXTURE = Path(__file__).resolve().parents[1] / 'docs/one-document-roundtrip-input.json'


def source_fixture():
    data = json.loads(FIXTURE.read_text())
    v = data['verification']
    v['provenance_evidence']['body_sha256'] = v['body_sha256']
    v.update(published_at=v['published_day'], publication_precision='DATE', publication_verified=True)
    v['publication_evidence'] = {'body_sha256': v['body_sha256'],
        'source_quote': 'Release Date: October 1, 2026', 'exact_time': 'UNKNOWN'}
    assert v['publication_evidence']['source_quote'] in data['body']
    return data


def operational_roundtrip(directory):
    """One document through acquisition, owned storage, cache screening and discovery."""
    data = source_fixture(); record = data['record']; body = data['body']; v = data['verification']
    db = directory / 'radar.sqlite3'; output = directory / 'candidates.json'; cache = directory / 'cache'
    observed = v['available_at']
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE radar_items(id TEXT,title TEXT,url TEXT,source TEXT,collected_at TEXT,updated_at TEXT,status TEXT,published_at TEXT)')
        c.execute('INSERT INTO radar_items VALUES(?,?,?,?,?,?,?,?)',
            (record['id'], 'Quarterly Coal Report', record['url'], 'EIA', observed, observed, 'active', None))
    # Only the already recovered body is delivered; no fetch or bulk run.
    def recovered(_):
        snapshot = record['acquisition']['versions'][record['source_version']]['latest']
        return {**snapshot, **v, 'body': body}
    first = run(db, output, limit=1, workers=1, cache_dir=cache, document_ids=[record['id']], fetcher=recovered)
    def offline(_):
        raise AssertionError('cache screening must not fetch')
    after = run(db, output, limit=1, workers=1, cache_dir=cache, document_ids=[record['id']],
                trigger='FILTER_CHANGED', fetcher=offline)
    saved = json.loads(output.read_text())['results'][record['id']]
    for state in (first, after):
        row = state['results'][record['id']]
        for k in ('origin_id', 'origin_url', 'origin_publisher', 'provenance_verified',
                  'published_at', 'publication_precision', 'publication_verified', 'available_at'):
            assert row[k] == v[k]
            assert row['versions'][v['body_sha256']][k] == v[k]
    document = discovery_document(saved, body)
    batch = stamp_export({'documents': [document], 'signals': data['signals'], 'confirmations': []})
    early = early_forecast.discover(batch)
    strict = forecast_discovery.discover(batch)
    return document, batch, early, strict


def test_real_snapshot_acquisition_storage_screening_discovery(tmp_path):
    document, batch, early, strict = operational_roundtrip(tmp_path)
    assert document['publication_precision'] == 'DATE'
    assert early['rejected_inputs'] == []
    assert early['outcomes'][0]['state'] == 'DATA_WAIT'
    # Strict resolves the same document, then rejects its historical inventory period.
    assert [r['reason'] for r in strict['rejected_inputs']] == ['period must be future']
    assert not early['candidates'] and not strict['candidates']
    broken = deepcopy(batch); broken['documents'][0]['provenance_verified'] = False
    before = early_forecast.discover(broken)
    assert before['rejected_inputs'][0]['reason'] == 'unverified original source'
    assert before['rejected_inputs'][1]['reason'] == repr(document['document_id'])


@pytest.mark.parametrize('engine', [early_forecast, forecast_discovery])
@pytest.mark.parametrize('day,blocked', [('2026-10-03', False), ('2026-10-04', True), ('2026-10-05', True)])
def test_date_cutoff_does_not_invent_a_publication_time(engine, day, blocked):
    data = source_fixture(); record = {**data['record'], **data['verification']}
    doc = discovery_document(record, data['body'])
    doc.update(published_at=day, available_at='2026-10-04T02:57:50+00:00')
    result = engine.discover(stamp_export({'documents': [doc], 'signals': [], 'confirmations': []}),
                             mode='SYNTHETIC', now='2026-10-04T23:59:59+00:00')
    assert bool(result['rejected_inputs']) is blocked
    if blocked:
        assert 'DATE publication not strictly before' in result['rejected_inputs'][0]['reason']
    assert doc['published_at'] == day


@pytest.mark.parametrize('published,available,reason', [
    ('2026-10-04T01:00:00+00:00', '2026-10-04T02:00:00+00:00', None),
    ('2026-10-04T04:00:00+00:00', '2026-10-04T04:00:00+00:00', 'not available'),
    ('2026-10-04T02:00:00+00:00', '2026-10-04T01:00:00+00:00', 'availability precedes'),
])
def test_exact_timestamp_cutoff_preserved(published, available, reason):
    doc = {'published_at': published, 'available_at': available, 'publication_precision': 'TIMESTAMP'}
    at = datetime(2026, 10, 4, 3, tzinfo=timezone.utc)
    if reason:
        with pytest.raises(ValueError, match=reason):
            forecast_discovery.publication_cutoff(doc, at)
    else:
        forecast_discovery.publication_cutoff(doc, at)


def test_provenance_needs_explicit_snapshot_bound_proof(tmp_path):
    data = source_fixture(); v = data['verification']; digest = v['body_sha256']
    assert verified_source_metadata(v, digest)['provenance_verified'] is True
    for field in ('provenance_evidence', 'origin_id', 'origin_publisher'):
        bad = deepcopy(v); bad.pop(field)
        assert 'provenance_verified' not in verified_source_metadata(bad, digest)
    assert verified_source_metadata(v, 'different-body') == {}
    bare = {'origin_url': v['origin_url'], 'provenance_verified': True,
            'body': data['body'], 'body_status': 'FULL'}
    acquired = acquire_document(v['origin_url'], 'v1', {}, tmp_path, lambda _: bare)
    assert 'provenance_verified' not in acquired['metadata']
    assert 'publication_verified' not in acquired['metadata']


@pytest.mark.parametrize('engine', [early_forecast, forecast_discovery])
def test_missing_availability_is_blocked_without_crashing(engine):
    data = source_fixture()
    doc = discovery_document({**data['record'], **data['verification']}, data['body'])
    doc['available_at'] = None
    result = engine.discover(stamp_export({'documents': [doc], 'signals': [], 'confirmations': []}))
    assert result['rejected_inputs'][0]['reason'] == 'BLOCKED: availability UNKNOWN'


def test_cache_flags_without_snapshot_proof_cannot_promote_official_domain(tmp_path):
    doc, _, _, _ = operational_roundtrip(tmp_path)
    path = tmp_path / 'candidates.json'
    state = json.loads(path.read_text())
    def remove_proof(value):
        if isinstance(value, dict):
            for field in ('provenance_evidence', 'publication_evidence'):
                if isinstance(value.get(field), dict):
                    value[field].pop('body_sha256', None)
            for child in value.values():
                remove_proof(child)
        elif isinstance(value, list):
            for child in value:
                remove_proof(child)
    remove_proof(state)
    path.write_text(json.dumps(state))
    def offline(_):
        raise AssertionError('no fetch')
    result = run(tmp_path / 'radar.sqlite3', path, limit=1, workers=1,
                 cache_dir=tmp_path / 'cache', document_ids=[doc['document_id']],
                 trigger='FILTER_CHANGED', fetcher=offline)
    saved = result['results'][doc['document_id']]
    assert saved['provenance_verified'] is False
    assert saved['publication_verified'] is False
    assert saved['origin_id'] is None
