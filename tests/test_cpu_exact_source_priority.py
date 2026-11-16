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
