"""Approved research intake/reading safety; authored cases are not accuracy gold."""
from copy import deepcopy
import hashlib
import json

import pytest

from bct.v4.public_input import selected_input, review_native
from bct.v4.free_ai import APIError, Router, source_input, SYSTEM, QUOTE_SCHEMA, VERSION
from bct.v4.store import Ledger, sha
from test_v4_repair import native
from test_v4_free_ai import config, router, Fake, document, response, NOW


def page_config():
    c = config(); c.update(max_input_characters=600, max_windows=2, input_policy="sentence-context-v2")
    return c


def test_long_independent_sentences_form_exact_bounded_pages_without_source_rewrite():
    body = " ".join(f"Forge{n} received new orders for gas turbines with annual production capacity of {100+n} units for industrial electricity generation across Europe." for n in range(8))
    d, raw, row = native(body); review = review_native(d, raw, row); before = deepcopy(d)
    pages = [selected_input(d, {**page_config(), "input_page": i}, review, {}) for i in range(3)]
    ranges = []
    for p in pages:
        assert p["selected_characters"] <= 600 and len(p["windows"]) <= 2
        for w in p["windows"]:
            assert d["body"][w["start"]:w["end"]] == w["text"] and w["text"].endswith(".")
            ranges.append((w["start"], w["end"]))
    assert len(ranges) == len(set(ranges)) and d == before
    assert sum(p["selected_characters"] for p in pages) > 600


@pytest.mark.parametrize("guard", ["However,", "Unless qualification is completed,", "The supplier did not expand capacity.", "It remains conditional."])
def test_long_conditions_and_anaphora_are_not_cut_into_passing_fragments(guard):
    text = "Forge received orders for gas turbines. " + "Capacity details for industrial plants remain under review. "*13 + guard
    d, raw, row = native(text);review=review_native(d,raw,row)
    with pytest.raises(ValueError, match="NO_COMPLETE_SAFE"):
        selected_input(d,page_config(),review,{})


def test_frozen_legacy_input_policy_stays_identical_and_secret_flags_still_block():
    d,raw,row=native("Forge received new orders for NovaLT16.")
    review=review_native(d,raw,row)
    c=config();c.update(max_input_characters=600,max_windows=2)
    selected=selected_input(d,c,review,{})
    assert selected["input_policy_version"]=="bct-v4-public-input-1"
    assert "page_index" not in selected
    d["api_transfer_forbidden"]=True
    with pytest.raises(ValueError):selected_input(d,page_config(),review,{})


@pytest.mark.parametrize("total,expected", [(1000,None),(None,"LOCAL_QUOTA"),(7000,"LOCAL_QUOTA")])
def test_rolling_budget_uses_reported_tokens_and_retains_unknown_reservations(tmp_path,total,expected):
    ledger=Ledger(tmp_path);c=config();c['accounts']['groq']['limits']['tpm']=8000
    with ledger.db:
        ledger.event('API_ATTEMPT',{'at':NOW.isoformat(),'provider':'groq','attempt_id':'old','reserved_tokens':6000})
        if total is not None:ledger.event('API_RECEIVED',{'attempt_id':'old','usage':{'total_tokens':total}})
    assert router(ledger,Fake({}),c).budget('groq',5000)==expected
    ledger.close()


def test_source_invalid_cached_response_is_not_reported_as_pass(tmp_path):
    ledger=Ledger(tmp_path);d=document(); c=config();src=source_input(d,c,{})
    invalid=response(d);item=json.loads(invalid['text']);item['items'][0]['context']['quote']='nonexistent exact quote'
    key=sha([VERSION,SYSTEM,QUOTE_SCHEMA,src,d['body_sha256']])
    with ledger.db:ledger.event('API_RESPONSE',{'provider':'groq','input_key':key,'text':json.dumps(item),'usage':invalid['usage']})
    fake=Fake({});r=router(ledger,fake,c).read(d)
    assert r['cached'] and r['status']=='REVIEW_REQUIRED' and not r['result']['items'] and not fake.calls
    ledger.close()


def test_same_source_version_skips_second_cpu_work_and_queue_entry(tmp_path,monkeypatch):
    from bct.v4.pipeline import cycle
    import bct.v4.pipeline as pipeline
    d=document();raw=b'public original';d['raw_sha256']=hashlib.sha256(raw).hexdigest()
    class Client:
        def document(self,url):return deepcopy(d),raw,{}
    calls=[]
    class CPU:
        def __init__(self,root):pass
        def extract(self,*a,**k):calls.append(1);return {'status':'PASS','spans':[]}
    monkeypatch.setattr(pipeline,'CPUExtractor',CPU)
    c={'urls':[d['origin_url']],'document_limit':1}
    a=cycle(tmp_path,c,client=Client(),mode='BACKFILL')
    b=cycle(tmp_path,c,client=Client(),mode='BACKFILL')
    assert len(calls)==1 and len(a['new_document_ids'])==1 and not b['new_document_ids']
    assert b['unchanged_document_ids']==[d['document_id']] and b['live_captured']==0
    ledger=Ledger(tmp_path)
    assert ledger.db.execute("SELECT count(*) FROM events WHERE kind='READ_QUEUE'").fetchone()[0]==1
    assert not ledger.status()['observed_live_days']
    ledger.close()


