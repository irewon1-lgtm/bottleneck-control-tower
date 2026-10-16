"""Consumed/synthetic research checks, never independent forecast accuracy."""
import json
import sys
from pathlib import Path

import pytest
from bct.v4 import official_discovery as d
from bct.v4.store import Ledger,sha,file_sha

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from v4_official_discovery import relation_index_links,bidirectional


@pytest.mark.parametrize('sentence,expected',[
 ('Production capacity for gas turbines increased in 2026.',('RELIEF','REPORTED_SUPPLY_CHANGE','REPORTED_ACTUAL')),
 ('Production capacity for gas turbines will increase in 2028.',('SUPPLY_PLAN','REPORTED_SUPPLY_CHANGE','PLANNED_OR_EXPECTED')),
 ('The gas turbine plant was delayed until 2028.',('CONSTRAINT','FACILITY_OR_QUALIFICATION_CONSTRAINT','REPORTED_ACTUAL')),
 ('Lead times for gas turbines increased.',('CONSTRAINT','REPORTED_SUPPLY_CHANGE','REPORTED_ACTUAL')),
 ('Lead times for gas turbines decreased.',('RELIEF','REPORTED_SUPPLY_CHANGE','REPORTED_ACTUAL')),
 ('Gas turbine production did not increase.',('CONTEXT','NEGATED_CHANGE','NEGATED')),
 ('The machine can process up to 1000 wafers per hour.',('CONTEXT','PROCESSING_SPECIFICATION_NOT_MANUFACTURER_CAPACITY','SPECIFICATION')),
 ('Customer orders for gas turbines were cancelled.',('RELIEF','DEMAND_REDUCTION','REPORTED_ACTUAL')),
 ('Gas turbine backlog increased to $800 million.',('DEMAND','BACKLOG_OR_BOOKINGS','REPORTED_ACTUAL')),
 ('The company plans investment in a new factory.',('SUPPLY_PLAN','INVESTMENT_NOT_AVAILABLE_CAPACITY','PLANNED_OR_EXPECTED')),
])
def test_direction_and_actual_vs_plan(sentence,expected):
 assert d.context_role(sentence)==expected


@pytest.mark.parametrize('text,expected',[
 ('Purchase of new gas turbines.','UNKNOWN_ORDINARY_ORDER_NOT_PROVEN_INCREMENT'),
 ('This contract replaces existing gas turbines.','REPLACEMENT_OR_RENEWAL_NOT_PROVEN_INCREMENT'),
 ('No additional orders were made.','CANCELLED_OR_NEGATED_NOT_INCREMENT'),
 ('The company received additional orders.','REPORTED_INCREMENT_PRIOR_BASELINE_UNKNOWN')])
def test_new_contract_is_not_incremental_demand(text,expected):
 assert d.demand_status(text)==expected


def page(sentence):
 raw=('<html><body><article><h1>Official update</h1><p>'+sentence+'</p><p>'+
      'The operating figures are reported by the facility operator. These figures do not establish customer allocation or the entire qualified supply pool.'+
      '</p></article></body></html>').encode()
 return raw,{'url':'https://example.gov/official-update','source_id':'OFFICIAL:example.gov',
             'sha256':sha(raw),'acquired_at':'2026-10-16T12:00:00Z','published_at':'2026-10-15'}


def test_exact_native_position_not_first_global_product_occurrence():
 raw,m=page('Gas turbines were discussed. Production capacity for gas turbines increased in 2026.')
 r=d.read_context(raw,m)
 e=next(e for e in r['events']if e['role']=='RELIEF')
 assert e['product']=='gas turbines'
 assert raw.decode()[e['product_position']['start']:e['product_position']['end']]=='gas turbines'
 assert e['product_position']['start']>raw.decode().lower().index('gas turbines')
 assert not e['qualified'] and e['qualified_capacity']is None
 assert d.context_seeds([r])[0]['role']=='SUPPLY_PLAN'
 assert 'source_quote'not in json.dumps(r) # body is not archived


def test_ambiguous_context_not_approved_at_first_match():
 raw,m=page('Production capacity for gas turbines increased in 2026. Production capacity for gas turbines increased in 2026.')
 r=d.read_context(raw,m)
 assert not any(e['state']=='SOURCE_BOUND_REPORTED_CHANGE'for e in r['events'])
 assert any(h['reason']=='RAW_CONTEXT_AMBIGUOUS'for h in r['holds'])


