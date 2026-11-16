"""Only authenticated, specifically reviewed zero-model failed runs can intervene."""
from types import SimpleNamespace
import pytest
from bct.v4 import cpu_s4_epoch_bridge as epoch
from test_s4_epoch_bridge import sample,CURRENT


def record(run_id):
    pin=epoch.REVIEWED_INERT[run_id]
    return {"id":run_id,"name":"BCT S4 isolated CPU epoch manual research",
            "event":"workflow_dispatch","path":".github/workflows/"+epoch.WORKFLOW,
            "head_branch":"main","head_sha":pin["sha"],
            "status":"completed","conclusion":"failure","run_attempt":1,
            "repository":{"full_name":"irewon1-lgtm/bottleneck-control-tower"}}


def jobs(run_id,*,tamper=None):
    pin=epoch.REVIEWED_INERT[run_id]
    cpu_name="Consume <=24 exact pending original CPU windows; no duplicates or stage promotions"
    return {"jobs":[
        {"name":"bridge","conclusion":"success"},
        {"name":"research","id":345678,"conclusion":"failure",
         "steps":[{"name":"Run actions/cache/restore@v4",
                   "conclusion":"failure" if pin["step"].startswith("Run actions") else "success"},
                  {"name":cpu_name,"conclusion":"failure" if pin["step"]==cpu_name else "skipped"},
                  {"name":"Seal only new CPU result with fixed epoch parent","conclusion":"skipped"}]},
        {"name":"publish","conclusion":"skipped"}
    ]}


def setup_reviewed(monkeypatch,tmp_path,run_id):
    parent,proof,path=sample(monkeypatch,tmp_path)
    # The proof must represent a *later* Actions run than all three
    # reviewed failed runs, never manufacture older current-run metadata.
    current="43810000111"
    monkeypatch.setenv("GITHUB_RUN_ID",current)
    parent["producer_run_id"]=current
    proof["producer_run_id"]=int(current)
    path.write_text(__import__("json").dumps(proof))
    old=epoch._github
    obj=record(run_id)
    def get(uri):
        if uri=="actions/runs/"+str(run_id):return obj
        if uri=="actions/runs/"+str(run_id)+"/jobs?per_page=100":return jobs(run_id)
        if uri.startswith("actions/workflows/"):
            return {"workflow_runs":[obj,{"id":int(current),"event":"workflow_dispatch",
                                             "status":"in_progress","run_attempt":1}]}
        return old(uri)
    monkeypatch.setattr(epoch,"_github",get)
    return parent,path


@pytest.mark.parametrize("run_id",[43800128467,43800182468])
def test_exact_real_cache_failures_can_be_verified_inert_without_touching_model(monkeypatch,tmp_path,run_id):
    parent,path=setup_reviewed(monkeypatch,tmp_path,run_id)
    result=epoch.verify_bridge(parent,path,acquisition_run=epoch.SOURCE_RUN)
    assert result["verified"] is True
    assert len(result["reconciled_inert_runs"])==1
    assert result["reconciled_inert_runs"][0]["model_execution_proven_absent"] is True


def test_actual_predecessor_guard_failure_requires_exact_original_log(monkeypatch,tmp_path):
    run_id=43802317441
    parent,path=setup_reviewed(monkeypatch,tmp_path,run_id)
    monkeypatch.setattr(epoch.subprocess,"run",lambda *args,**kwargs:SimpleNamespace(
        returncode=0,stdout="ValueError: EPOCH_INTERVENING_CPU_RUN_REQUIRES_RECONCILIATION\n"))
    result=epoch.verify_bridge(parent,path,acquisition_run=epoch.SOURCE_RUN)
    assert result["reconciled_inert_runs"][0]["id"]==run_id


@pytest.mark.parametrize("invalid",[
    "missing-log","wrong-error","model-executed","log-error"
])
def test_predecessor_failure_cannot_be_called_inert_with_ambiguous_log(monkeypatch,tmp_path,invalid):
    run_id=43802317441
    parent,path=setup_reviewed(monkeypatch,tmp_path,run_id)
    output={"missing-log":"","wrong-error":"ValueError: something else",
            "model-executed":"ValueError: EPOCH_INTERVENING_CPU_RUN_REQUIRES_RECONCILIATION\nBCT_S4_EPOCH_CPU_DURABLE",
            "log-error":"ValueError: EPOCH_INTERVENING_CPU_RUN_REQUIRES_RECONCILIATION"}[invalid]
    monkeypatch.setattr(epoch.subprocess,"run",lambda *args,**kwargs:SimpleNamespace(
        returncode=1 if invalid=="log-error" else 0,stdout=output))
    with pytest.raises(ValueError,match="PREMODEL_FAILURE"):
        epoch.verify_bridge(parent,path,acquisition_run=epoch.SOURCE_RUN)


def test_unknown_or_unreviewed_future_run_is_blocked_even_if_failed(monkeypatch,tmp_path):
    parent,proof,path=sample(monkeypatch,tmp_path)
    old=epoch._github
    monkeypatch.setattr(epoch,"_github",lambda req:
        {"workflow_runs":[{"id":43799799999,"status":"completed","conclusion":"failure"},
                          {"id":int(CURRENT),"status":"in_progress","event":"workflow_dispatch","run_attempt":1}]}
        if req.startswith("actions/workflows/") else old(req))
    with pytest.raises(ValueError,match="UNREVIEWED_INTERVENING"):
        epoch.verify_bridge(parent,path,acquisition_run=epoch.SOURCE_RUN)