def test_research_collector_isolates_failed_url_and_does_not_starve_other_roles(tmp_path):
    from bct.v4.research_intake import intake
    from pathlib import Path
    c=json.loads(Path('config/v4-research-intake.json').read_text())
    attempts=[]
    class Client:
        def fetch(self,url):
            prefix=next(s['article_prefix'] for s in c['sources'] if s['index_url']==url)
            body=''.join('<a href="'+prefix+x+'">article</a>' for x in ['a','b','c','a?token=unsafe'])
            return body.encode(),url,200,'text/html'
        def document(self,url):
            attempts.append(url)
            if url.endswith('/a') and 'airbus' in url:raise TimeoutError()
            d=document();d.update(document_id=hashlib.sha256(url.encode()).hexdigest(),origin_url=url)
            raw=b'official saved article';d['raw_sha256']=hashlib.sha256(raw).hexdigest()
            return d,raw,{}
    a=intake(tmp_path,c,client=Client())
    b=intake(tmp_path,c,client=Client())
    assert a['live_captured']==2 and b['live_captured']==3 and b['isolated_failed_URLs']==1
    assert len({x.split('/')[2] for x in attempts[:3]})==3
    assert len(attempts)==len(set(attempts))==6
    assert a['AI_requests']==b['AI_requests']==0 and b['read_queue']==5
    ledger=Ledger(tmp_path)
    assert ledger.db.execute('select count(*) from documents').fetchone()[0]==5
    ledger.close()


def test_failed_research_index_is_not_retried_unchanged(tmp_path):
    from bct.v4.research_intake import intake
    from pathlib import Path
    c=json.loads(Path('config/v4-research-intake.json').read_text());c['sources']=c['sources'][:1]
    attempts=[]
    class Client:
        def fetch(self,url):attempts.append(url);raise TimeoutError()
    a=intake(tmp_path,c,client=Client());b=intake(tmp_path,c,client=Client())
    assert len(attempts)==1 and a['failures'][0]['type']=='TimeoutError'
    assert b['failures'][0]['type']=='PRIOR_FAILURE_ISOLATED_REQUIRES_INVESTIGATION'


def test_listing_filter_exception_is_narrow_and_does_not_relax_article_input():
    from bct.v4.research_intake import valid_index_url
    from bct.v4.public_input import valid_article_url
    public='https://www.gevernova.com/news/media-hub?type%5Bpress_release%5D=press_release'
    assert valid_index_url(public) and not valid_article_url(public)
    assert not valid_index_url(public+'&token=secret')
    assert not valid_index_url(public.replace('press_release','session'))


def test_product_score_uses_frozen_aliases_and_counts_false_values_as_miss():
    import importlib.util
    spec=importlib.util.spec_from_file_location('scoped','tools/v4_scoped_evaluation.py')
    scoring=importlib.util.module_from_spec(spec);spec.loader.exec_module(scoring)
    gold={'targets':[{'entity':'NovaLT16','entity_aliases':['NovaLT16 gas turbines'],'events':[
        {'event_id':'e','reference':{'start':0,'end':100},'facts':[{'field':'product','status':'VERIFIED_PRESENT','value':'NovaLT16'}]}]}]}
    a=scoring.product_assess([{'value':'NovaLT16 gas turbines','span':{'start':5,'end':20}}],gold)
    b=scoring.product_assess([{'value':'NovaLT1','span':{'start':5,'end':12}}],gold)
    assert a['TP']==1 and a['FP']==a['FN']==0
    assert b['TP']==0 and b['FP']==b['FN']==1


def test_daily_refresh_retains_both_native_versions_and_only_queues_changed_body(tmp_path,monkeypatch):
    from bct.v4 import research_intake as intake
    from datetime import datetime,timedelta,timezone
    from pathlib import Path
    c=json.loads(Path('config/v4-research-intake.json').read_text());c['sources']=c['sources'][:1]
    url=c['sources'][0]['article_prefix']+'new-order';calls=[]
    class Client:
        body='Forge received an order for NovaLT16.'
        def fetch(self,index):return ('<a href="'+url+'">official</a>').encode(),index,200,'text/html'
        def document(self,u):
            calls.append(u);d=document();raw=self.body.encode()
            d.update(document_id=hashlib.sha256(raw).hexdigest(),origin_url=u,body=self.body,
                     raw_sha256=hashlib.sha256(raw).hexdigest(),body_sha256=hashlib.sha256(raw).hexdigest())
            return d,raw,{}
    client=Client();first=intake.intake(tmp_path,c,client=client)
    at=datetime.now(timezone.utc)+timedelta(days=2)
    monkeypatch.setattr(intake,'now',lambda:at.isoformat())
    client.body+=' Qualified capacity is delayed.'
    second=intake.intake(tmp_path,c,client=client)
    third=intake.intake(tmp_path,c,client=client)
    assert second['source_refreshes'][0]['status']=='BODY_CHANGED'
    assert second['read_queue']==2 and not third['live_captured'] and len(calls)==2
    at+=timedelta(days=2)
    fourth=intake.intake(tmp_path,c,client=client)
    assert fourth['source_refreshes'][0]['status']=='UNCHANGED_BODY' and fourth['read_queue']==2
    l=Ledger(tmp_path);assert l.db.execute('select count(*) from documents').fetchone()[0]==2
    with l.db:l.event('READ_QUEUE',{'document_id':second['source_refreshes'][0]['document_id'],'state':'WAIT_API_AUTH'})
    assert intake.reading_queue(l)['unfinished_versions']==2
    assert intake.reading_queue(l)['states']['WAIT_API_AUTH']==1
    l.close()
