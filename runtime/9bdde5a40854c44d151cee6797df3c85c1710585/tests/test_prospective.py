"""LIVE wrapper functional fixtures; not observed forecasting performance."""
from datetime import datetime, timezone
import hashlib
import json

import pytest
from bct import prospective as p
from bct.objective_lock import stamp_export


@pytest.fixture
def live(tmp_path, monkeypatch):
    clock = [datetime(2030, 1, 1, tzinfo=timezone.utc)]
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]
    monkeypatch.setattr(p.engine, 'datetime', Clock)
    monkeypatch.setattr(p, '_now', lambda: clock[0].isoformat())
    feeds = tmp_path / 'feeds.yaml'
    feeds.write_text('feeds:\n  official: https://gov.example/feed\n')
    root = tmp_path / 'live'
    p.start(root, feeds)
    def day(n):
        clock[0] = datetime(2030, 1, n, tzinfo=timezone.utc)
    return root, day


def batch(suffix=''):
    docs, signals = [], []
    for name, role, body in [('buyer', 'DEMAND', 'Orders require transformers in June 2031.'),
                             ('maker', 'SUPPLY', 'Qualified transformer ramp available September 2031.')]:
        did = name + suffix
        docs.append({'document_id': did, 'body': body, 'body_sha256': hashlib.sha256(body.encode()).hexdigest(),
                     'published_at': '2030-01-01T00:00:00Z', 'available_at': '2030-01-01T00:00:00Z',
                     'origin_id': name, 'origin_url': 'https://' + name + '.example/original',
                     'origin_publisher': name, 'provenance_verified': True})
        signals.append({'document_id': did, 'locator': {'start': 0, 'end': len(body)},
                        'target_id': 'transformer', 'target': '230kV transformers', 'specification': '230kV',
                        'region': 'US', 'supply_pool': 'qualified US',
                        'period': {'start': '2031-06-01', 'end': '2031-12-31'}, 'basis': 'total',
                        'role': role, 'signal_type': 'committed_order' if role == 'DEMAND' else 'production_ramp',
                        'quantity': 'UNKNOWN', 'unit': 'units',
                        'need_date': '2031-06-01' if role == 'DEMAND' else None,
                        'available_date': '2031-09-01' if role == 'SUPPLY' else None,
                        'qualified': role == 'SUPPLY', 'coverage_complete': False})
    return stamp_export({'mode': 'LIVE', 'documents': docs, 'signals': signals})


def confirmation(day):
    body = 'A shortage of 230kV transformers is confirmed.'
    return stamp_export({'mode': 'LIVE', 'target_id': 'transformer', 'target': '230kV transformers',
        'explicit': True, 'document': {'document_id': 'confirmation-' + str(day),
            'body': body, 'body_sha256': hashlib.sha256(body.encode()).hexdigest(),
            'published_at': f'2030-01-{day:02}T00:00:00Z', 'url': 'https://gov.example/original',
            'publication_verified': True, 'publication_precision': 'TIMESTAMP'},
        'locator': {'start': 0, 'end': len(body)},
        'target_match': {'confirmed': True, 'target_id': 'transformer', 'target': '230kV transformers',
                         'reason': 'The explicit locator refers to the same 230kV specification.'}})


def first(root):
    return next((root / 'candidates').glob('*.json'))


def row(root):
    return p.report(root)['rows'][0]


def test_A_first_snapshot_immutable(live):
    root, day = live
    day(2); p.run(root, batch())
    before = first(root).read_bytes()
    day(3); result = p.run(root, batch('-followup'))
    assert result['first_frozen'] == 0
    assert first(root).read_bytes() == before
    assert first(root).stat().st_mode & 0o222 == 0


def test_B_followup_evidence_only_appends_history(live):
    root, day = live
    day(2); p.run(root, batch())
    day(3); result = p.run(root, batch('-followup'))
    assert result['history_appended'] == 1
    history = [p._read(x) for x in (root / 'candidate-history').glob('*/*.json')]
    assert len(history) == 1
    assert history[0]['candidate_followup']['evidence'][0]['document_id'].endswith('-followup')
    assert json.loads(first(root).read_text())['source_document_ids'] == ['buyer', 'maker']


def test_C_later_confirmation_preserves_first(live):
    root, day = live
    day(12); p.observe(root, confirmation(12))
    path = next((root / 'confirmations').glob('*.json')); before = path.read_bytes()
    day(14); p.observe(root, confirmation(14))
    assert path.read_bytes() == before
    assert row(root)['first_scope_confirmation_at'] == '2030-01-12T00:00:00Z'
    assert len(list((root / 'confirmation-history').glob('*/*.json'))) == 2
    assert p.observe(root, confirmation(14))['status'] == 'ALREADY_APPLIED'


