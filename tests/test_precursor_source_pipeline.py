"""Adversarial source/identity/date and integrated collection regressions."""
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from bct import precursor_collection as c, precursor_scope_reader as s
from bct import precursor_temporal as t, precursor_source_search as search
from bct import precursor_discovery as pd
from bct import precursor_official_source as official


def doc(body, name='maker', url=None):
    h=hashlib.sha256(body.encode()).hexdigest()
    return {'document_id':name,'body':body,'body_sha256':h,'version':h,'origin_id':name,
            'origin_url':url or 'https://'+name+'.example/press-release/original','origin_publisher':name,
            'published_at':'2026-09-01T00:00:00+00:00','publication_precision':'TIMESTAMP',
            'available_at':'2026-10-05T00:00:00+00:00','acquired_at':'2026-10-05T00:00:00+00:00',
            'provenance_verified':True,'provenance':'PASS'}


def events(body):return c.structure(doc(body))['retained_collection_events']


def test_five_fields_natural_prose_and_split_document_binding():
    body=('Signed new orders for military-grade tungsten for military drones in United States.\n'
          'The military-grade tungsten is supplied by Atlas Metals, a qualified manufacturer for military drones.\n')
    d=c.structure(doc(body));e=d['retained_collection_events'][0]
    assert {k:f['value'] for k,f in e['scope'].items()}=={'product':'tungsten','specification':'military-grade','region':'United States','customer_group':'military drones','supply_pool':'Atlas Metals'}
    assert not e['missing_scope']
    assert s.validate_references(d,d['retained_collection_events'])
    assert e['scope']['supply_pool']['link_kind']=='EXACT_REPEATED_PRODUCT'
    assert d['scope_read_mode']=='BACKFILL_QA'


def test_supplier_relationship_alone_does_not_establish_eligibility():
    es=events('Signed new orders for tungsten for military drones in United States.\nThe tungsten is supplied by Atlas Metals.')
    assert 'supply_pool' not in es[0]['scope']


def test_named_project_links_without_company_or_pronoun_imputation():
    es=events('The Natchez project produces high-purity nickel in Mississippi.\nThe Natchez project commissioning is delayed until 2028.')
    assert es[0]['scope']['product']['value']=='high-purity nickel'
    assert es[0]['scope']['product']['link_kind']=='EXACT_NAMED_CONTRACT_OR_PROJECT'
    assert not events('Atlas Metals makes tungsten.\nAtlas Metals qualification completes in 2028.')[0]['scope']
    assert not events('Atlas Metals makes tungsten.\nIts qualification completes in 2028.')[0]['scope']


def test_conflicting_specifications_and_customers_do_not_cross_bind():
    body=('Signed new orders for military-grade tungsten for military drones in United States.\n'
          'Signed new orders for non-Chinese tungsten for industrial buyers in Canada.\n'
          'The tungsten is supplied by Atlas Metals.')
    es=events(body)
    assert len(es)==2
    assert 'supply_pool' not in es[0]['scope'] and 'supply_pool' not in es[1]['scope']
    assert es[0]['scope']['customer_group']['value']=='military drones'
    assert es[1]['scope']['customer_group']['value']=='industrial buyers'


def test_multiple_products_do_not_union_scope():
    e=events('Signed new orders for tungsten and nickel for military drones in United States.')[0]
    assert not e['scope'] and e['scope_unknown_reason']=='MULTIPLE_PRODUCTS_NO_EXPLICIT_EVENT_BINDING'
    e=events('During a panel on turbines, transformers, and supply chain timelines, a manager described capacity investment.')[0]
    assert not e['scope'] and e['scope_unknown_reason']=='MULTIPLE_PRODUCTS_NO_EXPLICIT_EVENT_BINDING'


def test_unspecified_component_or_fuel_is_unknown_without_blocking_specific_goods():
    assert not s.valid_product('component') and not s.valid_product('fuel')
    assert s.valid_product('precision components') and s.valid_product('nuclear fuel')


