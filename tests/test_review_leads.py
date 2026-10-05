"""Synthetic review-boundary checks; not historic or live detection evidence."""
from copy import deepcopy
from pathlib import Path
import pytest
from bct import review_leads as r
from bct.objective_lock import stamp_export


def fixture():
    body='Facility PX-1 signed an offtake plan. Facility PX-1 is ramping, ready date unknown. Model BX-2 is a different system. Actual shortage at facility PX-1 is confirmed.'
    doc={'document_id':'synthetic','body':body,'body_sha256':r.digest(body.encode()),'version':r.digest(body.encode()),'origin_id':'synthetic-primary','origin_url':'https://synthetic.example/article','origin_publisher':'Synthetic','provenance_verified':True,'published_at':'2020-01-01T00:00:00+00:00','publication_precision':'TIMESTAMP','acquired_at':'2020-01-02T00:00:00+00:00','available_at':'2020-01-02T00:00:00+00:00'}
    def ref(quote):
        a=body.index(quote);return {'document_id':doc['document_id'],'body_sha256':doc['body_sha256'],'locator':{'start':a,'end':a+len(quote)},'quote':quote}
    scope={'facility':{'value':'PX-1','reference':ref('PX-1')}}
    a={'target':'Synthetic PX-1','scope_fields':scope,'scope_relation':'MATCH','hypothesis_key':'offtake-vs-ramp',
       'facts':[{'fact_id':'f1','role':'DEMAND','evidence_kind':'EXPLICIT_PLAN','modality':'PLAN','description':'Synthetic source-bound offtake plan','reference':ref('Facility PX-1 signed an offtake plan.'),'scope_fields':scope}],
       'relation_references':[ref('PX-1')], 'hypothesis':{'link_assessment':'SPECIFIC','affected_fact_ids':['f1'],'mechanism':'Need may precede qualified ramp; hypothetical, not observed gap.','assumptions':['Need date and qualified output unknown']},
       'unknowns':[{'field':'allocation','status':'UNKNOWN','question':'What is allocated?'}], 'questions':['When is supply needed?'], 'refutation_conditions':['Need begins after ready date'],
       'confirmation':{'document':'NO','same_TARGET':'NO','references':[],'method':'Synthetic controlled label, not real original-source proof'}, 'counter_evidence':[], 'period_expressions':[],
       'existing_v2_reference':{'states':['DATA_WAIT'],'first_strict_condition_met_at':'UNKNOWN'}, 'annotation_method':'SYNTHETIC_TEST','annotator':'Test fixture','annotated_at':'2026-01-01T00:00:00+00:00'}
    bundle=stamp_export({'documents':[doc],'annotations':[a]})
    contract=stamp_export({'review_rules_version':r.VERSION,'review_contract_version':'BCT_REVIEW_LEAD_CONTRACT_1','applies_from':'2026-01-01T00:00:00+00:00'})
    return bundle,contract,ref


def test_single_origin_unknown_allocation_and_dates_remain_research(tmp_path):
    b,c,_=fixture();out=r.generate(b,c,tmp_path/'store');card=out['records'][0]['first']
    assert card['status']=='REVIEW_LEAD' and card['source_status']['single_source'] is True
    assert card['UNKNOWN'][0]['status']=='UNKNOWN' and card['strict_candidate_first_met_at']=='UNKNOWN'
    assert card['formal_TARGET_id'] is None and not card['EARLY_success']
    assert out['EARLY_count']==out['leading_detection_success_count']==0


def test_unknown_not_pass_and_invalid_source_reference_fail(tmp_path):
    b,c,_=fixture();b['annotations'][0]['unknowns'][0]['status']='PASS'
    with pytest.raises(ValueError,match='UNKNOWN_NOT_PASS'):r.generate(b,c,tmp_path/'bad-unknown')
    b,c,_=fixture();b['annotations'][0]['facts'][0]['reference']['quote']='invented evidence'
    with pytest.raises(ValueError,match='SOURCE_REFERENCE_MISMATCH'):r.generate(b,c,tmp_path/'bad-ref')


def test_explicit_model_mismatch_is_excluded(tmp_path):
    b,c,ref=fixture();a=b['annotations'][0];a['scope_fields']['model']={'value':'PX-1','reference':ref('PX-1')}
    a['facts'][0]['scope_fields']={**a['facts'][0]['scope_fields'],'model':{'value':'BX-2','reference':ref('BX-2')}}
    result=r.generate(b,c,tmp_path/'store');assert result['status_counts']['EXCLUDED']==1


@pytest.mark.parametrize('confirmation,status', [('YES','CONFIRMATION'),('UNKNOWN','HOLD')])
def test_known_and_possible_confirmation_are_not_leading(tmp_path,confirmation,status):
    b,c,ref=fixture();b['annotations'][0]['confirmation']={'document':'YES','same_TARGET':confirmation,'references':[ref('Actual shortage at facility PX-1 is confirmed.')]}
    out=r.generate(b,c,tmp_path/'store');assert out['status_counts'][status]==1 and out['status_counts']['REVIEW_LEAD']==0


