"""Development feature checks, not independent extraction performance."""
from copy import deepcopy
import pytest
from bct.v4.adapters import CPUExtractor
from bct.v4.exploration import retain, save, source_review
from bct.v4.store import Ledger, sha
from test_v4_free_ai import document


def data(text='Atlas ordered two novel valves.'):
    d=document(text);a=text.index('novel valves')
    r={'status':'PASS','selected_windows':[{'start':0,'end':len(text),'text':text}],
       'spans':[{'document_id':d['document_id'],'body_sha256':d['body_sha256'],'label':'product','text':'novel valves',
                 'locator':{'start':a,'end':a+len('novel valves')},'confidence':.8,'semantic_status':'UNKNOWN'}]}
    return d,r


def test_cpu_proposals_preserved_without_ai_or_despite_bad_ai():
    d,r=data();original=deepcopy(r)
    for ai in ([],[{'event':'invented','event_attributes':{'product':'missing','role':'SUPPLY_INCREASE'}}]):
        x=retain(d,[r],ai)
        assert [e['original_proposal']for e in x['discoveries']if e['origin']=='CPU']==r['spans']
        assert x['validated_event_count']==0 and x['S1_S2_S3']==[0,0,0]
        assert r==original


def test_bad_cpu_position_is_preserved_but_never_adopted():
    d,r=data();r['spans'][0]['text']='fabricated'
    x=retain(d,[r]);assert x['discoveries'][0]['source_status']=='HELD'
    assert x['discoveries'][0]['original_proposal']==r['spans'][0]
    assert not x['CPU_validation']['records']


def test_diagnostic_inference_keeps_valid_mentions_and_raw_invalid_item(tmp_path):
    d,r=data();text=d['body'];a=text.index('novel valves')
    raw={'entities':{'product':[{'start':a,'end':a+12,'text':'novel valves','confidence':.9},
                                {'start':0,'end':5,'text':'invented','confidence':.99},
                                {'start':len(text),'end':len(text)+2,'text':'xx','confidence':.9}]}}
    class Model:
        def extract_entities(self,*args,**kwargs):return deepcopy(raw)
    e=CPUExtractor(tmp_path);e.model=Model();e.revision='fixture'
    with pytest.raises(ValueError,match='MODEL_SPAN_SOURCE_MISMATCH'):e.extract_windows(d,r['selected_windows'])
    x=e.extract_windows(d,r['selected_windows'],diagnostic=True)
    assert x['status']=='PARTIAL_REVIEW' and len(x['spans'])==1
    assert x['raw_windows'][0]['output']==raw and len(x['rejected_spans'])==2
    assert {b['reason']for b in x['rejected_spans']}=={'MODEL_SPAN_SOURCE_MISMATCH','MODEL_SPAN_OUTSIDE_INPUT'}


def test_bad_one_window_does_not_erase_previous_window(tmp_path):
    d,r=data();r['selected_windows'].append({'start':0,'end':5,'text':d['body'][:5]})
    class Model:
        def extract_entities(self,text,*args,**kwargs):
            if len(text)==5:return {'entities':{'product':[{'start':0,'end':5,'text':'wrong'}]}}
            s=r['spans'][0];return {'entities':{'product':[{'start':s['locator']['start'],'end':s['locator']['end'],'text':s['text']}]}}
    e=CPUExtractor(tmp_path);e.model=Model();e.revision='fixture'
    x=e.extract_windows(d,r['selected_windows'],diagnostic=True)
    assert len(x['spans'])==1 and len(x['raw_windows'])==2 and len(x['rejected_spans'])==1


def test_storage_requery_restore_originals(tmp_path):
    d,r=data();l=Ledger(tmp_path/'live');x=save(l,d,[r]);n=l.status()
    l.backup(tmp_path/'restored/v4.sqlite3');l.close()
    for root in ('live','restored'):
        l=Ledger(tmp_path/root);assert save(l,d,[r])==x and l.status()==n;l.close()


def test_source_review_not_independent_or_primary_adoption():
    d,r=data();d['primary_source_verified']=False;s=r['spans'][0];a=s['locator']['start'];b=s['locator']['end']
    review={'review_type':'SAME_SESSION_CODEX_SOURCE_REVIEW','independent':False,'human_verified':False,
        'references':[{'start':0,'end':len(d['body']),'quote':d['body']}],
        'product_reference':{'start':a,'end':b,'quote':'novel valves'},'role':'DEMAND_INCREASE','actuality':'ACTUAL','fields':{}}
    x=source_review(d,review,r['selected_windows'])
    assert x['source_gate']=='HELD_PRIMARY_SOURCE' and x['s_stage']=='UNKNOWN' and not x['candidates']
    with pytest.raises(ValueError,match='OUTSIDE_ACTUAL_READ'):source_review(d,review,[])
    review['independent']=True
    with pytest.raises(ValueError,match='ATTRIBUTION'):source_review(d,review,r['selected_windows'])


def test_money_cannot_be_promoted_by_source_review():
    d,r=data('Atlas ordered novel valves for $20 million.');text=d['body'];a=text.index('novel valves');q=text.index('20')
    review={'review_type':'SAME_SESSION_CODEX_SOURCE_REVIEW','independent':False,'human_verified':False,
        'references':[{'start':0,'end':len(text),'quote':text}],
        'product_reference':{'start':a,'end':a+12,'quote':'novel valves'},'role':'DEMAND_INCREASE','actuality':'ACTUAL',
        'fields':{'quantity':{'surface':'20','reference':{'start':q,'end':q+2,'quote':'20'}}}}
    with pytest.raises(ValueError,match='MONEY_NOT'):source_review(d,review,r['selected_windows'])
