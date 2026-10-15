"""Existing gap engine forwarding on synthetic source-reviewed facts only."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import pytest

from bct.v4.stage_bridge import project,save
from bct.v4.evidence_path import accept
from bct.v4.store import Ledger,sha


COVER='including all qualified suppliers, usable inventory and alternative suppliers'


def fixture(supply=100, spec='Grade A', customer='Hospitals', start='2028-01-01', end='2028-12-31', covered=True):
    documents,records=[],[]
    for i,role in enumerate(('DEMAND_INCREASE','SUPPLY_DECREASE')):
        scope=f'(spec: {spec}; region: US; supply pool: US qualified pool; period: {start} to {end}; basis: total)'
        qty='120' if i==0 else str(supply)
        body=(f'Total demand for zirconium optical sleeves {scope} increased to {qty} units for {customer}.' if i==0 else
              f'Total qualified supply for zirconium optical sleeves {scope} decreased to {qty} units for {customer}'+(' '+COVER if covered else '')+'.')
        d={'document_id':f'synthetic-{i}','body':body,'body_sha256':sha(body.encode()),
           'raw_sha256':sha(body.encode()),'origin_url':f'https://example.org/{i}',
           'origin_id':f'original-{i}','origin_event_id':f'event-{i}','origin_publisher':f'publisher-{i}',
           'published_at':'2026-10-01','acquired_at':'2026-10-02','provenance':'PASS',
           'primary_source_verified':True,'synthetic':True}
        ref=lambda value: {'start':body.index(value),'end':body.index(value)+len(value),'quote':value}
        fields={k:{'surface':v,'reference':ref(v)} for k,v in {
            'specification':spec,'region':'US','customer_group':customer,'supply_pool':'US qualified pool',
            'quantity':qty,'unit':'units','period':start+' to '+end,'basis':'total',
            **({'qualified_supply_coverage':COVER} if i==1 and covered else {})}.items()}
        review={'review_type':'SAME_SESSION_CODEX_SOURCE_REVIEW','independent':False,'human_verified':False,
                'product_reference':ref('zirconium optical sleeves'),'references':[ref(body)],'fields':fields,
                'role':role,'actuality':'ACTUAL','reason_ko':'합성 기능시험이며 실제 사건이 아닙니다.'}
        p={'reference':ref(body),'product':{'value':'zirconium optical sleeves','reference':ref('zirconium optical sleeves')},
           'fields':{k:{'value':v['surface'],'reference':v['reference']} for k,v in fields.items()},
           'review_fields':fields,'role':role,'actuality':'ACTUAL'}
        records.append(accept(d,p,source_review=review));documents.append(d)
    return documents,records


def test_synthetic_positive_forwards_actual_existing_engine_S3_without_live(tmp_path):
    docs,records=fixture();original=deepcopy(records)
    l=Ledger(tmp_path);result=save(l,docs,records,as_of='2026-10-15',synthetic=True)
    assert result['gap_stage_counts']=={'S3':1}
    assert result['gap_probes'][0]['engine_result']['stage']=='S3'
    assert result['gap_probes'][0]['engine']=='bct.future_hypothesis.compare_gap'
    assert records==original and not result['candidates'] and result['automatic_promotion'] is False
    assert l.db.execute('SELECT count(*) FROM firsts').fetchone()[0]==0
    assert l.db.execute('SELECT mode FROM runs').fetchone()==('SYNTHETIC_STAGE_PROBE',);l.close()


@pytest.mark.parametrize('supply,stage',[(150,'S2'),(120,'S2'),(100,'S3')])
def test_negative_relief_prevents_false_gap(supply,stage):
    docs,records=fixture(supply=supply)
    r=project(docs,records,as_of='2026-10-15',synthetic=True)
    assert r['gap_probes'][0]['stage']==stage


@pytest.mark.parametrize('field',['origin_id','origin_event_id','origin_publisher'])
def test_requote_or_unknown_independence_cannot_reach_S3(field):
    docs,records=fixture();docs[1][field]=docs[0][field]
    r=project(docs,records,as_of='2026-10-15',synthetic=True)
    assert not r['gap_probes'] and any(x['reason']=='INDEPENDENCE_NOT_VERIFIED' for x in r['held'])


def test_future_information_and_reading_only_not_accepted():
    docs,records=fixture();docs[0]['published_at']='2027-01-01'
    r=project(docs,records,as_of='2026-10-15',synthetic=True)
    assert not r['gap_probes'] and any(x['reason']=='FUTURE_PUBLICATION' for x in r['held'])
    docs,records=fixture();del records[0]['source_review']
    r=project(docs,records,as_of='2026-10-15',synthetic=True)
    assert not r['gap_probes'] and any('NOT_CPU' in x['reason'] for x in r['held'])


@pytest.mark.parametrize('start,end',[('2026-11-01','2027-01-01'),('2029-11-01','2029-12-31')])
def test_existing_12_to36_horizon_not_relaxed(start,end):
    docs,records=fixture(start=start,end=end)
    r=project(docs,records,as_of='2026-10-15',synthetic=True)
    assert not r['gap_probes'] and any(x['reason']=='OUTSIDE_12_TO_36_MONTHS' for x in r['held'])


def test_incomplete_coverage_not_s3_and_no_unknown_or_early_conversion():
    docs,records=fixture(covered=False)
    r=project(docs,records,as_of='2026-10-15',synthetic=True)
    assert r['gap_stage_counts']=={'S2':1}
    assert r['gap_probes'][0]['engine_result']['gates']['qualified_supply']=='UNKNOWN'


def test_synthetic_cannot_be_relabelled_real_and_wrong_source_quote_rejected():
    docs,records=fixture()
    r=project(docs,records,as_of='2026-10-15')
    assert not r['gap_probes'] and len(r['held'])==2
    docs[0]['body']='changed'
    r=project(docs,records,as_of='2026-10-15',synthetic=True)
    assert not r['gap_probes'] and any(x['reason']=='BODY_HASH_MISMATCH' for x in r['held'])


@pytest.mark.parametrize('field,value',[('specification','Grade B'),('region','EU'),('customer_group','Other customers'),('supply_pool','Other pool')])
def test_wrong_target_pair_not_combined(field,value):
    # Select from two independently well-formed fixture pairs, so each quote
    # remains valid; mismatching dimensions must still prevent any pairing.
    docs,records=fixture();other_docs,other_records=fixture(spec='Grade B',customer='Other customers')
    if field in ('specification','customer_group'):
        docs[1]=other_docs[1];records[1]=other_records[1]
    else:
        # Mutating a reviewed field alone is itself invalid, never trusted.
        records[1]['target'][field]['surface']=value
    r=project(docs,records,as_of='2026-10-15',synthetic=True)
    assert not r['gap_probes']


def test_actual_ten_facts_revalidated_and_stage_eight_not_promoted():
    repo=Path(__file__).resolve().parents[1]
    import gzip
    db=sqlite3.connect(':memory:');db.deserialize(gzip.decompress((repo/'docs/v4/supply-linkage/research-snapshot.sqlite3.gz').read_bytes()))
    docs=[json.loads(p)for p, in db.execute('SELECT payload FROM documents')];db.close()
    records=json.loads((repo/'docs/v4/supply-linkage/engine-results.json').read_text())['engine']['records']
    r=project(docs,records,as_of='2026-10-15')
    assert r['record_stage_counts']=={'S1':8,'UNKNOWN':2}
    assert not r['gap_probes'] and not r['candidates']


def test_known_related_relief_blocks_gap_until_supply_review_refreshed():
    docs,records=fixture()
    # A separately source-reviewed relief statement with the same scoped target.
    d=deepcopy(docs[1]);d['document_id']='synthetic-relief'
    p=deepcopy(records[1]['original_proposal']);p['role']='RELIEF'
    review=deepcopy(records[1]['source_review']['original_review']);review['role']='RELIEF'
    # This is an explicit test review, not a claim of real supply recovery.
    relief=accept(d,p,source_review=review)
    docs.append(d);records.append(relief)
    r=project(docs,records,as_of='2026-10-15',synthetic=True)
    assert not r['gap_probes'] and any(x['reason']=='RELIEF_REQUIRES_REVIEWED_SUPPLY_REFRESH' for x in r['held'])
    # Another customer is unrelated and must not block the original target.
    other_docs,other_records=fixture(customer='Other customers')
    d=deepcopy(other_docs[1]);d['document_id']='synthetic-relief-other'
    p=deepcopy(other_records[1]['original_proposal']);p['role']='RELIEF'
    review=deepcopy(other_records[1]['source_review']['original_review']);review['role']='RELIEF'
    docs[-1]=d;records[-1]=accept(d,p,source_review=review)
    r=project(docs,records,as_of='2026-10-15',synthetic=True)
    assert r['gap_stage_counts']=={'S3':1}
