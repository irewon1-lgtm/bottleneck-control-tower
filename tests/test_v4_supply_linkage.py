"""Source-adjudicated BACKFILL linkage, not model accuracy or lead performance."""
from copy import deepcopy
import json
import pytest
from bct.v4 import evidence_path, supply_linkage
from bct.v4.store import Ledger
from test_v4_evidence_path import case, scoped


def reviewed(text='Atlas ordered two novel valves.', product='novel valves', role='DEMAND_INCREASE', actuality='ACTUAL'):
    d,p=case(text,product,role,actuality)
    d.update(provenance='PASS',primary_source_verified=True)
    r={'review_type':'SAME_SESSION_CODEX_SOURCE_REVIEW','independent':False,'human_verified':False,
       'references':[p['reference']],'product_reference':p['product']['reference'],
       'role':role,'actuality':actuality,'fields':{},'reason_ko':'명시적 원문 검토. 독립 평가 아님.'}
    return d,{'id':'review1','document_id':d['document_id'],'review':r}


def test_actual_primary_order_reaches_existing_engine_and_persists(tmp_path):
    d,c=reviewed();l=Ledger(tmp_path/'research')
    x=supply_linkage.save(l,[d],[c],as_of='2026-10-15')
    r=x['engine']['records'][0]
    assert r['event_status']=='ADOPTED_RESEARCH_EVENT' and r['s_stage']=='S1'
    assert r['source_review']['original_review']==c['review']
    assert r['meaning_status']=='EXPLICIT_SOURCE_REVIEW_NOT_INDEPENDENT_OR_AUTOMATIC'
    assert x['engine']['counts']['S2']==x['engine']['counts']['S3']==0 and not x['candidates']
    assert not l.db.execute('select * from firsts').fetchall()
    before=l.status();l.backup(tmp_path/'restored/v4.sqlite3');l.close()
    for root in ['research','restored']:
        l=Ledger(tmp_path/root)
        assert supply_linkage.save(l,[d],[c],as_of='2026-10-15')==x and l.status()==before
        l.close()


@pytest.mark.parametrize('mutate,reason',[
    (lambda d,c:d.update(primary_source_verified=False),'PRIMARY_SOURCE'),
    (lambda d,c:d.update(provenance='BLOCKED'),'PROVENANCE'),
    (lambda d,c:d.update(published_at='2027-01-01'),'FUTURE_SOURCE'),
    (lambda d,c:d.update(body_sha256='wrong'),'BODY_HASH'),
    (lambda d,c:c['review']['product_reference'].update(quote='invented'),'EXACT_SOURCE'),
    (lambda d,c:c['review']['product_reference'].update(document_id='other'),'FOREIGN_DOCUMENT'),
    (lambda d,c:c['review'].update(independent=True),'ATTRIBUTION')])
def test_one_bad_case_is_held_without_stopping_other_targets(mutate,reason):
    d,c=reviewed();bad=deepcopy(d);bad['document_id']='bad';b=deepcopy(c);b['document_id']='bad';mutate(bad,b)
    out=supply_linkage.analyze([bad,d],[b,c],as_of='2026-10-15')
    assert out['cases'][0]['status']=='HELD' and reason in out['cases'][0]['reason']
    assert out['cases'][1]['s_stage']=='S1' and len(out['engine']['records'])==1


@pytest.mark.parametrize('text,product,role,actuality,reason',[
    ('Atlas ordered machines to produce novel valves.','novel valves','DEMAND_INCREASE','ACTUAL','ORDER_OUTPUT'),
    ('Atlas did not order novel valves.','novel valves','DEMAND_INCREASE','ACTUAL','NEGATED_ORDER'),
    ('Atlas received a grant for novel valves.','novel valves','DEMAND_INCREASE','ACTUAL','FUNDING_NOT_ORDER'),
    ('Novel valves production will increase.','Novel valves','SUPPLY_INCREASE','ACTUAL','PLANNED_SUPPLY'),
    ('Novel valves production was not reduced.','Novel valves','SUPPLY_DECREASE','ACTUAL','NEGATED_SUPPLY')])
def test_explicit_review_cannot_override_clear_contradiction(text,product,role,actuality,reason):
    d,c=reviewed(text,product,role,actuality)
    out=supply_linkage.analyze([d],[c],as_of='2026-10-15')
    assert reason in out['cases'][0]['reason'] and not out['engine']['records']


