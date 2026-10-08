"""Positive path and falsification cases; synthetic evidence is never LIVE gain."""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import pytest

from bct import precursor_collection as c,precursor_evidence_graph as g
from bct import precursor_temporal as t,precursor_scope_reader as s
from bct import precursor_source_search as search
from test_precursor_source_pipeline import doc

ASOF='2026-10-08T17:30:00+00:00'


def pair(need='2028',ready='2029',customer='military drones',spec='military-grade',contract='K-242'):
    buyer=c.structure(doc(f'Meridian signed firm new orders for {spec} tungsten for {customer} in United States under contract {contract}; delivery required in {need}.','Meridian',url='https://meridian.example/press-release/order'))
    supplier=c.structure(doc(f'Atlas Metals production capacity for military-grade tungsten under contract {contract} is under construction and qualified supply ready in {ready}. Atlas Metals is a qualified manufacturer of tungsten.','Atlas Metals',url='https://atlasmetals.example/press-release/capacity'))
    return buyer,supplier


def test_cross_document_scope_and_unchanged_protected_engine_positive():
    b,su=pair();before=deepcopy([b,su]);r=g.analyze([b,su],mode='SYNTHETIC',now=ASOF)
    assert [b,su]==before
    assert r['complete_target_events']==2 and r['independent_pairs']==1
    assert r['comparable_period_pairs']==1 and len(r['protected_result']['candidates'])==1
    demand=r['protected_batch']['signals'][0]
    assert demand['graph_attribute_evidence']['supply_pool']['reference']['document_id']=='Atlas Metals'
    assert demand['graph_relationship_proofs'] and r['reference_checks']>0
    assert c.hashes()==before_hashes()


def before_hashes():
    return {'precursor_discovery.py':'614e841938daf41e34d7e31b97ec636f06f2997c8b7b4252926dd135e5bc2639','early_forecast.py':'51d90d2265baec516d20383579816c5155e46c69599a8e7b281d329843d17675','forecast_discovery.py':'5a491f55f14a3fef675c0ca652042bb1cd8b76cb0de40c6f003d55181e2480fd','prospective.py':'6ca939e378ffb02323feecb869aa1aac0e9f7b56ec5cbc92689233e30d65a153'}


def test_product_only_same_company_or_geography_does_not_link():
    b,su=pair();su=c.structure(doc(su['body'].replace(' under contract K-242',''),'Atlas Metals',url=su['origin_url']))
    r=g.analyze([b,su],mode='SYNTHETIC',now=ASOF)
    assert not r['edges'] and not r['protected_result']['candidates']


@pytest.mark.parametrize('change',[
    ('military-grade','non-Chinese'),('tungsten','nickel'),('K-242','K-243')
])
def test_wrong_specification_product_or_contract_does_not_join(change):
    b,su=pair();su=c.structure(doc(su['body'].replace(*change),'Atlas Metals',url=su['origin_url']))
    r=g.analyze([b,su],mode='SYNTHETIC',now=ASOF)
    assert not r['protected_result']['candidates']


def test_same_product_different_customer_prevents_transitive_union():
    b,su=pair();other=c.structure(doc(b['body'].replace('military drones','industrial buyers'),'Other',url='https://other.example/press-release/order'))
    r=g.analyze([b,su,other],mode='SYNTHETIC',now=ASOF)
    assert not r['protected_result']['candidates']
    assert any(o['unknowns'].get('customer_group')=='CONNECTED_COMPONENT_CONFLICT' for o in r['observations'])


def test_same_contract_two_announcements_not_independent_capacity_fact():
    b,su=pair();se=deepcopy(su['precursor_events'][0]);se['source_quote']='contract K-242 delivery required in 2028'
    de=deepcopy(b['precursor_events'][0]);de['source_quote']='contract K-242 signed new orders in 2028'
    assert g._independent(de,se,{b['document_id']:b,su['document_id']:su})==(False,'SAME_CONTRACT_EVENT')


def test_duplicate_issuer_copied_document_not_independent():
    b,su=pair();su=c.structure({**su,'origin_publisher':'Meridian'})
    assert not g.analyze([b,su],mode='SYNTHETIC',now=ASOF)['protected_result']['candidates']
    assert not g._independent(b['precursor_events'][0],su['precursor_events'][0],{b['document_id']:b,su['document_id']:su})[0]


