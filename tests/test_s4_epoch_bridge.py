"""Secret-free negative and positive epoch predecessor contracts."""
import json
from pathlib import Path
import pytest
from bct.v4 import cpu_s4_epoch_bridge as epoch
from bct.v4 import cpu_operations as op

CURRENT="43799800111"

def sample(monkeypatch,tmp_path):
    fields={"GITHUB_REPOSITORY":"irewon1-lgtm/bottleneck-control-tower",
       "GITHUB_REF":"refs/heads/main","GITHUB_EVENT_NAME":"workflow_dispatch",
       "GITHUB_JOB":"research","BCT_V4_S4_EPOCH_MODE":"verified-exact-manual-v1",
       "GITHUB_WORKFLOW_REF":"irewon1-lgtm/bottleneck-control-tower/.github/workflows/bct-s4-epoch-cpu-manual.yml@refs/heads/main",
       "GITHUB_RUN_ID":CURRENT,"GITHUB_RUN_ATTEMPT":"1"}
    for k,v in fields.items():monkeypatch.setenv(k,v)
    parent={"expected_parent":epoch.INITIAL_ACK,
            "producer_run_id":CURRENT,"producer_attempt":"1","producer_job":"bridge"}
    proof={"format":"bct-s4-epoch-bridge-proof-v1","ref":epoch.EPOCH_REF,
       "old_ack":epoch.ARCHIVED_ACK,
       "epoch_root":"1fd5c95a7cafdd5b1fd7d87acf07f07950f3f1e2",
       "epoch_link_verified":True,"archive_verified":True,
       "producer_run_id":int(CURRENT),"producer_attempt":1,
       "private_ack":epoch.INITIAL_ACK,
       "sqlite_sha256":"b330cdf20ebfe479bedcbe929dfbfe65b2df48639d04dfdfa7d6250082f9a572",
       "last_publisher_run":epoch.MIGRATION_RUN,"epoch_commit_count":2}
    path=tmp_path/"proof.json";path.write_text(json.dumps(proof))
    def github(req):
        if req=="actions/runs/"+str(epoch.MIGRATION_RUN):
            return {"status":"completed","conclusion":"success",
                    "id":epoch.MIGRATION_RUN,"head_branch":"ops/bct-s4-private-epoch-migrate-20261116",
                    "name":"BCT S4 one-shot split private CPU storage epoch migration"}
        if req.startswith("actions/workflows/"):
            return {"workflow_runs":[{"id":int(CURRENT),"event":"workflow_dispatch",
                                      "status":"in_progress","run_attempt":1}]}
        raise AssertionError(req)
    monkeypatch.setattr(epoch,"_github",github)
    return parent,proof,path


def test_migration_seed_bridge_proof_with_no_intervening_cpu_runs(monkeypatch,tmp_path):
    parent,p,path=sample(monkeypatch,tmp_path)
    x=epoch.verify_bridge(parent,path,acquisition_run=epoch.SOURCE_RUN)
    assert x["verified"] is True and x["scheduled"] is False
    assert x["epoch_predecessor"]==epoch.INITIAL_ACK
    assert x["model_calls_during_preflight"]==0


@pytest.mark.parametrize("change",[
    lambda x,y:x.update(producer_job="publish"),
    lambda x,y:x.update(producer_run_id="123"),
    lambda x,y:x.update(expected_parent="f"*40),
    lambda x,y:y.update(archive_verified=False),
    lambda x,y:y.update(epoch_root="f"*40),
    lambda x,y:y.update(epoch_commit_count=4),
    lambda x,y:y.update(last_publisher_run=1),
])
def test_epoch_source_proof_tamper_fails_closed(monkeypatch,tmp_path,change):
    parent,p,path=sample(monkeypatch,tmp_path)
    change(parent,p);path.write_text(json.dumps(p))
    with pytest.raises(ValueError):
        epoch.verify_bridge(parent,path,acquisition_run=epoch.SOURCE_RUN)


def test_intervening_automatic_or_failed_manual_blocks_duplicate_execution(monkeypatch,tmp_path):
    parent,p,path=sample(monkeypatch,tmp_path)
    old=epoch._github
    monkeypatch.setattr(epoch,"_github",lambda req: {
        "workflow_runs":[{"id":epoch.MIGRATION_RUN+10,"status":"completed","conclusion":"failure"}]
    } if req.startswith("actions/workflows/") else old(req))
    with pytest.raises(ValueError,match="INTERVENING"):
        epoch.verify_bridge(parent,path,acquisition_run=epoch.SOURCE_RUN)


