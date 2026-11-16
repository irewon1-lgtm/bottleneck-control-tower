"""Session 4 bounded CPU source-version prioritization under an exact manual proof.

These are task-selection tests, not empirical semantics/AI-quality tests.
"""
from pathlib import Path
import pytest
from bct.v4 import cpu_automation as q
from test_v4_cpu_automation import document, Extractor


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(q, 'analyze_queued', lambda *args,**kwargs: {})
    l=q.open_queue(tmp_path)
    sources=[]
    with l.worker():
        for suffix in ('older-a','older-b','target-new'):
            doc,raw=document(suffix=suffix)
            assert q.enqueue(l,doc,raw,{})=='QUEUED'
            sources.append(doc)
    return l,sources


def rows(ledger):
    return q.events(ledger,'CPU_QUEUE_WINDOW_RESULT')


def test_verified_exact_current_source_moves_ahead_of_unrelated_queue(tmp_path,monkeypatch):
    ledger, sources=setup(tmp_path,monkeypatch)
    target=sources[-1]
    context={'priority_source_versions':[{'document_id':target['document_id'],
                                           'body_sha256':target['body_sha256']}]}
    reader=Extractor()
    with ledger.worker():
        first=q.work(ledger,extractor=reader,max_windows=1,analysis_context=context)
        assert first['new_windows']==1
        assert rows(ledger)[0]['document_id']==target['document_id']
        second=q.work(ledger,extractor=reader,max_windows=2,analysis_context=context)
        assert second['new_windows']==2
        assert {r['document_id'] for r in rows(ledger)}=={d['document_id'] for d in sources}
        third=q.work(ledger,extractor=reader,max_windows=24,analysis_context=context)
        assert third['new_windows']==0 and reader.calls==3
        assert len({r['key'] for r in rows(ledger)})==3
    ledger.close()


def test_no_priority_preserves_existing_fifo(tmp_path,monkeypatch):
    ledger,sources=setup(tmp_path,monkeypatch)
    with ledger.worker():
        result=q.work(ledger,extractor=Extractor(),max_windows=1)
        assert result['new_windows']==1
        assert rows(ledger)[0]['document_id']==sources[0]['document_id']
    ledger.close()


def test_wrong_body_version_cannot_win_priority(tmp_path,monkeypatch):
    ledger,sources=setup(tmp_path,monkeypatch)
    with ledger.worker():
        q.work(ledger,extractor=Extractor(),max_windows=1,
               analysis_context={'priority_source_versions':[{
                   'document_id':sources[-1]['document_id'],
                   'body_sha256':'f'*64}]})
        assert rows(ledger)[0]['document_id']==sources[0]['document_id']
    ledger.close()


@pytest.mark.parametrize('invalid',[
    [],None,'all',{},[{'document_id':'x'}],
    [{'document_id':'x','body_sha256':'bad'}],
    [{'document_id':'x','body_sha256':'a'*64}, {'document_id':'x','body_sha256':'a'*64}],
])
def test_unverified_priority_input_fails_before_any_model_call(tmp_path,monkeypatch,invalid):
    ledger,sources=setup(tmp_path,monkeypatch)
    model=Extractor()
    with ledger.worker():
        with pytest.raises(ValueError,match='CPU_EXACT_SOURCE_PRIORITY'):
            q.work(ledger,extractor=model,max_windows=1,
                   analysis_context={'priority_source_versions':invalid})
        assert not rows(ledger) and model.calls==0
    ledger.close()


def test_priority_only_enabled_for_verified_manual_original_case():
    code=(Path(__file__).resolve().parents[1]/'tools/v4_cpu_private.py').read_text()
    assert "if manual and schedule['acquisition_run_id'] == 43645932280:" in code
    assert "SESSION4_EXACT_MANUAL_SOURCE_RECOVERY_NOT_VERIFIED" in code
    assert "'current_artifact_exact_holds_recovered'" in code
    assert "priority_context['priority_source_versions']" in code
    assert "analysis_context={'cache':a.cache,'manifest':manifest" in code


def test_verified_cohort_consumes_full_batch_before_unrelated_pending(tmp_path,monkeypatch):
    monkeypatch.setattr(q,'analyze_queued',lambda *args,**kwargs: {})
    ledger=q.open_queue(tmp_path)
    with ledger.worker():
        older1,raw1=document(suffix='old-1')
        older2,raw2=document(suffix='old-2')
        target,raw3=document(
            'Atlas ordered Helios heat pumps.\nA second separate paragraph.\n'
            'A third separate paragraph.\nA fourth paragraph.',suffix='target')
        for doc,raw in ((older1,raw1),(older2,raw2),(target,raw3)):
            assert q.enqueue(ledger,doc,raw,{})=='QUEUED'
        wanted=[{'document_id':target['document_id'],
                 'body_sha256':target['body_sha256']}]
        ctx={'priority_source_versions':wanted}
        queues=[d for d in q.events(ledger,'CPU_QUEUE_DOCUMENT')
                if d['document_id']==target['document_id']]
        assert len(queues)==1 and len(queues[0]['tasks'])>=3
        reader=Extractor()
        result=q.work(ledger,extractor=reader,max_windows=2,analysis_context=ctx)
        assert result['new_windows']==2
        assert [x['document_id'] for x in rows(ledger)]==[target['document_id']]*2
        assert reader.calls==2
        remaining=len(queues[0]['tasks'])-2
        second=q.work(ledger,extractor=reader,max_windows=remaining,analysis_context=ctx)
        assert second['new_windows']==remaining
        assert all(x['document_id']==target['document_id'] for x in rows(ledger))
        fallback=q.work(ledger,extractor=reader,max_windows=2,analysis_context=ctx)
        assert fallback['new_windows']==2
        assert [x['document_id'] for x in rows(ledger)[-2:]]==[older1['document_id'],older2['document_id']]
        no_repeat=q.work(ledger,extractor=reader,max_windows=24,analysis_context=ctx)
        assert no_repeat['new_windows']==0
        assert len({x['key'] for x in rows(ledger)})==reader.calls
    ledger.close()


def test_target_cohort_round_robin_fairness_within_manual_selection(tmp_path,monkeypatch):
    monkeypatch.setattr(q,'analyze_queued',lambda *args,**kwargs: {})
    ledger=q.open_queue(tmp_path)
    with ledger.worker():
        old,oldraw=document(suffix='old')
        first,first_raw=document('Atlas ordered Helios heat pumps.\nSecond paragraph.',suffix='first')
        second,second_raw=document('Atlas ordered Helios heat pumps.\nAnother paragraph.',suffix='second')
        for d,raw in ((old,oldraw),(first,first_raw),(second,second_raw)):
            q.enqueue(ledger,d,raw,{})
        ctx={'priority_source_versions':[
            {'document_id':d['document_id'],'body_sha256':d['body_sha256']}
            for d in (first,second)]}
        q.work(ledger,extractor=Extractor(),max_windows=4,analysis_context=ctx)
        assert [x['document_id'] for x in rows(ledger)]==[
            first['document_id'],second['document_id'],first['document_id'],second['document_id']]
        assert not any(x['document_id']==old['document_id'] for x in rows(ledger))
    ledger.close()