def test_chrome_menu_region_taxonomy_and_valid_table_footnote():
    body=('Signed new orders for tungsten.\nREGION: Canada Europe United States\n'
          'Related articles: Signed new orders for nickel in Canada.\n'
          'Qualified production capacity for military-grade tungsten in United States is 80 units.')
    d=doc(body);raw=b'<article><p>Signed new orders for tungsten.</p><div class="country-selector">REGION: Canada Europe United States</div><div class="related">Related articles: Signed new orders for nickel in Canada.</div><table><tr><td>Qualified production capacity for military-grade tungsten in United States is 80 units.</td></tr></table></article>'
    out=c.structure(d,raw)
    assert len(out['retained_collection_events'])==2
    assert not any('Canada Europe' in f['value'] for e in out['retained_collection_events'] for f in e['scope'].values())
    assert any(e['quantity']==80 for e in out['retained_collection_events'])
    assert len(out['excluded_page_regions'])==2


@pytest.mark.parametrize('value',['the ID','company','facility','product','market','shares','stock','revenue','cash','a new vote','days,” the FMC said','Energy is developing lasers'])
def test_invalid_products_do_not_generate_queries(value):
    assert not s.valid_product(value)
    scope={k:'UNKNOWN' for k in pd.SCOPE};scope['product']=value
    p=search.bounded_plan({'requests':[{'request_id':'x','target':value,'scope':scope,'query':value,'role':'SUPPLY'}],'blocked':[]})
    assert not p['requests']


def test_model_punctuation_exact_source_and_missing_fields():
    d=c.structure(doc('Volkswagen opened pre-orders for the ID. Polo GTI, the first electric hot hatch.'))
    e=d['retained_collection_events'][0]
    assert e['scope']['product']['value']=='ID. Polo GTI'
    assert set(e['missing_scope'])==set(pd.SCOPE)-{'product'}
    assert s.validate_references(d,d['retained_collection_events'])


@pytest.mark.parametrize('value,precision,start,end',[
 ('2027-03-04','DATE','2027-03-04','2027-03-04'),
 ('March 2027','MONTH','2027-03-01','2027-03-31'),
 ('Q3 2027','QUARTER','2027-07-01','2027-09-30'),
 ('first half of 2027','HALF','2027-01-01','2027-06-30'),
 ('2027년 하반기','HALF','2027-07-01','2027-12-31'),
 ('2027년 3분기','QUARTER','2027-07-01','2027-09-30'),
 ('2028','YEAR','2028-01-01','2028-12-31')])
def test_literal_precision_ranges(value,precision,start,end):
    v=t.bounds(value);assert (v['precision'],v['start'],v['end'])==(precision,start,end)
    assert v['text']==value


def test_qualitative_and_relative_dates_not_invented():
    assert t.bounds('early 2028')['precision']=='QUALITATIVE_YEAR'
    assert t.bounds('18 months after')['start']=='UNKNOWN'
    anchor={**t.bounds('2026-10-01'),'reference':{'source_quote':'contract signed 2026-10-01'}}
    assert t.bounds('18 months after',anchor)['start']=='2028-04-01'
    assert t.bounds('after customer qualification')['start']=='UNKNOWN'


def test_contract_need_and_readiness_periods_separate():
    q='Signed new orders for tungsten on 2026-10-01; delivery required in first half of 2027; qualified supply ready in Q3 2027.'
    e=events(q)[0];facts=e['temporal_facts']
    assert [(p['fact_kind'],p['precision']) for p in facts['periods']]==[('CONTRACT_DATE','DATE'),('DEMAND_NEED','HALF'),('SUPPLY_READY','QUARTER')]
    for p in facts['periods']:
        r=p['reference'];assert q[r['locator']['start']:r['locator']['end']]==r['source_quote']


def test_physical_quantity_and_nominal_capacity_not_qualified_output():
    e=events('Signed new orders for tungsten for 100 units in 2027; $75 million funding for planned capacity expansion to 2 MW in 2028.')[0]
    facts=e['temporal_facts'];assert facts['financial_amounts_not_output']
    assert all(x['unit'] not in ('$','USD') for x in facts['quantities'])
    assert any(x['unit']=='MW' and x['fact_kind']=='NOMINAL_OR_PLANNED_CAPACITY' for x in facts['quantities'])
    assert facts['quantities'][0]['period']=='UNKNOWN'
    assert facts['quantities'][1]['period']['text']=='2028'
    assert facts['quantities'][0]['fact_kind']=='ORDER_QUANTITY'


def test_quantities_never_inherit_a_contract_date_from_another_clause():
    e=events('Signed new orders for tungsten on 2026-10-01; production capacity is 100 units.')[0]
    assert e['temporal_facts']['quantities'][0]['period']=='UNKNOWN'