def test_no_cpu_epoch_activation_from_another_workflow(monkeypatch,tmp_path):
    parent,p,path=sample(monkeypatch,tmp_path)
    monkeypatch.setenv("GITHUB_WORKFLOW_REF","something.yml@main")
    with pytest.raises(ValueError,match="EXPLICIT"):
        epoch.verify_bridge(parent,path,acquisition_run=epoch.SOURCE_RUN)


def test_cpu_storage_ref_and_budget_remain_fixed():
    assert op.STATE_REF==epoch.EPOCH_REF
    assert op.STATE_HISTORY_LIMIT==64*1024*1024


def _inert_two_fixture():
    skipped=[
        "Download only same-run private GPG-sealed bridge (never private token)",
        "GPG-authenticate bridge and independently verify source-separated checkpoint",
        "Verify actual original RSS and acquisition workflow, not schedule attribution",
        "Retrieve exact signed current original, bounded older input, no URL refetch",
        "Consume <=24 exact pending original CPU windows; no duplicates or stage promotions",
        "Seal only new CPU result with fixed epoch parent",
        "Transfer ONLY authenticated encrypted CPU checkpoint"]
    steps=[{"name":name,"status":"completed","conclusion":"success"} for name in (
        "Set up job","Run actions/checkout@v4","Run actions/setup-python@v5",
        "Free-only guard and exact existing runtime cache key")]
    steps.append({"name":"Run actions/cache/restore@v4","status":"completed","conclusion":"failure"})
    steps += [{"name":name,"status":"completed","conclusion":"skipped"} for name in skipped]
    steps += [{"name":"Post Run actions/checkout@v4","status":"completed","conclusion":"success"},
              {"name":"Complete job","status":"completed","conclusion":"success"}]
    def run(run_id):
        return {"id":run_id,"name":"BCT S4 isolated CPU epoch manual research",
                "path":".github/workflows/"+epoch.WORKFLOW,
                "head_branch":"main","head_sha":epoch.INERT_WORKFLOW_SHA,
                "event":"workflow_dispatch","run_attempt":1,
                "status":"completed","conclusion":"failure"}
    def jobs(run_id):
        return {"total_count":3,"jobs":[
            {"name":"bridge","run_id":run_id,"run_attempt":1,"status":"completed",
             "conclusion":"success","steps":[]},
            {"name":"research","run_id":run_id,"run_attempt":1,"status":"completed",
             "conclusion":"failure","steps":steps},
            {"name":"publish","run_id":run_id,"run_attempt":1,"status":"completed",
             "conclusion":"skipped","steps":[]}]}
    return run,jobs


@pytest.mark.parametrize("run_id",sorted(epoch.INERT_CACHE_MISS_RUNS))
def test_only_exact_observed_cache_failure_can_be_classified_inert(monkeypatch,run_id):
    run,jobs=_inert_two_fixture()
    monkeypatch.setattr(epoch,"_github",lambda path: jobs(run_id))
    result=epoch.verified_inert_cache_miss(run(run_id))
    assert result["CPU_window_steps_skipped"]
    assert result["private_publish_skipped"]


def test_original_anchor_allows_only_the_two_independently_proved_inert_runs(monkeypatch,tmp_path):
    parent,p,path=sample(monkeypatch,tmp_path)
    run,jobs=_inert_two_fixture()
    base=epoch._github
    def github(req):
        if req=="actions/workflows/"+epoch.WORKFLOW+"/runs?per_page=100":
            return {"workflow_runs":[run(43800128467),run(43800182468),
                    {"id":int(CURRENT),"event":"workflow_dispatch","status":"in_progress","run_attempt":1}]}
        if req.endswith("/jobs?per_page=100"):
            return jobs(int(req.split("/")[2]))
        return base(req)
    monkeypatch.setattr(epoch,"_github",github)
    assert epoch.verify_bridge(parent,path,acquisition_run=epoch.SOURCE_RUN)["verified"]


@pytest.mark.parametrize("changed",[
    lambda g:g["jobs"][1]["steps"][9].update(conclusion="success"),
    lambda g:g["jobs"][2].update(conclusion="success"),
    lambda g:g["jobs"][1]["steps"][4].update(conclusion="success"),
    lambda g:g["jobs"][1].update(conclusion="success"),
])
def test_any_cpu_publish_or_cache_receipt_ambiguity_blocks_retry(monkeypatch,changed):
    run,jobs=_inert_two_fixture()
    res=jobs(43800128467)
    changed(res)
    monkeypatch.setattr(epoch,"_github",lambda path:res)
    with pytest.raises(ValueError):
        epoch.verified_inert_cache_miss(run(43800128467))
