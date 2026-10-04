"""Real worker/storage execution with isolated synthetic sources and model replies."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import hashlib
import json
import sqlite3
from urllib.error import HTTPError

import pytest

from bct.future_bottleneck import run as collect
from bct.future_body import cache_body, read_cached_body
from bct.future_reader import OpenAIQuickReader, estimated_cost
from bct.future_review import queue_summary
from bct.future_store import LocalJSONTransport
from bct.future_worker import LOCK_ID, run_worker


def sources(tmp_path, count=1, partial=()):
    db, candidates, tracking, cache = (tmp_path/'canonical.sqlite3', tmp_path/'future-candidates.json',
                                        tmp_path/'future-tracking.json', tmp_path/'cache')
    with sqlite3.connect(db) as sql:
        sql.execute('CREATE TABLE radar_items(id,title,url,source,collected_at,updated_at,status,source_type)')
        for i in range(count):
            sql.execute("INSERT INTO radar_items VALUES(?,?,?,?,?,?,'active','NEWS')",
                        (str(i), 'Demand for power transformers', f'https://example.test/{i}', 'source',
                         f'2026-10-01T00:{i:02d}:00Z', 'v1'))
    def fetch(url):
        i = int(url.rsplit('/',1)[1])
        tag = 'main class="preview"' if i in partial else 'article'
        close = 'main' if i in partial else 'article'
        return f'<{tag}><p>Demand for power transformers is growing. Report number {i}.</p></{close}>'
    collect(db,candidates,fetcher=fetch,cache_dir=cache,detection_mode='SYNTHETIC')
    tracking.write_text('{}')
    return db, candidates, tracking, cache


def reply(payload, *, disposition=None):
    return {'review': {'disposition': disposition or ('DATA_INSUFFICIENT' if payload['body_status']=='PARTIAL' else 'DEEP_NEEDED'),
                       'reason': 'Synthetic fixture judgment; not production analysis.',
                       'read_end': payload['expected_read_end']},
            'usage': {'input_tokens': 42, 'output_tokens': 12}, 'provider':'fixture','model':'fixture'}


def execute(paths, reader=reply, **kwargs):
    _, candidates, tracking, cache = paths
    return run_worker(LocalJSONTransport(),str(candidates),str(tracking),reader=reader,cache_dir=cache,
                      review_mode="API_REVIEW",**kwargs)


def test_1_new_candidate_claim_read_save_and_next_state(tmp_path):
    paths=sources(tmp_path)
    _, candidates, tracking, _=paths
    original=json.loads(candidates.read_text())['results']
    before=queue_summary(json.loads(candidates.read_text()),{})
    observed=[]
    def reader(payload):
        lock=json.loads(tracking.read_text())['runs'][LOCK_ID]
        assert lock['state']=='RUNNING'
        observed.append(payload)
        return reply(payload)
    result=execute(paths,reader)
    assert result['counts']=={'SUCCESS':1}
    assert result['after']['quick_pending']==before['quick_pending']-1
    assert result['after']['completed_documents']==result['after']['deep_pending']==1
    assert len(json.loads(tracking.read_text())['reviews'])==1
    assert json.loads(tracking.read_text())['runs'][LOCK_ID]['state']=='IDLE'
    assert json.loads(candidates.read_text())['results']==original
    assert json.loads(candidates.read_text())['summary']['review_queue']['computed_at']==result['after']['computed_at']
    assert len(observed)==1


def test_2_repeat_and_concurrent_workers_do_not_duplicate_reading(tmp_path):
    paths=sources(tmp_path)
    entered, release=Event(),Event()
    calls=[]
    def reader(payload):
        calls.append(payload['document_id'])
        entered.set()
        assert release.wait(5)
        return reply(payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(execute,paths,reader)
        assert entered.wait(5)
        second=execute(paths,reader)
        release.set()
        result=first.result(timeout=5)
    assert second['state']=='BUSY' and second['attempted']==0
    saved=deepcopy(json.loads(paths[2].read_text())['reviews'])
    again=execute(paths,reader)
    assert again['model_calls']==again['attempted']==0
    assert calls==['0'] and len(saved)==1
    assert json.loads(paths[2].read_text())['reviews']==saved
    assert result['counts']=={'SUCCESS':1}


def test_3_full_and_partial_keep_body_state_and_missing_data(tmp_path):
    paths=sources(tmp_path,2,partial=(1,))
    result=execute(paths)
    assert result['counts']=={'SUCCESS':2}
    assert result['after']['completed_documents']==2
    assert result['after']['quick_pending']==0
    assert result['after']['material_pending']==result['after']['candidate_data_wait']==1
    c=json.loads(paths[1].read_text())
    assert c['results']['0']['body_status']=='FULL'
    assert c['results']['1']['body_status']=='PARTIAL'


@pytest.mark.parametrize('failure',[TimeoutError(), HTTPError('https://fixture.test',429,'rate limit',{},None),
                                  HTTPError('https://fixture.test',500,'server error',{},None),
                                  'malformed', 'invalid-fields'])
def test_4_one_provider_failure_does_not_stop_other_cases(tmp_path,failure):
    paths=sources(tmp_path,2)
    calls=[]
    def requester(request):
        payload=json.loads(request['input'])
        calls.append(payload['document_id'])
        if payload['document_id']=='0':
            if isinstance(failure,Exception):
                raise failure
            output='{' if failure=='malformed' else json.dumps({'disposition':'CURRENT','read_end':99,'reason':'bad'})
        else:
            output=json.dumps(reply(payload)['review'])
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':output}]}],
                'usage':{'input_tokens':42,'output_tokens':12}}
    reader=OpenAIQuickReader(api_key='fixture-only-not-a-secret',requester=requester)
    result=execute(paths,reader)
    assert result['counts']=={'ERROR':1,'SUCCESS':1}
    assert result['after']['completed_documents']==1
    assert result['after']['quick_pending']==1
    assert len(json.loads(paths[2].read_text())['reviews'])==1
    again=execute(paths,reader)
    assert again['attempted']==0  # Failed items need an explicit bounded retry.
    assert calls==['0','1']


def test_5_bounded_ten_case_batch_measures_real_local_execution(tmp_path):
    paths=sources(tmp_path,12)
    db_hash=hashlib.sha256(paths[0].read_bytes()).hexdigest()
    original=json.loads(paths[1].read_text())['results']
    result=execute(paths,limit=10,input_rate=1.0,output_rate=2.0)
    assert result['attempted']==result['model_calls']==10
    assert result['counts']=={'SUCCESS':10}
    assert result['after']['quick_pending']==2
    assert result['after']['completed_documents']==10
    assert result['elapsed_seconds']>0 and result['mean_seconds']>0
    assert len(json.loads(paths[2].read_text())['reviews'])==10
    assert all(x['input_tokens']==42 and x['output_tokens']==12 for x in result['results'])
    assert all(x['estimated_cost_usd']==pytest.approx(0.000066) for x in result['results'])
    assert json.loads(paths[1].read_text())['results']==original
    assert hashlib.sha256(paths[0].read_bytes()).hexdigest()==db_hash


def test_missing_key_blocks_without_claim_body_fetch_or_fallback(tmp_path):
    paths=sources(tmp_path)
    before=[p.read_bytes() for p in paths[1:3]]
    def forbidden(_):
        pytest.fail('missing key must not fetch or call a provider')
    result=execute(paths,OpenAIQuickReader(api_key=None,requester=forbidden),fetcher=forbidden)
    assert result['state']=='BLOCKED' and result['reason']=='MISSING_API_KEY'
    assert result['attempted']==result['model_calls']==0
    assert [p.read_bytes() for p in paths[1:3]]==before


def test_source_block_records_access_only_and_continues(tmp_path):
    paths=sources(tmp_path,2)
    c=json.loads(paths[1].read_text())
    digest=c['results']['0']['body_sha256']
    (paths[3]/(digest+'.txt')).unlink()
    def fetch(_):
        raise TimeoutError()
    result=execute(paths,fetcher=fetch)
    assert result['counts']=={'BLOCKED':1,'SUCCESS':1}
    assert result['after']['completed_documents']==1
    assert result['after']['material_pending']==1
    access=[r for r in json.loads(paths[2].read_text())['reviews'].values() if r['kind']=='access']
    assert len(access)==1 and access[0]['access_status']=='BLOCKED'
    assert 'read_complete' not in access[0]


def test_input_budget_never_truncates_or_falsely_completes(tmp_path):
    paths=sources(tmp_path)
    def forbidden(_):
        pytest.fail('over-budget body must not reach provider')
    result=execute(paths,forbidden,max_input_chars=5)
    assert result['counts']=={'BLOCKED':1}
    assert result['results'][0]['reason']=='INPUT_BUDGET_EXCEEDED'
    assert result['after']['quick_pending']==1
    assert result['after']['completed_documents']==0
    assert not json.loads(paths[2].read_text()).get('reviews')


def test_exact_body_event_reuses_judgment_for_other_document_reference(tmp_path):
    paths=sources(tmp_path,2)
    c=json.loads(paths[1].read_text())
    c['results']['1']={**deepcopy(c['results']['0']),'id':'1','url':'https://example.test/1'}
    paths[1].write_text(json.dumps(c))
    result=execute(paths)
    assert result['attempted']==2 and result['model_calls']==1
    assert result['results'][1]['reused'] is True
    assert result['after']['completed_documents']==2 and result['after']['pending_events']==1  # Deep review still pending.
    again=execute(paths)
    assert again['attempted']==again['model_calls']==0
    reviews=json.loads(paths[2].read_text())['reviews']
    assert len(reviews)==2 and len({r['worker_event_id'] for r in reviews.values()})==1


def test_incomplete_actual_range_resumes_with_a_new_checkpoint(tmp_path):
    paths=sources(tmp_path)
    def partial(payload):
        result=reply(payload)
        result['review'].update(disposition='INCOMPLETE',read_end=20)
        return result
    first=execute(paths,partial)
    assert first['after']['completed_documents']==0 and first['after']['preview'][0]['resume_at']==20
    positions=[]
    def finish(payload):
        positions.append(payload['read_start'])
        return reply(payload)
    second=execute(paths,finish)
    assert positions==[20]
    assert second['after']['completed_documents']==1
    assert len(json.loads(paths[2].read_text())['reviews'])==2


def test_cost_unknown_without_prices_and_bad_limits_fail_before_claim(tmp_path):
    assert estimated_cost({'input_tokens':42,'output_tokens':12}) is None
    paths=sources(tmp_path)
    for kwargs in ({'limit':51},{'max_input_chars':12001},{'input_rate':-1.0,'output_rate':2.0}):
        with pytest.raises(ValueError):
            execute(paths,**kwargs)
    assert json.loads(paths[2].read_text())=={}


@pytest.mark.parametrize('limit,required',[(10,1),(50,10)])
def test_live_pilot_cannot_skip_previous_real_batch(tmp_path,limit,required):
    paths=sources(tmp_path,2)
    result=execute(paths,limit=limit,require_pilot_gates=True)
    assert result['state']=='BLOCKED' and result['reason']==f'PRIOR_LIVE_{required}_BATCH_REQUIRED'
    assert result['attempted']==result['model_calls']==0
    assert json.loads(paths[2].read_text())=={}


def test_successful_stored_one_case_gate_allows_ten_but_not_fifty(tmp_path):
    paths=sources(tmp_path,12)
    first=execute(paths,limit=1,require_pilot_gates=True)
    assert first['completed_delta']==1 and first['quick_pending_delta']==-1
    assert first['source_records_unchanged'] and first['duplicate_auto_reviews']==0
    assert execute(paths,limit=50,require_pilot_gates=True)['state']=='BLOCKED'
    ten=execute(paths,limit=10,require_pilot_gates=True)
    assert ten['attempted']==10 and ten['counts']=={'SUCCESS':10}
    # These records are confined to synthetic tmp_path; they are not real API proof.


def test_budget_includes_title_and_provider_instructions_not_only_body(tmp_path):
    paths=sources(tmp_path)
    c=json.loads(paths[1].read_text())
    c['results']['0']['title']='x'*12001
    paths[1].write_text(json.dumps(c))
    def forbidden(_):
        pytest.fail('oversized metadata must not reach the model')
    reader=OpenAIQuickReader(api_key='fixture-only-not-a-secret',requester=forbidden)
    result=execute(paths,reader)
    assert result['model_calls']==0 and result['counts']=={'BLOCKED':1}
