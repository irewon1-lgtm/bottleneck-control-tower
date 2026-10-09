"""Same-source facts, source eligibility and scoped temporal falsification."""
from copy import deepcopy
import pytest
from bct import precursor_collection as c, precursor_evidence_graph as g
from bct import precursor_scope_reader as s, precursor_temporal as t
from test_precursor_source_pipeline import doc
from test_precursor_evidence_graph import pair, ASOF


def test_literal_multiple_products_survive_without_target_union():
    d=c.structure(doc('Integrated optical engines and detachable fiber connectors support enterprise AI customers.'))
    obs=g.observations(d)
    assert {'Integrated optical engines','detachable fiber connectors'} <= {f['value'] for o in obs for f in o['literal_fields'].get('product',[])}
    assert not any(o['fields'] for o in obs)
    assert not g.analyze([d],mode='SYNTHETIC',now=ASOF)['protected_result']['candidates']


def test_compound_wafer_substrate_and_purchase_object_model():
    d=c.structure(doc('Signed new orders for InP wafer substrates.'))
    assert d['precursor_events'][0]['scope']['product']['value']=='wafer substrates'
    d=c.structure(doc('A provider of burn-in solutions for semiconductor devices received a production order from its lead silicon photonics customer for a fully automated FOX-XP multi-wafer burn-in system.'))
    assert d['precursor_events'][0]['scope']['product']['value']=='FOX-XP'
    assert d['precursor_events'][0]['scope']['customer_group']['customer_identity_status'].startswith('UNNAMED')


def test_unnamed_customer_description_is_literal_not_an_identity_key():
    d=c.structure(doc('Signed a new order from a major new customer that is a global leader in networking products and solutions and a major supplier to data centers.'))
    facts=[f for o in g.observations(d) for f in o['literal_fields'].get('customer_group',[])]
    assert any(f['value']=='a global leader in networking products and solutions' for f in facts)
    assert not g.analyze([d],mode='SYNTHETIC',now=ASOF)['protected_result']['candidates']


def test_chips_act_is_not_an_equipment_model():
    d=c.structure(doc('The CHIPS Act funds chip manufacturing in the U.S.'))
    assert not any(f['value']=='CHIPS' for o in g.observations(d) for f in o['literal_fields']['product'])


def test_tungsten_concentrate_and_metal_powder_are_distinct_products():
    a=c.structure(doc('Signed new orders for tungsten concentrate under contract K-242 in 2028.'))
    b=c.structure(doc('Qualified production capacity for tungsten metal powder under contract K-242 is ready in 2029.','other'))
    assert a['precursor_events'][0]['scope']['product']['value']=='tungsten concentrate'
    assert b['precursor_events'][0]['scope']['product']['value']=='tungsten metal powder'
    assert not g.build([a,b])['edges']


@pytest.mark.parametrize('field,value',[
    ('available_at','2026-12-01T00:00:00+00:00'),
    ('published_at','2026-12-01T00:00:00+00:00'),
])
def test_future_scope_support_cannot_complete_a_past_target(field,value):
    b,su=pair()
    su=c.structure(doc(su['body'].split(' Atlas Metals is')[0],'Atlas Metals',url=su['origin_url']))
    support=doc('Atlas Metals is a qualified manufacturer of military-grade tungsten under contract K-242.','Certifier',url='https://certifier.gov/notices/qualification')
    good=c.structure(support)
    assert len(g.analyze([b,su,good],mode='SYNTHETIC',now=ASOF)['protected_result']['candidates'])==1
    support[field]=value;support=c.structure(support)
    assert not g.analyze([b,su,support],mode='SYNTHETIC',now=ASOF)['protected_result']['candidates']


def test_unnamed_customer_cannot_cross_model_only_identity_link():
    a=c.structure(doc('Signed new orders for Axon27 gas turbines for the lead military customer in United States. Axon27 gas turbines are manufactured by Atlas Metals.','Meridian'))
    b=c.structure(doc('Atlas Metals manufactures Axon27 gas turbines for the lead military customer in United States.','Atlas Metals'))
    graph=g.build([a,b])
    # A relative "lead customer" of each issuer is not a verified same buyer.
    assert not any(e['references'][0]['document_id']!=e['references'][1]['document_id'] for e in graph['edges'])


