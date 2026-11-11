"""Model progress and source-bound analysis have independent durable receipts."""
import json
import sys
import types
import subprocess

from bct.v4 import cpu_automation as q
from test_v4_cpu_automation import document, Extractor


def bound_context(tmp_path,doc,raw):
    """A complete declared empty counterpart set, bound to real fixture bytes."""
    from bct.v4.store import sha
    from test_v4_cpu_resume import cache_source
    cache,_=cache_source(tmp_path,doc,raw)
    native='raw/'+doc['raw_sha256']+'.html';member='documents/doc.json'
    files={name:{'bytes':(cache/name).stat().st_size,'sha256':sha((cache/name).read_bytes())}
           for name in (native,member)}
    descriptor={k:doc[k] for k in ('document_id','origin_url','body_sha256','raw_sha256')}
    descriptor.update(document_member=member,native_member=native,metadata_sha256=files[member]['sha256'],source_kind='RSS')
    manifest={'format':'bct-cpu-source-delta-1','status':'READY','documents':[descriptor],'files':files,
              'graph_context_complete':True,'required_graph_sources':[],'unavailable_graph_sources':[]}
    return {'cache':cache,'manifest':manifest}


def adapter(monkeypatch, callback):
    module = types.ModuleType('bct.v4.cpu_review')
    module.record_analysis = callback
    monkeypatch.setitem(sys.modules, 'bct.v4.cpu_review', module)
    import bct.v4
    monkeypatch.setattr(bct.v4, 'cpu_review', module, raising=False)


def test_analysis_error_preserves_windows_other_documents_and_retries_without_model(tmp_path, monkeypatch):
    ledger = q.open_queue(tmp_path)
    docs = [document(suffix=suffix) for suffix in ('one', 'two')]
    for doc, raw in docs:
        q.enqueue(ledger, doc, raw, {})
    calls = []
    def broken(store, doc, **kwargs):
        calls.append(doc['document_id'])
        if doc['document_id'] == docs[0][0]['document_id']:
            raise RuntimeError('private source text must never be retained')
        return {'id': 'safe', 'delivery': 'NEW_ANALYSIS'}
    adapter(monkeypatch, broken)
    model = Extractor()
    result = q.work(ledger, extractor=model)
    assert model.calls == 2 and len(q.events(ledger, 'CPU_QUEUE_WINDOW_RESULT')) == 2
    assert len(calls) == 2 and result['analysis_runtime_failures'] == 1
    failure = q.events(ledger, 'CPU_ANALYSIS_FAILURE')[0]
    assert failure['document_id'] == docs[0][0]['document_id']
    assert failure['body_sha256'] == docs[0][0]['body_sha256']
    assert failure['raw_sha256'] == docs[0][0]['raw_sha256']
    assert failure['reason_code'] == 'ANALYSIS_RUNTIME_FAILED'
    assert 'private source' not in json.dumps(failure)
    adapter(monkeypatch, lambda store, doc, **kw: {'id': 'safe', 'delivery': 'NEW_ANALYSIS'})
    retried = q.work(ledger, extractor=model)
    assert retried['new_windows'] == 0 and model.calls == 2
    assert retried['analysis_attempts'] == 2 and retried['analysis_runtime_failures'] == 0
    ledger.close()


def test_unexpected_analysis_failure_does_not_rollback_committed_model_window(tmp_path, monkeypatch):
    ledger = q.open_queue(tmp_path)
    doc, raw = document()
    q.enqueue(ledger, doc, raw, {})
    def interrupted(store, doc, **kwargs):
        raise KeyboardInterrupt()
    adapter(monkeypatch, interrupted)
    import pytest
    with pytest.raises(KeyboardInterrupt):
        q.work(ledger, extractor=Extractor())
    ledger.close()
    ledger = q.open_queue(tmp_path)
    assert len(q.events(ledger, 'CPU_QUEUE_WINDOW_RESULT')) == 1
    assert q.state(ledger)['pending_windows'] == 0
    ledger.close()


def test_complete_model_progress_restores_exact_source_and_retries_only_analysis(tmp_path,monkeypatch):
    from bct.v4 import cpu_resume as resume
    from test_v4_cpu_resume import cache_source
    ledger=q.open_queue(tmp_path/'original');doc,raw=document()
    q.enqueue(ledger,doc,raw,{})
    with monkeypatch.context() as scoped:
        def broken(*args,**kwargs):raise RuntimeError('analysis only')
        adapter(scoped,broken)
        first=q.work(ledger,extractor=Extractor())
    assert first['new_windows']==1 and first['analysis_errors']==1
    ledger.close();resume.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'safe')
    ledger=q.open_queue(tmp_path/'safe');resume.audit(ledger)
    old_keys={r['key'] for r in resume.rows(ledger.db,'CPU_RESUME_WINDOW')}
    cache,policy=cache_source(tmp_path,doc,raw)
    resumed=resume.hydrate(ledger,cache,policy,retry_analysis=True)
    assert resumed[0]['status']=='SOURCE_REHYDRATED_NO_COMPLETED_WINDOW_RERUN'
    model=Extractor();retried=q.work(ledger,extractor=model)
    assert retried['new_windows']==0 and model.calls==0 and retried['new_analysis_results']==1
    analysis=q.events(ledger,'CPU_ANALYSIS_RESULT')[-1]
    assert analysis['read_state']=='READ_COMPLETE'
    assert analysis['restored_success_windows']==1 and analysis['new_inference_windows']==0
    ledger.close();resume.export_state(tmp_path/'safe/v4.sqlite3',tmp_path/'second')
    ledger=q.open_queue(tmp_path/'second');resume.audit(ledger)
    assert {r['key'] for r in resume.rows(ledger.db,'CPU_RESUME_WINDOW')}==old_keys
    assert q.events(ledger,'CPU_ANALYSIS_RESULT')[-1]==analysis
    assert len(q.events(ledger,'CPU_ANALYSIS_FAILURE'))==1
    ledger.close()
    code='''import sys,json
from bct.v4 import cpu_automation as q,cpu_resume as r
l=q.open_queue(sys.argv[1]);r.audit(l);r.export_state(l.path,sys.argv[2]);l.close()
l=q.open_queue(sys.argv[2]);r.audit(l);print(json.dumps(q.events(l,"CPU_ANALYSIS_RESULT")));l.close()
'''
    output=subprocess.check_output([sys.executable,'-c',code,str(tmp_path/'second'),str(tmp_path/'third')],text=True)
    assert json.loads(output)[-1]==analysis


def test_readonly_graph_context_is_not_materialized_as_an_extra_cpu_analysis_root(tmp_path):
    from bct.v4 import cpu_resume as resume
    from test_v4_cpu_resume import cache_source
    ledger=q.open_queue(tmp_path/'original');doc,raw=document();q.enqueue(ledger,doc,raw,{})
    q.work(ledger,extractor=Extractor());ledger.close()
    resume.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'safe')
    ledger=q.open_queue(tmp_path/'safe');cache,policy=cache_source(tmp_path,doc,raw)
    assert resume.hydrate(ledger,cache,policy,retry_analysis=True,analysis_document_ids=set())==[]
    model=Extractor();result=q.work(ledger,extractor=model)
    assert result['analysis_attempts']==0 and result['new_windows']==0 and model.calls==0
    assert not q.events(ledger,'CPU_QUEUE_DOCUMENT')
    ledger.close()
