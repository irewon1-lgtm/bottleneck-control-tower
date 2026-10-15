"""Synthetic queue contracts, distinct from actual saved-artifact CPU proof."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from bct.v4 import cpu_automation as q
from bct.v4.adapters import MODEL,MODEL_REVISION
from bct.v4.store import Ledger,sha


def document(body='Atlas ordered Helios heat pumps.\nHowever, delivery is not yet qualified.', suffix='one'):
    raw=('<html><body><article>'+''.join('<p>'+p+'</p>'for p in body.split('\n'))+'</article></body></html>').encode()
    return {'document_id':sha([suffix,body]),'origin_url':'https://official.example/'+suffix,
        'body':body,'body_sha256':sha(body.encode()),'raw_sha256':sha(raw),
        'published_at':'2026-10-01','acquired_at':'2026-10-02','provenance':'PASS',
        'provenance_verified':True,'body_status':'FULL','checks':{'http_success':True}},raw


class Extractor:
    def __init__(self, fail=False): self.calls=0;self.fail=fail
    def extract_windows(self,doc,windows,**kwargs):
        self.calls+=1
        if self.fail and self.calls==1: raise RuntimeError('isolated synthetic failure')
        text=doc['body'];a=text.find('Helios heat pumps');spans=[]
        if a>=0 and any(w['start']<=a<a+17<=w['end'] for w in windows):
            spans=[{'text':'Helios heat pumps','label':'product','locator':{'start':a,'end':a+17},
                    'document_id':doc['document_id'],'body_sha256':doc['body_sha256']}]
        return {'status':'PASS','model':MODEL,'revision':MODEL_REVISION,
                'selected_windows':windows,'spans':spans,'raw_windows':[]}


def test_unowned_existing_database_refused_without_mutation(tmp_path):
    l=Ledger(tmp_path);l.close();p=tmp_path/'v4.sqlite3';before=sha(p.read_bytes())
    with pytest.raises(ValueError,match='NON_QUEUE'): q.open_queue(tmp_path)
    assert sha(p.read_bytes())==before


def test_no_work_never_loads_or_calls_model(tmp_path):
    l=q.open_queue(tmp_path);model=Extractor()
    with l.worker(): r=q.work(l,extractor=model)
    assert r['new_windows']==0 and model.calls==0 and not r['model_loaded']
    assert not l.db.execute('SELECT * FROM runs').fetchall();l.close()


def test_exact_duplicate_and_new_version_only(tmp_path):
    l=q.open_queue(tmp_path);d,raw=document();model=Extractor()
    with l.worker():
        assert q.enqueue(l,d,raw,{})=='QUEUED'
        assert q.enqueue(l,d,raw,{})=='UNCHANGED_BODY_ALREADY_QUEUED'
        r=q.work(l,extractor=model)
        # Raw/page version changes with same body are not a second CPU job.
        d2=deepcopy(d);d2['document_id']='v2';d2['raw_sha256']=sha(raw+b' ')
        assert q.enqueue(l,d2,raw+b' ',{})=='UNCHANGED_BODY_ALREADY_QUEUED'
        d3,raw3=document(d['body']+'\nNew text.')
        assert q.enqueue(l,d3,raw3,{})=='QUEUED'
    assert model.calls==1 and r['validated_events']==0 and r['S3']==0
    assert l.db.execute('SELECT count(*) FROM firsts').fetchone()[0]==0;l.close()


def test_new_process_resume_committed_windows_no_repeat(tmp_path):
    d,raw=document('Atlas ordered Helios heat pumps.\nA second separate paragraph.')
    l=q.open_queue(tmp_path)
    with l.worker():
        q.enqueue(l,d,raw,{})
        first=Extractor();assert q.work(l,extractor=first,max_windows=1)['new_windows']==1
    l.close();l=q.open_queue(tmp_path)
    with l.worker():
        second=Extractor();r=q.work(l,extractor=second)
        assert first.calls==second.calls==1 and r['after']['pending_windows']==0
        assert q.work(l,extractor=second)['new_windows']==0 and second.calls==1
    l.close()
    script='from bct.v4.cpu_automation import open_queue,state;import sys,json;l=open_queue(sys.argv[1]);print(json.dumps(state(l)));l.close()'
    actual=json.loads(subprocess.check_output([sys.executable,'-c',script,str(tmp_path)]))
    assert actual['completed_windows']==2 and actual['pending_windows']==0


def test_interrupted_attempt_retries_only_uncommitted_local_window(tmp_path):
    d,raw=document('Atlas ordered Helios heat pumps.\nSecond paragraph.')
    l=q.open_queue(tmp_path)
    class Interrupt(Extractor):
        def extract_windows(self,*args,**kwargs): raise KeyboardInterrupt()
    with l.worker():
        q.enqueue(l,d,raw,{})
        with pytest.raises(KeyboardInterrupt):q.work(l,extractor=Interrupt())
    assert len(q.events(l,'CPU_QUEUE_WINDOW_ATTEMPT'))==1 and not q.events(l,'CPU_QUEUE_WINDOW_RESULT')
    l.close();l=q.open_queue(tmp_path)
    with l.worker():r=q.work(l,extractor=Extractor())
    assert r['after']['completed_windows']==2 and r['after']['pending_windows']==0;l.close()


def test_failure_isolation_and_no_unchanged_failure_retry(tmp_path):
    l=q.open_queue(tmp_path)
    for suffix in ('one','two'):
        d,raw=document(suffix=suffix)
        with l.worker():q.enqueue(l,d,raw,{})
    with l.worker():
        e=Extractor(fail=True);r=q.work(l,extractor=e)
        assert r['after']['failed_windows']==1 and r['new_windows']==2 and e.calls==2
        assert q.work(l,extractor=e)['new_windows']==0
    l.close()


def test_parallel_worker_refused(tmp_path):
    l=q.open_queue(tmp_path);other=q.open_queue(tmp_path)
    with l.worker():
        with pytest.raises(BlockingIOError):
            with other.worker(): pass
    other.close();l.close()


def test_contact_or_secret_or_bad_hash_stays_held(tmp_path):
    l=q.open_queue(tmp_path)
    for body in ('Contact: test@example.org','Authorization: secret','api key is private'):
        d,raw=document(body)
        with pytest.raises(q.APIError):q.enqueue(l,d,raw,{})
    d,raw=document();d['body_sha256']='bad'
    with pytest.raises(ValueError,match='HASH'):q.enqueue(l,d,raw,{})
    assert not q.events(l,'CPU_QUEUE_DOCUMENT');l.close()


def test_context_and_negative_relief_preserved_and_oversize_held():
    d,_=document();windows,held=q.plan(d)
    assert len(windows)==1 and 'not yet qualified' in windows[0]['text']
    d,_=document('A'*1900+'\nHowever, no shortage exists.')
    windows,held=q.plan(d)
    assert not windows and held[0]['reason']=='WHOLE_LINKED_CONTEXT_EXCEEDS_CPU1800'


def test_failed_or_missing_source_does_not_prevent_other_delta(tmp_path):
    cache=tmp_path/'cache';(cache/'documents').mkdir(parents=True);(cache/'raw').mkdir()
    d,raw=document();d['raw_path']='old-runner/'+d['raw_sha256']+'.html'
    (cache/'documents/d.json').write_text(json.dumps(d));(cache/'raw'/Path(d['raw_path']).name).write_bytes(raw)
    manifest={'format':'bct-new-rss-delta-v1','documents':[{'document_id':'missing','url':'https://official.example/missing'},
                {'document_id':d['document_id'],'url':d['origin_url']}]}
    l=q.open_queue(tmp_path/'ledger')
    with l.worker():
        rows=q.ingest_delta(l,manifest,cache,upstream_run_id='test')
        assert [r['status'] for r in rows]==['HELD_ISOLATED','QUEUED']
        again=q.ingest_delta(l,manifest,cache,upstream_run_id='test')
    assert all(r['status']=='ALREADY_IMPORTED' for r in again);l.close()


def test_native_cache_path_escape_cannot_be_read(tmp_path):
    cache=tmp_path/'cache';(cache/'documents').mkdir(parents=True);(cache/'raw').mkdir()
    d,raw=document();d['raw_path']='../credentials';(cache/'documents/d.json').write_text(json.dumps(d))
    m={'format':'bct-new-rss-delta-v1','documents':[{'document_id':d['document_id'],'url':d['origin_url']}]}
    l=q.open_queue(tmp_path/'queue')
    with l.worker():r=q.ingest_delta(l,m,cache,upstream_run_id='test')
    assert r[0]['reason']=='RAW_PATH_HASH_IDENTITY';l.close()


def test_invalid_source_span_and_foreign_model_are_isolated(tmp_path):
    l=q.open_queue(tmp_path);d,raw=document()
    class Bad(Extractor):
        def extract_windows(self,*args,**kwargs):
            x=super().extract_windows(*args,**kwargs);x['spans'][0]['text']='invented';return x
    with l.worker():
        q.enqueue(l,d,raw,{});r=q.work(l,extractor=Bad())
    assert r['actually_read_characters']==len(d['body']) and r['after']['failed_windows']==1
    assert q.events(l,'CPU_QUEUE_WINDOW_RESULT')[0]['CPU_original_rejected_by_validation']
    assert l.db.execute('SELECT count(*) FROM readings').fetchone()[0]==1
    assert not q.events(l,'CROSS_COMMON_EVIDENCE');l.close()


def test_backup_all_tables_restore_and_no_candidate_registration(tmp_path):
    l=q.open_queue(tmp_path/'source');d,raw=document()
    with l.worker():q.enqueue(l,d,raw,{});q.work(l,extractor=Extractor())
    l.backup(tmp_path/'restored/v4.sqlite3');before=q.state(l);l.close()
    r=q.open_queue(tmp_path/'restored');assert q.state(r)==before
    assert not r.db.execute('select * from firsts').fetchall()
    assert all(json.loads(p)['candidates']==[] for p, in r.db.execute('select payload from runs'));r.close()


def test_ui_reads_exact_proposals_and_queue_without_marking_adopted(tmp_path):
    from bct.v4.dashboard import ResearchReader
    root=Path(__file__).resolve().parents[1];l=q.open_queue(tmp_path/'queue');d,raw=document()
    with l.worker():q.enqueue(l,d,raw,{});q.work(l,extractor=Extractor())
    path=l.path;before=sha(path.read_bytes());l.close()
    reader=ResearchReader(root,path);ui=reader.dashboard()
    assert ui['automation']['cpu_research']['completed_windows']==1
    assert ui['automation']['cpu_research']['scheduled']=='NOT_RUN_DISABLED'
    assert ui['automation']['last_cpu_at']
    assert ui['counts']['reviewed']==0 and ui['counts']['future_candidates']=={'S1':0,'S2':0,'S3':0}
    assert ui['records'] and all(r['stage']=='UNKNOWN' and r['is_future_candidate'] is False for r in ui['records'])
    for r in ui['records']:
        assert reader.evidence(r['id'])['all_references_verified']
    assert sha(path.read_bytes())==before


def test_real_legacy_receipt_blocks_model_reexecution(tmp_path):
    d,raw=document('Atlas ordered Helios heat pumps.')
    legacy=Ledger(tmp_path/'legacy');legacy.capture(d,raw)
    w={'start':0,'end':len(d['body']),'text':d['body']}
    with legacy.db:legacy.event('CPU_WINDOW_RESULT',{'status':'PASS','document_id':d['document_id'],'key':'old',
        'window':w,'CPU':{'model':MODEL,'revision':MODEL_REVISION}})
    lp=legacy.path;legacy.close();l=q.open_queue(tmp_path/'queue')
    with l.worker():
        assert q.seed_completed(l,lp)==1
        q.enqueue(l,d,raw,{})
        model=Extractor();r=q.work(l,extractor=model)
    assert model.calls==0 and r['new_windows']==0 and r['after']['legacy_documents_reused']==1
    l.close()


def test_committed_real_queue_restores_and_completed_work_does_not_require_model(tmp_path):
    repo=Path(__file__).resolve().parents[1]
    archive=repo/'docs/v4/cpu-automation/ledger.sqlite3.gz'
    command=[sys.executable,str(repo/'tools/v4_cpu_automation.py'),'--restore',str(archive),
             '--root',str(tmp_path/'restored'),'--execute-cpu']
    result=json.loads(subprocess.check_output(command,cwd=repo))
    assert result['queue']['completed_windows']==67 and result['queue']['pending_windows']==0
    assert result['queue']['actually_read_characters']==14038
    assert result['work']['new_windows']==0 and result['work']['model_loaded'] is False
    assert result['API_calls']==0
    # Refuse a second archive restore onto an existing research checkpoint.
    failed=subprocess.run(command,cwd=repo,capture_output=True)
    assert failed.returncode!=0 and b'RESTORE_REQUIRES_FRESH_ROOT' in failed.stderr


def test_hold_release_requires_explicit_new_upstream_cache_evidence(tmp_path):
    cache=tmp_path/'cache';(cache/'documents').mkdir(parents=True);(cache/'raw').mkdir()
    d,raw=document();d['raw_path']=d['raw_sha256']+'.html'
    m={'format':'bct-new-rss-delta-v1','documents':[{'document_id':d['document_id'],'url':d['origin_url']}]}
    l=q.open_queue(tmp_path/'queue')
    with l.worker():
        assert q.ingest_delta(l,m,cache,upstream_run_id='test')[0]['status']=='HELD_ISOLATED'
        assert q.ingest_delta(l,m,cache,upstream_run_id='test',reconsider_held=True)[0]['status']=='ALREADY_IMPORTED'
        (cache/'documents/d.json').write_text(json.dumps(d));(cache/'raw'/d['raw_path']).write_bytes(raw)
        assert q.ingest_delta(l,m,cache,upstream_run_id='test')[0]['status']=='ALREADY_IMPORTED'
        r=q.ingest_delta(l,m,cache,upstream_run_id='test',reconsider_held=True)
        assert r[0]['status']=='QUEUED' and r[0]['reconsidered_after_new_cache_evidence']
    assert q.state(l)['isolated_imports']==0;l.close()


def test_unrelated_native_body_cannot_be_associated_by_metadata_hash(tmp_path):
    l=q.open_queue(tmp_path);d,raw=document();other,other_raw=document('Different unapproved text.')
    d['raw_sha256']=sha(other_raw)
    with pytest.raises(ValueError,match='NATIVE_TO_BODY'):q.enqueue(l,d,other_raw,{})
    assert not q.events(l,'CPU_QUEUE_DOCUMENT');l.close()
