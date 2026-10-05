"""Generic AMPX-shaped fixtures; synthetic functional evidence, not performance."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import pytest
from bct import precursor_discovery as pd, prospective, early_forecast, forecast_discovery
from bct.objective_lock import stamp_export

NOW='2030-02-01T00:00:00Z'
SCOPE={'product':'energy storage cells','specification':'high specific energy grade X','region':'North America','customer_group':'public safety aerial systems','supply_pool':'origin-certified domestic manufacturers'}


def doc(name,text,scope=None):
    body='; '.join(f'{k.replace("_"," ")}: {v}' for k,v in (scope or SCOPE).items())+'\n'+text
    return {'document_id':name,'body':body,'body_sha256':hashlib.sha256(body.encode()).hexdigest(),
            'published_at':'2030-01-01T00:00:00Z','available_at':'2030-01-02T00:00:00Z',
            'origin_id':name,'origin_url':f'https://{name}.example/original','origin_publisher':name,
            'provenance_verified':True,'publication_precision':'TIMESTAMP'}


def fixture():
    return stamp_export({'mode':'LIVE','precursor_discovery':True,'documents':[
        doc('buyer','The agency awarded new procurement orders for deployment in 2031.'),
        doc('regulator','Origin restrictions on imports become effective in 2031.'),
        doc('investor','Government DPA investment funds a new factory for production in 2031.'),
        doc('manufacturer','Production ramp is delayed; qualification completes in 2032.')], 'signals':[]})


def replay(b):return pd.discover(b,mode='SYNTHETIC',now=NOW)


def field(event,doc,key,value,phrase):
    start=doc['body'].index(phrase)
    event[key]=value;event.setdefault('field_references',{})[key]={'locator':{'start':start,'end':start+len(phrase)},'source_quote':phrase}


def test_01_new_target_synthesized_without_dictionary():
    r,p=replay(fixture())
    assert len(p['synthesized_targets'])==1
    target=p['synthesized_targets'][0]
    assert target['scope']=={k:v.casefold() for k,v in SCOPE.items()}
    assert target['target_id'].startswith('precursor-')
    assert len(target['events'])==4
    assert target['independent_origin_count']==4
    assert len(r['candidates'])==1


def test_02_ampx_shape_unknown_totals_early_but_no_strict_s3():
    b=fixture();r,p=replay(b)
    c=r['candidates'][0]
    assert c['candidate_class']==early_forecast.CLASS
    assert c['future_demand_window']['text']=='2031'
    assert c['known_supply_window']['text']=='2032'
    assert c['quantitative_comparison']=='UNKNOWN' and c['decisive_UNKNOWN']
    assert {e['document_id'] for e in c['evidence']}=={'buyer','regulator','investor','manufacturer'}
    assert all(e.get('quantity','UNKNOWN')=='UNKNOWN' for e in c['evidence'])
    assert not forecast_discovery.discover(p,mode='SYNTHETIC',now=NOW)['candidates']
    from bct.future_hypothesis import compare_gap
    assert compare_gap([],now=NOW,change_confirmed=True)['stage']=='S2'
    assert all(not forecast_discovery.PUBLIC_CONFIRMATION.search(d['body']) for d in b['documents'])


def test_negative_A_sufficient_qualified_supply_before_need():
    b=fixture();d=doc('alternate','Sufficient qualified supply covers all contracted demand in 2030.')
    e=pd.extract_events(d)[0]
    field(e,d,'qualified',True,'qualified supply')
    field(e,d,'coverage_complete',True,'all contracted demand')
    field(e,d,'sufficiency_verified',True,'Sufficient qualified supply covers all contracted demand')
    d['precursor_events']=[e];b['documents'].append(d)
    r,_=replay(b)
    assert not r['candidates'] and r['outcomes'][0]['state']=='REFUTED'


def test_negative_B_demand_delayed_alongside_ramp():
    b=fixture();b['documents'][0]=doc('buyer','Confirmed new procurement orders are postponed for deployment in 2033.')
    r,p=replay(b)
    assert not r['candidates'] and p['synthesized_targets'][0]['state']=='DATA_WAIT'


def test_negative_C_same_company_releases_not_independent():
    b=fixture()
    for d in b['documents']:d.update(origin_publisher='One Manufacturer',origin_id=d['document_id'],origin_url='https://one.example/release/'+d['document_id'])
    r,p=replay(b)
    assert not r['candidates']
    assert p['synthesized_targets'][0]['independent_origin_count']==1


def test_negative_D_different_specifications_never_merge():
    b=fixture();b['documents'][3]=doc('manufacturer','Production ramp is delayed; qualification completes in 2032.',{**SCOPE,'specification':'incompatible grade Y'})
    r,p=replay(b)
    assert len(p['synthesized_targets'])==2 and not r['candidates']


def test_negative_E_prior_shortage_is_confirmation_not_discovery():
    b=fixture();b['documents'].append(doc('confirmation','A shortage of these cells is publicly confirmed.'))
    r,p=replay(b)
    assert not r['candidates'] and r['outcomes'][0]['state']=='MISSED_EARLY_DETECTION'
    assert all(s['document_id']!='confirmation' for s in p['signals'])


@pytest.mark.parametrize('missing',['supply','demand','scope','window','provenance'])
def test_missing_early_core_condition_is_data_wait(missing):
    b=fixture()
    if missing=='supply':b['documents']=b['documents'][:1]
    if missing=='demand':b['documents']=b['documents'][1:]
    if missing=='scope':
        d=b['documents'][3];d['body']=d['body'].replace('customer group: public safety aerial systems','unclassified customer');d['body_sha256']=hashlib.sha256(d['body'].encode()).hexdigest()
    if missing=='window':b['documents'][3]=doc('manufacturer','Production ramp is delayed; qualification completion date is unconfirmed.')
    if missing=='provenance':b['documents'][3]['provenance_verified']=False
    r,_=replay(b);assert not r['candidates']
    assert all(o['state']=='DATA_WAIT' for o in r['outcomes'])


def test_pending_with_overlapping_windows_alone_is_insufficient():
    b=fixture();b['documents'][3]=doc('manufacturer','Production ramp is delayed; qualification completes in 2031.')
    assert not replay(b)[0]['candidates']


def test_events_preserved_without_scope_or_shortage_words():
    d=doc('events','Export controls effective in 2031.\nInventory declined.\nLead time increased.\nSole supplier dependence persists.\nAlternative supplier certification is delayed until 2032.')
    events=pd.extract_events(d)
    assert {'REGULATION','INVENTORY','LEAD_TIME','CONCENTRATION','RAMP'} <= {k for e in events for k in e['event_types']}


def test_unsupported_scope_or_field_reference_rejected():
    b=fixture();d=b['documents'][3];e=pd.extract_events(d)[0]
    e['scope']['region']['value']='Europe';d['precursor_events']=[e]
    r,_=replay(b);assert not r['candidates'] and r['rejected_inputs']
    b=fixture();d=b['documents'][3];e=pd.extract_events(d)[0];e['qualified']=True;d['precursor_events']=[e]
    assert replay(b)[0]['rejected_inputs']


def test_forecast_not_committed_procurement():
    b=fixture();b['documents'][0]=doc('buyer','A forecast expects new procurement orders for deployment in 2031.')
    assert not replay(b)[0]['candidates']


@pytest.fixture
def live(tmp_path,monkeypatch):
    ticks=[datetime(2030,2,1,tzinfo=timezone.utc)]
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return ticks[0]
    monkeypatch.setattr(pd,'datetime',Clock);monkeypatch.setattr(early_forecast,'datetime',Clock)
    monkeypatch.setattr(prospective,'_now',lambda:ticks[0].isoformat())
    feeds=tmp_path/'feeds.yaml';feeds.write_text('feeds:\n  confirmation: https://confirmation.example/feed\n')
    root=tmp_path/'fixture-store';prospective.start(root,feeds)
    return root,ticks


def test_synthesis_freezes_and_confirmation_appends_without_backdate(live):
    root,ticks=live
    r=prospective.run(root,fixture(),early=True)
    assert r['first_frozen']==1
    path=next((root/'candidates').glob('*.json'));before=path.read_bytes();first=json.loads(before)
    assert len(first['source_document_ids'])==4
    assert first['candidate_first_detected_at']=='2030-02-01T00:00:00+00:00'
    ticks[0]=datetime(2030,2,2,tzinfo=timezone.utc)
    b=fixture();d=doc('confirmation','A shortage of these cells is publicly confirmed.')
    d.update(published_at='2030-02-02T00:00:00Z',available_at='2030-02-02T00:00:00Z');b['documents'].append(d)
    r=prospective.run(root,b,early=True)
    assert r['history_appended']==1 and path.read_bytes()==before
    assert r['evaluation']['rows'][0]['status']=='CONFIRMED'
    assert len(list((root/'runs').glob('*.json')))==2
    assert prospective._read(path)['record_sha256']==first['record_sha256']


def test_live_cannot_backdate():
    with pytest.raises(ValueError):pd.discover(fixture(),now=NOW)


def test_future_physical_quantity_gap_without_pending_ramp():
    b=stamp_export({'mode':'LIVE','documents':[
        doc('buyer','Firm new orders signed for 100 units total in 2031.'),
        doc('manufacturer','Total qualified capacity is 80 units in 2031.') ]})
    r,p=replay(b)
    assert len(r['candidates'])==1
    assert r['candidates'][0]['reason']=='POSSIBLE_QUANTITY_GAP'
    assert r['candidates'][0]['candidate_class']==early_forecast.CLASS
    assert r['candidates'][0]['s_stage_unchanged']
    # Prepared inputs still do not claim total coverage, S3, or exact period bounds.
    assert not forecast_discovery.discover(p,mode='SYNTHETIC',now=NOW)['candidates']


def test_growing_qualified_capacity_is_not_a_gap():
    b=stamp_export({'mode':'LIVE','documents':[
        doc('buyer','Firm new orders signed for 100 units total in 2031.'),
        doc('manufacturer','Total qualified capacity is 120 units in 2031.') ]})
    assert not replay(b)[0]['candidates']


def test_uncertain_ramp_requires_explicit_possible_missed_window():
    b=fixture();b['documents'][3]=doc('manufacturer','Production ramp may miss the demand window in 2031; qualification is pending.')
    assert replay(b)[0]['candidates']


def test_unverified_events_are_preserved_but_never_promoted():
    b=fixture()
    for d in b['documents']:d['provenance_verified']=False
    r,p=replay(b)
    assert not r['candidates'] and not p['synthesized_targets']
    assert len(p['retained_precursor_events'])==4
    assert all(e['extraction_status']=='PROVENANCE_OR_PUBLICATION_UNVERIFIED' for e in p['retained_precursor_events'])


def test_zero_quantity_requires_original_reference():
    b=fixture();d=b['documents'][3];e=pd.extract_events(d)[0];e['quantity']=0;d['precursor_events']=[e]
    assert replay(b)[0]['rejected_inputs']


def test_verified_component_relation_requires_same_scope_and_explicit_required_window():
    b=fixture();end_product='sensor packs'
    b['documents'][0]=doc('buyer','The agency awarded new procurement orders for deployment in 2031.',{**SCOPE,'product':end_product})
    relation_doc=doc('relation','energy storage cells required for sensor packs in 2031.',{**SCOPE,'product':end_product})
    quote=relation_doc['body'].split('\n')[-1];start=relation_doc['body'].index(quote)
    w=relation_doc['body'].index('2031')
    b['documents'].append(relation_doc)
    b['relationships']=[{'document_id':'relation','locator':{'start':start,'end':len(relation_doc['body'])},'source_quote':quote,'relationship':'VERIFIED_SUPPLY_CHAIN','component_product':'energy storage cells','target_product':end_product,'required_component_window':{'text':'2031','locator':{'start':w,'end':w+4}}}]
    r,p=replay(b)
    assert len(r['candidates'])==1
    assert 'relation' in {e['document_id'] for e in r['candidates'][0]['evidence']}
    b['relationships'][0].pop('required_component_window')
    assert not replay(b)[0]['candidates']


def test_snapshot_parser_never_promotes_domain_or_feed_dates(tmp_path):
    from bct.objective_lock import stamp_export
    d=doc('doc','The agency awarded new procurement orders for deployment in 2031.')
    path=tmp_path/'body.txt';path.write_text(d['body'])
    snapshot=stamp_export({'documents':[{'document_id':'doc','body_path':'body.txt','snapshot_metadata':{'id':'doc','body_sha256':d['body_sha256'],'provenance_verified':True,'published_at':'2030-01-01T00:00:00Z'}}]})
    b=pd.snapshot_batch(snapshot,tmp_path)
    assert b['documents'][0]['provenance_verified'] is False
    assert b['documents'][0]['published_at'] is None
    assert not replay(b)[0]['candidates']
    snapshot['documents'][0]['body_path']='../outside.txt'
    with pytest.raises(ValueError,match='outside artifact root'):pd.snapshot_batch(snapshot,tmp_path)


def test_freeze_followup_preserves_first_and_refutation(live):
    root,ticks=live
    r=prospective.run(root,fixture(),early=True)
    path=next((root/'candidates').glob('*.json'));before=path.read_bytes()
    ticks[0]=datetime(2030,2,2,tzinfo=timezone.utc)
    assert prospective.run(root,fixture(),early=True)['history_appended']==1
    b=fixture();d=doc('alternate','Sufficient qualified inventory covers all contracted demand in 2030.')
    e=pd.extract_events(d)[0]
    field(e,d,'qualified',True,'qualified inventory');field(e,d,'coverage_complete',True,'all contracted demand');field(e,d,'sufficiency_verified',True,'Sufficient qualified inventory covers all contracted demand')
    d['precursor_events']=[e];b['documents'].append(d)
    ticks[0]=datetime(2030,2,3,tzinfo=timezone.utc)
    r=prospective.run(root,b,early=True)
    assert r['evaluation']['rows'][0]['status']=='REFUTED'
    assert path.read_bytes()==before
    assert len(list((root/'candidate-history').glob('*/*.json')))==2


def test_date_precision_survives_prospective_freeze(live):
    root,_=live;b=fixture()
    for d in b['documents']:d.update(published_at='2030-01-01',publication_precision='DATE')
    assert prospective.run(root,b,early=True)['first_frozen']==1
    first=prospective._read(next((root/'candidates').glob('*.json')))
    assert set(first['source_publication_timestamps'].values())=={'2030-01-01'}
    assert all(d['publication_precision']=='DATE' for d in first['source_documents'])


def test_automatic_inventory_relief_blocks_without_reviewer_flags():
    b=fixture();b['documents'].append(doc('alternate','Sufficient qualified inventory covers all contracted demand in 2030.'))
    r,p=replay(b)
    assert not r['candidates'] and r['outcomes'][0]['state']=='REFUTED'
    assert any(e.get('sufficiency_verified') for e in p['retained_precursor_events'])


def test_qualified_substitute_ready_before_need_is_refutation():
    b=fixture();b['documents'].append(doc('alternate','Sufficient qualified supply from the alternative supplier covers all committed demand in 2030.'))
    assert replay(b)[0]['outcomes'][0]['state']=='REFUTED'


@pytest.mark.parametrize('key,value',[('region','different region'),('customer_group','different customers'),('supply_pool','different suppliers')])
def test_physical_scope_differences_never_fuse(key,value):
    b=fixture();b['documents'][3]=doc('manufacturer','Production ramp is delayed; qualification completes in 2032.',{**SCOPE,key:value})
    assert not replay(b)[0]['candidates']


def test_confirmation_cannot_expand_frozen_publisher_universe():
    b=fixture();b['documents'].append(doc('outside','A shortage is publicly confirmed.'))
    result,_=pd.discover(b,mode='SYNTHETIC',now=NOW,confirmation_domains=['confirmation.example'])
    assert not any(o['state'] in ('CONFIRMED','MISSED_EARLY_DETECTION') for o in result['outcomes'])
    assert any(r['reason']=='CONFIRMATION_OUTSIDE_FROZEN_SCOPE' for r in result['rejected_inputs'])


def test_exact_future_need_and_ready_dates_with_unknown_quantities():
    b=fixture();b['documents'][0]=doc('buyer','Firm new orders require delivery by 2031-03-01.')
    b['documents'][3]=doc('manufacturer','Qualification is pending; ready on 2031-12-31.')
    r,_=replay(b)
    assert r['candidates'] and r['candidates'][0]['quantitative_comparison']=='UNKNOWN'


def test_explicit_readiness_range_crossing_need_retains_unknown_date():
    b=fixture();b['documents'][3]=doc('manufacturer','Qualification completes in 2031–2032; ramp is pending.')
    r,_=replay(b)
    assert r['candidates']
    assert r['candidates'][0]['known_supply_window']['text']=='2031–2032'
    assert r['candidates'][0]['quantitative_comparison']=='UNKNOWN'
    assert all(e.get('available_date') is None for e in r['candidates'][0]['evidence'])


@pytest.mark.parametrize('rate',['kg/day','kg/hour','kg/person/day','kg per operating day'])
def test_stock_quantity_and_daily_production_rate_never_compare(rate):
    b=stamp_export({'mode':'LIVE','documents':[
        doc('buyer','Firm new orders signed for 1000 kg total in 2031.'),
        doc('manufacturer',f'Total qualified capacity is 80 {rate} in 2031.') ]})
    r,p=replay(b)
    assert not r['candidates']
    assert next(e for e in p['retained_precursor_events'] if e['document_id']=='manufacturer')['unit']==rate
