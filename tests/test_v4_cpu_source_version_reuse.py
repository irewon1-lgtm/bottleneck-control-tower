"""A new native version can reuse exact complete body inputs, never infer anew."""
from copy import deepcopy

import pytest

from bct.v4 import cpu_automation as q,cpu_resume as resume
from bct.v4.store import sha
from test_v4_cpu_automation import document,Extractor
from test_v4_cpu_resume import cache_source


def separated(tmp_path,*,partial=False):
    doc,raw=document('Atlas ordered Helios heat pumps.\nA second separate paragraph.')
    ledger=q.open_queue(tmp_path/'original');q.enqueue(ledger,doc,raw,{})
    q.work(ledger,extractor=Extractor(),max_windows=1 if partial else 24);ledger.close()
    resume.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'safe')
    return doc,raw,q.open_queue(tmp_path/'safe')


@pytest.mark.parametrize('new_id',[False,True])
def test_new_native_identity_has_explicit_old_model_receipt_binding_without_model(tmp_path,new_id):
    doc,raw,ledger=separated(tmp_path)
    oldkeys={r['key'] for r in resume.rows(ledger.db,'CPU_RESUME_WINDOW')}
    native=raw+b'\n<!-- a new native capture; article body unchanged -->'
    current={**doc,'raw_sha256':sha(native)}
    if new_id:current['document_id']='new-source-'+sha(native)
    cache,policy=cache_source(tmp_path,current,native)
    manifest={'format':'bct-new-rss-delta-v1','documents':[{'document_id':current['document_id'],'url':current['origin_url']}]}
    imported=q.ingest_delta(ledger,manifest,cache,upstream_run_id='source-version',storage_policy=policy,source_separated=True)
    assert imported[0]['status']=='SOURCE_VERSION_ANALYSIS_ONLY_IDENTICAL_MODEL_INPUT_REUSED'
    model=Extractor();result=q.work(ledger,extractor=model)
    assert result['new_windows']==0 and not result['model_loaded'] and model.calls==0
    assert result['new_analysis_results']==1 and result['complete_analyzed_new_CPU_documents']==0
    binding=q.events(ledger,'CPU_INPUT_REUSE_BINDING')[-1]
    assert binding['original_document_id']==doc['document_id'] and binding['original_raw_sha256']==doc['raw_sha256']
    assert binding['document_id']==current['document_id'] and binding['raw_sha256']==current['raw_sha256']
    assert binding['new_CPU_windows']==0 and binding['model_loads']==0
    receipt=q.events(ledger,'CPU_ANALYSIS_RESULT')[-1]
    assert receipt['document_id']==current['document_id'] and receipt['raw_sha256']==current['raw_sha256']
    assert receipt['new_inference_windows']==0 and receipt['restored_success_windows']==2
    assert receipt['derived_reuse_binding_sha256']==sha(binding)
    assert {r['key'] for r in resume.rows(ledger.db,'CPU_RESUME_WINDOW')}==oldkeys
    assert not q.events(ledger,'CPU_QUEUE_WINDOW_ATTEMPT')
    ledger.close();resume.export_state(tmp_path/'safe/v4.sqlite3',tmp_path/'next')
    ledger=q.open_queue(tmp_path/'next');resume.audit(ledger)
    assert q.events(ledger,'CPU_INPUT_REUSE_BINDING')[-1]==binding
    assert {r['key'] for r in resume.rows(ledger.db,'CPU_RESUME_WINDOW')}==oldkeys
    ledger.close()


@pytest.mark.parametrize('bad',['partial','native','provenance','window'])
def test_unproven_version_reuse_holds_without_fabricating_new_read(tmp_path,bad):
    doc,raw,ledger=separated(tmp_path,partial=bad=='partial')
    current={**doc,'document_id':'new-source-'+sha(raw),'raw_sha256':sha(raw+b' ')};native=raw+b' '
    if bad=='native':native=b'<article><p>Different original body.</p></article>';current['raw_sha256']=sha(native)
    if bad=='provenance':current['provenance_verified']=False
    if bad=='window':
        old=deepcopy(resume.rows(ledger.db,'CPU_RESUME_WINDOW')[0]);old['window']['input_sha256']='0'*64
        with ledger.db:ledger.event('CPU_RESUME_WINDOW',old)
    with pytest.raises((ValueError,q.APIError)):
        resume.reuse_completed_version(ledger,current,native,{})
    assert not q.events(ledger,'CPU_INPUT_REUSE_BINDING')
    assert not q.events(ledger,'CPU_QUEUE_WINDOW_ATTEMPT')
    assert not q.events(ledger,'CPU_QUEUE_DOCUMENT')
    ledger.close()


@pytest.mark.parametrize('new_id',[False,True])
def test_new_native_cannot_materialize_old_partial_tasks_or_reread_done_windows(tmp_path,new_id):
    doc,raw,ledger=separated(tmp_path,partial=True)
    native=raw+b' ';current={**doc,'raw_sha256':sha(native)}
    if new_id:current['document_id']='new-source-'+sha(native)
    cache,policy=cache_source(tmp_path,current,native)
    manifest={'format':'bct-new-rss-delta-v1','documents':[{'document_id':current['document_id'],'url':current['origin_url']}]}
    imported=q.ingest_delta(ledger,manifest,cache,upstream_run_id='later',storage_policy=policy,source_separated=True)
    assert imported[0]['status']=='HELD_ISOLATED'
    assert imported[0]['reason']=='SOURCE_VERSION_HOLD_PENDING_EXACT_NATIVE_REQUIRED'
    model=Extractor();result=q.work(ledger,extractor=model)
    assert result['new_windows']==0 and model.calls==0
    assert not q.events(ledger,'CPU_QUEUE_DOCUMENT')
    assert len(resume.rows(ledger.db,'CPU_RESUME_WINDOW'))==1
    ledger.close()
