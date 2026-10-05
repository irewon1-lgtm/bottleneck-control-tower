"""Contract fixtures are synthetic functional checks, never corpus performance."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from bct import precursor_v2 as v2, shadow_v2 as store

NOW='2030-01-02T00:00:00+00:00'
DEMAND='US Agency signed firm additional orders for 100 units of manufacturer Aster model AX-1 for US contract C-1, which requires certification CERT-X, for delivery in H1 2031.'
SUPPLY='Manufacturer Aster model AX-1 for US requires certification CERT-X; production is allocated to contract C-1 and qualification to CERT-X completes in H2 2031.'


def document(name,body,**kw):
    return {'document_id':name,'body':body,'body_sha256':v2.digest(body.encode()),'version':v2.digest(body.encode()),
            'origin_id':name,'origin_url':f'https://{name}.example/original','origin_publisher':name,
            'provenance_verified':True,'published_at':'2029-12-01T00:00:00Z','publication_precision':'TIMESTAMP',
            'available_at':'2029-12-02T00:00:00Z',**kw}


def pair(demand=DEMAND,supply=SUPPLY,extras=(),**kw):
    docs=[document('buyer',demand),document('maker',supply),*extras]
    es=[e for d in docs for e in v2.extract(d)]
    d=next(e for e in es if e['document_id']=='buyer' and e['role']=='DEMAND')
    s=next(e for e in es if e['document_id']=='maker' and e['role']=='SUPPLY')
    return v2.evaluate_pair_v2(d,s,documents=docs,as_of=NOW,relationships=v2.relation_edges(docs),context_events=es,**kw)


def test_natural_prose_nonoverlap_readiness_delay_and_unknown_totals():
    r=pair()
    assert r['early_eligible'] and r['state']=='EARLY_FORECAST_CANDIDATE'
    assert r['relation']['kind']=='CONTRACT_ALLOCATION'
    assert r['demand_window']['end']<r['supply_window']['start']
    assert 'total_supply' in r['decisive_UNKNOWN']


@pytest.mark.parametrize('replacement',[
    ('certification CERT-X','certification CERT-Y'),
    ('for US','for Canada'),
    ('model AX-1','model AX-2'),
    ('Manufacturer Aster','Manufacturer Boreal'),
    ('contract C-1','contract C-2'),
])
def test_incompatible_scope_is_never_early(replacement):
    assert not pair(supply=SUPPLY.replace(*replacement))['early_eligible']


def test_qualification_unknown_blocks_even_when_model_contract_match():
    r=pair(supply=SUPPLY.replace(' requires certification CERT-X','').replace('qualification to CERT-X','qualification'))
    assert not r['early_eligible'] and 'QUALIFICATION_APPLICABILITY_UNKNOWN' in r['reasons']


def test_customer_label_absence_is_not_unknown_contract_applicability():
    assert pair()['early_eligible']
    assert not pair(supply=SUPPLY.replace('allocated to contract C-1','commissioned for contract C-1'))['early_eligible']


def test_overlap_alone_is_not_delay():
    assert not pair(supply=SUPPLY.replace('H2 2031','H1 2031'))['early_eligible']
    assert not pair(demand=DEMAND.replace('H1 2031','2031'),supply=SUPPLY.replace('H2 2031','2031'))['early_eligible']


def test_exact_dates_define_delay_without_window_overlap():
    r=pair(demand=DEMAND.replace('in H1 2031','on 2031-06-30'),supply=SUPPLY.replace('in H2 2031','on 2031-07-01'))
    assert r['early_eligible']


def test_qualified_comparable_quantities_and_basis_required():
    supply='Manufacturer Aster model AX-1 for US is certified to CERT-X; unallocated qualified capacity of 80 units in H1 2031 is allocated to contract C-1.'
    assert pair(supply=supply)['comparison']=='COMPARABLE_QUANTITY_GAP'
    assert not pair(supply=supply.replace('80 units','80 units per year'))['early_eligible']
    assert not pair(supply=supply.replace('unallocated','nominal'))['early_eligible']
    assert not pair(supply=supply.replace('qualified capacity','not qualified capacity'))['early_eligible']


def test_negative_A_qualified_supply_covers_all_before_need():
    relief=document('alternate','Manufacturer Aster model AX-1 for US is certified to CERT-X; sufficient qualified supply available in H2 2030 covers all demand for contract C-1.')
    r=pair(extras=[relief]);assert r['refuted'] and not r['early_eligible']


def test_negative_B_demand_delayed_with_supply():
    adverse=document('buyer-update','Manufacturer Aster model AX-1 for US requires certification CERT-X; orders for contract C-1 are postponed to H1 2032.')
    r=pair(extras=[adverse]);assert r['refuted'] and not r['early_eligible']


def test_negative_C_same_origin_or_requoted_origin():
    ds=[document('buyer',DEMAND,origin_publisher='One Company'),document('maker',SUPPLY,origin_publisher='One Company')]
    p=v2.synthesize(ds,as_of=NOW);assert not any(e['early_eligible'] for e in p['evaluations'])
    assert not pair(supply='According to Aster, '+SUPPLY)['early_eligible']


def test_negative_D_unknown_shared_scope_does_not_merge():
    r=pair(demand=DEMAND.replace('manufacturer Aster ','').replace('model AX-1','the product'),supply=SUPPLY.replace('Manufacturer Aster ','').replace('model AX-1','the product'))
    assert r['state']=='PARTIAL_SCOPE_PAIR' and not r['early_eligible']
    assert r['target_id'] is None and r['provisional_pair_id']==r['pair_id']


def test_negative_E_prior_confirmation_in_another_paragraph():
    confirmation=document('observer','An unrelated product has sufficient supply.\nManufacturer Aster model AX-1 for US contract C-1 has a confirmed shortage.')
    r=pair(extras=[confirmation]);assert r['state']=='MISSED_EARLY_DETECTION' and not r['early_eligible']


def test_negated_or_other_model_shortage_does_not_exclude_body():
    for text in ['Manufacturer Aster model AX-1 for US has no shortage.','Manufacturer Aster model AX-2 for US has a confirmed shortage.','Manufacturer Aster model AX-1 for US may face a shortage.']:
        assert pair(extras=[document('observer',text)])['early_eligible']


def test_possible_prior_confirmation_blocks_without_fake_same_target():
    r=pair(extras=[document('observer','Model AX-1 has a confirmed shortage.')])
    assert r['prior_confirmation']=='POSSIBLE_PRIOR_CONFIRMATION' and not r['early_eligible']


def test_date_only_same_day_confirmation_is_uncertain():
    d=document('observer','Manufacturer Aster model AX-1 for US contract C-1 has a confirmed shortage.',published_at='2030-01-01',publication_precision='DATE',available_at='2030-01-01T13:00:00Z')
    # Discovery Jan 2 permits publication cutoff, but first shadow freeze Jan 1 is uncertain.
    r=pair(extras=[d],first_frozen_at='2030-01-01T12:00:00Z')
    assert r['prior_confirmation']=='POSSIBLE_PRIOR_CONFIRMATION'


def test_source_reference_tampering_is_rejected():
    docs=[document('buyer',DEMAND),document('maker',SUPPLY)];d=v2.extract(docs[0])[0];s=v2.extract(docs[1])[0]
    d['fields']['region']['value']='canada'
    with pytest.raises(ValueError,match='EVENT_NOT'):v2.evaluate_pair_v2(d,s,documents=docs,as_of=NOW)


def test_adjacent_period_only_transfers_with_explicit_same_event():
    base='Manufacturer Aster model AX-1 signed firm orders for US contract C-1, which requires certification CERT-X.'
    linked=base+' Manufacturer Aster model AX-1 for contract C-1 requires delivery in H1 2031.'
    unlinked=base+' Delivery is required in H1 2031.'
    assert v2.extract(document('buyer',linked))[0]['period']
    assert v2.extract(document('buyer',unlinked))[0]['period'] is None
    conflict=base+' Manufacturer Aster model AX-1 for contract C-2 requires delivery in H1 2031.'
    assert v2.extract(document('buyer',conflict))[0]['period'] is None


def test_explicit_alias_only_not_model_similarity():
    alias=document('registry','Manufacturer Aster model AX-1 is identical to manufacturer Aster model AX-ONE.')
    assert pair(supply=SUPPLY.replace('AX-1','AX-ONE'),extras=[alias])['early_eligible']
    assert not pair(supply=SUPPLY.replace('AX-1','AX-ONE'))['early_eligible']


def test_component_relation_preserves_direction_period_and_unknown_ratio():
    edge=document('engineering','Manufacturer Boreal model CELL-1 is required for manufacturer Aster model AX-1; component needed in H1 2031.')
    supply=SUPPLY.replace('Manufacturer Aster model AX-1','Manufacturer Boreal model CELL-1')
    r=pair(supply=supply,extras=[edge]);assert r['early_eligible'] and r['relation']['kind']=='REQUIRED_COMPONENT'
    assert r['comparison']=='QUALIFIED_READINESS_AFTER_NEED'
    assert not pair(supply=supply,extras=[document('engineering',edge['body'].replace('; component needed in H1 2031',''))])['early_eligible']


def test_common_result_counts_and_freeze_no_second_overlap_gate(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'now',lambda:NOW)
    docs=[document('buyer',DEMAND),document('maker',SUPPLY)]
    activation=store.activate(tmp_path);prepared=v2.synthesize(docs,as_of=NOW)
    assert v2.counters(prepared)['early_targets']==1
    assert store.freeze(tmp_path,prepared,activation)['first_shadow_frozen']==1
    first=next((tmp_path/'candidates').glob('*.json')).read_bytes()
    assert store.freeze(tmp_path,prepared,activation)['first_shadow_frozen']==0
    assert first==next((tmp_path/'candidates').glob('*.json')).read_bytes()


def test_entrypoint_calls_v2_and_never_v1_prospective(tmp_path,monkeypatch):
    from bct import prospective
    monkeypatch.setattr(prospective,'run',lambda *a,**k:pytest.fail('v1 prospective called'))
    monkeypatch.setattr(store,'now',lambda:NOW)
    original=v2.evaluate_pair_v2;calls=[]
    def spy(*a,**k):calls.append(True);return original(*a,**k)
    monkeypatch.setattr(v2,'evaluate_pair_v2',spy)
    docs=[document('buyer',DEMAND),document('maker',SUPPLY)]
    a=store.run(tmp_path,docs);assert calls and a['freeze']['first_shadow_frozen']==1
    assert store.run(tmp_path,docs)==a and len(calls)==1


def test_live_store_rejected_and_epoch_hash_change_fails_closed(tmp_path,monkeypatch):
    (tmp_path/'session.json').write_text('{}')
    with pytest.raises(ValueError,match='V1_LIVE'):store.activate(tmp_path)
    other=tmp_path/'separate';store.activate(other)
    monkeypatch.setattr(store,'engine_hashes',lambda:{'changed':'hash'})
    with pytest.raises(ValueError,match='EPOCH_ENGINE'):store.activate(other)


def test_decision_tampering_cannot_be_frozen(tmp_path):
    r=pair();r['early_eligible']=False
    with pytest.raises(ValueError,match='DECISION_INTEGRITY'):store.validate_decision(r)


def test_natural_manufactures_predicate_and_product_equivalence():
    assert pair(supply=SUPPLY.replace('Manufacturer Aster model AX-1','Aster manufactures model AX-1'))['early_eligible']
    d=DEMAND.replace('model AX-1','product "precision cells" specification G1')
    s=SUPPLY.replace('model AX-1','product "precision cells" specification G1')
    assert pair(demand=d,supply=s)['relation']['kind']=='SAME_PRODUCT'


def test_negated_refutation_and_unsigned_demand_are_not_facts():
    text='Manufacturer Aster model AX-1 for US is certified to CERT-X; qualified supply available in H2 2030 cannot cover all demand for contract C-1.'
    assert pair(extras=[document('alternate',text)])['early_eligible']
    text='Manufacturer Aster model AX-1 for US requires certification CERT-X; orders for contract C-1 are not cancelled.'
    assert pair(extras=[document('buyer-update',text)])['early_eligible']
    assert not pair(demand=DEMAND.replace('signed firm','not signed'))['early_eligible']


def test_scope_unknown_confirmation_is_possible_and_forecast_not_actual():
    assert not pair(extras=[document('observer','Manufacturer Aster model AX-1 has a confirmed shortage.')])['early_eligible']
    assert pair(extras=[document('observer','Manufacturer Aster model AX-1 for US contract C-1 may face a shortage.')])['early_eligible']


def test_shadow_refutation_and_later_confirmation_append_history(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'now',lambda:NOW)
    docs=[document('buyer',DEMAND),document('maker',SUPPLY)]
    store.run(tmp_path,docs)
    candidate=next((tmp_path/'candidates').glob('*.json'));first=candidate.read_bytes()
    monkeypatch.setattr(store,'now',lambda:'2030-01-04T00:00:00+00:00')
    confirmation=document('observer','Manufacturer Aster model AX-1 for US contract C-1 has a confirmed shortage.',published_at='2030-01-03T00:00:00Z',available_at='2030-01-03T01:00:00Z')
    r=store.run(tmp_path,docs+[confirmation])
    assert r['prepared']['evaluations'][0]['state']=='CONFIRMED'
    assert r['freeze']['first_shadow_frozen']==0 and r['freeze']['history_appended']==1
    assert candidate.read_bytes()==first
    relief=document('alternate','Manufacturer Aster model AX-1 for US is certified to CERT-X; sufficient qualified supply available in H2 2030 covers all demand for contract C-1.')
    r=store.run(tmp_path,docs+[relief]);assert r['prepared']['evaluations'][0]['state']=='REFUTED'
    assert candidate.read_bytes()==first and r['freeze']['history_appended']==1


def test_frozen_gold_change_is_rejected_before_shadow_creation(tmp_path):
    inp=tmp_path/'input.json';gold=tmp_path/'gold.json';seal=tmp_path/'seal.json'
    inp.write_text('{"documents":[]}');gold.write_text('{"cases":[],"frozen_before_v2_outputs":true}')
    seal.write_text(json.dumps({'input.json':v2.digest(inp.read_bytes()),'gold.json':v2.digest(gold.read_bytes())}))
    gold.write_text('{"cases":[]}')
    with pytest.raises(ValueError,match='SEAL_CHANGED'):store.compare(tmp_path/'shadow',input_path=inp,gold_path=gold,seal_path=seal)
    assert not (tmp_path/'shadow').exists()


def test_ready_factory_without_qualification_completion_does_not_promote():
    supply=SUPPLY.replace('qualification to CERT-X completes','production ready')
    assert not pair(supply=supply)['early_eligible']


def test_relative_fiscal_periods_and_two_dates_remain_unknown():
    for text in ['next year','FY2031','H1 2031 and delivery in H2 2031']:
        assert not pair(demand=DEMAND.replace('H1 2031',text))['early_eligible']


def test_two_positive_pairs_freeze_one_target_only(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'now',lambda:NOW)
    docs=[document('buyer',DEMAND),document('maker',SUPPLY),document('maker2',SUPPLY.replace('production is allocated','production capacity is allocated'))]
    r=store.run(tmp_path,docs)
    assert r['counts']['early_pairs']==2 and r['counts']['early_targets']==1
    assert r['freeze']['first_shadow_frozen']==1


def test_raw_document_hash_and_version_mismatch_are_rejected():
    d=document('buyer',DEMAND);d['version']='wrong'
    r=v2.synthesize([d,document('maker',SUPPLY)],as_of=NOW)
    assert r['document_rejections'][0]['reason']=='BODY_VERSION_MISMATCH'


def test_independent_source_family_and_duplicate_body_are_not_counted():
    docs=[document('buyer',DEMAND,origin_family='Origin Agency'),document('maker',SUPPLY,origin_family='Origin Agency')]
    assert not v2.synthesize(docs,as_of=NOW)['evaluations'][0]['early_eligible']


def test_same_model_different_facility_requires_contract_allocation():
    d=DEMAND.replace('for US contract C-1','for facility F-1 in US contract C-1')
    s=SUPPLY.replace('for US','for facility F-2 in US')
    assert pair(demand=d,supply=s)['early_eligible']
    s=s.replace('allocated to contract C-1','for customer Agency')
    assert not pair(demand=d,supply=s)['early_eligible']


def test_verified_prior_confirmation_cannot_be_downgraded_by_ambiguous_one():
    certain=document('observer','Manufacturer Aster model AX-1 for US contract C-1 has a confirmed shortage.')
    possible=document('other-observer','Model AX-1 has a confirmed shortage.')
    r=pair(extras=[certain,possible]);assert r['state']=='MISSED_EARLY_DETECTION'


def test_conflicting_same_facility_readiness_waits_for_reconciliation():
    supply=SUPPLY.replace('for US','for facility F-1 in US')
    conflict=document('second-proof',supply.replace('H2 2031','H1 2031'))
    r=pair(supply=supply,extras=[conflict])
    assert not r['early_eligible'] and 'CONFLICTING_SAME_FACILITY_READINESS' in r['reasons']


def test_precision_lower_bound_does_not_pass_small_perfect_sample():
    assert store.lower_bound(10,10)<.95
    assert store.lower_bound(59,59)>=.95
    assert store.lower_bound(0,0) is None


def test_comparable_allocated_alternative_quantity_refutes_late_facility():
    alternative=document('alternate','Manufacturer Aster model AX-1 for US is certified to CERT-X; unallocated qualified capacity of 100 units in H1 2031 is allocated to contract C-1.')
    r=pair(extras=[alternative]);assert r['refuted'] and not r['early_eligible']
    # A nominal or differently measured alternative is not a proven substitute.
    for text in [alternative['body'].replace('100 units','100 units per year'),alternative['body'].replace('unallocated','nominal')]:
        assert pair(extras=[document('alternate',text)])['early_eligible']


def test_alias_statement_binds_its_endpoints_not_other_models_in_paragraph():
    unrelated=document('registry','Manufacturer Aster model AX-1 differs from manufacturer Aster model AX-ONE; manufacturer Aster model AX-3 is identical to manufacturer Aster model AX-4.')
    assert not pair(supply=SUPPLY.replace('AX-1','AX-ONE'),extras=[unrelated])['early_eligible']
    prefix=document('registry','Manufacturer Aster model AX-100 is identical to manufacturer Aster model AX-ONE.')
    assert not pair(supply=SUPPLY.replace('AX-1','AX-ONE'),extras=[prefix])['early_eligible']


def identity_pair(doc,demand_offset=None,supply_offset=None):
    events=v2.extract(doc)
    d=next(e for e in events if e['role']=='DEMAND' and (demand_offset is None or e['reference']['locator']['start']==demand_offset))
    s=next(e for e in events if e['role']=='SUPPLY' and (supply_offset is None or e['reference']['locator']['start']==supply_offset))
    return d,s,v2.relationship(d,s,v2.relation_edges([doc]),{doc['document_id']:doc})


def test_natural_variant_full_name_alias_is_source_bound():
    doc=document('notice','A signed award covers future orders of Block 3 of the Energy Delivery Module, or EDM.\nEDM Block 3 production is moving beyond testing.')
    d,s,rel=identity_pair(doc)
    assert rel['state']=='VERIFIED' and d['fields']['model']['value']=='edm block 3'
    assert d['fields']['model']['derivation']=='EXPLICIT_VARIANT_ALIAS'
    for ref in rel['references']:v2.verify_reference(ref,{doc['document_id']:doc})
    assert not v2._independent(d,s,{doc['document_id']:doc})


def test_speaker_demonstrative_refers_to_named_model_not_arbitrary_neighbor():
    body='Northline Vehicles builds iVector 300 trucks; production began last year.\nMorgan Casey, a driver, is taking an iVector 300 on a tour.\n"What is the next step in order to build support around those trucks?" Casey said.'
    doc=document('maker',body);d,s,rel=identity_pair(doc)
    assert rel['state']=='VERIFIED' and d['fields']['model']['value']=='ivector 300'
    assert d['period'] is None and 'region' not in d['fields']
    assert d['fields']['model']['support_references']
    # Another speaker cannot borrow this model.
    other=document('other',body.replace('Casey said','Lee said'))
    assert 'model' not in next(e for e in v2.extract(other) if e['role']=='DEMAND')['fields']


def test_named_model_does_not_merge_different_models_or_known_manufacturers():
    for supply in ('Manufacturer Boreal iVector 300 production is ready.','Manufacturer Aster iVector 400 production is ready.'):
        doc=document('notice','Manufacturer Aster signed orders for iVector 300 trucks.\n'+supply)
        assert identity_pair(doc)[2]['state']!='VERIFIED'


def plant_article(second=''):
    return ('Bright Systems’ new methane plant in Ridgeview, Lakeside awaits energization.\n'
            'Morgan Lee, general manager of Bright Systems, discussed the project.\n'+second+
            'It is approaching initial commissioning, Lee said.\n'
            'Demand for the methane is meant to come partly from Westgrid. The nomination says an offtake agreement supports distribution to regional users.')


def test_owned_facility_product_and_manager_coreferences_preserve_unknowns():
    doc=document('plant',plant_article());d,s,rel=identity_pair(doc)
    assert rel['state']=='VERIFIED' and rel['kind']=='SAME_FACILITY'
    assert d['period'] is None and s['period'] is None
    assert 'region' not in d['fields'] and 'qualification' not in s['fields']
    for ref in rel['references']:v2.verify_reference(ref,{doc['document_id']:doc})
    assert not v2._independent(d,s,{doc['document_id']:doc})


def test_two_owned_facilities_do_not_resolve_an_ambiguous_it():
    second='Bright Systems’ new methane plant in Hillview, Lakeside also awaits energization.\n'
    doc=document('plant',plant_article(second));d,s,rel=identity_pair(doc)
    assert 'facility' not in d['fields'] and 'facility' not in s['fields']
    assert rel['state']!='VERIFIED'


def test_same_owner_speaker_is_not_evidence_for_another_system():
    doc=document('plant',plant_article().replace('It is approaching','Another plant is approaching'))
    d,s,rel=identity_pair(doc)
    assert 'facility' not in s['fields'] and rel['state']!='VERIFIED'


@pytest.mark.parametrize('text',[
    'The manufacturer announced orders for new vehicles.',
    'Production should be a model to follow.',
    'Engineering Qualification Model in a testing chamber supports production.',
])
def test_verbs_and_prepositions_are_not_identifiers(text):
    for e in v2.extract(document('notice',text)):
        assert not any(f['value'] in ('announced','to','in') for f in e['fields'].values())


@pytest.mark.parametrize('text',[
    'A company has agreed to purchase 80 vehicles under a long-term agreement.',
    'A government committed funding to build a new plant.',
    'The next step will be service validation before it is operational.',
    'The policy will reduce dependencies over upcoming years.',
    'The supplier will be deployed through its manufacturing partners.',
])
def test_missing_precursor_vocabulary_is_retained_without_invented_period(text):
    events=v2.extract(document('notice',text))
    assert events and all(e['period'] is None for e in events)


@pytest.mark.parametrize('text',[
    'Investigators have found a shipment during the investigation.',
    'The European Commission has partnered with a museum for an exhibition.',
    'Investor Contact: Morgan Casey.',
    'This press release contains forward-looking statements about investments in new plants.',
    'The bond market and investment gold attract investors.',
    'A company is investing in junior miners dependent on risk capital.',
    'The investments in new factories have not yet been reflected in employment data.',
])
def test_new_retention_does_not_restore_investigator_or_boilerplate_noise(text):
    assert not v2.extract(document('notice',text))
