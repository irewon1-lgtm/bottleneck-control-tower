"""Strict source-free predecessor attestation for isolated manual CPU epoch.

The GPG-authenticated bridge was created within THIS Actions run by the
private credential-only job, from an immutable remote ref. This preflight
does not use the private token and never reads native article text.
No old scheduled path is changed or allowed to use the new state ref.
"""
import json
import os
from pathlib import Path
import re
import subprocess
from . import cpu_operations as op

WORKFLOW = "bct-s4-epoch-cpu-manual.yml"
ARCHIVED_ACK = "8493ce906aea1c4ef14693873ba016e708d30245"
INITIAL_ACK = "9dd255c99d382c4bd3b366474e30ed1e7cb2d1bf"
SOURCE_RUN = 43645932280
MIGRATION_RUN = 43797154689
EPOCH_REF = "refs/heads/codex/bct-v4-cpu-research-epoch-20261116"

def _github(path):
    result=subprocess.run(["gh","api","repos/irewon1-lgtm/bottleneck-control-tower/"+path],
                          capture_output=True,text=True,timeout=25)
    if result.returncode:raise ValueError("EPOCH_PUBLIC_RUN_PROOF_UNAVAILABLE")
    return json.loads(result.stdout)


# Only these three already-observed and independently traceable failures are
# eligible for source-free, non-model execution reconciliation. Future failed
# runs MUST stop until explicitly reviewed; no broad 'failed == inert' shortcut.
REVIEWED_INERT = {
    43800128467: {"sha":"a85e86fad091e10ea2df13211a0687e4166e6e0f",
                  "step":"Run actions/cache/restore@v4"},
    43800182468: {"sha":"a85e86fad091e10ea2df13211a0687e4166e6e0f",
                  "step":"Run actions/cache/restore@v4"},
    43802317441: {"sha":"1ebe82ddd0ba536d255e30f2254ca5d3ec7f240d",
                  "step":"Consume <=24 exact pending original CPU windows; no duplicates or stage promotions"},
}


def _verified_inert_epoch_run(record):
    """Source-free independent Actions attestation, not a success assumption.

    The prior two failures stopped during required cache restore. The third
    stopped inside predecessor verification before the CPU extractor could
    initialize; prove the exact preflight exception via sealed job logs.
    """
    run_id=record.get("id")
    pinned=REVIEWED_INERT.get(run_id)
    if pinned is None:
        raise ValueError("EPOCH_UNREVIEWED_INTERVENING_RUN_BLOCKED")
    run=_github("actions/runs/"+str(run_id))
    expected={"id":run_id,"name":"BCT S4 isolated CPU epoch manual research",
              "event":"workflow_dispatch",
              "path":".github/workflows/"+WORKFLOW,
              "head_branch":"main","head_sha":pinned["sha"],
              "status":"completed","conclusion":"failure","run_attempt":1}
    if any(run.get(k)!=v or record.get(k)!=v for k,v in expected.items()):
        raise ValueError("EPOCH_INERT_RUN_IDENTITY_OR_ATTEMPT_MISMATCH")
    if run.get("repository",{}).get("full_name")!="irewon1-lgtm/bottleneck-control-tower":
        raise ValueError("EPOCH_INERT_RUN_REPOSITORY_CHANGED")
    jobs=_github("actions/runs/"+str(run_id)+"/jobs?per_page=100").get("jobs")
    if not isinstance(jobs,list) or len(jobs)!=3 or {j.get("name") for j in jobs}!={"bridge","research","publish"}:
        raise ValueError("EPOCH_INERT_JOBS_NOT_THREE")
    by_name={j["name"]:j for j in jobs}
    if any(by_name[name].get("conclusion")!=conclusion
           for name,conclusion in (("bridge","success"),("research","failure"),("publish","skipped"))):
        raise ValueError("EPOCH_INERT_JOB_STATUS_NOT_PROVEN")
    steps=by_name["research"].get("steps")
    if not isinstance(steps,list):
        raise ValueError("EPOCH_INERT_RESEARCH_STEPS_MISSING")
    failed=[s for s in steps if s.get("conclusion")=="failure"]
    if len(failed)!=1 or failed[0].get("name")!=pinned["step"]:
        raise ValueError("EPOCH_INERT_FAILURE_STAGE_MISMATCH")
    cpu_name="Consume <=24 exact pending original CPU windows; no duplicates or stage promotions"
    cpu=[s for s in steps if s.get("name")==cpu_name]
    seal=[s for s in steps if s.get("name")=="Seal only new CPU result with fixed epoch parent"]
    if len(cpu)!=1 or len(seal)!=1 or seal[0].get("conclusion")!="skipped":
        raise ValueError("EPOCH_INERT_CPU_OR_SEAL_STEPS_UNVERIFIED")
    if pinned["step"]!=cpu_name:
        if cpu[0].get("conclusion")!="skipped":
            raise ValueError("EPOCH_CACHE_FAILED_BUT_MODEL_STEP_NOT_SKIPPED")
    else:
        if cpu[0].get("conclusion")!="failure":
            raise ValueError("EPOCH_PREPROCESS_STEP_NOT_FAILED")
        job=by_name["research"]
        job_id=job.get("id")
        if type(job_id) is not int:
            raise ValueError("EPOCH_PREPROCESS_JOB_ID_INVALID")
        result=subprocess.run(
            ["gh","run","view",str(run_id),"--job",str(job_id),"--repo",
             "irewon1-lgtm/bottleneck-control-tower","--log"],
            capture_output=True,text=True,timeout=45)
        # Do not emit or save log contents. Verified exact guard name alone is
        # not enough; this error is thrown before the model is instantiated.
        if (result.returncode!=0
                or result.stdout.count(
                    "ValueError: EPOCH_INTERVENING_CPU_RUN_REQUIRES_RECONCILIATION")!=1
                or "BCT_S4_EPOCH_CPU_DURABLE" in result.stdout):
            raise ValueError("EPOCH_PREMODEL_FAILURE_SIGNATURE_UNVERIFIED")
    return {"id":run_id,"failure_step":pinned["step"],
            "model_execution_proven_absent":True}

