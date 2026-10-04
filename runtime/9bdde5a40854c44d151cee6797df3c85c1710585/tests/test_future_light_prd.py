"""PRD synthetic functional gates. These are never forecast-performance labels."""
import pytest

from bct.future_bottleneck import screen
from bct.future_hypothesis import classify_public, compare_gap, extract_facts, hypothesis_patch, outcome_update, performance_report
from bct.future_store import PatchError, apply_owned_patch


SCOPE = '(spec: Grade A; region: US; supply pool: US qualified pool; period: 2027-01-01 to 2027-12-31; basis: total)'


def docs(*bodies):
    import hashlib
    records = {}
    for i, body in enumerate(bodies):
        s = screen(body)
        sha = hashlib.sha256(body.encode()).hexdigest()
        records[str(i)] = {**s, **extract_facts(body, s), 'id': str(i), 'body_sha256': sha,
            'body_chars': len(body), 'body_status': 'FULL', 'url': f'https://example.org/{i}',
            'collected_at': '2026-10-02T00:00:00Z', 'queue_entered_at': '2026-10-02T00:00:00Z'}
    return {'results': records}


def generated(state):
    p = hypothesis_patch(state, {}, now='2026-10-02T12:00:00Z', mode='SYNTHETIC')
    return apply_owned_patch(state, owner='bundle', patch=p, operation_id='generate')


@pytest.mark.parametrize('body,name,path', [
    ('Orders for zirconium optical sleeves increased by 40 percent in 2027.', 'zirconium optical sleeves', 'DEMAND'),
    ('Production of zirconium optical sleeves was halted after the plant closed.', 'zirconium optical sleeves', 'SUPPLY'),
    ('Certification of zirconium optical sleeves was delayed until 2028.', 'zirconium optical sleeves', 'SUPPLY'),
])
def test_prd_stage1_open_discovery(body, name, path):
    result = screen(body)
    assert result['candidate'] and path in result['discovery_paths']
    assert name in [x['name'].lower() for x in result['targets']]
    assert result['bottleneck_tags'] == []
    assert result['final_bottleneck'] is None


def test_prd_stage1_unknown_target_and_keyword_tag_retained():
    assert screen('The factory will close next year.')['candidate']
    result = screen('Orders for zirconium optical sleeves increased. A future bottleneck is possible.')
    assert result['candidate'] and result['bottleneck_tags'] == ['bottleneck']


def test_prd_stage2_auto_draft_without_target_dictionary_or_person():
    state = generated(docs(f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.',
        f'Total qualified supply for zirconium optical sleeves {SCOPE} is 100 units including all qualified suppliers, usable inventory and alternative suppliers.'))
    assert len(state['hypotheses']) == 1
    h = next(iter(state['hypotheses'].values()))
    assert h['current']['draft']['kind'] == 'INFERENCE'
    assert h['current']['draft']['facts']['DEMAND'] and h['current']['draft']['facts']['SUPPLY']
    assert all('locator' in f and 'document_id' in f for f in h['current']['evidence'])


@pytest.mark.parametrize('replace', [('Grade A', 'Grade B'), ('US qualified pool', 'other qualified pool'), ('region: US', 'region: EU')])
def test_prd_stage2_incompatible_scope_never_merges(replace):
    scope2 = SCOPE.replace(*replace)
    state = generated(docs(f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.',
        f'Production of zirconium optical sleeves {scope2} was halted.'))
    assert len(state['hypotheses']) == 2


def test_prd_stage2_reprint_and_same_order_not_added_as_new_demand():
    body = f'Orders for zirconium optical sleeves {SCOPE} increased to 70 units under contract Z100.'
    state = generated(docs(body, body))
    h = next(iter(state['hypotheses'].values()))
    assert len([f for f in h['current']['evidence'] if f['role'] == 'DEMAND']) == 1
    assert h['current']['draft']['comparison_missing']


def test_prd_stage2_documented_relationship_expands_one_hop_only():
    state = generated(docs('Orders for quantum storage racks increased.',
        'zirconium optical sleeves are used in quantum storage racks.',
        'ceramic pellets are used in zirconium optical sleeves.'))
    h = next(iter(state['hypotheses'].values()))
    assert len(h['current']['related_evidence']) == 1
    assert h['current']['related_evidence'][0]['component'] == 'zirconium optical sleeves'
    assert h['current']['stage'] != 'S3'


