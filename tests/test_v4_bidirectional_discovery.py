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
 ('Production capacity for gas turbines increased in 2026.',('SUPPLY_CHANGE','REPORTED_SUPPLY_CHANGE','REPORTED_ACTUAL')),
 ('Production capacity for gas turbines will increase in 2028.',('SUPPLY_PLAN','REPORTED_SUPPLY_CHANGE','PLANNED_OR_EXPECTED')),
 ('The gas turbine plant was delayed until 2028.',('CONSTRAINT','FACILITY_OR_QUALIFICATION_CONSTRAINT','REPORTED_ACTUAL')),
 ('Lead times for gas turbines increased.',('CONSTRAINT','REPORTED_SUPPLY_CHANGE','REPORTED_ACTUAL')),
 ('Lead times for gas turbines decreased.',('SUPPLY_CHANGE','REPORTED_SUPPLY_CHANGE','REPORTED_ACTUAL')),
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
 e=next(e for e in r['events']if e['role']=='SUPPLY_CHANGE')
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



def test_inline_html_markup_preserves_exact_native_product_and_raw_span():
 raw,meta=page('Production capacity for <strong>gas turbines</strong> increased in 2026.')
 result=d.read_context(raw,meta)
 matched=[e for e in result['events']if e['product']=='gas turbines']
 assert matched
 event=next(e for e in matched if e['role']=='SUPPLY_CHANGE')
 native=raw.decode()
 assert event['raw_alignment']=='VERIFIED_INLINE_MARKUP_TEXT_ONLY'
 assert '<strong>' in native[event['raw_position']['start']:event['raw_position']['end']]
 assert native[event['product_position']['start']:event['product_position']['end']]=='gas turbines'
 assert not event['qualified'] and event['qualified_capacity'] is None


def test_inline_product_split_across_tags_cannot_be_native_verified():
 raw,meta=page('Production capacity for <strong>gas</strong> turbines increased in 2026.')
 result=d.read_context(raw,meta)
 assert not any(e['product']=='gas turbines' and e['state']=='SOURCE_BOUND_REPORTED_CHANGE'
                for e in result['events'])
 assert any(h['reason']=='INLINE_PRODUCT_NOT_CONTIGUOUS_NATIVE_SPAN' for h in result['holds'])


def test_repeated_inline_quote_is_ambiguous_not_first_match():
 raw,meta=page('Production capacity for <strong>gas turbines</strong> increased in 2026. '
               'Production capacity for <strong>gas turbines</strong> increased in 2026.')
 result=d.read_context(raw,meta)
 assert not any(e['product']=='gas turbines' and e['state']=='SOURCE_BOUND_REPORTED_CHANGE'
                for e in result['events'])
 assert any(h['reason']=='RAW_CONTEXT_AMBIGUOUS' for h in result['holds'])


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
 assert by['new']['role']=='FACILITY_STATUS' and by['retire']['role']=='CONSTRAINT'
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


def test_parent_base_is_respected_and_irrelevant_news_not_read():
 from v4_official_discovery import link_selection
 raw=b'<base href="/"><a href="news/new-factory-production">Factory production expanded</a><a href="news/sports-race">Sports race</a><a href="news/">News</a>'
 links=relation_index_links(raw,'https://example.gov/news/article')
 by={x['url']:x for x in links}
 assert by['https://example.gov/news/new-factory-production']['selection']['decision']=='READ_SOURCE'
 assert by['https://example.gov/news/sports-race']['selection']['decision']=='EXCLUDE'
 assert by['https://example.gov/news/']['selection']['decision']=='DISCOVER_LINKS_ONLY'
 assert link_selection('https://example.gov/')['decision']=='HOLD'
 assert link_selection('https://example.gov/news/medical-research')['decision']=='HOLD'
 assert link_selection('https://example.gov/news/supply-qualification-conference')['decision']=='EXCLUDE'


def test_corroborated_article_date_is_not_index_creation_or_retrieval():
 html='''<link rel="canonical" href="https://example.gov/news/plant"><h1>Factory update</h1><meta name="dc.date" content="2026-10-01"><time datetime="2026-10-01T12:00:00Z"></time><script type="application/ld+json">{"@type":"Article","headline":"Factory update","datePublished":"2026-10-01"}</script>'''
 result=d.publication_evidence(html.encode(),'https://example.gov/news/plant','2026-10-16T00:00:00Z')
 assert result['published_at']=='2026-10-01' and not result['first_publication_verified']
 assert all(html[p['start']:p['end']]=='2026-10-01' for p in result['positions'])
 assert d.publication_evidence(html.replace('"Article"','"CollectionPage"').encode(),'https://example.gov/news/plant','2026-10-16')['published_at']=='UNKNOWN'
 assert d.publication_evidence(html.replace('2026-10-01T12','2026-10-02T12').encode(),'https://example.gov/news/plant','2026-10-16')['published_at']=='UNKNOWN'
 assert d.publication_evidence(html.encode(),'https://example.gov/news/other','2026-10-16')['published_at']=='UNKNOWN'