def test_expansion_only_or_tam_only_not_a_candidate():
    b,su=pair()
    assert not g.analyze([su],mode='SYNTHETIC',now=ASOF)['protected_result']['candidates']
    b=c.structure(doc(b['body'].replace('signed firm new orders','forecasts TAM of'),'Meridian',url=b['origin_url']))
    assert not g.analyze([b,su],mode='SYNTHETIC',now=ASOF)['protected_result']['candidates']


@pytest.mark.parametrize('text',[
    'Atlas Metals is not yet a qualified manufacturer of tungsten.',
    'Atlas Metals plans to become a qualified manufacturer of tungsten.',
    'Atlas Metals expects to complete qualification of tungsten.',
])
def test_prequalification_does_not_create_qualified_supplier_pool(text):
    b,su=pair();su=c.structure(doc(su['body'].split(' Atlas Metals is')[0]+' '+text,'Atlas Metals',url=su['origin_url']))
    assert not g.analyze([b,su],mode='SYNTHETIC',now=ASOF)['protected_result']['candidates']


def test_ready_before_need_and_unanchored_relative_period_do_not_find_gap():
    assert not g.analyze(pair(ready='2027'),mode='SYNTHETIC',now=ASOF)['protected_result']['candidates']
    assert not g.analyze(pair(ready='within 18 months'),mode='SYNTHETIC',now=ASOF)['protected_result']['candidates']
    assert t.bounds('within 18 months')['start']=='UNKNOWN'


def test_supported_graph_must_have_current_new_document_for_live():
    b,su=pair();assert not g.analyze([b,su],mode='LIVE',new_document_ids=set())['protected_result']['candidates']
    assert len(g.analyze([b,su],mode='LIVE',new_document_ids={b['document_id']})['protected_result']['candidates'])==1
    with pytest.raises(ValueError,match='backdate'):g.analyze([b,su],mode='LIVE',now=ASOF)


def test_new_graph_preserves_existing_physical_target_identity():
    result=g.analyze(pair(),mode='SYNTHETIC',now=ASOF)
    target=result['targets'][0]
    tid,title=c.pd._target(target['scope'])
    candidate=result['protected_result']['candidates'][0]
    assert candidate['target_id']==tid and candidate['target']==title


def test_public_shortage_and_unverified_relation_document_do_not_promote():
    b,su=pair();su=c.structure(doc(su['body']+' A shortage is confirmed.','Atlas Metals',url=su['origin_url']))
    assert not g.analyze([b,su],mode='SYNTHETIC',now=ASOF)['protected_result']['candidates']
    b,su=pair();su['provenance']='BLOCKED';su['provenance_verified']=False
    assert not g.analyze([b,su],mode='SYNTHETIC',now=ASOF)['protected_result']['candidates']


def test_natural_month_is_retained_without_normalizing_to_an_engine_year():
    b,su=pair(need='March 2028',ready='May 2029')
    r=g.analyze([b,su],mode='SYNTHETIC',now=ASOF)
    assert not r['protected_result']['candidates']
    assert r['pairs'][0]['comparison']['state']=='POSSIBLE_TIMING_GAP'
    assert r['pairs'][0]['engine_state']=='PROTECTED_ENGINE_UNSUPPORTED_LITERAL_WINDOW'


def test_source_reference_tampering_fails_closed():
    b,su=pair();ref=su['precursor_events'][0]['scope']['product']['reference'];ref['body_sha256']='changed'
    with pytest.raises(ValueError,match='GRAPH_SOURCE'):g.analyze([b,su],mode='SYNTHETIC',now=ASOF)


def test_filing_accounting_and_currency_codes_are_not_physical_models_or_specs():
    d=c.structure(doc('FORM 10-Q. ITEM 2. ASC 820. RMB 40 million. ISO4217. Signed new orders for tungsten, worth 20 mil lion dollars.'))
    observed=g.observations(d)
    assert not any(s.NONPRODUCT_IDENTIFIER.search(o['fields']['product']['value']) for o in observed if 'product' in o['fields'])
    assert not any(o['fields'].get('specification') for o in observed)
    engineering=c.structure(doc('Signed new orders for MIL-STD-810 tungsten under ASTM A36 and ISO 9001.'))
    specs=[m[0] for m in s.SPEC.finditer(engineering['body'])]
    assert specs==['MIL-STD-810','ASTM A36','ISO 9001']


