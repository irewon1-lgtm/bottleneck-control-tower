from copy import deepcopy
import json
import pytest
from bct.v4.evidence_path import accept,analyze,reference,save,normalize_quantity
from bct.v4.research_reading import decode
from bct.v4.store import Ledger,sha


def case(text='Atlas ordered two Helios heat pumps.',name='Helios heat pumps',role='DEMAND_INCREASE',actuality='ACTUAL',publisher='Atlas'):
    d={'document_id':sha([text,publisher]),'body':text,'body_sha256':sha(text.encode()),'origin_url':'https://official.example/'+publisher,'origin_id':publisher,'origin_publisher':publisher,'published_at':'2026-01-01','acquired_at':'2026-01-02'}
    a=text.index(name);p={'reference':{'start':0,'end':len(text),'quote':text},'product':{'value':name,'reference':{'start':a,'end':a+len(name),'quote':name}},'role':role,'actuality':actuality,'fields':{}}
    return d,p


def test_novel_product_without_old_event_whitelist_keeps_actual_order():
    d,p=case();r=accept(d,p);assert r['event_status']=='ADOPTED_RESEARCH_EVENT'and r['s_stage']=='S1'
    assert r['target']['supply_pool']is None and not r['fields']


def test_same_word_elsewhere_does_not_invalidate_explicit_exact_position():
    d,p=case('Helios heat pumps are described. Atlas ordered two Helios heat pumps.')
    a=d['body'].rindex('Helios heat pumps');p['product']['reference'].update(start=a,end=a+len('Helios heat pumps'))
    assert accept(d,p)['event_status']=='ADOPTED_RESEARCH_EVENT'


@pytest.mark.parametrize('body,name,role,actuality,adopt',[
 ('Atlas plans to order Helios heat pumps.','Helios heat pumps','DEMAND_INCREASE','ACTUAL',False),
 ('Atlas did not order Helios heat pumps.','Helios heat pumps','DEMAND_INCREASE','ACTUAL',False),
 ('Atlas ordered equipment to manufacture Helios heat pumps.','Helios heat pumps','DEMAND_INCREASE','ACTUAL',False),
 ('Helios heat pumps will be used in special operations.','Helios heat pumps','SUPPLY_INCREASE','PLAN',False),
 ('Helios heat pumps production decreased.','Helios heat pumps','SUPPLY_DECREASE','ACTUAL',True),
 ('Helios heat pumps delivery was delayed.','Helios heat pumps','SUPPLY_DELAY','ACTUAL',True),
 ('Helios heat pumps lead times shortened.','Helios heat pumps','RELIEF','ACTUAL',True),
 ('Atlas received funding for Helios heat pumps.','Helios heat pumps','SUPPLY_INCREASE','ACTUAL',False),
 ('Helios heat pumps are stable; Zeta engines production decreased.','Helios heat pumps','SUPPLY_DECREASE','ACTUAL',False),
 ('Atlas ordered Beta services.','Beta services','DEMAND_INCREASE','ACTUAL',False),
 ('Helios heat pumps production will increase.','Helios heat pumps','SUPPLY_INCREASE','ACTUAL',False)])
def test_roles_and_counterexamples(body,name,role,actuality,adopt):
    d,p=case(body,name,role,actuality);r=accept(d,p);assert (r['event_status']=='ADOPTED_RESEARCH_EVENT')==adopt
    assert r['s_stage']!='S3'


def test_one_bad_document_does_not_stop_batch_and_default_is_disabled():
    d,p=case();bad=deepcopy(p);bad['product']['reference']['quote']='invented'
    r=analyze([d],{d['document_id']:[bad,p]},enabled=True);assert len(r['held'])==1 and r['counts']['events']==1
    assert analyze([d],{d['document_id']:[p]})['counts']['events']==0


def test_raw_surface_and_deterministic_number_conversion():
    assert normalize_quantity('four')=={'surface':'four','normalized':'4','rule':'NUMBER_WORD'}
    assert normalize_quantity('$800 million')['normalized']is None


def test_model_literal_target_fields_are_not_independent_semantic_proof_for_S2():
    text='Atlas ordered Helios heat pumps standard A in US for Hospital from Pool during 2028.';d,p=case(text)
    for k,v in [('specification','standard A'),('region','US'),('customer_group','Hospital'),('supply_pool','Pool'),('need_time','2028')]:
        a=text.index(v);p['fields'][k]={'value':v,'reference':{'start':a,'end':a+len(v),'quote':v}}
    assert accept(d,p)['s_stage']=='S1'


def test_restore_requery_idempotence_and_original_proposal_preserved(tmp_path):
    d,p=case();l=Ledger(tmp_path/'owned');r=save(l,[d],{d['document_id']:[p]},enabled=True);l.close();l=Ledger(tmp_path/'owned')
    assert save(l,[d],{d['document_id']:[p]},enabled=True)==r
    assert r['records'][0]['original_proposal']==p;l.backup(tmp_path/'backup/v4.sqlite3');l.close()


def test_decoder_rejects_example_contamination_and_ambiguous_sentence():
    d,p=case();wire={'extractions':[{'event':'Northwind ordered two VX valves.','event_attributes':{'product':'VX valves'}}]}
    accepted,held=decode(json.dumps(wire),d,[{'start':0,'end':len(d['body']),'text':d['body']}]);assert not accepted and held


