from copy import deepcopy
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
import pytest
from bct import precursor_collection as c, precursor_discovery as pd, prospective, early_forecast

SCOPE={'product':'precision components','specification':'grade Z','region':'North America','customer_group':'industrial buyers','supply_pool':'qualified domestic producers'}


def html(name,text,scope=None):
    body='; '.join(k.replace('_',' ')+' is '+v for k,v in (scope or SCOPE).items())+'\n'+text
    ld={'@type':'NewsArticle','url':f'https://{name}.example/doc','@id':f'https://{name}.example/doc#article','datePublished':'2026-10-05T00:00:00Z','publisher':{'name':name}}
    raw='<html><head><link rel="canonical" href="https://'+name+'.example/doc"><meta property="og:site_name" content="'+name+'"><script type="application/ld+json">'+json.dumps(ld)+'</script></head><body><article>'+''.join('<p>'+line+'</p>' for line in body.split('\n'))+'</article></body></html>'
    return raw.encode()


def manifest(names):
    return {'collection_started_at':'2026-10-05T01:00:00Z','preexisting_document_ids':['old'],'preexisting_urls':['https://old.example/doc'],
            'documents':[{'document_id':n,'url':f'https://{n}.example/doc','collected_at':'2026-10-05T02:00:00Z'} for n in names]}


@pytest.fixture
def transport(monkeypatch):
    calls=[]
    source={'buyer':html('buyer','The customer signed firm new orders for 100 units in 2031.'),
            'maker':html('maker','Production ramp is delayed; qualification completes in 2031-2032.')}
    def fetch(url):
        calls.append(url);return source[url.split('//')[1].split('.')[0]],url,200,'text/html'
    monkeypatch.setattr(c.acquisition,'fetch',fetch)
    monkeypatch.setattr(c.acquisition,'now',lambda:'2026-10-05T03:00:00+00:00')
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return datetime(2026,10,5,3,tzinfo=timezone.utc)
    monkeypatch.setattr(pd,'datetime',Clock)
    monkeypatch.setattr(early_forecast,'datetime',Clock)
    return calls,source


def test_new_scope_pair_common_window_and_synthesis(tmp_path,transport):
    r=c.cycle(tmp_path,manifest(['buyer','maker']))
    assert r['scope_complete_events']==2 and len(r['independent_demand_supply_pairs'])==1
    assert len(r['common_future_window_pairs'])==1 and r['synthesized_targets']==1
    assert r['early_preflight']==1 and r['live_execution']['state']=='EXISTING_LIVE_STORE_NOT_CONFIGURED'
    assert r['existing_corpus_reprocessed']==0
    assert c.stored_documents(tmp_path)[0]['version']==c.stored_documents(tmp_path)[0]['body_sha256']


def test_opposite_side_request_only_and_resume_does_not_refetch(tmp_path,transport,monkeypatch):
    calls,source=transport
    reqs=[]
    def search(req,endpoint):reqs.append(req);return ['https://maker.example/doc']
    monkeypatch.setattr(c.acquisition,'search',search)
    # This fixture explicitly authorizes disclosure to its mocked transport.
    # Production private-cache queries default to blocked.
    m={**manifest(['buyer']),'external_query_authorized':True};r=c.cycle(tmp_path,m,search_endpoint='https://configured.example/search')
    assert [q['role'] for q in reqs]==['SUPPLY']
    assert reqs[0]['scope']['specification']=='grade z'
    assert r['early_preflight']==1 and len(calls)==2
    assert c.cycle(tmp_path,m,search_endpoint='https://configured.example/search')==r
    assert len(calls)==2


def test_old_ids_urls_and_pre_cutover_never_fetch(tmp_path,transport):
    calls,_=transport;m=manifest(['old']);m['documents']+=[{'document_id':'other','url':'https://old.example/doc','collected_at':'2026-10-05T02:00:00Z'},
           {'document_id':'prior','url':'https://prior.example/doc','collected_at':'2026-10-04T02:00:00Z'}]
    r=c.cycle(tmp_path,m)
    assert not calls and r['new_verified_documents']==0


def test_completed_history_is_excluded_after_existing_cache_activation(tmp_path,transport):
    calls,_=transport
    activation=c.init(tmp_path,manifest([]))
    completed=c.read(Path(__file__).resolve().parents[1]/'config/precursor-completed-exclusions.json')
    historic_id=next(x for x in completed['document_ids'] if x not in activation['excluded_document_ids'])
    historic_url=next(x for x in completed['urls'] if x not in activation['excluded_urls'])
    before=(tmp_path/'activation.json').read_bytes()
    assert c.capture(tmp_path,'https://buyer.example/doc',historic_id,activation)['status']=='EXISTING_CORPUS_EXCLUDED'
    assert c.capture(tmp_path,historic_url,'new-rss-id',activation)['status']=='EXISTING_CORPUS_EXCLUDED'
    assert not calls
    assert (tmp_path/'activation.json').read_bytes()==before
    assert c.capture(tmp_path,'https://buyer.example/doc','buyer',activation,collected_at='2026-10-05T02:00:00Z')['status']=='CAPTURED'


