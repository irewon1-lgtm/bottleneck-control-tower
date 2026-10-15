"""Synthetic relation/cursor guards plus preserved real regression packets."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from bct import target_acquisition as a
from bct.objective_lock import stamp_export
from bct.v4 import quantitative_counterpart as q
from bct.v4.store import Ledger,sha,file_sha


def seed(product='NovelQ-17 device',role='DEMAND',kind='PRODUCT'):
    return {'id':'source-event','product':product,'entity_kind':kind,'role':role,
            'source':{'document_id':'doc','body_sha256':'h','origin_url':'https://maker.example/release','published_at':'2026-10-01'},
            'fields':{'supplier':'Maker Corporation','customer':'Customer Organization'}}


def test_party_facility_query_works_without_product_name_and_retains_scope_unknown():
    tasks=q.relation_tasks([seed()]);assert len(tasks)==4
    task=next(t for t in tasks if t['facet']=='MANUFACTURER_FACILITY')
    assert 'Maker Corporation'in task['query']and'NovelQ-17'not in task['query']
    assert task['independence']=='UNKNOWN'and task['s_stage']=='UNKNOWN'
    assert 'qualified_capacity'in task['missing']and 'need_window'in task['missing']


def test_facility_is_not_product_and_duplicate_seed_does_not_duplicate_tasks():
    s=seed('Example factory',kind='FACILITY')
    tasks=q.relation_tasks([s,s]);assert len(tasks)==4
    assert all(t['product']is None for t in tasks)
    bad=deepcopy(tasks[0]);bad['product']='Example factory'
    with pytest.raises(ValueError,match='FACILITY_NOT_PRODUCT'):q.validate_relation(bad)


def test_cross_institution_citation_can_be_found_without_product_literal():
    raw=b'<a href="https://agency.example/procurement/contract-123">Customer purchase contract</a><a href="https://maker.example/investor-relations/">Annual reports</a>'
    d={'origin_url':'https://maker.example/release','document_id':'doc','raw_sha256':sha(raw)}
    t=next(t for t in q.relation_tasks([seed()])if t['facet']=='CUSTOMER_CONTRACT')
    links=q.relation_links(t,d,raw)
    assert links[0]['url']=='https://agency.example/procurement/contract-123'
    assert links[0]['relation']=='UNKNOWN_REVIEW_REQUIRED'


def test_missing_manufacturer_does_not_start_global_manufacturing_menu_crawl():
    s=seed();s['fields']['supplier']=None;t=q.relation_tasks([s])[0]
    raw=b'<a href="https://www.eia.gov/consumption/manufacturing/">Manufacturing</a>'
    assert q.relation_links(t,{'origin_url':'https://www.eia.gov/x','document_id':'e','raw_sha256':sha(raw)},raw)==[]


def test_all_search_results_preserved_for_queue_not_only_three(monkeypatch):
    raw=('<rss><channel>'+''.join('<item><link>https://agency.example/'+str(i)+'</link></item>'for i in range(12))+'</channel></rss>').encode()
    monkeypatch.setattr(a,'fetch',lambda u:(raw,u,200,'application/xml'))
    assert len(a.search({'query':'public source'},'https://search.example'))==3
    assert len(a.search({'query':'public source'},'https://search.example',limit=20))==12


def test_pending_urls_and_cursor_survive_restart_and_are_not_adopted(tmp_path):
    t=q.relation_tasks([seed()])[0]
    t['urls']=[{'url':'https://agency.example/'+str(i),'via_document_id':'doc','status':'UNFETCHED_RELATION_LEAD','relation':'UNKNOWN_REVIEW_REQUIRED'}for i in range(9)]
    t['cursor']=3;t['id']=sha(['q2-relation-state-1',{k:v for k,v in t.items()if k!='id'}]);packet=stamp_export({'tasks':[t]})
    l=Ledger(tmp_path);assert q.save_relations(l,packet)['added']==1;l.close()
    l=Ledger(tmp_path);before=file_sha(l.path);assert q.save_relations(l,packet)['added']==0
    r=json.loads(l.db.execute("SELECT payload FROM events WHERE kind=?",(q.RELATION_KIND,)).fetchone()[0])
    assert len(r['urls'])-r['cursor']==6 and r['s_stage']=='UNKNOWN';assert file_sha(l.path)==before;l.close()
    newer=deepcopy(t);newer['cursor']=4;newer['id']=sha(['q2-relation-state-1',{k:v for k,v in newer.items()if k!='id'}])
    l=Ledger(tmp_path);q.save_relations(l,stamp_export({'tasks':[newer]}));current=q.latest_relations(l)
    assert len(current['tasks'])==1 and current['tasks'][0]['cursor']==4
    assert l.db.execute('SELECT count(*)FROM events').fetchone()[0]==2;l.close()


def test_manufacturer_model_proof_never_merges_configuration_or_loses_repeated_positions():
    raw=b'<link rel="canonical" href="https://www.aehr.com/spec"><h1>FOX-XP</h1><p>FOX-XP supports different configurations.</p>'
    body='FOX-XP\nFOX-XP supports different configurations.'
    d={'document_id':'catalogue','origin_url':'https://www.aehr.com/spec','body':body,'body_sha256':sha(body.encode()),'raw_sha256':sha(raw),'body_status':'FULL'}
    records=q.catalogue_identity(d,raw,['FOX-XP TM system','FOX-XP ® wafer-level equipment'])
    assert len(records)==2 and all(len(r['positions'])==2 for r in records)
    assert all(r['specification_equivalence']=='UNKNOWN_NOT_MERGED'for r in records)
    s=seed('FOX-XP TM system');s['verified_model_proof']=records[0]
    tasks=q.relation_tasks([s]);capacity=next(t for t in tasks if t['facet']=='FACILITY_CAPACITY_READY')
    assert '"FOX-XP"'in capacity['query']and'TM system'not in capacity['query']
    assert capacity['product']=='FOX-XP TM system'and capacity['scope']['manufacturer_model_proof']==records[0]
    s['verified_model_proof']=records[1]
    with pytest.raises(ValueError,match='MODEL_PROOF_SCOPE'):q.relation_tasks([s])


def test_real_twelve_regression_cases_and_qualified_supply_remain_unchanged():
    packet=json.loads(Path('docs/v4/quantitative/counterpart-review.json').read_text())
    assert len(packet['records'])==12
    for r in packet['records']:q.validate(r)
    facts=json.loads(Path('docs/v4/quantitative/relation-facts.json').read_text())['records']
    capacity=next(f for f in facts if f['relation']=='REPORTED_PRODUCT_CAPACITY')
    assert capacity['subject']=='Sonoma'and capacity['quantity']=='20'and capacity['unit']=='systems/month'
    assert capacity['bound']=='GREATER_THAN'and capacity['qualification']=='UNKNOWN'
    assert all(f['s_stage']=='UNKNOWN'for f in facts)
