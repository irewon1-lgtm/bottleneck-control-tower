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
        raise ValueError("EPOCH_INTERVENING_CPU_RUN_REQUIRES_RECONCILIATION")
    same=[x for x in running if x.get("id")==int(current)]
    if (len(same)!=1 or same[0].get("run_attempt")!=int(attempt)
            or same[0].get("status") not in ("in_progress","queued")
            or same[0].get("event")!="workflow_dispatch"):
        raise ValueError("EPOCH_CURRENT_ACTIONS_RUN_NOT_VERIFIED")
    return {"verified":True,"epoch_predecessor":parent_sha,
            "previous_publisher_run":previous,"bridge_run_id":int(current),
            "source_original_acquisition_run":SOURCE_RUN,
            "scheduled":False,"model_calls_during_preflight":0}