@pytest.mark.parametrize('value,start,end',[
    ('First half of 2027','2027-01-01','2027-06-30'),
    ('third quarter of 2027','2027-07-01','2027-09-30'),
    ('fourth quarter of 2026','2026-10-01','2026-12-31'),
])
def test_natural_half_and_quarter_spelling(value,start,end):
    result=t.bounds(value);assert (result['start'],result['end'])==(start,end)


def test_independence_role_scope_and_copy_verification():
    seed=c.structure(doc('Signed new orders for tungsten in United States.','buyer'))
    maker=c.structure(doc('maker has qualified production capacity for tungsten in United States of 80 units.','maker'))
    req={'role':'SUPPLY','seed_document_ids':['buyer'],'scope':{k:'UNKNOWN' for k in pd.SCOPE}}
    req['scope'].update(product='tungsten',region='united states')
    assert search.validate_capture(req,maker,[seed])['state']=='VALID_PRIMARY_EVIDENCE'
    same=deepcopy(maker);same['origin_publisher']='buyer'
    assert search.validate_capture(req,same,[seed])['state']=='SAME_ORIGIN'
    wrong=deepcopy(req);wrong['scope']['region']='canada'
    assert search.validate_capture(wrong,maker,[seed])['new_evidence']==0
    secondary=deepcopy(maker);secondary['origin_url']='https://news.example/article'
    assert search.validate_capture(req,secondary,[seed])['state']=='SECONDARY_SOURCE_LEAD'
    assert search.validate_capture(req,maker,[maker,{**maker,'document_id':'copy'}])['state']=='DUPLICATE_OR_REPUBLICATION'


def test_press_release_path_does_not_promote_an_unrelated_publisher():
    d=c.structure(doc('Qualified production capacity for tungsten is 80 units.','newswire',url='https://newswire.example/press-release/copied-claim'))
    req={'role':'SUPPLY','seed_document_ids':[],'scope':{'product':'tungsten'}}
    assert search.validate_capture(req,d,[])['state']=='SECONDARY_SOURCE_LEAD'


def test_multiword_product_only_plan_does_not_execute_a_general_query(tmp_path,monkeypatch):
    import importlib.util
    spec=importlib.util.spec_from_file_location('collection_fixture',Path(__file__).with_name('test_precursor_collection.py'))
    f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
    raw=f.html('buyer','Signed firm new orders for precision components in 2031.',{'irrelevant':'context'})
    monkeypatch.setattr(c.acquisition,'fetch',lambda url:(raw,url,200,'text/html'))
    calls=[];monkeypatch.setattr(c.acquisition,'search',lambda *args:calls.append(args))
    result=c.cycle(tmp_path,f.manifest(['buyer']),search_endpoint=c.DEFAULT_SEARCH_ENDPOINT)
    assert not calls and result['search_statuses']==['BLOCKED_SEARCH_SCOPE']
    saved=c.read(next((tmp_path/'requests').glob('*.json')))
    assert saved['search_blocker']=='PRODUCT_ONLY_NO_VERIFIED_PROGRAM_SPEC_REGION_OR_PARTY'


def test_same_release_republication_with_new_metadata_is_duplicate():
    body=' '.join('word'+str(i) for i in range(100))
    assert search.copied_body(doc(body),doc('Different title '+body+' Extra footer'))


def test_primary_order_general_pages_and_access_errors():
    urls=['https://en.wikipedia.org/wiki/Tungsten','https://news.example/a','https://maker.example/press-release/a','https://agency.gov/a','https://www.sec.gov/Archives/a']
    assert search.select_urls(urls)==[urls[4],urls[3],urls[2]]
    assert search.error_status(HTTPError('url',403,'',{},None))=='HTTP_403'
    assert search.error_status(HTTPError('url',429,'',{},None))=='HTTP_429'
    assert search.error_status(TimeoutError())=='TIMEOUT'


def test_public_confirmation_excluded_and_replay_deterministic():
    d=doc('A shortage is now confirmed. Signed new orders for tungsten in 2027.')
    a=c.structure(d);b=c.structure(d)
    assert a==b and not c.evidence_plan([a])['requests']


def test_source_reference_tamper_fails():
    d=c.structure(doc('Signed new orders for tungsten in United States.'))
    d['retained_collection_events'][0]['scope']['product']['value']='nickel'
    with pytest.raises(ValueError,match='LOCATOR'):s.validate_references(d,d['retained_collection_events'])


