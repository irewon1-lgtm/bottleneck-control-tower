"""Bounded, serial Session 4 epoch CPU follow-on with source-free ACK proofs.

Only dispatch the already reviewed single-source-cohort CPU workflow.
No model calls in this coordinator, no old private state access or writes,
and no automatic LIVE/S-class candidate promotion. Any unknown outcome
halts further dispatches; never silently rerun a possibly completed job.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import tempfile

REPO="irewon1-lgtm/bottleneck-control-tower"
WORKFLOW="bct-s4-epoch-cpu-manual.yml"
MAIN_SHA="509d6fcdb894f74f4f7fb3ce77b10cb35f5891a6"
CPU_CODE_SHA="aca2ccf56032c7841188997e857828142dadcb0a"
ACQUISITION=43645932280
INITIAL_RUN=43804165764
INITIAL_ACK="c65ab5be1d5b683fd33c1c4843b4f05325892697"
MAX_BATCHES=7
MAX_NEW_WINDOWS=24
EXPECTED_UNREAD=157

def digest(data):
    return hashlib.sha256(data).hexdigest()

def json_bytes(data):
    return json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def cmd(args,timeout=60):
    r=subprocess.run(args,capture_output=True,timeout=timeout)
    if r.returncode:
        raise ValueError("S4_GITHUB_PROVIDER_CALL_FAILED_NO_AUTOMATIC_RETRY")
    return r.stdout

def api(path):
    return json.loads(cmd(["gh","api","repos/"+REPO+"/"+path]))

def current_main():
    sha=api("git/ref/heads/main")["object"]["sha"]
    if sha!=MAIN_SHA:
        raise ValueError("S4_PRODUCTION_MAIN_SHA_CHANGED")
    return sha

def run_list():
    rows=api("actions/workflows/"+WORKFLOW+"/runs?event=workflow_dispatch&per_page=100").get("workflow_runs",[])
    if not isinstance(rows,list) or len(rows)>100 or any(type(x.get("id")) is not int for x in rows):
        raise ValueError("S4_WORKFLOW_RUN_LIST_INVALID")
    return rows

def verify_run_identity(row,run_id):
    if (row.get("id")!=run_id
            or row.get("name")!="BCT S4 isolated CPU epoch manual research"
            or row.get("event")!="workflow_dispatch"
            or row.get("path")!=".github/workflows/"+WORKFLOW
            or row.get("head_branch")!="main"
            or row.get("head_sha")!=MAIN_SHA
            or row.get("run_attempt")!=1):
        raise ValueError("S4_MANUAL_RUN_IDENTITY_INVALID")

def await_run(run_id,timeout_seconds=750):
    until=time.monotonic()+timeout_seconds
    while time.monotonic()<until:
        row=api("actions/runs/"+str(run_id))
        verify_run_identity(row,run_id)
        if row.get("status")=="completed":
            if row.get("conclusion")!="success":
                raise ValueError("S4_CPU_OR_PRIVATE_CAS_NOT_FULL_SUCCESS")
            return row
        time.sleep(12)
    raise ValueError("S4_RUNNING_CPU_RESULT_UNKNOWN_DO_NOT_REDISPATCH")

def proof(run_id,folder):
    folder=Path(folder)
    if folder.exists():
        raise ValueError("S4_ARTIFACT_DIRECTORY_EXISTS")
    folder.mkdir(parents=True)
    cmd(["gh","run","download",str(run_id),"-R",REPO,
         "--name","bct-s4-epoch-private-published",
         "--dir",str(folder)],timeout=75)
    items=list(folder.glob("*.json"))
    if len(items)!=1 or items[0].name!="epoch-s4-publication.json":
        raise ValueError("S4_EXACT_PUBLISHED_ACK_ARTIFACT_MISSING")
    value=json.loads(items[0].read_bytes())
    required={"format":"bct-s4-epoch-cpu-publication-receipt-v1",
              "status":"PASS_REMOTE_PRIVATE_EPOCH_CAS_RESTORED",
              "publisher_run_id":run_id,
              "code_sha":CPU_CODE_SHA,
              "analysis_errors":0,
              "model_api_calls":0,
              "LIVE_registration":False,
              "old_private_ref_writes":0}
    if any(value.get(k)!=v for k,v in required.items()):
        raise ValueError("S4_EPOCH_PUBLISHED_RECEIPT_NOT_VERIFIED")
    if (type(value.get("successful_new_windows")) is not int
            or not 0<value["successful_new_windows"]<=MAX_NEW_WINDOWS
            or value.get("new_complete_analyzed_documents",0)<0
            or any(not re.fullmatch("[0-9a-f]{40}",value.get(k,""))
                   for k in ("private_ack_commit","checkpoint_commit"))
            or not re.fullmatch("[0-9a-f]{64}",value.get("sqlite_sha256",""))):
        raise ValueError("S4_EPOCH_ACK_HASH_OR_WINDOW_COUNT_INVALID")
    return value

def dispatch(previous):
    current_main()
    before=run_list()
    if any(x.get("status") not in ("completed",) for x in before):
        raise ValueError("S4_OTHER_EPOCH_CPU_RUN_IN_PROGRESS_DO_NOT_OVERLAP")
    old_ids={x["id"] for x in before}
    with tempfile.TemporaryDirectory(prefix="bct-s4-cpu-epoch-request-") as t:
        file=Path(t)/"request.json"
        file.write_bytes(json_bytes(
            {"ref":"main","inputs":{"purpose":"manual-research",
                                    "acquisition_run":str(ACQUISITION)}}))
        cmd(["gh","api","--method","POST",
             "repos/"+REPO+"/actions/workflows/"+WORKFLOW+"/dispatches",
             "--input",str(file)])
    deadline=time.monotonic()+75
    while time.monotonic()<deadline:
        new=[x for x in run_list()
             if x["id"] not in old_ids
             and x.get("head_branch")=="main"
             and x.get("head_sha")==MAIN_SHA]
        if len(new)>1:
            raise ValueError("S4_MULTIPLE_CONCURRENT_MANUAL_RUNS_AMBIGUOUS")
        if len(new)==1:
            verify_run_identity(new[0],new[0]["id"])
            return new[0]["id"]
        time.sleep(5)
    raise ValueError("S4_MANUAL_DISPATCH_ACCEPTED_BUT_ID_UNKNOWN_STOP")

def write(path,value):
    Path(path).write_bytes(json_bytes(value)+b"\n")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        raise ValueError("S4_PROGRESS_FILE_EXISTS")
    if os.environ.get("GITHUB_REPOSITORY")!=REPO or not os.environ.get("GH_TOKEN"):
        raise ValueError("S4_AUTHORIZED_ACTIONS_RUNNER_REQUIRED")
    current_main()
    data={"format":"bct-s4-epoch-bounded-cpu-progress-v1",
          "status":"STARTED_NO_NEW_BATCHES",
          "original_exact_documents":11,
          "original_total_cpu_windows":240,
          "already_verified_durable_window_count":83,
          "original_pending_cpu_windows_before_followon":EXPECTED_UNREAD,
          "previous_published_cpu_run":INITIAL_RUN,
          "previous_epoch_ack":INITIAL_ACK,
          "manual_cpu_sha":CPU_CODE_SHA,
          "max_followon_batches":MAX_BATCHES,
          "new_external_model_api_calls":0,
          "candidate_or_LIVE_promotions":0,
          "operations":[]}
    write(args.output,data)
    try:
        previous=INITIAL_ACK
        initial_row=api("actions/runs/"+str(INITIAL_RUN))
        verify_run_identity(initial_row,INITIAL_RUN)
        if initial_row.get("conclusion")!="success":
            raise ValueError("S4_INITIAL_SUCCESSFUL_EPOCH_RUN_NOT_VERIFIED")
        with tempfile.TemporaryDirectory(prefix="bct-s4-published-check-") as t:
            initial=proof(INITIAL_RUN,Path(t)/"initial")
            if initial["private_ack_commit"]!=INITIAL_ACK or initial["successful_new_windows"]!=24:
                raise ValueError("S4_INITIAL_DURABLE_ACK_CHANGED")
            for number in range(1,MAX_BATCHES+1):
                current_main()
                run_id=dispatch(previous)
                data["active_run_id"]=run_id
                data["status"]="RUNNING_SOURCE_BOUND_PRIVATE_CPU"
                write(args.output,data)
                await_run(run_id)
                item=proof(run_id,Path(t)/("batch-"+str(number)))
                if item["private_ack_commit"]==previous:
                    raise ValueError("S4_DID_NOT_ADVANCE_PRIVATE_EPOCH_ACK")
                previous=item["private_ack_commit"]
                data["operations"].append({
                    "batch":number,"run_id":run_id,
                    "new_successful_cpu_windows":item["successful_new_windows"],
                    "new_complete_analyzed_documents":item["new_complete_analyzed_documents"],
                    "epoch_ack":item["private_ack_commit"],
                    "sqlite_sha256":item["sqlite_sha256"],
                    "analysis_errors":0,
                    "remote_cas_restore_verified":True})
                data.pop("active_run_id",None)
                data["status"]="PASS_SERIAL_PRIVATE_EPOCH_BATCHES_SOURCE_COUNTS_PENDING_FINAL_RECHECK"
                write(args.output,data)
                print("S4_EPOCH_CAS_BATCH_PASS "+json.dumps({
                    "batch":number,"run_id":run_id,
                    "new_windows":item["successful_new_windows"],
                    "new_complete_analyzed_documents":item["new_complete_analyzed_documents"],
                    "private_cas_restore":"PASS"},sort_keys=True),flush=True)
            data["status"]="PASS_7_BOUNDED_PRIVATE_CPU_BATCHES_REQUIRES_EXACT_SOURCE_FINAL_RECHECK"
            data["total_new_successful_cpu_windows"]=sum(x["new_successful_cpu_windows"]
                                                            for x in data["operations"])
            data["final_epoch_ack"]=previous
            write(args.output,data)
    except Exception as exc:
        data["status"]="PARTIAL_SAFE_STOP_NO_UNVERIFIED_RETRY"
        data["stop_reason"]=type(exc).__name__+":"+str(exc)[:180]
        write(args.output,data)
        raise

if __name__=="__main__":
    main()