def test_restart_dedup_tamper_and_source_absence(tmp_path):
 raw,m=page('Production capacity for gas turbines increased in 2026.')
 r=d.read_context(raw,m);l=Ledger(tmp_path/'ledger')
 assert d.save_context(l,r,raw=raw,meta=m)['added']==1;l.close()
 before=file_sha(tmp_path/'ledger/v4.sqlite3');l=Ledger(tmp_path/'ledger')
 assert d.save_context(l,r,raw=raw,meta=m)['added']==0
 with pytest.raises(ValueError,match='CONTEXT_REPLAY_REQUIRED'):d.save_context(l,r)
 r['events'][0]['qualified']=True
 with pytest.raises(ValueError):d.save_context(l,r,raw=raw,meta=m)
 l.close();assert file_sha(tmp_path/'ledger/v4.sqlite3')==before


def test_index_navigation_is_discovery_not_qualified_supply():
 raw=b'<nav><a href="https://ir.example.gov/annual-reports/">Annual reports</a><a href="https://evil.example/production/">Production</a></nav>'
 links=relation_index_links(raw,'https://example.gov/')
 assert len(links)==1 and links[0]['url']=='https://ir.example.gov/annual-reports/'
 assert links[0]['relation']=='PUBLISHER_INDEX_LEAD_NOT_TARGET_EQUIVALENCE'


def test_same_contract_quantity_comparison_excludes_money():
 assert d.demand_status('',previous='2',quantity_now='3')=='SAME_ITEM_COMMITTED_QUANTITY_INCREASE'
 assert d.demand_status('replacement',previous='2',quantity_now='3').startswith('REPLACEMENT')


def test_empty_queue_never_fetches_or_loads_models(tmp_path,monkeypatch):
 import v4_official_discovery as t
 monkeypatch.setattr(t,'fetch',lambda *a:pytest.fail('empty queue GET'))
 l=Ledger(tmp_path/'ledger')
 r=bidirectional(l,tmp_path/'captures',network=True)
 assert r['summary']['new_HTTP_this_batch']==0 and r['AI_calls']==r['CPU_windows']==0
 l.close()


def test_structured_facility_change_not_missing_row_or_nameplate_gap(monkeypatch):
 from bct.v4 import quantitative as q
 def obs(identity,month,sheet,value='10',planned='2027'):
  return {'id':sha([identity,month,sheet,value]),'record':{
   'source_id':'eia','metric':'nameplate_capacity','entity_or_facility_id':identity,
   'product_or_classification':'Unseen technology','geography':'CA','unit_original':'MW',
   'period_start':month,'attributes':{'sheet':sheet,'Planned Operation Year':planned,'Planned Operation Month':'1'},
   'value_decimal_or_null':value,'raw_or_safe_payload_hash':sha([month]),
   'source_locator':{'format':'XLSX','sheet':sheet,'cell':'M2'},'source_url':'https://www.eia.gov/snapshot.xlsx',
   'published_at':'UNKNOWN'}}
 rows=[obs('new','2026-07-01','Planned'),obs('new','2026-08-01','Operating'),
       obs('retire','2026-07-01','Operating'),obs('retire','2026-08-01','Retired'),
       obs('missing','2026-07-01','Operating'),
       obs('plan','2026-07-01','Planned'),obs('plan','2026-08-01','Planned',planned='2028'),
       obs('mw','2026-07-01','Operating'),obs('mw','2026-08-01','Operating',value='15')]
 monkeypatch.setattr(q,'research_export',lambda _: {'observations':rows})
 r=d.structured_supply_changes(None);by={e['facility_id']:e for e in r['changes']}
 assert set(by)=={'new','retire','plan','mw'}
 assert by['new']['role']=='RELIEF' and by['retire']['role']=='CONSTRAINT'
 assert by['plan']['role']==by['mw']['role']=='CONTEXT'
 assert all(not e['qualified'] and e['qualified_capacity']is None for e in by.values())