def test_temporal_comparison_requires_disjoint_need_ready_and_relief_check():
    demand={'scope':{'product':'tungsten'},'temporal_facts':{'periods':[{**t.bounds('first half of 2027'),'fact_kind':'DEMAND_NEED'}]}}
    supply={'scope':demand['scope'],'temporal_facts':{'periods':[{**t.bounds('Q3 2027'),'fact_kind':'QUALIFICATION'}]}}
    assert t.compare(demand,supply)['state']=='POSSIBLE_TIMING_GAP'
    supply['temporal_facts']['periods'][0]= {**t.bounds('2027'),'fact_kind':'QUALIFICATION'}
    assert t.compare(demand,supply)['state']=='UNKNOWN'
    supply['temporal_facts']['relief']=[{'kind':'DEMAND_CANCEL_OR_DELAY'}]
    assert t.compare(demand,supply)['state']=='RECONCILE_RELIEF'
    supply['temporal_facts']['relief']=[{'kind':'COMPLETED_CAPACITY'}]
    assert t.compare(demand,supply)['state']=='RECONCILE_RELIEF'


def test_protected_engines_and_objective_byte_hashes():
    root=Path(__file__).resolve().parents[1]
    expected={'precursor_discovery.py':'614e841938daf41e34d7e31b97ec636f06f2997c8b7b4252926dd135e5bc2639','early_forecast.py':'51d90d2265baec516d20383579816c5155e46c69599a8e7b281d329843d17675','forecast_discovery.py':'5a491f55f14a3fef675c0ca652042bb1cd8b76cb0de40c6f003d55181e2480fd','prospective.py':'6ca939e378ffb02323feecb869aa1aac0e9f7b56ec5cbc92689233e30d65a153'}
    assert c.hashes()==expected
    assert '0b2de0186c92fa0c5466539b42cdf5a4fba164a7c9fb62092e396cb4ebe0cff7' in (root/'BCT_OBJECTIVE_LOCK.md').read_text()


def test_actual_six_case_excerpts_replay_without_research_verdict_as_truth():
    root=Path(__file__).resolve().parents[1]
    v=json.loads((root/'tests/fixtures/precursor_actual_sources.json').read_text())
    assert v['mode']=='BACKFILL_QA' and len(v['cases'])==6
    for row in v['cases']:
        assert hashlib.sha256(row['body'].encode()).hexdigest()==row['body_sha256']
        d=doc(row['body'],row['case'],row['source_url']);d['provenance_verified']=False
        first=c.structure(d);second=c.structure(d)
        assert first==second and s.validate_references(first,first['retained_collection_events'])
        assert first['scope_read_mode']=='BACKFILL_QA'
        # Excerpt metadata never turns a prior research verdict into a verified
        # original or supplies the missing product/customer/qualification scope.
        assert not first['provenance_verified']
        assert all(e['missing_scope'] for e in first['retained_collection_events'])
        if row['case']=='cpo_els_isolators':
            assert first['retained_collection_events'][0]['scope']['product']['value']=='Isolators'
            assert 'supply_pool' not in first['retained_collection_events'][0]['scope']
        if row['case']=='defense_tungsten':
            assert 'product' not in first['retained_collection_events'][0]['scope']
        if row['case']=='gas_turbine_slots':
            fact=t.extract(d,{'source_quote':row['body'],'locator':{'start':0,'end':len(row['body'])},'role':'CONTEXT'})
            assert fact['periods'][0]['precision']=='QUARTER'
            assert fact['periods'][0]['text']=='fourth quarter of 2026'
            assert fact['quantities'][0]['unit']=='GW'
            assert all(q['fact_kind']!='QUALIFIED_OUTPUT' for q in fact['quantities'])


def sec_listing():
    value={'cik':123,'name':'Atlas Metals','filings':{'recent':{'form':['8-K'],'accessionNumber':['0000000123-26-000001'],'filingDate':['2026-09-01'],'primaryDocument':['atlas.htm']}}}
    raw=json.dumps(value).encode();meta={'url':'https://data.sec.gov/submissions/CIK0000000123.json','status':'CAPTURED','acquired_at':'2026-10-05T00:00:00+00:00','raw_sha256':hashlib.sha256(raw).hexdigest()}
    return raw,meta


