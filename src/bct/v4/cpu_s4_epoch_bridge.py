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

# Exactly two previously observed cache-key failures. Their complete Actions job
# graphs must prove no native source read, no CPU inference and no publish.
# These are NOT generic "ignore failed runs" exceptions.
INERT_CACHE_MISS_RUNS = {43800128467, 43800182468}
INERT_WORKFLOW_SHA = "a85e86fad091e10ea2df13211a0687e4166e6e0f"

def verified_inert_cache_miss(run):
    run_id=run.get("id")
    if (run_id not in INERT_CACHE_MISS_RUNS
            or run.get("name")!="BCT S4 isolated CPU epoch manual research"
            or run.get("path")!=".github/workflows/"+WORKFLOW
            or run.get("head_branch")!="main"
            or run.get("head_sha")!=INERT_WORKFLOW_SHA
            or run.get("event")!="workflow_dispatch"
            or run.get("run_attempt")!=1
            or run.get("status")!="completed"
            or run.get("conclusion")!="failure"):
        raise ValueError("EPOCH_UNVERIFIED_PRIOR_FAILED_CPU_RUN")
    result=_github("actions/runs/"+str(run_id)+"/jobs?per_page=100")
    jobs=result.get("jobs",[])
    if (result.get("total_count")!=3 or len(jobs)!=3
            or {j.get("name") for j in jobs}!={"bridge","research","publish"}
            or any(j.get("run_id")!=run_id or j.get("run_attempt")!=1
                   or j.get("status")!="completed" for j in jobs)):
        raise ValueError("EPOCH_PRIOR_CACHE_FAILURE_JOB_GRAPH_MISSING")
    jobs={j["name"]:j for j in jobs}
    if (jobs["bridge"].get("conclusion")!="success"
            or jobs["research"].get("conclusion")!="failure"
            or jobs["publish"].get("conclusion")!="skipped"
            or jobs["publish"].get("steps")!=[]):
        raise ValueError("EPOCH_PRIOR_CPU_OR_PUBLICATION_MAY_HAVE_RUN")
    steps=jobs["research"].get("steps",[])
    names=[s.get("name") for s in steps]
    if len(steps)<10 or len(names)!=len(set(names)) or "Run actions/cache/restore@v4" not in names:
        raise ValueError("EPOCH_PRIOR_RESEARCH_STEPS_UNVERIFIED")
    index=names.index("Run actions/cache/restore@v4")
    if (steps[index].get("status")!="completed"
            or steps[index].get("conclusion")!="failure"
            or any(x.get("conclusion")!="success" for x in steps[:index])
            or sum(x.get("conclusion")=="failure" for x in steps)!=1):
        raise ValueError("EPOCH_PRIOR_FAILURE_NOT_EXACT_CACHE_MISS")
    required_skipped=(
        "Download only same-run private GPG-sealed bridge (never private token)",
        "GPG-authenticate bridge and independently verify source-separated checkpoint",
        "Verify actual original RSS and acquisition workflow, not schedule attribution",
        "Retrieve exact signed current original, bounded older input, no URL refetch",
        "Consume <=24 exact pending original CPU windows; no duplicates or stage promotions",
        "Seal only new CPU result with fixed epoch parent",
        "Transfer ONLY authenticated encrypted CPU checkpoint",
    )
    if (any(name not in names or steps[names.index(name)].get("conclusion")!="skipped"
            for name in required_skipped)
            or any(steps[i].get("conclusion") not in ("skipped","success")
                   for i in range(index+1,len(steps)))):
        raise ValueError("EPOCH_PRIOR_CPU_SIDE_EFFECTS_NOT_EXCLUDED")
    return {"run_id":run_id,"failed_only_at_cache":True,"CPU_window_steps_skipped":True,
            "private_publish_skipped":True}

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
    if later:
        if (parent_sha!=INITIAL_ACK
                or {x.get("id") for x in later}!=INERT_CACHE_MISS_RUNS):
            raise ValueError("EPOCH_INTERVENING_CPU_RUN_REQUIRES_RECONCILIATION")
        # Exact prior cache-only failures have no CPU or private write. This
        # claim is verified from GitHub's actual job/step receipts, not labels.
        for run in later:
            verified_inert_cache_miss(run)
    same=[x for x in running if x.get("id")==int(current)]
    if (len(same)!=1 or same[0].get("run_attempt")!=int(attempt)
            or same[0].get("status") not in ("in_progress","queued")
            or same[0].get("event")!="workflow_dispatch"):
        raise ValueError("EPOCH_CURRENT_ACTIONS_RUN_NOT_VERIFIED")
    return {"verified":True,"epoch_predecessor":parent_sha,
            "previous_publisher_run":previous,"bridge_run_id":int(current),
            "source_original_acquisition_run":SOURCE_RUN,
            "scheduled":False,"model_calls_during_preflight":0}