def test_missing_scope_no_domain_or_query_imputation(tmp_path,transport):
    calls,source=transport
    source['buyer']=html('buyer','The customer signed firm new orders in 2031.',{'product':'precision components'})
    r=c.cycle(tmp_path,manifest(['buyer']))
    assert r['scope_complete_events']==0 and r['synthesized_targets']==0
    d=c.stored_documents(tmp_path)[0]
    assert d['precursor_events'][0]['future_period']['precision']=='SOURCE_WINDOW_NOT_EXACT_NEED_DATE'
    assert set(d['precursor_events'][0]['missing_scope'])==set(pd.SCOPE)-{'product'}


def test_different_specification_never_pairs(tmp_path,transport):
    _,source=transport;source['maker']=html('maker','Production ramp is delayed; qualification completes in 2031-2032.',{**SCOPE,'specification':'different grade'})
    r=c.cycle(tmp_path,manifest(['buyer','maker']))
    assert r['synthesized_targets']==2 and not r['independent_demand_supply_pairs'] and not r['early_preflight']


def test_same_publisher_does_not_complete_independent_pair(tmp_path,transport):
    _,source=transport
    source['maker']=source['maker'].replace(b'"name": "maker"',b'"name": "buyer"').replace(b'content="maker"',b'content="buyer"')
    r=c.cycle(tmp_path,manifest(['buyer','maker']))
    assert not r['independent_demand_supply_pairs'] and not r['early_preflight']


def test_common_window_is_required_for_collection_freeze(tmp_path,transport):
    _,source=transport;source['maker']=html('maker','Production ramp is delayed; qualification completes in 2032.')
    r=c.cycle(tmp_path,manifest(['buyer','maker']))
    assert r['early_preflight']==1 and not r['common_future_window_pairs']
    assert r['live_execution']['state']=='NO_COMMON_FUTURE_WINDOW'


def test_provenance_failure_durable_and_other_sources_continue(tmp_path,transport):
    calls,source=transport;source['buyer']=source['buyer'].replace(b'<link rel="canonical"',b'<link rel="other"')
    r=c.cycle(tmp_path,manifest(['buyer','maker']))
    assert len(calls)==2 and r['new_verified_documents']==1
    assert r['new_seed_statuses']['PROVENANCE_BLOCKED']==1 and not r['early_preflight']


def test_public_shortage_only_confirmation(tmp_path,transport):
    _,source=transport;source['maker']=html('maker','A shortage is now confirmed. Production ramp is delayed; qualification completes in 2031-2032.')
    r=c.cycle(tmp_path,manifest(['buyer','maker']))
    assert not r['early_preflight'] and not r['common_future_window_pairs']


def test_scope_ambiguity_and_unknown_are_not_filled():
    body='product is parts; product is different parts; grade is UNKNOWN; market is US'
    fields=c.scope_fields(body)
    assert 'product' not in fields and 'specification' not in fields and fields['region']['value']=='US'


def test_bound_scope_values_match_source_and_relative_period_stays_raw():
    raw=html('buyer','Confirmed new orders for deployment next year.')
    d=c.acquisition.verify(raw,'https://buyer.example/doc','https://buyer.example/doc','2026-10-05T03:00:00+00:00');d['document_id']='buyer'
    d=c.structure(d);e=d['precursor_events'][0]
    for f in e['scope'].values():assert d['body'][f['locator']['start']:f['locator']['end']]==f['value']
    assert e['future_period']['start']=='UNKNOWN' and e['raw_period_references'][0]['text']=='next year'


def test_changed_hash_or_missing_session_cannot_freeze(tmp_path,transport):
    c.cycle(tmp_path,manifest(['buyer','maker']))
    activation=c.read(tmp_path/'activation.json');batch=c.read(next((tmp_path/'evaluations').glob('*.json')))['batch']
    result,prepared=pd.discover(batch,mode='LIVE');stats=c.counters(result,prepared)
    bad=deepcopy(activation);bad['engine_hashes']['early_forecast.py']='bad'
    with pytest.raises(ValueError,match='hash changed'):c.freeze(tmp_path,batch,result,stats,tmp_path/'missing',bad)
    with pytest.raises(ValueError,match='existing LIVE'):c.freeze(tmp_path,batch,result,stats,tmp_path/'missing',activation)
    assert not (tmp_path/'missing').exists()


