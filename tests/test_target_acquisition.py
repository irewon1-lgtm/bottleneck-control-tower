import hashlib
import json
from pathlib import Path
from copy import deepcopy
import pytest
from bct import target_acquisition as a


def test_plan_preserves_leads_without_claiming_completeness():
    targets=[{'target':'widgets','demand_signal':True,'supply_signal':False,'document_ids':['seed']}]
    result=a.plan(targets)
    assert result['targets'][0]['sides']['DEMAND']['signal_present']
    assert result['requests'][0]['kind']=='MISSING_FIELDS'
    assert result['requests'][1]['kind']=='MISSING_SIDE'
    assert result['targets'][0]['common_future_period']=='UNKNOWN'


def test_complete_side_is_not_reacquired():
    facts={k: 'explicit' for k in a.FIELDS}
    result=a.plan([{'target':'widgets','demand_signal':True,'supply_signal':False,'document_ids':[], 'existing_verified_facts':{'DEMAND':[facts]}}])
    assert [r['role'] for r in result['requests']]==['SUPPLY']


def source(pub='Maker',date='2026-09-01T08:00:00+00:00'):
    ld={'@type':'NewsArticle','@id':'https://maker.example/document#article','url':'https://maker.example/document', 'datePublished':date,'publisher':{'name':pub}}
    return ('<html><head><link rel="canonical" href="https://maker.example/document"><meta property="og:site_name" content="Maker"><script type="application/ld+json">'+json.dumps(ld)+'</script></head><body><article><p>Maker qualified production capacity for widgets is 80 units.</p></article></body></html>').encode()


def test_provenance_requires_source_metadata_and_attribution():
    args=('https://maker.example/document','https://maker.example/document','2026-10-04T00:00:00+00:00')
    assert a.verify(source(),*args)['provenance']=='PASS'
    assert a.verify(source(pub='Reuters'),*args)['provenance']=='BLOCKED'
    assert a.verify(source(date=None),*args)['provenance']=='BLOCKED'
    assert a.verify(source(),args[0],'https://else.example/document',args[2])['provenance']=='BLOCKED'


def test_leads_preserve_period_and_units_without_scope_imputation():
    result=a.leads('Widgets capacity expands to 2 MW by 2027; commissioning is planned.','widgets',['SUPPLY'])
    assert result[0]['raw_quantities']==['2 MW']
    assert result[0]['raw_period_expressions']==['2027']
    assert result[0]['period']=='UNKNOWN'
    assert result[0]['region']=='UNKNOWN'
    assert not a.leads('A different product receives 100 orders.','widgets',['DEMAND'])


def test_single_ambiguous_quote_never_becomes_two_signals():
    result=a.leads('Widgets orders rise as widgets capacity expands.','widgets',a.ROLES)
    assert len(result)==1 and result[0]['role']=='AMBIGUOUS'


def test_blocked_provider_does_not_repeat_and_completed_requests_resume(tmp_path,monkeypatch):
    value=a.plan([{'target':'widgets','demand_signal':True,'supply_signal':False,'document_ids':[]}])
    calls=[]
    def blocked(req,endpoint):
        calls.append(req);raise OSError('Tunnel connection failed: 403 Forbidden')
    monkeypatch.setattr(a,'search',blocked)
    reqs,docs=a.collect(value,tmp_path,search_endpoint='https://search.example/search')
    assert len(calls)==1 and not docs
    assert all(r['search_status']=='CONNECT_BLOCKED' for r in reqs)
    a.collect(value,tmp_path,search_endpoint='https://search.example/search')
    assert len(calls)==1


def fixture_docs():
    result=[]
    for role,name,qty in [('DEMAND','buyer',100),('SUPPLY','maker',80)]:
        body=f'{name} independently reports {qty} widget units for 2027.'
        h=a.digest(body)
        result.append({'document_id':name,'body':body,'body_sha256':h,'origin_id':name,'origin_url':f'https://{name}.example/original', 'origin_publisher':name,'published_at':'2026-09-01T00:00:00+00:00','publication_precision':'TIMESTAMP','available_at':'2026-09-02T00:00:00+00:00','provenance':'PASS','provenance_verified':True,'evidence':[{'target':'widgets','role':role,'specification':'model A','region':'US','supply_pool':'US qualified model A', 'quantity':qty,'unit':'units','period':{'start':'2027-01-01','end':'2027-12-31'},'basis':'total','actual_statement':True,'status':'EXPLICIT_SCOPE_FACT','locator':{'start':0,'end':len(body)},'source_quote':body,'need_date':None,'available_date':None,'qualified':role=='SUPPLY'}]})
    return result


def test_frozen_engine_positive_and_unknown_and_independence_gates():
    docs=fixture_docs()
    assert a.evaluate(docs)['strict_ready']==['widgets']
    docs[1]['origin_publisher']='buyer'
    assert not a.evaluate(docs)['strict_ready']
    docs=fixture_docs();docs[1]['evidence'][0]['supply_pool']='UNKNOWN'
    assert not a.evaluate(docs)['strict_ready']
    docs=fixture_docs();docs[1]['provenance']='BLOCKED'
    assert not a.evaluate(docs)['strict_ready']


def test_private_urls_and_immutable_outputs(tmp_path):
    for u in ['https://127.0.0.1/a','https://localhost/a','http://public.example/a','https://user:pass@public.example/a']:
        with pytest.raises(ValueError):a.public_url(u)
    p=tmp_path/'result.json';a.put(p,{'value':1})
    with pytest.raises(FileExistsError):a.put(p,{'value':2})
    assert json.loads(p.read_text())=={'value':1}


def test_periods_intersect_without_expanding_source_windows():
    docs=fixture_docs()
    docs[0]['evidence'][0]['period']={'start':'2027-01-01','end':'2027-10-31'}
    docs[1]['evidence'][0]['period']={'start':'2027-03-01','end':'2027-12-31'}
    result=a.evaluate(docs)
    assert result['strict_ready']==['widgets']
    assert result['explicit_scope_period_overlaps'][0]['period']=={'start':'2027-03-01','end':'2027-10-31'}
    assert result['batch']['signals'][0]['source_period']==docs[0]['evidence'][0]['period']
    docs[1]['evidence'][0]['period']={'start':'2028-01-01','end':'2028-12-31'}
    assert not a.evaluate(docs)['strict_ready']


def test_republication_claim_cannot_become_independent_signal():
    docs=fixture_docs()
    docs[1]['evidence'][0]['claim_attribution']='INDEPENDENT_ORIGIN_UNVERIFIED'
    assert not a.evaluate(docs)['strict_ready']


def test_duplicate_body_not_counted_as_independent_input():
    docs=fixture_docs();docs.append(deepcopy(docs[1]))
    result=a.evaluate(docs)
    assert result['unique_body_documents']==2
    assert len(result['batch']['documents'])==2