def test_actual_capture_packet_import_dedup_and_tamper(tmp_path):
 from copy import deepcopy
 from bct.v4 import quantitative_counterpart as q
 from bct.objective_lock import stamp_export
 from v4_official_discovery import import_bidirectional
 packet=json.loads(Path('docs/v4/quantitative/OFFICIAL_BIDIRECTIONAL_RESULTS.json').read_text())
 base=json.loads(Path('docs/v4/quantitative/OFFICIAL_AUTO_RESULTS.json').read_text())
 l=Ledger(tmp_path/'ledger');q.save_relations(l,stamp_export({'tasks':base['counterparts']['relation_tasks']}))
 assert import_bidirectional(l,packet)['added']==1
 l.close();before=file_sha(tmp_path/'ledger/v4.sqlite3');l=Ledger(tmp_path/'ledger')
 assert import_bidirectional(l,packet)['added']==0
 bad=deepcopy(packet);bad['context_results'][0]['source']['sha256']='0'*64
 with pytest.raises(ValueError,match='CAPTURE_RECEIPT'):import_bidirectional(l,bad)
 bad=deepcopy(packet);bad['resume_parent_ids'][next(iter(bad['resume_parent_ids']))]='0'*64
 with pytest.raises(ValueError,match='CURSOR_ADVANCED'):import_bidirectional(l,bad)
 l.close();assert file_sha(tmp_path/'ledger/v4.sqlite3')==before


def test_supply_to_customer_official_query_uses_shared_scope_and_no_repeat(tmp_path,monkeypatch):
 from bct.collectors.usaspending.collector import USAspendingTransport
 from v4_official_discovery import structured_demand_queries
 calls=[]
 def post(_,body):
  calls.append(body)
  return json.dumps({'spending_level':'awards','results':[],'page_metadata':{'hasNext':False}}).encode()
 monkeypatch.setattr(USAspendingTransport,'post',post)
 changes=[{'product':'electricity','region':'CA','role':'RELIEF'}]*16
 first=structured_demand_queries(changes,tmp_path,network=True,as_of='2026-10-16')
 assert len(calls)==1 and first['successful_queries']==1 and first['award_identity_leads']==0
 assert calls[0]['filters']['keywords']==['electricity']
 assert calls[0]['filters']['place_of_performance_locations']==[{'country':'USA','state':'CA'}]
 structured_demand_queries(changes,tmp_path,network=True,as_of='2026-10-16')
 assert len(calls)==1
 assert first['queries'][0]['customer_need_date']is None


def test_explicit_gzip_body_and_positions_use_original_native_hash():
 import gzip
 raw,m=page('Production capacity for gas turbines increased in 2026.')
 encoded=gzip.compress(raw);m={**m,'sha256':sha(encoded)}
 r=d.read_context(encoded,m)
 assert r['source']['sha256']==sha(encoded)
 assert r['source']['position_space']=='GZIP_DECODED_UTF8_HTML_CHARACTERS'
 e=next(e for e in r['events']if e['product']=='gas turbines')
 assert raw.decode()[e['product_position']['start']:e['product_position']['end']]=='gas turbines'
 with pytest.raises(ValueError,match='SIZE_LIMIT'):d.html_source(gzip.compress(b'X'*4_000_001))


def test_real_collector_hook_compares_same_contract_revision_not_new_order(tmp_path):
 from test_v4_official_discovery import native
 from copy import deepcopy
 l=Ledger(tmp_path/'ledger')
 data=native();meta={'source_id':'find_tender','url':'https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages',
                    'sha256':sha(json.dumps(data).encode()),'acquired_at':'2026-10-16T08:00:00Z'}
 assert d.enqueue(l,data,meta)['added']==1
 revised=deepcopy(data);revised['releases'][0].update(id='notice2',date='2026-10-15T12:00:00Z')
 revised['releases'][0]['tender']['description']=revised['releases'][0]['tender']['description'].replace('fifteen','seventeen')
 meta={**meta,'sha256':sha(json.dumps(revised).encode())}
 assert d.enqueue(l,revised,meta)['added']==1
 payload=json.loads(l.db.execute("select payload from events where kind='QUANTITATIVE_VALIDATION' order by seq desc limit 1").fetchone()[0])
 change=payload['policy']['order_change_evidence'][0]
 assert change['state']=='SAME_ITEM_COMMITTED_QUANTITY_INCREASE'
 assert change['before_quantity']=='15' and change['after_quantity']=='17'
 assert change['market_demand_increase']=='UNKNOWN' and not change['Q3_eligible']
 assert payload['policy']['Q3']['S3']==0
 l.close()