def verify_bridge(parent, proof_path, *, acquisition_run):
    if (os.environ.get("GITHUB_REPOSITORY")!="irewon1-lgtm/bottleneck-control-tower"
            or os.environ.get("GITHUB_REF")!="refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME")!="workflow_dispatch"
            or os.environ.get("GITHUB_JOB")!="research"
            or os.environ.get("GITHUB_WORKFLOW_REF","").split("@")[0].split("/")[-1]!=WORKFLOW
            or os.environ.get("BCT_V4_S4_EPOCH_MODE")!="verified-exact-manual-v1"
            or acquisition_run!=SOURCE_RUN
            or op.STATE_REF!=EPOCH_REF):
        raise ValueError("EPOCH_EXPLICIT_RESEARCH_CONTEXT_REQUIRED")
    current=os.environ.get("GITHUB_RUN_ID","")
    attempt=os.environ.get("GITHUB_RUN_ATTEMPT","")
    if not (current.isdecimal() and attempt.isdecimal() and int(current)>MIGRATION_RUN
            and 1<=int(attempt)<=3):
        raise ValueError("EPOCH_CURRENT_RUN_IDENTITY_UNVERIFIED")
    if (parent.get("producer_job")!="bridge"
            or parent.get("producer_run_id")!=current
            or parent.get("producer_attempt")!=attempt):
        raise ValueError("EPOCH_BRIDGE_NOT_FROM_THIS_RUN")
    receipt=json.loads(Path(proof_path).read_bytes())
    required={"format":"bct-s4-epoch-bridge-proof-v1",
              "ref":EPOCH_REF,
              "old_ack":ARCHIVED_ACK,
              "epoch_root":"1fd5c95a7cafdd5b1fd7d87acf07f07950f3f1e2",
              "epoch_link_verified":True,
              "archive_verified":True,
              "producer_run_id":int(current),
              "producer_attempt":int(attempt)}
    if any(receipt.get(k)!=v for k,v in required.items()):
        raise ValueError("EPOCH_BRIDGE_PROOF_FIELDS_INVALID")
    parent_sha=parent.get("expected_parent")
    if (not isinstance(parent_sha,str) or not re.fullmatch("[a-f0-9]{40}",parent_sha)
            or parent_sha!=receipt.get("private_ack")
            or not re.fullmatch("[a-f0-9]{64}",receipt.get("sqlite_sha256",""))):
        raise ValueError("EPOCH_BRIDGE_PARENT_OR_DB_HASH_INVALID")
    previous=receipt.get("last_publisher_run")
    if type(previous) is not int or previous<MIGRATION_RUN:
        raise ValueError("EPOCH_PUBLISHER_RUN_UNVERIFIED")
    old=_github("actions/runs/"+str(previous))
    if (old.get("status")!="completed" or old.get("conclusion")!="success"
            or old.get("id")!=previous or old.get("head_branch") not in
             ("main","ops/bct-s4-private-epoch-migrate-20261116")):
        raise ValueError("EPOCH_PREVIOUS_PUBLISHER_NOT_SUCCESS")
    if parent_sha==INITIAL_ACK:
        if (previous!=MIGRATION_RUN or old.get("name")!="BCT S4 one-shot split private CPU storage epoch migration"
                or receipt.get("epoch_commit_count")!=2):
            raise ValueError("EPOCH_INITIAL_MIGRATION_ACK_MISMATCH")
    else:
        if (previous==MIGRATION_RUN or old.get("path")!=".github/workflows/"+WORKFLOW
                or old.get("event")!="workflow_dispatch"
                or receipt.get("epoch_commit_count",0)<4
                or receipt["epoch_commit_count"]%2):
            raise ValueError("EPOCH_PRIOR_MANUAL_PUBLISHER_NOT_VERIFIED")
    running=_github("actions/workflows/"+WORKFLOW+"/runs?per_page=100").get("workflow_runs",[])
    if not isinstance(running,list) or len(running)>100:
        raise ValueError("EPOCH_PREVIOUS_RUN_LIST_NOT_COMPLETE")
    later=[x for x in running if previous<x.get("id",-1)<int(current)]
    reconciled=[]
    for prior in later:
        reconciled.append(_verified_inert_epoch_run(prior))

    same=[x for x in running if x.get("id")==int(current)]
    if (len(same)!=1 or same[0].get("run_attempt")!=int(attempt)
            or same[0].get("status") not in ("in_progress","queued")
            or same[0].get("event")!="workflow_dispatch"):
        raise ValueError("EPOCH_CURRENT_ACTIONS_RUN_NOT_VERIFIED")
    return {"verified":True,"epoch_predecessor":parent_sha,
            "previous_publisher_run":previous,"bridge_run_id":int(current),
            "source_original_acquisition_run":SOURCE_RUN,
            "scheduled":False,"model_calls_during_preflight":0,"reconciled_inert_runs":reconciled}
