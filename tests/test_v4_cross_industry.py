import json
from dataclasses import dataclass
from urllib.error import HTTPError
import pytest
from bct.v4.cross_industry import feed_sources,fair_select,collect,reading_result,classify_error,safe_url
from bct.v4.store import Ledger,sha


def document(text='Nova ordered two osmosis cartridges.',host='issuer.example'):
 return {'document_id':sha([text,host]),'origin_url':'https://'+host+'/article','origin_id':host,'origin_publisher':host,'published_at':'2026-10-10','acquired_at':'2026-10-14','body':text,'body_sha256':sha(text.encode()),'raw_sha256':sha(text.encode()),'body_status':'FULL','provenance':'PASS','primary_source_verified':True}


def reading(d,name='osmosis cartridges'):
 a=d['body'].index(name)
 return {'status':'PASS','spans':[{'label':'product','text':name,'body_sha256':d['body_sha256'],'locator':{'start':a,'end':a+len(name)}}],'selected_windows':[{'start':0,'end':len(d['body']),'text':d['body']}]}


def test_source_catalog_reuses_all_active_and_keeps_disabled():
 active,disabled=feed_sources();assert len(active)==125 and len(disabled)==21
 assert len({s['industry_hint']for s in active})==10


def test_new_unknown_section_is_fair_not_keyword_filtered():
 items=[{'url':'https://chips.example/'+str(i),'industry_hint':'chips'}for i in range(8)]+[{'url':'https://new.example/1','industry_hint':'new membranes'}]
 assert fair_select(items,2)[1]['industry_hint']=='new membranes'


def test_unknown_product_industry_without_old_parser_order_keyword():
 # Existing ORDER regex does not recognize ordered, but the shared relation does.
 d=document();r=reading_result(d,reading(d));assert r['limited_relation_diagnostic']['counts']['S1']==1 and r['counts']['S1']==0
 assert r['records'][0]['product']['surface']=='osmosis cartridges'
 assert r['counts']['S2']==r['counts']['S3']==0 and r['priority']=='SOURCE_OR_PRODUCT_REVIEW'


@pytest.mark.parametrize('text',['Nova did not order osmosis cartridges.','Nova plans to order osmosis cartridges.','Nova received funding for osmosis cartridges.'])
def test_negation_plan_funding_cannot_become_actual_shortage(text):
 d=document(text);r=reading_result(d,reading(d));assert r['counts']['S1']==r['counts']['S3']==0


def test_provenance_hash_and_original_verification_not_relaxed():
 d=document();d['primary_source_verified']=False;r=reading_result(d,reading(d));assert r['counts']['events']==0 and r['CPU_products']==1
 d['body_sha256']='bad'
 with pytest.raises(ValueError,match='BODY_HASH'):reading_result(d,reading(d))


def test_source_location_checked_even_on_pending_origin():
 d=document();c=reading(d);c['spans'][0]['text']='invented'
 with pytest.raises(ValueError,match='SOURCE_MISMATCH'):reading_result(d,c)


def test_bad_industry_does_not_block_other_source_and_no_repeat(tmp_path):
 class Feed:
  def __init__(self):self.calls=[]
  def get(self,url):
   self.calls.append(url)
   if 'bad.example'in url:raise HTTPError(url,403,'blocked',{},None)
   return b'<rss><channel><item><title>New membranes</title><link>https://issuer.example/article</link><pubDate>Mon, 12 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>'
 class Client:
  def document(self,url):
   d=document();return d,d['body'].encode(),{}
 f=Feed();sources=[{'kind':'RSS','name':h,'url':'https://'+h+'/rss','industry_hint':h}for h in ['bad.example','good.example']]
 first=collect(tmp_path,sources,client=Client(),feed_transport=f,workers=2)
 assert first['sources_executed']==2 and len(first['captured'])==1
 assert len([r for r in first['source_results']if r['status']=='FAILED_ISOLATED'])==1
 second=collect(tmp_path,sources,client=Client(),feed_transport=f,workers=2)
 assert second['sources_executed']==0 and second['article_attempts']==0 and len(f.calls)==2
 l=Ledger(tmp_path);assert l.db.execute('SELECT COUNT(*) FROM documents').fetchone()[0]==1;l.close()


def test_retry_policy_and_credential_urls():
 assert classify_error(HTTPError('https://x',429,'rate',{},None))=='B_COMMUNICATION_OR_LIMIT'
 assert classify_error(TimeoutError())=='B_COMMUNICATION_OR_LIMIT'
 assert classify_error(HTTPError('https://x',403,'denied',{},None))=='A_ACCESS_RESTRICTED'
 with pytest.raises(ValueError):safe_url('https://example.org/?session=secret')


