"""Synthetic transport/hold checks; these inputs are not live research pairs."""
from copy import deepcopy

import pytest

from bct import precursor_collection as collection, precursor_evidence_graph as graph
from bct.v4 import official_discovery as official
from test_precursor_source_pipeline import doc

AS_OF = '2026-10-08T17:30:00+00:00'


def timing_documents(*, ready='2029', coverage=True):
    buyer = collection.structure(doc(
        'Meridian signed firm new orders for military-grade tungsten for military drones '
        'in United States under contract K-242; total demand delivery required in 2028.',
        'Meridian', url='https://meridian.example/press-release/order'))
    covered = ' covers all committed demand' if coverage else ''
    maker = collection.structure(doc(
        'Atlas Metals production capacity for military-grade tungsten under contract K-242 '
        'is under construction; total qualified supply ready in '+ready+covered+'. '
        'Atlas Metals is a qualified manufacturer of tungsten.',
        'Atlas Metals', url='https://atlasmetals.example/press-release/capacity'))
    return [buyer, maker]


def scalar_pair():
    target = {k: {'normalized': v} for k, v in zip(official.TARGET,
              ('test device', 'grade a', 'region a', 'buyer a', 'pool a'))}
    demand = {'id': 'synthetic-buyer', 'source_fact_id': 'synthetic-buyer-fact',
              'target': target, 'role': 'DEMAND', 'state': 'SOURCE_BOUND_EVENT',
              'lineage': 'buyer', 'unit': 'units', 'period': '2028', 'actuality': 'ACTUAL',
              'quantity': 10, 'source_hash': 'buyerhash'}
    supply = {**demand, 'id': 'synthetic-maker', 'source_fact_id': 'synthetic-maker-fact',
              'role': 'SUPPLY', 'lineage': 'maker', 'source_hash': 'makerhash',
              'quantity': 5, 'qualified': True, 'coverage_complete': True}
    return [demand, supply]


def test_incomplete_target_retains_ids_first_blocker_and_secondary_missing_fields():
    document = collection.structure(doc(
        'Signed firm new orders for tungsten; delivery required in 2028.'))
    before = deepcopy(document)
    event, = document['precursor_events']
    result = graph.analyze([document], mode='SYNTHETIC', now=AS_OF)
    held, = result['blocked']
    assert held['event_id'] == event['event_id']
    assert held['document_id'] == document['document_id']
    assert held['observation_id'] in {o['observation_id'] for o in result['observations']}
    assert held['reason'] == 'INCOMPLETE_TARGET_SCOPE'
    assert held['first_blocker'] == 'NO_SOURCE_BOUND_SPECIFICATION'
    assert held['missing_fields'] == ['specification', 'region', 'customer_group', 'supply_pool']
    assert held['secondary_missing_fields'] == ['region', 'customer_group', 'supply_pool']
    assert held['missing_field_reasons']['supply_pool'] == 'NO_SOURCE_BOUND_SUPPLY_POOL'
    assert result['complete_target_events'] == result['independent_pairs'] == 0
    assert not result['protected_batch']['signals']
    assert document == before


def test_event_without_bound_observation_is_explicitly_held():
    document = collection.structure(doc('Signed firm new orders for tungsten in 2028.'))
    event, = document['precursor_events']
    document['retained_collection_events'] = []
    result = graph.analyze([document], mode='SYNTHETIC', now=AS_OF)
    held, = result['blocked']
    assert held['event_id'] == event['event_id']
    assert held['document_id'] == document['document_id']
    assert held['first_blocker'] == 'GRAPH_OBSERVATION_NOT_BOUND'
    assert held['observation_id'] is None
    assert not result['protected_batch']['signals']


def test_scalar_eligible_pair_has_explicit_source_binding_hold():
    events = scalar_pair()
    before = deepcopy(events)
    result = official.q3_input(events, [], as_of=AS_OF)
    assert result['structured_precheck_eligible_pairs'] == 1
    held, = result['structured_pair_blocks']
    assert held['demand_event'] == events[0]['id']
    assert held['supply_event'] == events[1]['id']
    assert held['first_blocker'] == 'STRUCTURED_PAIR_SOURCE_BINDING_REQUIRED'
    assert 'SOURCE_FACT_TO_GRAPH_EVENT_BINDING' in held['missing_contract']
    assert result['reasons']['STRUCTURED_PAIR_SOURCE_BINDING_REQUIRED'] == 1
    assert result['eligible_pairs'] == result['strict_engine_candidates'] == 0
    assert result['S2'] == result['S3'] == 0 and not result['formal_Q3_complete']
    assert events == before