@pytest.mark.parametrize('demand,supply,stage,gap', [
    (120, 150, 'S2', 'FALSE'),
    (120, 100, 'S3', 'TRUE'),
])
def test_prd_stage3_actual_matched_supply_comparison(demand, supply, stage, gap):
    state = generated(docs(f'Total demand for zirconium optical sleeves {SCOPE} increased to {demand} units.',
        f'Total qualified supply for zirconium optical sleeves {SCOPE} is {supply} units including all qualified suppliers, usable inventory and alternative suppliers.'))
    h = next(iter(state['hypotheses'].values()))
    assert h['current']['stage'] == stage and h['current']['gates']['supply_gap'] == gap


@pytest.mark.parametrize('bodies', [
    [f'Production of zirconium optical sleeves {SCOPE} was halted.'],
    [f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.',
     f'Certification of zirconium optical sleeves {SCOPE} was delayed.',
     f'Total qualified supply for zirconium optical sleeves {SCOPE} is 150 units including all qualified suppliers, usable inventory and alternative suppliers.'],
    [f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.',
     f'Total qualified supply for zirconium optical sleeves {SCOPE} is 100 units at one supplier.'],
])
def test_prd_stage3_closure_alternative_supply_missing_market_coverage(bodies):
    state = generated(docs(*bodies))
    assert all(h['current']['stage'] != 'S3' for h in state['hypotheses'].values())


def test_prd_stage3_timing_gap_and_unknown_or_conflicting_figures():
    state = generated(docs(f'Total demand for zirconium optical sleeves {SCOPE} increased, needed by 2027-06-01.',
        f'Total qualified supply for zirconium optical sleeves {SCOPE} is available from 2028-01-01 including all qualified suppliers, usable inventory and alternative suppliers.'))
    h = next(iter(state['hypotheses'].values()))
    assert h['current']['stage'] == 'S3'
    facts = h['current']['evidence']
    supply = next(f for f in facts if f['role'] == 'SUPPLY')
    supply['available_date'] = None
    assert compare_gap(facts, now='2026-10-02T00:00:00Z')['gates']['supply_gap'] == 'UNKNOWN'


def test_prd_stage3_reservations_basis_and_units_cannot_mix():
    state = generated(docs(f'Additional demand for zirconium optical sleeves {SCOPE.replace("basis: total", "basis: additional")} increased to 120 units.',
        f'Total qualified supply for zirconium optical sleeves {SCOPE} is 100 units including all qualified suppliers, usable inventory and alternative suppliers.'))
    assert all(h['current']['stage'] != 'S3' for h in state['hypotheses'].values())


def test_prd_stage3_capex_never_becomes_component_quantity():
    state = generated(docs('The customer invested 100000000 dollars. Orders for zirconium optical sleeves increased.'))
    assert all(f['quantity'] is None for h in state['hypotheses'].values() for f in h['current']['evidence'])


def test_prd_stage3_static_numbers_do_not_satisfy_change_gate():
    state = generated(docs(f'Total demand for zirconium optical sleeves {SCOPE} is 120 units.',
        f'Total qualified supply for zirconium optical sleeves {SCOPE} is 100 units including all qualified suppliers, usable inventory and alternative suppliers.'))
    assert all(h['current']['stage'] != 'S3' for h in state['hypotheses'].values())
    assert all(h['current']['gates']['change'] == 'UNKNOWN' for h in state['hypotheses'].values())


def test_prd_stage3_incomplete_review_period_stays_unknown_without_crashing():
    from bct.future_review import _earned_stage
    gate = {'value': 'TRUE', 'evidence': [{'locator': 'source paragraph'}]}
    review = {'target': 'zirconium optical sleeves', 'discovery_path': 'DEMAND',
              'as_of': '2026-10-02', 'temporal_status': 'FUTURE',
              'period': {'start': '2027-01-01', 'end': '2027-12-31'},
              'gates': {k: gate for k in ('change', 'target_relation', 'future_demand',
                         'supply_constraint', 'future_period', 'relief_reviewed')},
              'relief': {'alternatives': {'status': 'FOUND', 'reason': 'checked', 'resolved': True}},
              'comparison': {'facts': [{'period': 'UNKNOWN'}]}}
    assert _earned_stage(review) == 'S2'


