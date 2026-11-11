"""Original model-run attribution survives analysis-only restoration and reuse."""
import json

import pytest

from bct.v4 import cpu_automation as q,cpu_operations as op,cpu_resume as resume
from bct.v4.store import sha
from test_v4_cpu_automation import document,Extractor
from test_v4_cpu_resume import cache_source


def test_source_accepts_workflow_expected_c_without_hardcoded_seed_pin(monkeypatch):
    code='a'*40
    class Result:returncode=0;stdout=code+'\n'
    monkeypatch.setattr(op.subprocess,'run',lambda *a,**kw:Result())
    monkeypatch.setenv('CPU_CODE_SHA',code)
    assert op.verify_execution_pin(code)==code
    with pytest.raises(ValueError,match='PIN_INVALID'):op.verify_execution_pin('221fa')
    monkeypatch.setenv('CPU_CODE_SHA','b'*40)
    with pytest.raises(ValueError,match='PIN_INVALID'):op.verify_execution_pin(code)


def test_new_model_window_producer_is_restored_original_and_never_current_retry(tmp_path,monkeypatch):
    producer={'run_id':100,'run_attempt':1,'execution_sha':'a'*40,'workflow_sha':'b'*40}
    monkeypatch.setenv('GITHUB_ACTIONS','true');monkeypatch.setenv('GITHUB_REPOSITORY','irewon1-lgtm/bottleneck-control-tower')
    monkeypatch.setenv('GITHUB_RUN_ID','100');monkeypatch.setenv('GITHUB_RUN_ATTEMPT','1')
    monkeypatch.setenv('GITHUB_WORKFLOW_SHA','b'*40);monkeypatch.setenv('EXPECTED_CPU_CODE_SHA','a'*40)
    monkeypatch.setattr(op,'verify_execution_pin',lambda expected:'a'*40)
    doc,native=document();ledger=q.open_queue(tmp_path/'original');q.enqueue(ledger,doc,native,{})
    q.work(ledger,extractor=Extractor())
    assert q.events(ledger,'CPU_QUEUE_WINDOW_RESULT')[0]['inference_producer']==producer
    ledger.close();resume.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'safe')
    cache,policy=cache_source(tmp_path,doc,native);ledger=q.open_queue(tmp_path/'safe')
    assert resume.rows(ledger.db,'CPU_RESUME_WINDOW')[0]['inference_producer']==producer
    monkeypatch.setenv('GITHUB_RUN_ID','200');monkeypatch.setenv('GITHUB_WORKFLOW_SHA','c'*40)
    resume.hydrate(ledger,cache,policy,retry_analysis=True)
    model=Extractor();result=q.work(ledger,extractor=model)
    assert result['new_windows']==model.calls==0
    assert q.events(ledger,'CPU_QUEUE_WINDOW_RESULT')[0]['inference_producer']==producer
    assert q.events(ledger,'CPU_ANALYSIS_RESULT')[-1]['model_read_producer']==producer
    ledger.close()