def test_existing_source_bound_timing_route_reaches_forecast_without_quantities():
    documents = timing_documents()
    before = deepcopy(documents)
    evaluated = graph.analyze(documents, mode='SYNTHETIC', now=AS_OF)
    assert evaluated['pairs'][0]['comparison']['state'] == 'POSSIBLE_TIMING_GAP'
    assert all(s['quantity'] == 'UNKNOWN' for s in evaluated['protected_batch']['signals'])
    result = official.q3_input([], [], as_of=AS_OF, documents=documents)
    assert result['eligible_pairs'] == result['strict_engine_candidates'] == 1
    assert result['graph_forwarded_signals'] == 2
    assert result['S2'] == result['S3'] == 0 and not result['formal_Q3_complete']
    assert documents == before


def test_verified_dates_with_incomplete_qualified_supply_coverage_stay_supply_unknown():
    result = official.q3_input([], [], as_of=AS_OF, documents=timing_documents(coverage=False))
    assert result['graph_independent_pairs'] == 1
    assert result['graph_forwarded_signals'] == 2
    held, = result['graph_pair_blocks']
    assert held['reason'] == 'SUPPLY_UNKNOWN'
    assert held['first_blocker'] == 'QUALIFIED_ENTIRE_SUPPLY_SCOPE_UNPROVEN'
    assert held['missing_fields'] == ['coverage_complete']
    assert result['eligible_pairs'] == result['strict_engine_candidates'] == 0
    assert result['S2'] == result['S3'] == 0


def test_source_bound_ready_before_need_never_produces_forecast_candidate():
    result = official.q3_input([], [], as_of=AS_OF, documents=timing_documents(ready='2027'))
    assert result['eligible_pairs'] == result['strict_engine_candidates'] == 0
    assert result['S2'] == result['S3'] == 0


def test_target_block_trace_reaches_q3_caller():
    document = collection.structure(doc('Signed firm new orders for tungsten in 2028.'))
    result = official.q3_input([], [], as_of=AS_OF, documents=[document])
    held, = result['graph_blocked_events']
    assert held['event_id'] == document['precursor_events'][0]['event_id']
    assert held['reason'] == 'INCOMPLETE_TARGET_SCOPE'
    assert result['eligible_pairs'] == 0


@pytest.mark.parametrize('change', ['publisher', 'source_hash', 'target', 'planned', 'coverage'])
def test_structured_pair_prechecks_keep_existing_rejection_gates(change):
    events = scalar_pair()
    if change == 'publisher': events[1]['lineage'] = events[0]['lineage']
    elif change == 'source_hash': events[1]['source_hash'] = events[0]['source_hash']
    elif change == 'target':
        events[1]['target'] = deepcopy(events[1]['target'])
        events[1]['target']['region']['normalized'] = 'other region'
    elif change == 'planned': events[1]['actuality'] = 'PLAN'
    else: events[1]['coverage_complete'] = False
    result = official.q3_input(events, [], as_of=AS_OF)
    assert result['structured_precheck_eligible_pairs'] == 0
    assert not result['structured_pair_blocks']
    assert result['eligible_pairs'] == result['strict_engine_candidates'] == 0
    assert result['reasons']
    assert result['S2'] == result['S3'] == 0


def test_scalar_precheck_and_independent_graph_results_remain_distinct():
    # The graph-backed documents prove transport; unrelated scalar metadata
    # still lacks its own native-fact to graph-event binding contract.
    result = official.q3_input(scalar_pair(), [], as_of=AS_OF, documents=timing_documents())
    assert result['structured_precheck_eligible_pairs'] == 1
    assert result['structured_pair_blocks'][0]['state'] == 'BLOCKED'
    assert result['eligible_pairs'] == result['strict_engine_candidates'] == 1
    assert result['S2'] == result['S3'] == 0