def test_prd_stage3_different_target_comparison_cannot_promote_review():
    from bct.future_review import _earned_stage
    state = generated(docs(f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.',
        f'Total qualified supply for zirconium optical sleeves {SCOPE} is 100 units including all qualified suppliers, usable inventory and alternative suppliers.'))
    gate = {'value': 'TRUE', 'evidence': [{'locator': 'source paragraph'}]}
    review = {'target': 'other laser components', 'discovery_path': 'DEMAND',
              'as_of': '2026-10-02', 'temporal_status': 'FUTURE',
              'period': {'start': '2027-01-01', 'end': '2027-12-31'},
              'gates': {k: gate for k in ('change', 'target_relation', 'future_demand',
                         'supply_constraint', 'future_period', 'relief_reviewed')},
              'relief': {'alternatives': {'status': 'FOUND', 'reason': 'checked', 'resolved': True}},
              'comparison': {'facts': next(iter(state['hypotheses'].values()))['current']['evidence']}}
    assert _earned_stage(review) == 'S2'


def test_prd_stage4_first_detection_hypothesis_and_s3_are_different():
    from copy import deepcopy
    demand = f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.'
    supply = f'Total qualified supply for zirconium optical sleeves {SCOPE} is 100 units including all qualified suppliers, usable inventory and alternative suppliers.'
    state = generated(docs(demand))
    eid = next(iter(state['hypotheses']))
    assert 'first_s3' not in state['hypotheses'][eid]
    state['results']['1'] = docs(supply)['results']['0']
    state['results']['1']['id'] = '1'
    patch = hypothesis_patch(state, {}, now='2026-11-01T12:00:00Z', mode='SYNTHETIC')
    state = apply_owned_patch(state, owner='bundle', patch=patch, operation_id='s3')
    h = state['hypotheses'][eid]
    assert h['first_detected_at'] == h['first_hypothesis_at'] == '2026-10-02T12:00:00+00:00'
    assert h['first_s3']['at'] == '2026-11-01T12:00:00+00:00'
    original = deepcopy(h['first_s3'])
    assert hypothesis_patch(state, {}, now='2026-11-02T12:00:00Z', mode='SYNTHETIC')['hypotheses'] == {}
    # A later supply improvement changes current evidence but preserves the first S3.
    state['results']['1']['scope_facts'][0]['quantity'] = 150
    patch = hypothesis_patch(state, {}, now='2026-11-03T12:00:00Z', mode='SYNTHETIC')
    state = apply_owned_patch(state, owner='bundle', patch=patch, operation_id='relief')
    assert state['hypotheses'][eid]['current']['stage'] == 'S2'
    assert state['hypotheses'][eid]['first_s3'] == original
    assert len(state['hypotheses'][eid]['history']) == 3


