"""Source event identity and incomplete-target diagnostic preservation."""
from copy import deepcopy
from bct import precursor_collection as collection, precursor_evidence_graph as graph
from test_precursor_source_pipeline import doc
AS_OF = '2026-10-08T17:30:00+00:00'


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