def test_missing_publication_is_local_source_hold_not_batch_exception():
 from bct.v4.cross_industry import source_review
 d=document();d['published_at']=None
 assert source_review(d,d['body'].encode())=={'status':'BLOCKED','reasons':['PUBLICATION_UNKNOWN']}
 assert reading_result(d,reading(d))['counts']['S1']==0


def test_exact_public_excerpt_receipt_does_not_upgrade_document_provenance():
 d=document();d['provenance']='BLOCKED';d['primary_source_verified']=False
 d['native_source_review']={'status':'PASS',**{k:d[k]for k in ('document_id','body_sha256','raw_sha256','origin_url','published_at')}}
 x=reading_result(d,reading(d));assert x['source_validation_scope']=='VERIFIED_PUBLIC_EXCERPT_ONLY'
 assert x['original_provenance_preserved']=='BLOCKED'and x['limited_relation_diagnostic']['counts']['S1']==1 and x['counts']['S1']==0
 d['native_source_review']['body_sha256']='different'
 assert reading_result(d,reading(d))['counts']['events']==0


def test_cpu_relation_proposals_are_preserved_without_unreviewed_promotion():
 d=document('Aehr Receives Production Orders for Customer AI Processor.');x=reading_result(d,reading(d,'AI Processor'))
 assert x['limited_relation_diagnostic']['counts']['S1']==1
 assert x['records'][0]['event_status']=='DISCOVERY_ONLY'and x['counts']['S1']==0
 assert x['records'][0]['meaning_status']=='CPU_RELATION_REVIEW_PENDING'


def test_blocked_CPU_declared_windows_are_not_reported_as_actually_read():
 d=document();r=reading(d);r['status']='BLOCKED';r['spans']=[]
 assert reading_result(d,r)['read_characters']==0


def test_bad_feed_payload_is_preserved_for_offline_diagnosis(tmp_path):
 class Feed:
  def get(self,url):return b'<html>Not an RSS feed</html>'
 x=collect(tmp_path,[{'kind':'RSS','name':'unknown','url':'https://new.example/rss','industry_hint':'unknown'}],feed_transport=Feed(),workers=1)
 assert x['source_results'][0]['error']['category']=='C_EXTRACTION_OR_VALIDATION'
 assert x['source_results'][0]['error']['parser_reason']=='unsupported feed format'
 l=Ledger(tmp_path);assert l.db.execute('SELECT data FROM blobs').fetchone()[0]==b'<html>Not an RSS feed</html>';l.close()


def test_successful_source_and_body_refresh_daily_but_failed_stays_isolated(tmp_path,monkeypatch):
 from bct.v4 import cross_industry as m
 clock=['2026-10-14T00:00:00+00:00'];monkeypatch.setattr(m,'now',lambda:clock[0])
 class Feed:
  def __init__(self):self.calls=0
  def get(self,url):
   self.calls+=1
   return ('<rss><channel><title>'+str(self.calls)+'</title><item><title>new</title><link>https://issuer.example/article</link></item></channel></rss>').encode()
 class Client:
  def __init__(self):self.calls=0
  def document(self,url):
   self.calls+=1;d=document('Nova ordered '+str(self.calls)+' osmosis cartridges.');d['origin_url']=url
   return d,d['body'].encode(),{}
 f=Feed();c=Client();sources=[{'kind':'RSS','name':'open','url':'https://open.example/rss','industry_hint':'Unknown'}]
 collect(tmp_path,sources,client=c,feed_transport=f,workers=1)
 assert collect(tmp_path,sources,client=c,feed_transport=f,workers=1)['sources_executed']==0
 clock[0]='2026-10-15T00:00:01+00:00'
 x=collect(tmp_path,sources,client=c,feed_transport=f,workers=1)
 assert x['sources_executed']==1 and x['managed_daily_refresh_slots']==1 and c.calls==2
 l=Ledger(tmp_path);assert l.db.execute("SELECT COUNT(*) FROM events WHERE kind='CROSS_SOURCE_VERSION'").fetchone()[0]==1
 assert l.db.execute("SELECT COUNT(*) FROM events WHERE kind='CROSS_ARTICLE_CHANGE'").fetchone()[0]==1
 assert l.db.execute('SELECT COUNT(*) FROM documents').fetchone()[0]==2;l.close()