def test_discovery_without_event_is_not_product_FP():
    from bct.v4.comparison_evaluation import score_products,score_events
    d,p=case('Helios heat pumps are on display.');p['role']='UNKNOWN';r=accept(d,p)
    g={'targets':[{'target_id':'heat','entity':'Helios heat pumps','entity_aliases':[],'events':[],'discovery_reference':p['product']['reference']}]}
    assert score_products([r],g)['TP']==1 and score_products([r],g)['FP']==0
    assert score_events([r],g)['precision']is None and score_events([r],g)['recall']is None


def test_financial_purchase_does_not_become_physical_order():
    d,p=case('Atlas purchased shares in Helios heat pumps.')
    assert accept(d,p)['event_status']=='DISCOVERY_ONLY'


def test_inventory_relief_is_retained_for_its_own_product():
    d,p=case('Helios heat pumps inventories increased.','Helios heat pumps','RELIEF')
    r=accept(d,p);assert r['event_status']=='ADOPTED_RESEARCH_EVENT'and r['s_stage']=='UNKNOWN'


def scoped(text,name,role,publisher,period='2028',region='US',customer='Hospital',pool='Pool'):
    d,p=case(text,name,role,publisher=publisher)
    for field,v in [('specification','spec A'),('region',region),('customer_group',customer),('supply_pool',pool),('need_time'if role=='DEMAND_INCREASE'else'ready_time',period)]:
        a=text.index(v);p['fields'][field]={'value':v,'reference':{'start':a,'end':a+len(v),'quote':v}}
    return d,p


def test_unrelated_relief_does_not_globally_remove_a_target_pair():
    d,p=scoped('Atlas ordered Helios heat pumps spec A in US for Hospital from Pool needed in 2028.','Helios heat pumps','DEMAND_INCREASE','Atlas')
    s,q=scoped('Delta Helios heat pumps production decreased spec A in US for Hospital from Pool in 2028.','Helios heat pumps','SUPPLY_DECREASE','Delta')
    other,r=case('Zeta engines lead times shortened.','Zeta engines','RELIEF',publisher='Other')
    out=analyze([d,s,other],{d['document_id']:[p],s['document_id']:[q],other['document_id']:[r]},enabled=True)
    assert len(out['pairs'])==1 and not out['pairs'][0]['related_relief'] and not out['candidates']
    assert out['pairs'][0]['s_stage']=='UNKNOWN'and out['counts']['S3']==0


@pytest.mark.parametrize('region,customer,pool,period,publisher',[
 ('EU','Hospital','Pool','2028','Delta'),('US','OtherBuyer','Pool','2028','Delta'),
 ('US','Hospital','OtherPool','2028','Delta'),('US','Hospital','Pool','2029','Delta'),
 ('US','Hospital','Pool','2028','Atlas')])
def test_wrong_scope_time_or_requotation_cannot_pair(region,customer,pool,period,publisher):
    d,p=scoped('Atlas ordered Helios heat pumps spec A in US for Hospital from Pool needed in 2028.','Helios heat pumps','DEMAND_INCREASE','Atlas')
    s,q=scoped(f'Delta Helios heat pumps production decreased spec A in {region} for {customer} from {pool} in {period}.','Helios heat pumps','SUPPLY_DECREASE',publisher,period,region,customer,pool)
    out=analyze([d,s],{d['document_id']:[p],s['document_id']:[q]},enabled=True);assert not out['pairs']and not out['candidates']


def test_nonphysical_company_or_financial_target_is_not_product_truth():
    from bct.v4.comparison_evaluation import score_products
    g={'targets':[{'target_id':'shares','entity':'ordinary shares','discovery_kind':'NON_PHYSICAL','discovery_reference':{'start':0,'end':15,'quote':'ordinary shares'},'events':[]}]}
    m=score_products([],g);assert m['FN']==0 and m['precision']is None and m['recall']is None


def test_ordered_machine_not_output_or_customer_object_even_without_manufacture_word():
    d,p=case('Atlas ordered Helios heat pumps for testing Zeta chips.','Zeta chips')
    assert accept(d,p)['event_status']=='DISCOVERY_ONLY'
    d,p=case('Atlas ordered Helios heat pumps for Hospital.','Helios heat pumps')
    assert accept(d,p)['event_status']=='ADOPTED_RESEARCH_EVENT'


def test_model_cannot_omit_same_order_cancellation_from_transmitted_context():
    text='Atlas ordered Helios heat pumps. However, this order was cancelled.';d,p=case(text)
    raw=json.dumps({'extractions':[{'event':'Atlas ordered Helios heat pumps.','event_attributes':{'product':'Helios heat pumps','role':'DEMAND_INCREASE','actuality':'ACTUAL'}}]})
    ps,held=decode(raw,d,[{'start':0,'end':len(text),'text':text}]);assert not held
    assert accept(d,ps[0])['event_status']=='DISCOVERY_ONLY'


def test_unrelated_other_order_cancellation_does_not_block_target():
    d,p=case('Atlas ordered Helios heat pumps. Beta Zeta engines order was cancelled.')
    assert accept(d,p)['event_status']=='ADOPTED_RESEARCH_EVENT'
