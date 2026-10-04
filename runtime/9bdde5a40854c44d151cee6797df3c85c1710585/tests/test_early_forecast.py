"""EARLY functional regressions; none constitutes observed prediction success."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pytest
from bct import early_forecast as early, prospective as p
from bct.objective_lock import stamp_export
from bct.future_hypothesis import compare_gap


def batch():
    texts = [('buyer', 'DEMAND', 'Confirmed new orders require qualified transformers in 2031.'),
             ('maker', 'SUPPLY', 'Transformer capacity expansion remains under construction until 2032.')]
    docs, signals = [], []
    for org, role, text in texts:
        docs.append({'document_id':org,'body':text,'body_status':'FULL',
                     'body_sha256':hashlib.sha256(text.encode()).hexdigest(),
                     'published_at':'2030-01-01T00:00:00Z','available_at':'2030-01-01T00:00:00Z',
                     'origin_id':org,'origin_publisher':org,'origin_url':'https://'+org+'.example/source',
                     'provenance_verified':True})
        loc={'start':0,'end':len(text)}
        s={'document_id':org,'target_id':'transformer','target':'Qualified transformers',
           'specification':'230kV','region':'US','supply_pool':'qualified US',
           'period':{'start':'2031-01-01','end':'2031-12-31'},'role':role,
           'signal_type':'committed_order' if role=='DEMAND' else 'production_ramp',
           'quantity':'UNKNOWN','unit':'UNKNOWN','basis':'total','qualified':False,
           'target_relation_verified':True,'locator':loc,'source_quote':text}
        if role=='DEMAND':s.update(demand_status='COMMITTED',increase_kind='NEW_ORDER',increase_locator=loc,
                                  future_demand_window={'text':'2031','locator':loc})
        else:s.update(supply_status='UNDER_CONSTRUCTION',status_locator=loc,
                       known_supply_window={'text':'2032','locator':loc})
        s['target_relation_reference']={'document_id':org,'locator':loc,'source_quote':text,'relationship':'SAME_TARGET'}
        signals.append(s)
    return stamp_export({'mode':'LIVE','documents':docs,'signals':signals})


def replay(b):return early.discover(b,mode='SYNTHETIC',now='2030-02-01T00:00:00Z')


def test_A_one_independent_source_no_candidate():
    b=batch();b['documents'][1].update(origin_id='buyer',origin_publisher='buyer',origin_url=b['documents'][0]['origin_url'])
    r=replay(b);assert not r['candidates'];assert r['outcomes'][0]['independent_origin_count']==1


def test_B_three_reposts_do_not_increase_origin_count():
    b=batch();original=b['documents'][0]
    for d in b['documents']:d.update(origin_id='buyer',origin_publisher='buyer',origin_url=original['origin_url'])
    for i in range(3):
        d=deepcopy(b['documents'][1]);d['document_id']='reprint-'+str(i)
        s=deepcopy(b['signals'][1]);s['document_id']=d['document_id']
        b['documents'].append(d);b['signals'].append(s)
    r=replay(b);assert not r['candidates'];assert r['outcomes'][0]['independent_origin_count']==1


def test_C_unrelated_targets_never_fused():
    b=batch();b['signals'][1]['target_id']='other';b['signals'][1]['target']='Other product'
    assert not replay(b)['candidates']


def test_D_unknown_totals_generate_only_early_candidate():
    r=replay(batch());assert len(r['candidates'])==1
    c=r['candidates'][0];assert c['candidate_class']==early.CLASS
    assert c['independent_origin_count']==2 and c['quantitative_comparison']=='UNKNOWN'
    assert all(e['quantity']=='UNKNOWN' for e in c['evidence'])
    assert c['future_demand_window']['text']=='2031' and c['refutation_conditions']
    assert c['candidate_first_detected_at']=='2030-02-01T00:00:00+00:00'
    assert r['performance_PASS'] is None


def sufficient():
    b=batch();b['signals'][0].update(quantity=100,unit='units',need_date='2031-06-01')
    b['signals'][1].update(quantity=120,unit='units',qualified=True,coverage_complete=True,
                            available_date='2031-05-01')
    for index,text in enumerate(['Confirmed new orders require 100 qualified transformers on June 1, 2031.',
                                 'Qualified transformer expansion secures 120 units by May 1, 2031 before need.']):
        d=b['documents'][index];s=b['signals'][index];d.update(body=text,body_sha256=hashlib.sha256(text.encode()).hexdigest())
        loc={'start':0,'end':len(text)};s.update(source_quote=text,locator=loc)
        s['target_relation_reference'].update(source_quote=text,locator=loc)
        if index==0:s.update(increase_locator=loc,future_demand_window={'text':'2031','locator':loc})
        else:s.update(status_locator=loc,known_supply_window={'text':'2031','locator':loc})
    return b


def test_E_complete_qualified_supply_before_need_refutes():
    r=replay(sufficient());assert not r['candidates'];assert r['outcomes'][0]['state']=='REFUTED'


def confirmation():
    text='A shortage of qualified transformers is publicly confirmed.'
    return {'target_id':'transformer','explicit':True,'target_match_verified':True,
            'document':{'body':text,'body_sha256':hashlib.sha256(text.encode()).hexdigest(),
                        'published_at':'2030-01-15T00:00:00Z','available_at':'2030-01-15T00:00:00Z',
                        'url':'https://official.example/original','provenance_verified':True},
            'locator':{'start':0,'end':len(text)}}


def test_F_prior_explicit_confirmation_is_missed_not_new_early():
    b=batch();b['confirmations']=[confirmation()];r=replay(b)
    assert not r['candidates'];assert r['outcomes'][0]['state']=='MISSED_EARLY_DETECTION'
    assert r['outcomes'][0]['early_detection_success'] is False


def test_G_early_does_not_promote_S2_or_write_reviews(tmp_path):
    tracking=tmp_path/'tracking.json';tracking.write_text(json.dumps({'reviews':{'r':{'s_stage':'S2'}}}))
    before=tracking.read_bytes();assert replay(batch())['candidates']
    assert tracking.read_bytes()==before
    assert compare_gap([],now='2030-02-01T00:00:00Z',change_confirmed=True)['stage']=='S2'
    assert not any('s_stage' in c for c in replay(batch())['candidates'])


def test_H_existing_S_gate_meanings_still_enforced():
    from test_future_review_v33 import deep_review, documents, gate
    from bct.future_review import validate_review
    from bct.future_store import PatchError
    r=deep_review();assert validate_review(documents(),{},r)['s_stage']=='S3'
    r['gates']['future_demand']=gate('UNKNOWN')
    with pytest.raises(PatchError):validate_review(documents(),{},r)
    r['s_stage']='S2';assert validate_review(documents(),{},r)['s_stage']=='S2'
    r['gates']['target_relation']=gate('UNKNOWN');r['s_stage']='S1'
    assert validate_review(documents(),{},r)['s_stage']=='S1'
    r['gates']['change']=gate('FALSE');r['s_stage']='NONE'
    assert validate_review(documents(),{},r)['s_stage']=='NONE'


@pytest.fixture
def live(tmp_path,monkeypatch):
    ticks=[datetime(2030,2,1,tzinfo=timezone.utc)]
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return ticks[0]
    monkeypatch.setattr(early,'datetime',Clock)
    monkeypatch.setattr(p,'_now',lambda:ticks[0].isoformat())
    feeds=tmp_path/'feeds.yaml';feeds.write_text('feeds:\n  official: https://official.example/feed\n')
    root=tmp_path/'live';p.start(root,feeds)
    return root,ticks


def test_I_first_snapshot_immutable_followups_and_refutation_append(live):
    root,ticks=live;r=p.run(root,batch(),early=True);assert r['first_frozen']==1
    path=next((root/'candidates').glob('*.json'));before=path.read_bytes()
    first=json.loads(before);assert first['candidate_class']==early.CLASS
    assert first['candidate_first_detected_at']=='2030-02-01T00:00:00+00:00'
    assert first['future_demand_window']['text']=='2031'
    assert r['evaluation']['rows'][0]['status']=='OPEN'
    ticks[0]=datetime(2030,2,2,tzinfo=timezone.utc)
    b=batch();b['candidate_annotations']={'transformer':{'decisive_UNKNOWN':['Updated quantity UNKNOWN']}}
    assert p.run(root,b,early=True)['history_appended']==1
    assert path.read_bytes()==before
    ticks[0]=datetime(2030,2,3,tzinfo=timezone.utc)
    result=p.run(root,sufficient(),early=True)
    assert result['history_appended']==1 and path.read_bytes()==before
    assert result['evaluation']['rows'][0]['status']=='REFUTED'
    assert len(list((root/'candidate-history').glob('*/*.json')))==2


@pytest.mark.parametrize('change',['forecast','no_window','wrong_quote','scope','no_pending','past_window','hash'])
def test_fail_closed_missing_or_invalid_requirements(change):
    b=batch()
    if change=='forecast':b['signals'][0]['demand_status']='GENERAL_FORECAST'
    elif change=='no_window':b['signals'][0].pop('future_demand_window')
    elif change=='wrong_quote':b['signals'][1]['source_quote']='Invented statement'
    elif change=='scope':b['signals'][1]['specification']='Different specification'
    elif change=='no_pending':b['signals'][1]['supply_status']='UNKNOWN'
    elif change=='past_window':b['signals'][0]['future_demand_window']['text']='2029'
    else:b['documents'][1]['body_sha256']='0'*64
    assert not replay(b)['candidates']


def test_live_cannot_backdate_and_backfill_cannot_enter_wrapper(live):
    root,_=live
    with pytest.raises(ValueError):early.discover(batch(),now='2000-01-01T00:00:00Z')
    b=batch();b['mode']='BACKFILL'
    with pytest.raises(p.Blocked):p.run(root,b,early=True)


def test_confirmation_without_verified_hash_is_not_trusted():
    b=batch();b['confirmations']=[confirmation()];b['confirmations'][0]['document']['body_sha256']='0'*64
    with pytest.raises(ValueError):replay(b)



def test_verified_qualitative_relief_before_window_blocks_pending_supplier():
    b=batch();d=deepcopy(b['documents'][1]);d['document_id']='alternative'
    d['body']='Sufficient qualified transformer supply for all orders is secured in 2030.'
    d['body_sha256']=hashlib.sha256(d['body'].encode()).hexdigest()
    d.update(origin_id='alternative',origin_publisher='alternative',origin_url='https://alternative.example/source')
    s=deepcopy(b['signals'][1]);s['document_id']='alternative'
    loc={'start':0,'end':len(d['body'])}
    s.update(quantity='UNKNOWN',qualified=True,coverage_complete=True,supply_status='AVAILABLE',
             sufficiency_verified=True,sufficiency_locator=loc,source_quote=d['body'],locator=loc,
             known_supply_window={'text':'2030','locator':loc})
    s['target_relation_reference'].update(document_id='alternative',locator=loc,source_quote=d['body'])
    b['documents'].append(d);b['signals'].append(s)
    r=replay(b);assert not r['candidates'];assert r['outcomes'][0]['state']=='REFUTED'
    assert compare_gap([],now='2030-02-01T00:00:00Z',change_confirmed=True)['stage']=='S2'


def test_unknown_publication_is_retained_only_with_real_acquisition_bound(live):
    root,_=live;b=batch();d=b['documents'][1]
    d.update(published_at=None,publication_precision='UNKNOWN',public_snapshot_observed_at=d['available_at'])
    assert p.run(root,b,early=True)['first_frozen']==1
    stored=p._read(next((root/'candidates').glob('*.json')))
    assert stored['source_publication_timestamps']['maker'] is None
    invalid=batch();invalid['documents'][1].update(published_at=None,publication_precision='UNKNOWN')
    assert not replay(invalid)['candidates']


def test_old_early_output_is_not_fresh_live_input(live):
    root,_=live;b=batch();b['format']='bct-early-forecast-v1'
    with pytest.raises(p.Blocked):p.run(root,b,early=True)



def test_generic_short_lead_time_does_not_imply_future_tension():
    b=batch();d=b['documents'][1];s=b['signals'][1]
    text='Transformer lead time is six weeks, with availability planned in 2031.'
    d.update(body=text,body_sha256=hashlib.sha256(text.encode()).hexdigest())
    loc={'start':0,'end':len(text)}
    s.update(source_quote=text,locator=loc,status_locator=loc,supply_status='LONG_LEAD_TIME',
             known_supply_window={'text':'2031','locator':loc})
    s['target_relation_reference'].update(source_quote=text,locator=loc)
    r=replay(b);assert not r['rejected_inputs']
    assert not r['candidates'] and r['outcomes'][0]['state']=='DATA_WAIT'


def test_known_sufficient_supplier_in_other_scope_does_not_refute_this_target():
    b=sufficient();b['signals'][1]['specification']='Different product'
    r=replay(b);assert not r['candidates'];assert all(x['state']=='DATA_WAIT' for x in r['outcomes'])