def test_sec_original_listing_identity_body_tables_and_exhibit_refusal():
    raw=b'<html><head><title>8-K</title></head><body><p>SEC Form 8-K</p><table><tr><td>Signed new orders for tungsten for 100 units in 2027.</td></tr></table><p>'+b'Issuer filing text. '*15+b'</p></body></html>'
    listing,meta=sec_listing();url='https://www.sec.gov/Archives/edgar/data/123/000000012326000001/atlas.htm'
    result=official.verify(raw,url,url,'2026-10-05T01:00:00+00:00',metadata_record=meta,metadata_raw=listing)
    assert result['provenance']=='PASS' and result['origin_publisher']=='Atlas Metals'
    assert result['publication_precision']=='DATE' and result['published_at']=='2026-09-01'
    assert '100 units' in result['body']
    other=url.replace('atlas.htm','exhibit.htm')
    assert official.verify(raw,other,other,'2026-10-05T01:00:00+00:00',metadata_record=meta,metadata_raw=listing)['provenance']=='BLOCKED'
    with pytest.raises(ValueError,match='HASH'):official.verify(raw,url,url,'2026-10-05T01:00:00+00:00',metadata_record=meta,metadata_raw=listing+b' ')


def test_sec_listing_is_acquired_once_across_workers(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    listing,meta=sec_listing();calls=[]
    monkeypatch.setattr(c.acquisition,'fetch',lambda url:(calls.append(url) or listing,url,200,'application/json'))
    url='https://www.sec.gov/Archives/edgar/data/123/000000012326000001/atlas.htm'
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda i:official.metadata(tmp_path,url),range(6)))
    assert len(calls)==1 and all(r==results[0] for r in results)


def test_sec_invalid_body_and_future_listing_cannot_pass():
    listing,meta=sec_listing();url='https://www.sec.gov/Archives/edgar/data/123/000000012326000001/atlas.htm'
    result=official.verify(b'blocked',url,url,'2026-10-05T01:00:00+00:00',metadata_record=meta,metadata_raw=listing)
    assert result['official_blocker']=='INVALID_FILING_BODY'
    raw=b'<html><body><p>'+b'SEC Form 8-K valid filing text. '*30+b'</p></body></html>'
    result=official.verify(raw,url,url,'2026-10-04T23:00:00+00:00',metadata_record=meta,metadata_raw=listing)
    assert result['provenance']=='BLOCKED' and not result['checks']['metadata_before_use']


def test_physical_unit_rate_mismatch_blocks_temporal_pair():
    demand={'scope':{'product':'tungsten'},'temporal_facts':{'periods':[{**t.bounds('first half of 2027'),'fact_kind':'DEMAND_NEED'}],'quantities':[{'unit':'units','rate':False}]}}
    supply={'scope':demand['scope'],'temporal_facts':{'periods':[{**t.bounds('Q3 2027'),'fact_kind':'QUALIFICATION'}],'quantities':[{'unit':'MW','rate':False}]}}
    assert t.compare(demand,supply)['reason']=='PHYSICAL_UNIT_OR_RATE_MISMATCH'


def test_older_parser_capture_cannot_become_live_or_query_on_new_cycle(tmp_path,monkeypatch):
    # Old immutable fixture capture, not a historical LIVE success.
    import importlib.util
    spec=importlib.util.spec_from_file_location('collection_fixture',Path(__file__).with_name('test_precursor_collection.py'))
    f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
    raw=f.html('buyer','Signed firm new orders for 100 units in 2031.')
    monkeypatch.setattr(c.acquisition,'fetch',lambda url:(raw,url,200,'text/html'))
    c.cycle(tmp_path,f.manifest(['buyer']))
    p=next((tmp_path/'documents').glob('*.json'));old=c.read(p)
    old.pop('scope_reader_version');old.pop('scope_read_mode');p.write_text(json.dumps(old))
    old_bytes=p.read_bytes();calls=[]
    monkeypatch.setattr(c.acquisition,'search',lambda *a:calls.append(a))
    result=c.cycle(tmp_path,{**f.manifest([]),'batch_number':2},search_endpoint=c.DEFAULT_SEARCH_ENDPOINT)
    assert result['backfill_qa_documents']==1 and result['early_preflight']==0 and not calls
    assert p.read_bytes()==old_bytes