def test_prd_stage4_period_edit_preserves_event_id_and_original_period():
    state = generated(docs(f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.'))
    eid = next(iter(state['hypotheses']))
    state['results']['0']['scope_facts'][0]['period']['end'] = '2028-12-31'
    patch = hypothesis_patch(state, {}, now='2026-11-01T12:00:00Z', mode='SYNTHETIC')
    assert list(patch['hypotheses']) == [eid]


def test_prd_stage4_recurring_gap_appends_history_without_rewriting_first_s3():
    from copy import deepcopy
    state = generated(docs(f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.',
        f'Total qualified supply for zirconium optical sleeves {SCOPE} is 100 units including all qualified suppliers, usable inventory and alternative suppliers.'))
    eid = next(iter(state['hypotheses']))
    original = deepcopy(state['hypotheses'][eid]['first_s3'])
    for day, quantity in [(3, 150), (4, 100)]:
        state['results']['1']['scope_facts'][0]['quantity'] = quantity
        patch = hypothesis_patch(state, {}, now=f'2026-10-0{day}T12:00:00Z', mode='SYNTHETIC')
        state = apply_owned_patch(state, owner='bundle', patch=patch, operation_id=f'cycle-{day}')
    assert state['hypotheses'][eid]['current']['stage'] == 'S3'
    assert state['hypotheses'][eid]['first_s3'] == original
    assert len(state['hypotheses'][eid]['history']) == 3
    assert len({h['id'] for h in state['hypotheses'][eid]['history']}) == 3


@pytest.mark.parametrize('mode', ['BACKFILL', 'SYNTHETIC'])
def test_prd_stage4_backfill_never_counts_as_live_pre_public(mode):
    first = {'at': '2026-10-02T12:00:00Z', 'detection_mode': mode}
    scan = {'frozen_scope': ['example.org'], 'complete': True, 'checked_through': '2026-10-03T00:00:00Z', 'evidence': ['scan manifest']}
    assert classify_public(first, [], scan) == 'UNKNOWN'


def test_prd_stage4_keyword_free_public_constraint_and_date_precision():
    first = {'at': '2026-10-02T12:00:00Z', 'detection_mode': 'LIVE'}
    source = {'same_event': True, 'explicit_constraint': True, 'publication_verified': True,
              'published_at': '2026-10-01T12:00:00Z', 'precision': 'TIMESTAMP',
              'locator': 'paragraph 1: no new order slots'}
    assert classify_public(first, [source], {}) == 'PUBLIC_AT_DETECTION'
    assert classify_public(first, [], {}) == 'UNKNOWN'
    source.update(published_at='2026-10-02', precision='DAY')
    assert classify_public(first, [source], {'complete': True}) == 'UNKNOWN'
    scan = {'frozen_scope': ['example.org'], 'complete': True, 'checked_through': '2026-10-03T00:00:00Z', 'evidence': ['manifest']}
    assert classify_public(first, [], scan) == 'PRE_PUBLIC'
    source.update(publication_verified=False)
    assert classify_public(first, [source], scan) == 'UNKNOWN'


def test_prd_stage4_verified_prior_public_confirmation_wins_over_ambiguous_same_day():
    first = {'at': '2026-10-02T12:00:00Z', 'detection_mode': 'LIVE'}
    ambiguous = {'same_event': True, 'explicit_constraint': True, 'publication_verified': True,
                 'published_at': '2026-10-02', 'precision': 'DAY', 'locator': 'no new order slots'}
    prior = {**ambiguous, 'published_at': '2026-09-30T12:00:00Z', 'precision': 'TIMESTAMP'}
    assert classify_public(first, [ambiguous, prior], {}) == 'PUBLIC_AT_DETECTION'


def test_prd_stage4_confirmed_then_relieved_preserves_actual_occurrence():
    period = {'start': '2027-01-01', 'end': '2027-12-31'}
    confirmed = outcome_update({}, {'status': 'CONFIRMED', 'at': '2027-03-02T00:00:00Z',
        'actual_started_at': '2027-03-01', 'same_scope': True, 'evidence': [{'locator': 'actual shortage report'}]}, period)
    relieved = outcome_update(confirmed, {'status': 'RELIEVED', 'at': '2027-04-01T00:00:00Z',
        'evidence': [{'locator': 'supply recovered'}]}, period)
    assert relieved['status'] == 'RELIEVED' and relieved['actual_occurred'] == 'TRUE'
    assert relieved['actual_started_at'] == '2027-03-01' and len(relieved['history']) == 2
    relieved_only = outcome_update({}, {'status': 'RELIEVED', 'at': '2027-04-01T00:00:00Z',
        'evidence': [{'locator': 'supply expanded'}]}, period)
    assert relieved_only['actual_occurred'] == 'UNKNOWN'
    with pytest.raises(ValueError, match='entire period'):
        outcome_update({}, {'status': 'DISCONFIRMED', 'actual_occurred': 'FALSE', 'at': '2028-01-01T00:00:00Z',
            'evidence': [{'locator': 'no news'}]}, period)


def test_prd_stage4_initial_hypothesis_cannot_be_overwritten_by_any_writer():
    state = generated(docs(f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.',
        f'Total qualified supply for zirconium optical sleeves {SCOPE} is 100 units including all qualified suppliers, usable inventory and alternative suppliers.'))
    eid = next(iter(state['hypotheses']))
    with pytest.raises(PatchError, match='immutable'):
        apply_owned_patch(state, owner='bundle', patch={'hypotheses': {eid: {'first_s3': {'at': '2020-01-01'}}}}, operation_id='bad')
    with pytest.raises(PatchError, match='another writer'):
        apply_owned_patch(state, owner='collection', patch={'hypotheses': {eid: {'current': {}}}}, operation_id='bad-owner')


def test_prd_stage4_synthetic_pass_never_becomes_forecast_performance():
    state = generated(docs(f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.',
        f'Total qualified supply for zirconium optical sleeves {SCOPE} is 100 units including all qualified suppliers, usable inventory and alternative suppliers.'))
    result = performance_report(state['hypotheses'])
    assert result['status'] == 'BLOCKED' and result['accuracy'] is None and result['recall'] is None
    assert result['forecast_pass'] is None


def test_prd_stage4_real_collection_cache_bundle_and_cas_roundtrip(tmp_path):
    import hashlib
    import json
    import sqlite3
    from bct.future_bottleneck import run
    from bct.future_review import ensure_bundle
    from bct.future_store import LocalJSONTransport, store_patch
    db_path, output = tmp_path / 'source.sqlite3', tmp_path / 'candidates.json'
    with sqlite3.connect(db_path) as db:
        db.execute('CREATE TABLE radar_items(id,title,url,source,collected_at,updated_at,status,published_at)')
        for i in range(2):
            db.execute('INSERT INTO radar_items VALUES(?,?,?,?,?,?,?,?)',
                (str(i), 'synthetic document', f'https://example.org/{i}', 'example.org', '2026-10-02T00:00:00Z', 'v1', 'active', '2026-10-01T00:00:00Z'))
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    bodies = [f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.',
        f'Total qualified supply for zirconium optical sleeves {SCOPE} is 100 units including all qualified suppliers, usable inventory and alternative suppliers.']
    calls = []
    def fetch(url):
        calls.append(url)
        return '<article><p>' + bodies[int(url[-1])] + '</p></article>'
    state = run(db_path, output, workers=1, fetcher=fetch, detection_mode='SYNTHETIC')
    assert all(r['publication_precision'] == 'TIMESTAMP' and r['publication_verified'] is False for r in state['results'].values())
    patch = ensure_bundle(state, {}, now='2026-10-02T12:00:00Z')
    saved = store_patch(LocalJSONTransport(), str(output), owner='bundle', patch=patch,
        operation_id='synthetic-bundle', prepared_document=state)
    assert saved.status == 'APPLIED'
    reread = json.loads(output.read_text())
    assert len(reread['hypotheses']) == 1 and next(iter(reread['bundles'].values()))['hypothesis_drafts']
    again = run(db_path, output, workers=1, fetcher=fetch)
    assert len(calls) == 2 and again['summary']['processed_this_run'] == 0
    assert again['hypotheses'] == reread['hypotheses']
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before


def test_prd_stage4_s1_prediction_does_not_freeze_s3_timing_or_reset_outcome():
    from copy import deepcopy
    from bct.future_review import READER_VERSION, review_patch
    state = generated(docs(f'Total demand for zirconium optical sleeves {SCOPE} increased to 120 units.',
        f'Total qualified supply for zirconium optical sleeves {SCOPE} is 100 units including all qualified suppliers, usable inventory and alternative suppliers.'))
    eid, hypothesis = next(iter(state['hypotheses'].items()))
    del state['hypotheses']  # This scenario exercises request-driven S3 without a prior automatic S3.
    doc = state['results']['0']
    gate = {'value': 'TRUE', 'evidence': [{'locator': 'synthetic whole document'}]}
    review = {'review_id': 'early', 'document_id': '0', 'body_sha256': doc['body_sha256'],
        'reader_version': READER_VERSION, 'kind': 'deep', 'read_start': 0, 'read_end': doc['body_chars'],
        'reviewed_at': '2026-10-02T00:00:00Z', 'as_of': '2026-10-02', 'disposition': 'DATA_INSUFFICIENT',
        'discovery_path': 'DEMAND', 'target': 'zirconium optical sleeves', 's_stage': 'S2', 'temporal_status': 'FUTURE',
        'period': {'start': '2027-01-01', 'end': '2027-12-31'}, 'detection_mode': 'SYNTHETIC',
        'gates': {k: deepcopy(gate) for k in ('change', 'target_relation', 'future_demand', 'supply_constraint', 'future_period', 'relief_reviewed')},
        'relief': {'alternatives': {'status': 'FOUND', 'reason': 'included in matched total', 'important': True, 'resolved': True}},
        'comparison': {'facts': hypothesis['current']['evidence']},
        'prediction': {'target_id': eid, 'target': 'zirconium optical sleeves', 'hypothesis': 'first incomplete draft'}}
    review['gates']['supply_constraint'] = {'value': 'UNKNOWN', 'evidence': []}
    tracking = apply_owned_patch({}, owner='review', patch=review_patch(state, {}, review), operation_id='r-early')
    assert 'first_s3' not in tracking['prediction_ledger'][eid]
    review.update(review_id='s3', reviewed_at='2026-11-01T00:00:00Z', as_of='2026-11-01', s_stage='S3')
    review['gates']['supply_constraint'] = gate
    tracking = apply_owned_patch(tracking, owner='review', patch=review_patch(state, tracking, review), operation_id='r-s3')
    initial = deepcopy(tracking['prediction_ledger'][eid]['first_s3'])
    assert initial['at'] == '2026-11-01T00:00:00Z'
    review.update(review_id='confirmed', reviewed_at='2027-03-02T00:00:00Z', as_of='2027-03-02', s_stage='S2')
    review['prediction']['outcome_update'] = {'status': 'CONFIRMED', 'at': '2027-03-02T00:00:00Z',
        'actual_started_at': '2027-03-01', 'same_scope': True, 'evidence': [{'locator': 'actual report'}]}
    tracking = apply_owned_patch(tracking, owner='review', patch=review_patch(state, tracking, review), operation_id='r-confirmed')
    assert tracking['prediction_ledger'][eid]['outcome']['actual_occurred'] == 'TRUE'
    assert tracking['prediction_ledger'][eid]['first_s3'] == initial


def test_prd_stage4_review_bundle_reserves_old_and_new_and_keeps_excess():
    from bct.future_review import build_bundle
    state = docs('Orders for existing laser units increased.', 'Orders for existing laser units increased.',
                 'Orders for newly named optical sleeves increased.', 'Orders for existing laser units increased.')
    bundle = build_bundle(state, {'targets': [{'target': 'existing laser units'}]}, max_documents=2,
        now='2026-10-02T12:00:00Z')
    assert [r['document_id'] for r in bundle['documents']] == ['0', '2']
    assert len(state['results']) == 4


def test_operation_guard_seven_days_without_prd_budget_evidence_cannot_pass():
    """Synthetic guard coverage, never an actual seven-day operating trial."""
    from bct.future_hypothesis import CRITERIA_VERSION, POLICY, operation_report
    samples = [{'recorded_at': f'2026-10-{day:02d}T00:00:00Z', 'actual_execution': True,
                'criteria_version': CRITERIA_VERSION, 'fixed_policy': POLICY,
                **{k: 0 for k in ('inflow_total', 'completed_total', 'retries', 'material_wait',
                   'pending_total', 'oldest_wait_seconds', 'user_wait', 'system_wait')}} for day in range(2, 10)]
    report = operation_report(samples, now='2026-10-10T00:00:00Z')
    assert report['status'] == 'BLOCKED' and report['forecast_pass'] is None
    assert report['missing_evidence']
    for sample in samples:
        sample.update(collection_budget_verified=True, candidate_retention_verified=True,
                      source_wide_scan=True, review_bundle_budget_verified=True,
                      selection_reservations_verified=True, review_documents_total=1,
                      review_seconds_total=None)
    assert operation_report(samples, now='2026-10-10T00:00:00Z')['status'] == 'BLOCKED'
    samples[-1]['candidate_retention_verified'] = False
    assert operation_report(samples, now='2026-10-10T00:00:00Z')['status'] == 'FAIL'