def test_generic_explicit_product_relation_is_proposal_and_keeps_measures():
 raw,m=page('Production capacity for ceramic membranes increased to 120 units per month in 2026.')
 r=d.read_context(raw,m);e=next(e for e in r['events']if e['role']=='SUPPLY_CHANGE')
 assert e['product']=='ceramic membranes' and e['state']=='PRODUCT_RELATION_PROPOSAL'
 assert e['reported_measures'][0]['value']==120
 assert e['reported_measures'][0]['unit']=='units per month'
 assert e['reported_periods'][0]['start']=='2026-01-01'
 assert not e['bottleneck_relief_verified'] and e['qualified_capacity']is None
 assert not d.context_seeds([r])


def test_mixed_demand_and_supply_must_not_assign_one_role_to_all_objects():
 assert d.context_role('Orders rose while production capacity fell.')[0]=='CONTEXT'
 raw,m=page('Gas turbine backlog increased to $800 million.')
 r=d.read_context(raw,m)
 assert all(not e['reported_measures'] and e['qualified_capacity']is None for e in r['events'])


def test_source_selection_blocks_irrelevant_before_network(tmp_path,monkeypatch):
 import v4_official_discovery as t
 from bct.v4 import quantitative_counterpart as q
 monkeypatch.setattr(t,'fetch',lambda *a:pytest.fail('irrelevant source fetched'))
 seed={'id':'seed','event_key':'event','product':'gas turbines','role':'DEMAND',
       'source':{'document_id':'doc','body_sha256':sha(b'parent'),'origin_url':'https://example.gov/','published_at':'2026-10-01'},'fields':{}}
 tasks=q.relation_tasks([seed])
 for task in tasks:
  task['scope']['automatic_stored_search']=[]
  task['checked_sources']=[{'url':'https://example.gov/','source_hash':sha(b'parent'),'status':200}]
  task['id']=sha(['q2-relation-state-1',{k:v for k,v in task.items()if k!='id'}])
 l=Ledger(tmp_path/'ledger');q.save_relations(l,__import__('bct.objective_lock',fromlist=['stamp_export']).stamp_export({'tasks':tasks}))
 report=bidirectional(l,tmp_path/'captures',network=True,seed_links=[{'seed_id':'seed','url':'https://example.gov/news/sports-race','via_url':'https://example.gov/','via_hash':sha(b'parent')}])
 assert report['summary']['new_HTTP_this_batch']==0
 assert report['pending'][0]['selection']['decision']=='EXCLUDE'
 l.close()


def test_pdf_text_coordinates_are_not_pdf_bytes_and_tables_remain_partial(monkeypatch):
 import subprocess
 from types import SimpleNamespace
 content='Official report\f\nProduction capacity for ceramic membranes increased to 120 units per month in 2026.\n'
 def extract(*args,**kwargs):
  assert args[0][0:2]==['pdftotext','-layout'] and kwargs['timeout']==20
  return SimpleNamespace(stdout=content.encode())
 monkeypatch.setattr(subprocess,'run',extract)
 raw=b'%PDF-test-native';m={'url':'https://example.gov/report.pdf','source_id':'OFFICIAL:example.gov','sha256':sha(raw),'acquired_at':'2026-10-16','published_at':'UNKNOWN'}
 r=d.read_context(raw,m)
 assert r['source']['position_space']=='PDF_LAYOUT_TEXT_CHARACTERS'
 assert r['source']['body_status']=='PARTIAL' and r['source']['extracted_text_sha256']==sha(content.encode())
 e=next(e for e in r['events']if e['product']=='ceramic membranes')
 assert e['page']==2
 assert content[e['product_position']['start']:e['product_position']['end']]=='ceramic membranes'
 assert e['state']=='PRODUCT_RELATION_PROPOSAL' and e['qualified_capacity']is None


def test_visible_ir_header_publication_not_dates_in_body_or_index():
 html='<link rel="canonical" href="https://example.gov/report"><h1>Quarterly report</h1><div class="_metadata"><span class="date">August 27, 2026</span></div><div class="__bodytext">Order information</div>'
 r=d.publication_evidence(html.encode(),'https://example.gov/report','2026-10-16')
 assert r['published_at']=='2026-08-27' and not r['first_publication_verified']
 loc=r['positions'][0];assert html[loc['start']:loc['end']]=='August 27, 2026'
 assert d.publication_evidence(html.replace('__bodytext','menu').encode(),'https://example.gov/report','2026-10-16')['published_at']=='UNKNOWN'
 assert d.publication_evidence(html.replace('2026</span>','2027</span>').encode(),'https://example.gov/report','2026-10-16')['published_at']=='UNKNOWN'


def test_visible_date_does_not_override_conflicting_article_metadata():
 html='<link rel="canonical" href="https://example.gov/report"><h1>Quarterly report</h1><span class="date">August 27, 2026</span><div class="__bodytext">Report</div><script type="application/ld+json">{"@type":"Article","headline":"Different article","datePublished":"2026-01-01"}</script>'
 assert d.publication_evidence(html.encode(),'https://example.gov/report','2026-10-16')['published_at']=='UNKNOWN'