def test_named_model_and_same_paragraph_noun_antecedent():
    d=c.structure(doc('Signed new orders for NovaLT16 gas turbines for AI data centers in North America.'))
    assert d['retained_collection_events'][0]['scope']['product']['value']=='NovaLT16'
    d=c.structure(doc('Signed new orders for NDAA-compliant pouch cells. These cells are for military drones in United States.'))
    assert d['retained_collection_events'][0]['scope']['customer_group']['value']=='military drones'
    assert s.validate_references(d,d['retained_collection_events'])


def test_syntactic_entity_and_actual_eligibility_are_distinct():
    d=c.structure(doc('Signed new orders for military-grade tungsten. The tungsten is manufactured by Atlas Metals, which plans customer qualification in 2029.'))
    assert not d['retained_collection_events'][0]['scope'].get('supply_pool')


@pytest.mark.parametrize('text,precision,start,end',[
    ('2028년 7월','MONTH','2028-07-01','2028-07-31'),
    ('2028년 7월 9일','DATE','2028-07-09','2028-07-09'),
])
def test_korean_date_precision(text,precision,start,end):
    assert (t.bounds(text)['precision'],t.bounds(text)['start'],t.bounds(text)['end'])==(precision,start,end)


def test_physical_reserved_nominal_and_unknown_substitute_are_not_qualified_available():
    d=c.structure(doc('Signed new orders for tungsten; production capacity of 100 units/year is already reserved in 2028; alternative supplier may be available in 2029.'))
    f=d['retained_collection_events'][0]['temporal_facts']
    assert f['quantities'][0]['fact_kind']=='CUSTOMER_ALLOCATION'
    assert not any(x['kind']=='QUALIFIED_SUBSTITUTE' for x in f['relief'])
    assert any(x['kind']=='UNVERIFIED_SUBSTITUTE' for x in f['relief'])