def test_actual_wrapper_freeze_on_existing_fixture_session(tmp_path,transport,monkeypatch):
    # Existing regression fixture session under tmp only; not the operating LIVE store.
    feeds=tmp_path/'feeds.yaml';feeds.write_text('feeds:\n  primary: https://buyer.example/feed\n')
    store=tmp_path/'synthetic-fixture-store'
    monkeypatch.setattr(prospective,'_now',lambda:'2026-10-05T00:30:00+00:00')
    prospective.start(store,feeds)
    before=(store/'session.json').read_bytes()
    r=c.cycle(tmp_path/'collector',manifest(['buyer','maker']),live_store=store)
    assert r['live_execution']['frozen']==1
    first=next((store/'candidates').glob('*.json'));saved=prospective._read(first)
    assert saved['candidate_class']=='EARLY_FORECAST_CANDIDATE'
    assert (store/'session.json').read_bytes()==before
    assert {e['origin_publisher'] for e in saved['candidate_as_generated']['evidence']}=={'buyer','maker'}
    copied=tmp_path/'copied-first.json';copied.write_bytes(first.read_bytes())
    assert prospective._read(copied)['record_sha256']==saved['record_sha256']


def test_raw_capture_relocation_rebinds_private_paths(tmp_path,transport,monkeypatch):
    import shutil
    c.cycle(tmp_path/'first',manifest(['buyer']))
    shutil.copytree(tmp_path/'first',tmp_path/'second')
    changed={**manifest([]),'batch_number':2}
    r=c.cycle(tmp_path/'second',changed)
    assert r['new_verified_documents']==0 and r['context_verified_documents']==1


def test_workflow_consumes_delta_and_preserves_canonical_and_live():
    repo=Path(__file__).resolve().parents[1]
    rss=(repo/'.github/workflows/rss-live-check.yml').read_text()
    flow=(repo/'.github/workflows/precursor-acquisition.yml').read_text()
    assert 'if r[0] not in prior_ids' in rss and 'new-document-manifest.json' in flow
    assert 'scope' not in flow.split('git update-index')[1].split('\n')[0]
    assert 'git read-tree "$BASE_DATA_SHA"' in flow and 'test "$current_sha" = "$BASE_LIVE_SHA"' in flow
    assert 'session.json' in flow and 'canonical.sqlite3' not in flow
    assert 'retention-days: 30' in flow and 'git archive "$live_sha"' in flow


def test_unlabelled_prose_product_becomes_bounded_missing_scope_request(tmp_path,transport):
    _,source=transport
    source['buyer']=html('buyer','Signed firm new orders for precision components in 2031.',{'irrelevant':'context'})
    r=c.cycle(tmp_path,manifest(['buyer']))
    assert not r['scope_complete_events'] and not r['early_preflight']
    d=c.stored_documents(tmp_path)[0]
    assert d['precursor_events'][0]['scope']['product']['value']=='precision components'
    plan=c.evidence_plan([d]);assert {q['role'] for q in plan['requests']}=={'DEMAND','SUPPLY'}
    assert all(q['target']=='precision components' for q in plan['requests'])


def test_indirect_claim_retained_for_primary_source_acquisition_not_pair(tmp_path,transport):
    _,source=transport
    source['buyer']=html('buyer','According to a manufacturer, signed firm new orders for precision components in 2031.')
    r=c.cycle(tmp_path,manifest(['buyer']))
    d=c.stored_documents(tmp_path)[0]
    assert d['retained_collection_events'] and not d['precursor_events']
    assert not r['early_preflight'] and r['requests_this_cycle']==2


def test_both_sides_without_tension_request_only_missing_comparison_fields(tmp_path,transport):
    _,source=transport
    source['maker']=html('maker','Production ramp is delayed; qualification completes in 2031.')
    r=c.cycle(tmp_path,manifest(['buyer','maker']))
    assert r['independent_demand_supply_pairs'] and r['common_future_window_pairs'] and not r['early_preflight']
    plan=c.evidence_plan(c.stored_documents(tmp_path))
    assert len(plan['requests'])==2
    assert all('explicit_need_or_qualified_readiness_date' in q['missing_fields'] for q in plan['requests'])


def test_cached_publisher_cannot_be_changed_with_body_hash_unchanged(tmp_path,transport):
    c.cycle(tmp_path,manifest(['buyer']))
    path=next((tmp_path/'documents').glob('*.json'));record=c.read(path)
    record['origin_publisher']='Fake independent publisher'
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='provenance no longer bound'):c.stored_documents(tmp_path)