def test_D_ten_days_early_success(live):
    root, day = live
    day(2); p.run(root, batch())
    day(12); p.observe(root, confirmation(12))
    assert row(root)['status'] == 'SUCCESS'
    assert row(root)['lead_time_days'] == 10


def test_E_two_days_late_missed(live):
    root, day = live
    day(2); p.observe(root, confirmation(2))
    day(4); p.run(root, batch())
    assert row(root)['status'] == 'MISSED_EARLY_DETECTION'
    assert row(root)['lead_time_days'] == -2


def test_F_no_candidate_no_detection(live):
    root, day = live
    day(2); p.observe(root, confirmation(2))
    assert row(root)['status'] == 'NO_DETECTION'


def test_G_no_confirmation_open(live):
    root, day = live
    day(2); p.run(root, batch())
    assert row(root)['status'] == 'OPEN'
    assert row(root)['T_global'] == 'UNKNOWN'


def test_H_backfill_cannot_mix_with_live(live):
    root, day = live
    for mode in ['BACKFILL', 'SYNTHETIC', 'HISTORICAL']:
        b = batch(); b['mode'] = mode
        with pytest.raises(p.Blocked): p.run(root, b)
        c = confirmation(2); c['mode'] = mode
        with pytest.raises(p.Blocked): p.observe(root, c)
    old = confirmation(2); old['document']['published_at'] = '2029-12-31T00:00:00Z'
    with pytest.raises(p.Blocked): p.observe(root, old)
    old = batch(); old['format'] = 'bct-forecast-discovery-v1'
    with pytest.raises(p.Blocked): p.run(root, old)
    assert not list((root / 'candidates').glob('*.json'))
    assert not list((root / 'confirmations').glob('*.json'))
    # Even an externally copied, correctly hashed non-LIVE record is blocked.
    p._write(root / 'candidates' / 'foreign.json', stamp_export({'mode': 'BACKFILL', 'target_id': 'old'}))
    with pytest.raises(p.Blocked, match='NON_LIVE_RECORD'): p.report(root)


def test_scope_does_not_restrict_operating_discovery(live):
    root, day = live
    day(2); assert p.run(root, batch())['first_frozen'] == 1
    # Buyer/maker sources outside confirmation domains still reach unchanged discovery.
    c = confirmation(2); c['document']['url'] = 'https://outside.example/article'
    with pytest.raises(p.Blocked, match='OUTSIDE_FROZEN'): p.observe(root, c)


def test_snapshot_tampering_or_deletion_is_blocked(live):
    root, day = live
    day(2); p.run(root, batch())
    path = first(root); path.chmod(0o600)
    before = path.read_text(); data = json.loads(before); data['candidate_first_detected_at'] = '2020-01-01T00:00:00Z'
    path.write_text(json.dumps(data))
    with pytest.raises(p.Blocked, match='INTEGRITY'): p.report(root)
    path.write_text(before); path.unlink()
    with pytest.raises(p.Blocked, match='MISSING'): p.report(root)


def test_earlier_late_observed_confirmation_blocks_success(live):
    root, day = live
    day(2); p.run(root, batch())
    day(12); p.observe(root, confirmation(12))
    p.observe(root, confirmation(5))
    assert row(root)['status'] == 'BLOCKED_EARLIER_SCOPE_CONFIRMATION'
    assert row(root)['lead_time_days'] is None


def test_start_idempotent_and_objective_mismatch_blocked(live):
    root, day = live
    before = (root / 'session.json').read_bytes()
    p.start(root, root.parent / 'feeds.yaml')
    assert (root / 'session.json').read_bytes() == before
    b = batch(); b['objective_sha256'] = 'wrong'
    with pytest.raises(ValueError): p.run(root, b)


def test_multiple_scopes_share_one_target_first_and_history(live):
    root, day = live
    b = batch()
    b['signals'] += [{**s, 'region': 'EU'} for s in b['signals']]
    day(2); assert p.run(root, b)['first_frozen'] == 1
    assert len(list((root / 'candidates').glob('*.json'))) == 1
    before = first(root).read_bytes()
    day(3); assert p.run(root, b)['history_appended'] == 1
    assert first(root).read_bytes() == before
    history = p._read(next((root / 'candidate-history').glob('*/*.json')))
    assert len(history['candidate_followups']) == 2