def test_unrelated_confirmation_does_not_exclude_target(tmp_path):
    b,c,ref=fixture();b['annotations'][0]['confirmation']={'document':'YES','same_TARGET':'NO','references':[ref('BX-2')]}
    assert r.generate(b,c,tmp_path/'store')['status_counts']['REVIEW_LEAD']==1


def test_generic_expansion_is_held_and_rhetorical_event_excluded(tmp_path):
    b,c,_=fixture();b['annotations'][0]['hypothesis']['link_assessment']='GENERIC_ONLY'
    assert r.generate(b,c,tmp_path/'generic')['status_counts']['HOLD']==1
    b,c,_=fixture();b['annotations'][0]['facts'][0]['evidence_kind']='NON_FACTUAL'
    assert r.generate(b,c,tmp_path/'rhetorical')['status_counts']['EXCLUDED']==1


def test_unverified_provenance_is_not_silently_promoted(tmp_path):
    b,c,_=fixture();b['documents'][0]['provenance_verified']=False
    assert r.generate(b,c,tmp_path/'unverified')['status_counts']['HOLD']==1


def test_backfill_first_time_and_append_only_replay(tmp_path,monkeypatch):
    b,c,ref=fixture();root=tmp_path/'store';monkeypatch.setattr(r,'now',lambda:'2026-10-05T15:30:00+00:00')
    result=r.generate(b,c,root);first=result['records'][0]['first'];p=root/'first'/(first['review_id']+'.json');before=p.read_bytes()
    assert first['mode']=='BACKFILL' and first['first_review_recorded_at']=='2026-10-05T15:30:00+00:00'
    assert first['sources'][0]['published_at']=='2020-01-01T00:00:00+00:00'
    monkeypatch.setattr(r,'now',lambda:'2026-10-06T15:30:00+00:00')
    assert r.generate(b,c,root)['new_first_records']==0 and p.read_bytes()==before
    event=stamp_export({'kind':'REFUTATION','summary':'Synthetic later evidence, no LIVE success','annotator':'Synthetic reader','same_TARGET':'YES','references':[ref('Facility PX-1 is ramping, ready date unknown.')],'status_after':'REFUTED','recorded_at':'1990-01-01T00:00:00Z'})
    follow=r.append_event(root,c,b,first['review_id'],event)
    assert follow['recorded_at']=='2026-10-06T15:30:00+00:00' and p.read_bytes()==before
    assert r.append_event(root,c,b,first['review_id'],event)==follow
    out=r.load_store(root);assert len(out['records'][0]['history'])==1 and out['records'][0]['current_status']=='REFUTED'
    assert out['EARLY_count']==0 and out['records'][0]['first']['first_review_recorded_at']=='2026-10-05T15:30:00+00:00'


def test_no_overwrite_or_early_promotion(tmp_path):
    b,c,_=fixture();root=tmp_path/'store';first=r.generate(b,c,root)['records'][0]['first']
    changed=deepcopy(b);changed['annotations'][0]['hypothesis']['mechanism']='Changed hypothesis'
    with pytest.raises(ValueError,match='EXPLICIT_APPEND'):r.generate(changed,c,root)
    event=stamp_export({'kind':'REVIEW','summary':'Synthetic','annotator':'Test','status_after':'EARLY_FORECAST_CANDIDATE'})
    with pytest.raises(ValueError,match='NOT_EARLY_PROMOTION'):r.append_event(root,c,b,first['review_id'],event)


def test_period_precision_stays_raw_and_duplicates_not_independent(tmp_path):
    b,c,ref=fixture();b['annotations'].append(deepcopy(b['annotations'][0]))
    out=r.generate(b,c,tmp_path/'duplicate');assert len(out['records'])==1 and out['records'][0]['first']['source_status']['observed_origin_count']==1
    b,c,ref=fixture();b['annotations'][0]['period_expressions']=[{'raw':'ready date unknown','normalized':'2027-03-31','precision_note':'Invented','reference':ref('ready date unknown')}]
    with pytest.raises(ValueError,match='MUST_STAY_RAW_UNKNOWN'):r.generate(b,c,tmp_path/'invented-period')


def test_protected_store_and_objective_binding_fail(tmp_path):
    b,c,_=fixture()
    with pytest.raises(ValueError,match='PROTECTED_STORE'):r.generate(b,c,tmp_path/'live-state')
    bad=deepcopy(c);bad['objective_sha256']='different'
    with pytest.raises(ValueError,match='OBJECTIVE_BATCH_MISMATCH'):r.generate(b,bad,tmp_path/'bad-objective')