def test_iso_quality_system_is_not_product_customer_qualification():
    d=c.structure(doc('Signed new orders for tungsten for military drones. Tungsten is supplied by Atlas Metals, an ISO 9001 certified company.'))
    assert 'supply_pool' not in d['precursor_events'][0]['scope']


def time_pair(need='2028',ready='2029'):
    d={'scope':{'product':'tungsten','specification':'military-grade','region':'US','customer_group':'military drones','supply_pool':'Atlas'},
       'temporal_facts':{'periods':[{**t.bounds(need),'fact_kind':'DEMAND_NEED'}],'quantities':[]}}
    su={'scope':deepcopy(d['scope']),'qualified':True,
        'temporal_facts':{'periods':[{**t.bounds(ready),'fact_kind':'SUPPLY_READY'}],'quantities':[]}}
    return d,su


def test_incomplete_same_scope_is_unknown_even_when_dicts_equal():
    d,su=time_pair();d['scope'].pop('customer_group');su['scope'].pop('customer_group')
    assert t.compare(d,su,require_complete_scope=True)['state']=='UNKNOWN'


def test_pending_qualification_and_qualification_start_are_not_ready_dates():
    d=c.structure(doc('Production capacity for tungsten is under construction and customer qualification starts in 2029.'))
    facts=d['precursor_events'][0]['temporal_facts']
    assert not any(p['fact_kind'] in ('SUPPLY_READY','QUALIFICATION') for p in facts['periods'])


def test_unrelated_percentage_does_not_prevent_valid_physical_comparison():
    d,su=time_pair()
    d['temporal_facts']['quantities']=[{'unit':'percent','rate':False,'fact_kind':'YIELD_OR_PERCENT_REQUIRES_ATTRIBUTION'}]
    assert t.compare(d,su)['state']=='POSSIBLE_TIMING_GAP'


def test_quantity_gap_requires_same_basis_not_only_same_unit():
    d,su=time_pair(ready='2027');period=t.bounds('2028')
    d['temporal_facts']['quantities']=[{'unit':'units/year','rate':True,'fact_kind':'ORDER_QUANTITY','period':period,'value':100,'basis':'DELIVERED_GOOD_UNITS'}]
    su['temporal_facts']['quantities']=[{'unit':'units/year','rate':True,'fact_kind':'UNRESERVED_CAPACITY','qualification_status':'SOURCE_ASSERTED','coverage':'UNRESERVED','period':period,'value':80,'basis':'NAMEPLATE_INPUT_UNITS'}]
    assert t.compare(d,su)['state']=='UNKNOWN'


def test_physical_supply_shortfall_is_not_claimed_from_missing_quantity():
    d,su=time_pair();result=t.compare(d,su)
    assert result['state']=='POSSIBLE_TIMING_GAP'
    assert result.get('quantitative_shortage')=='UNKNOWN'


def test_period_kind_uses_nearest_role_not_distant_construction():
    d=c.structure(doc('Production capacity for tungsten will start in 2029, but delivery is required in 2028.'))
    ps=d['precursor_events'][0]['temporal_facts']['periods']
    assert [p['fact_kind'] for p in ps]==['SUPPLY_READY','DEMAND_NEED']


def test_relative_duration_cannot_borrow_another_clauses_contract_anchor():
    d=c.structure(doc('Signed new orders under a contract effective 2026-10-01; delivery requires within 18 months; production ready 24 months after the contract.'))
    ps=d['precursor_events'][0]['temporal_facts']['periods']
    eighteen=next(p for p in ps if p.get('months')==18)
    twentyfour=next(p for p in ps if p.get('months')==24)
    assert eighteen['start']=='UNKNOWN'
    assert twentyfour['start']=='2028-10-01'