def test_money_is_not_quantity_and_reported_maker_is_not_qualified_pool():
    d,c=reviewed('Atlas ordered novel valves from Maker for $800 million.')
    text=d['body'];a=text.index('800')
    c['review']['fields']={'quantity':{'surface':'800','reference':{'start':a,'end':a+3,'quote':'800'}}}
    out=supply_linkage.analyze([d],[c],as_of='2026-10-15')
    assert 'MONEY_NOT_PHYSICAL' in out['cases'][0]['reason']
    a=text.index('Maker');c['review']['fields']={'supply_pool':{'surface':'Maker','reference':{'start':a,'end':a+5,'quote':'Maker'}}}
    out=supply_linkage.analyze([d],[c],as_of='2026-10-15');r=out['engine']['records'][0]
    assert r['target']['supply_pool'] is None and r['fields']['reported_supplier']['surface']=='Maker'
    assert c['review']['fields']['supply_pool']['surface']=='Maker'


def pair():
    d,p=scoped('Atlas ordered Helios heat pumps spec A in US for Hospital from Pool needed in 2028.','Helios heat pumps','DEMAND_INCREASE','Atlas')
    s,q=scoped('Delta Helios heat pumps production decreased spec A in US for Hospital from Pool in 2028.','Helios heat pumps','SUPPLY_DECREASE','Delta')
    return [d,s],{d['document_id']:[p],s['document_id']:[q]}


def test_same_underlying_announcement_is_not_independent_even_on_two_sites():
    docs,ps=pair();assert len(evidence_path.analyze(docs,ps,enabled=True)['pairs'])==1
    for d in docs:d['origin_event_id']='same-announcement'
    assert not evidence_path.analyze(docs,ps,enabled=True)['pairs']


def test_planned_supply_is_not_counted_as_available_supply():
    docs,ps=pair();ps[docs[1]['document_id']][0]['actuality']='PLAN'
    out=evidence_path.analyze(docs,ps,enabled=True)
    assert not out['pairs'] and not out['candidates']


def test_actual_and_planned_relief_preserved_but_unrelated_target_not_mixed():
    docs,ps=pair()
    for pub,mode in [('Epsilon','ACTUAL'),('Zeta','PLAN')]:
        r,p=scoped('Helios heat pumps lead times shortened spec A in US for Hospital from Pool in 2028.','Helios heat pumps','RELIEF',pub)
        p['actuality']=mode;docs.append(r);ps[r['document_id']]=[p]
    out=evidence_path.analyze(docs,ps,enabled=True);p=out['pairs'][0]
    assert len(p['related_relief'])==len(p['planned_relief_not_available_supply'])==1
    assert p['s_stage']=='UNKNOWN' and not out['candidates']


def test_historical_event_never_records_live_or_unsupported_S2_S3():
    d,c=reviewed();d['published_at']='2021-03-02';d['acquired_at']='2026-10-14'
    x=supply_linkage.analyze([d],[c],as_of='2026-10-15')
    assert x['cases'][0]['s_stage']=='S1' and not x['cases'][0]['live_discovery']
    assert x['new_LIVE_S1_S2_S3']==[0,0,0] and x['forecast_performance']=='NOT_RUN'


def test_contract_to_build_the_product_is_not_an_equipment_output():
    d,c=reviewed('Atlas awarded Builder a contract to produce novel valves.')
    x=supply_linkage.analyze([d],[c],as_of='2026-10-15')
    assert x['cases'][0]['s_stage']=='S1'


def test_new_review_run_does_not_duplicate_the_same_fact_in_existing_UI(tmp_path):
    from bct.v4.dashboard import ResearchReader
    d,c=reviewed();l=Ledger(tmp_path/'research')
    supply_linkage.save(l,[d],[c],as_of='2026-10-14')
    supply_linkage.save(l,[d],[c],as_of='2026-10-15');l.close()
    reader=ResearchReader(tmp_path,tmp_path/'research/v4.sqlite3')
    with reader.connection() as db:
        records,_,_=reader._state(db)
    assert len(records)==1 and next(iter(records.values()))['s_stage']=='S1'