def test_common_schema_keeps_located_CPU_unknown_and_structured_not_available_supply():
 from bct.v4.cross_industry import common_evidence,common_structured
 d=document();r=reading_result(d,reading(d))['records'][0];n=common_evidence(r,d,'CPU_DISCOVERY_UNVERIFIED')
 row={'url':'https://www.eia.gov/source','raw_sha256':'abc','period':'2026-07','fields':{'Technology':'Batteries','Plant State':'CA'},'cells':{'Technology':'T8'},'row':8}
 s=common_structured({'id':'row','role':'SUPPLY_INCREASE','before':row,'after':row})
 assert set(n['target'])==set(s['target'])=={'product','specification','region','customer_group','supply_pool'}
 assert n['s_stage']==s['s_stage']=='UNKNOWN'and n['future_gap']==s['future_gap']=='UNKNOWN'
 assert n['meaning_status']=='CPU_RELATION_REVIEW_PENDING'and s['actuality']=='REPORTED_STATUS_NOT_PHYSICALLY_VERIFIED'
 assert s['references'][1]['cells']['Technology']=='T8'


def test_deep_retrieval_caps_sources_and_does_not_merge_different_scope():
 from bct.v4.cross_industry import common_evidence,deepen
 d=document();r=reading_result(d,reading(d))['records'][0];n=common_evidence(r,d,'REUSED_SOURCE_ONLY_AI_REVIEW_NOT_NEW_DISCOVERY')
 docs=[document('Other ordered '+str(i)+' osmosis cartridges.',host='issuer'+str(i)+'.example')for i in range(5)]
 other=json.loads(json.dumps(n));other['event_id']='other';other['role']='SUPPLY_INCREASE';other['target']['region']='different'
 x=deepen(n,docs,[n,other]);assert len(x['selected_source_documents'])==3 and x['additional_matching_documents_not_read']==2
 assert x['related_reviewed_records'][0]['TARGET_equivalence']=='UNPROVEN_SCOPE'
 assert not x['S2']and not x['S3']
 with pytest.raises(ValueError):deepen(n,docs,[],limit=4)


def test_orphan_refresh_attempts_remain_quarantined_after_restart(tmp_path,monkeypatch):
 from bct.v4 import cross_industry as m
 clock=['2026-10-14T00:00:00+00:00'];monkeypatch.setattr(m,'now',lambda:clock[0])
 class Feed:
  def __init__(self):self.calls=0
  def get(self,url):
   self.calls+=1;return b'<rss><channel><item><title>x</title><link>https://issuer.example/article</link></item></channel></rss>'
 class Client:
  def document(self,url):
   d=document();return d,d['body'].encode(),{}
 source={'kind':'RSS','name':'open','url':'https://open.example/rss','industry_hint':'unknown'};f=Feed()
 assert collect(tmp_path,[source,source],client=Client(),feed_transport=f,workers=1)['sources_executed']==1
 clock[0]='2026-10-15T00:00:00+00:00';l=Ledger(tmp_path)
 with l.db:
  l.event('CROSS_SOURCE_ATTEMPT',{'url':source['url'],'at':clock[0]})
  l.event('CROSS_ARTICLE_ATTEMPT',{'url':'https://issuer.example/article','at':clock[0]})
 l.close();clock[0]='2026-10-16T00:00:00+00:00'
 x=collect(tmp_path,[source],client=Client(),feed_transport=f,workers=1)
 assert x['sources_executed']==x['article_attempts']==0 and f.calls==1


def test_alternative_body_keeps_original_and_never_claims_full_or_provenance():
 from bct.v4.cross_industry import alternative_body_view
 d=document('');d['body_status']='UNAVAILABLE';raw=b'<html><article></article><div>Public paragraph</div></html>';d['raw_sha256']=sha(raw);before=json.loads(json.dumps(d))
 view=alternative_body_view(d,raw,views={'trafilatura':'Public paragraph'})
 assert d==before and view['body_status']=='PARTIAL'and view['provenance']=='BLOCKED'
 assert view['original_document_id']==d['document_id']and view['document_id']!=d['document_id']and view['raw_sha256']==d['raw_sha256']


def test_explicit_access_marker_blocks_even_if_alternative_could_extract_text():
 from bct.v4.cross_industry import alternative_body_view
 d=document('');d['body_status']='UNAVAILABLE';raw=b'<html><div class="body gsd-paywall">Protected article</div></html>';d['raw_sha256']=sha(raw)
 with pytest.raises(ValueError,match='EXPLICIT_ACCESS_RESTRICTION'):alternative_body_view(d,raw,views={'trafilatura':'Protected article'})