def test_private_derived_query_blocked_but_direct_original_capture_is_allowed(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('test_precursor_collection.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
    raw=f.html('buyer','Signed firm new orders for 100 units in 2028.')
    monkeypatch.setattr(c.acquisition,'fetch',lambda url:(raw,url,200,'text/html'))
    calls=[];monkeypatch.setattr(c.acquisition,'search',lambda *args:calls.append(args))
    r=c.cycle(tmp_path,f.manifest(['buyer']),search_endpoint=c.DEFAULT_SEARCH_ENDPOINT)
    assert not calls and r['search_statuses']==['BLOCKED_PRIVATE_QUERY_DISCLOSURE']
    assert not search.external_query_allowed({'query_data_classification':'PUBLIC_ONLY','public_query_references':[{'url':'https://agency.gov/public'}]})
    assert not search.external_query_allowed({})


def test_repeated_operating_cycle_retains_context_without_counting_it_as_new(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('repeat_fixture',Path(__file__).with_name('test_precursor_collection.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
    raw=f.html('buyer','Signed firm new orders for tungsten in 2028.')
    monkeypatch.setattr(c.acquisition,'fetch',lambda url:(raw,url,200,'text/html'))
    first=c.cycle(tmp_path,f.manifest(['buyer']))
    repeat=c.cycle(tmp_path,{**f.manifest([]),'batch_number':2})
    assert first['new_verified_documents']==1
    assert repeat['new_verified_documents']==0 and repeat['context_verified_documents']==1
    assert repeat['graph_early_preflight']==0 and repeat['live_execution']['frozen']==0


def test_model_namespace_uses_explicit_maker_not_ticker_or_publisher():
    b=c.structure(doc('Meridian signed firm new orders for Axon27 gas turbines for military drones in United States in 2028. Axon27 gas turbines are manufactured by Atlas Metals.','Meridian',url='https://meridian.example/press-release/order'))
    su=c.structure(doc('Atlas Metals manufactures Axon27 gas turbines with production capacity under construction until 2029.','Atlas Metals',url='https://atlasmetals.example/press-release/capacity'))
    graph=g.build([b,su])
    assert any(e['keys']==['model:axon27|supplier:atlas metals'] for e in graph['edges'])
    assert not any('meridian' in key for e in graph['edges'] for key in e['keys'])


def test_generic_project_and_model_without_maker_are_not_join_keys():
    assert s.named_anchors('The project commissioning is delayed until 2029.')==[]
    a=c.structure(doc('Signed new orders for Axon27 gas turbines for military drones in 2028.','Meridian'))
    b=c.structure(doc('Production capacity for Axon27 gas turbines is under construction until 2029.','Atlas Metals'))
    assert not g.build([a,b])['edges']


def test_private_query_text_cannot_be_relabelled_as_public(tmp_path):
    b,su=pair()
    request={'target':'tungsten','scope':{'product':'tungsten','region':'united states'},'seed_document_ids':['Meridian'], 'query':'private secret customer list','role':'SUPPLY','missing_fields':['supply_pool']}
    assert not search.external_query_allowed(search.public_query_request(request,[b],set()))
    public=search.public_query_request(request,[b],{'Meridian'})
    assert search.external_query_allowed(public)
    assert 'private secret' not in public['query'] and public['public_query_references']


def test_canonical_same_host_redirect_keeps_actual_identity_cross_site_does_not():
    from bct import precursor_official_source as official
    from test_precursor_collection import html
    raw=html('maker','Maker signed firm new orders for tungsten in 2028.')
    old='https://maker.example/old';final='https://maker.example/doc'
    proof=official.verify(raw,old,final,'2026-10-08T17:30:00+00:00')
    assert proof['provenance']=='PASS' and proof['requested_url']==old
    assert proof['identity_reference']['observed_final_url']==final
    assert official.verify(raw,'https://copy.example/old',final,'2026-10-08T17:30:00+00:00')['provenance']=='BLOCKED'


def test_relative_within_window_and_explicit_contract_anchor_precision():
    anchor={**t.bounds('2026-10-08'),'reference':{'source_quote':'Contract effective 2026-10-08'}}
    b=t.bounds('within 18 months',anchor)
    assert b['precision']=='RELATIVE_WINDOW' and b['start']=='2026-10-08' and b['end']=='2028-04-08'
    assert t.bounds('계약 발효 후 24개월')['unknown_reason']=='REFERENCE_EVENT_DATE_NOT_VERIFIED'


def test_quantity_comparison_requires_unreserved_qualified_same_period_and_unit():
    need={**t.bounds('2028'),'fact_kind':'DEMAND_NEED'};ready={**t.bounds('2027'),'fact_kind':'QUALIFICATION'}
    period=t.bounds('2028')
    demand={'scope':{'product':'tungsten'},'temporal_facts':{'periods':[need],'quantities':[{'unit':'units/year','rate':True,'fact_kind':'ORDER_QUANTITY','period':period,'value':100}]}}
    supply={'scope':demand['scope'],'qualified':True,'temporal_facts':{'periods':[ready],'quantities':[{'unit':'units/year','rate':True,'fact_kind':'UNRESERVED_CAPACITY','qualification_status':'SOURCE_ASSERTED','coverage':'UNRESERVED','period':period,'value':80}]}}
    assert t.compare(demand,supply)['gap']==20
    supply['temporal_facts']['quantities'][0]['fact_kind']='CUSTOMER_ALLOCATION'
    assert t.compare(demand,supply)['state']!='POSSIBLE_QUANTITY_GAP'
    supply['temporal_facts']['quantities'][0]['fact_kind']='NOMINAL_OR_PLANNED_CAPACITY'
    assert t.compare(demand,supply)['state']!='POSSIBLE_QUANTITY_GAP'


def test_more_precise_month_qualitative_year_and_korean_half_never_lose_precision():
    for when in ('early 2028','March 2028','first half of 2028','2028년 하반기'):
        e=c.structure(doc('Signed firm new orders for tungsten; delivery required in '+when+'.'))['retained_collection_events'][0]
        assert e['window'] is None
        assert e['temporal_facts']['periods'][0]['text']==when
