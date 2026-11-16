#!/usr/bin/env python3
"""One-shot, bounded Session 4 CPU drain driven by already approved manual path.

Only source-free GitHub workflow metadata/public research receipts are examined
here. The V4 CPU workflow handles native sources and sealed private CAS state.
No unreviewed source bytes, decrypted state, AI calls or private credentials enter
this public orchestration runner. It stops on *any* inconclusive proof.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time

REPOSITORY = "irewon1-lgtm/bottleneck-control-tower"
WORKFLOW = "v4-cpu-private-research.yml"
PINNED_CPU_SHA = "1cf2b3aea3046c73f7d9a65c627b485f63c4a305"
SOURCE_RUN = 43645932280
SOURCE_HOLD_RUN = 43698475837
INITIAL_CPU_RUN = 43782542564
TOTAL_TARGET_WINDOWS = 240
MAX_BATCHES = 12
SECONDS_PER_RUN = 540
EXPECTED_MAIN_SHA = os.environ.get("EXPECTED_MAIN_SHA", "")
OUT = Path(os.environ.get("BCT_S4_PROGRESS_FILE", "session4-drain-progress.json"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode()


def call(args, *, timeout=55):
    process = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    if process.returncode != 0:
        raise ValueError("S4_EXTERNAL_GITHUB_VERIFICATION_OR_ACTION_FAILED")
    return process.stdout


def api_json(path):
    return json.loads(call(["gh", "api", "repos/" + REPOSITORY + "/" + path]))


def assert_main():
    current = api_json("git/ref/heads/main")["object"]["sha"]
    if current != EXPECTED_MAIN_SHA:
        raise ValueError("S4_MAIN_SHA_CHANGED_NO_NEW_WORK")
    return current


def download(run_id, name, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("S4_DOWNLOAD_DESTINATION_EXISTS")
    destination.mkdir(parents=True)
    call(["gh", "run", "download", str(run_id), "-R", REPOSITORY,
          "--name", name, "--dir", str(destination)], timeout=90)


def original_targets(tmp):
    where = tmp / "exact-source-holds"
    download(SOURCE_HOLD_RUN,
             "bct-session4-real-source-hold-" + str(SOURCE_HOLD_RUN), where)
    db_path = where / "session4.sqlite3"
    receipt = json.loads((where / "receipt.json").read_bytes())
    if (receipt.get("status") != "PASS_BACKFILL_HOLD_ONLY"
            or sha(db_path.read_bytes()) != receipt["ledger_sha256"]
            or receipt["source_verified_documents"] != 11
            or receipt["pending_cpu_windows_in_exact_documents"] != TOTAL_TARGET_WINDOWS):
        raise ValueError("S4_ORIGINAL_11_SOURCE_RECEIPT_UNTRUSTED")
    db = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("S4_ORIGINAL_HOLD_LEDGER_CORRUPTED")
        targets = []
        for case_id, payload_sha, raw in db.execute(
                "SELECT id,payload_sha256,payload FROM cases ORDER BY id"):
            if sha(raw.encode()) != payload_sha:
                raise ValueError("S4_HELD_CASE_CONTENT_CHANGED")
            case = json.loads(raw)
            if (case["case_id"] != case_id or case["decision"] != "HOLD"
                    or case["auto_promoted"] is not False):
                raise ValueError("S4_UNVERIFIED_OR_PROMOTED_HOLD")
            src = case["source"]
            targets.append(tuple(src[k] for k in
                                 ("document_id", "body_sha256", "raw_sha256")))
    finally:
        db.close()
    if len(targets) != 11 or len(set(targets)) != 11:
        raise ValueError("S4_EXACT_SOURCE_SET_NOT_11")
    return targets


def counts_from_public(run_id, targets, tmp, *, expected_code):
    dest = tmp / ("public-" + str(run_id))
    download(run_id, "bct-public-research-1", dest)
    raw = (dest / "snapshot.json").read_bytes()
    manifest = json.loads((dest / "manifest.json").read_bytes())
    snap = json.loads(raw)
    if (manifest.get("file_sha256") != sha(raw)
            or manifest.get("snapshot_sha256") != snap.get("snapshot_sha256")
            or sha(canonical({k:v for k,v in snap.items()
                             if k != "snapshot_sha256"})) != snap["snapshot_sha256"]
            or manifest.get("generation") != snap.get("generation")
            or manifest.get("transport_run_id") != run_id
            or snap.get("format") != "bct-public-research-1"):
        raise ValueError("S4_PUBLIC_SNAPSHOT_DIGEST_OR_PRODUCER_MISMATCH")
    gen = snap["generation"]
    proof = snap.get("proof", {})
    if (gen.get("producer_run_id") != run_id
            or gen.get("execution_sha") != expected_code
            or gen.get("workflow_sha") is None
            or proof.get("new_process_restore_verified") is not True
            or proof.get("remote_restore_verified") is not True):
        raise ValueError("S4_PRIVATE_CAS_AND_PUBLIC_PRODUCER_NOT_VERIFIED")
    if (snap.get("counts",{}).get("analysis_runtime_failures") != 0
            or snap.get("analysis",{}).get("status") == "ERROR_PROGRESS_PRESERVED"
            or snap.get("last_read_batch",{}).get("new_CPU_windows") !=
               snap.get("last_read_batch",{}).get("successful_new_CPU_windows")):
        raise ValueError("S4_CPU_OR_SEMANTIC_ANALYSIS_ERRORS_PRESERVED")
    trace = snap["trace"]
    if len({(x.get("document_id"),x.get("body_sha256"),x.get("raw_sha256"))
            for x in trace}) != len(trace):
        raise ValueError("S4_PUBLIC_TRACE_IDENTITY_DUPLICATE")
    index = {(x.get("document_id"), x.get("body_sha256"), x.get("raw_sha256")):x
             for x in trace}
    out = []
    for target in targets:
        match = index.get(target)
        if not match or match.get("source_verification") != "EXACT_NATIVE_AND_BODY_HASHES":
            raise ValueError("S4_TARGET_SOURCE_NOT_PROVABLE_IN_PUBLIC_TRACE")
        count = match["window_counts"]
        if (any(type(count.get(k)) is not int or count[k] < 0
                for k in ("total", "success", "failed", "unread"))
                or count["success"] + count["failed"] + count["unread"] != count["total"]):
            raise ValueError("S4_TARGET_WINDOW_COUNTS_INVALID")
        out.append({"document_id":target[0], "body_sha256":target[1],
                    "raw_sha256":target[2], "window_counts":count,
                    "read_state":match.get("read_state"),
                    "review_state":match.get("review_state"),
                    "reason_code":match.get("reason_code")})
    sums = {k:sum(row["window_counts"][k] for row in out)
            for k in ("total", "success", "failed", "unread")}
    if sums["total"] != TOTAL_TARGET_WINDOWS:
        raise ValueError("S4_SOURCE_COHORT_WINDOW_TOTAL_CHANGED")
    return {"run_id":run_id,"generation":gen,"counts":sums,
            "source_status":out,"new_cpu_windows":snap["last_read_batch"]["new_CPU_windows"],
            "new_cpu_documents":snap["last_read_batch"]["new_CPU_documents"],
            "new_read_batch_run":snap["last_read_batch"]["consumer_run_id"],
            "analysis_states":snap["analysis"]["states"],
            "trace_truncated":snap["analysis"]["trace_truncated"]}


def snapshots_match(old, new):
    if (old["counts"]["total"] != new["counts"]["total"]
            or new["counts"]["failed"] != 0):
        raise ValueError("S4_SOURCE_FAILED_OR_TOTAL_CHANGED")
    old_docs = {x["document_id"]:x for x in old["source_status"]}
    for row in new["source_status"]:
        before = old_docs.get(row["document_id"])
        if (not before or row["body_sha256"] != before["body_sha256"]
                or row["raw_sha256"] != before["raw_sha256"]
                or row["window_counts"]["total"] != before["window_counts"]["total"]
                or row["window_counts"]["success"] < before["window_counts"]["success"]
                or row["window_counts"]["unread"] > before["window_counts"]["unread"]
                or row["window_counts"]["failed"] != 0):
            raise ValueError("S4_SOURCE_PROGRESS_NOT_MONOTONIC")
    return (new["counts"]["success"] - old["counts"]["success"],
            old["counts"]["unread"] - new["counts"]["unread"])


def save(progress):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Never record original article body, quotes, private CPU outputs or tokens.
    OUT.write_bytes(canonical(progress) + b"\n")


def current_manual_ids():
    data = api_json("actions/workflows/" + WORKFLOW +
                    "/runs?event=workflow_dispatch&per_page=40")
    return {x["id"] for x in data.get("workflow_runs",[])}


def dispatch_one(before):
    with tempfile.TemporaryDirectory(prefix="bct-s4-dispatch-") as temporary:
        data = Path(temporary) / "input.json"
        data.write_bytes(canonical({"ref":"main","inputs":{
            "purpose":"manual-research","acquisition_run":str(SOURCE_RUN)}}))
        call(["gh","api","--method","POST",
              "repos/"+REPOSITORY+"/actions/workflows/"+WORKFLOW+"/dispatches",
              "--input",str(data)])
    deadline = time.monotonic() + 70
    while time.monotonic() < deadline:
        found = api_json("actions/workflows/" + WORKFLOW +
                         "/runs?event=workflow_dispatch&per_page=40").get("workflow_runs",[])
        matches = [x for x in found
                   if x["id"] not in before
                   and x.get("head_branch") == "main"
                   and x.get("head_sha") == EXPECTED_MAIN_SHA]
        if len(matches) > 1:
            raise ValueError("S4_AMBIGUOUS_CONCURRENT_MANUAL_CPU_RUN")
        if len(matches) == 1:
            return matches[0]["id"]
        time.sleep(5)
    raise ValueError("S4_DISPATCHED_RUN_ID_NOT_VERIFIED_DO_NOT_REDISPATCH")


def confirmed_run(run_id):
    deadline=time.monotonic()+SECONDS_PER_RUN
    while time.monotonic()<deadline:
        row=api_json("actions/runs/"+str(run_id))
        if (row.get("id")!=run_id or row.get("head_branch")!="main"
                or row.get("head_sha")!=EXPECTED_MAIN_SHA
                or row.get("event")!="workflow_dispatch"
                or row.get("path")!=".github/workflows/"+WORKFLOW):
            raise ValueError("S4_CPU_RUN_IDENTITY_MISMATCH")
        if row["status"]=="completed":
            if row["conclusion"] != "success":
                raise ValueError("S4_CPU_PRODUCER_OR_REMOTE_PUBLISH_NOT_SUCCESS")
            return
        time.sleep(8)
    raise ValueError("S4_BOUNDED_CPU_RUN_TIMEOUT_UNKNOWN_NO_RETRY")


def main():
    if not os.environ.get("GH_TOKEN") or not EXPECTED_MAIN_SHA:
        raise ValueError("S4_ACTIONS_TOKEN_OR_MAIN_SHA_NOT_PRESENT")
    progress={"format":"bct-session4-originals-bounded-drain-v1",
              "status":"STARTED_NOT_YET_COMPLETE",
              "main_sha":EXPECTED_MAIN_SHA,
              "pinned_cpu_sha":PINNED_CPU_SHA,
              "source_acquisition_run":SOURCE_RUN,
              "original_source_count":11,
              "target_total_windows":TOTAL_TARGET_WINDOWS,
              "max_batches":MAX_BATCHES,
              "new_external_paid_ai_api_calls":0,
              "production_source_writes":0,
              "automatic_candidate_promotions":0,
              "batches":[]}
    save(progress)
    try:
        assert_main()
        upstream=api_json("actions/runs/"+str(SOURCE_RUN))
        if (upstream.get("conclusion")!="success"
                or upstream.get("head_branch")!="main"
                or upstream.get("name")!="New precursor evidence acquisition"):
            raise ValueError("S4_ORIGINAL_SOURCE_ACQUISITION_NOT_SUCCESS")
        with tempfile.TemporaryDirectory(prefix="bct-s4-public-proof-") as tmpstr:
            temp=Path(tmpstr)
            originals=original_targets(temp)
            previous=counts_from_public(INITIAL_CPU_RUN,originals,temp,
                                        expected_code=PINNED_CPU_SHA)
            if previous["counts"]!={"total":240,"success":35,"failed":0,"unread":205}:
                raise ValueError("S4_BASELINE_CHANGED_NOT_SILENTLY_RELABELED")
            progress["initial"]={"run_id":INITIAL_CPU_RUN,"counts":previous["counts"]}
            progress["current"]={"run_id":INITIAL_CPU_RUN,"counts":previous["counts"],
                                 "source_status":previous["source_status"]}
            save(progress)
            for batch in range(1,MAX_BATCHES+1):
                if previous["counts"]["unread"]==0:
                    break
                assert_main()
                before=current_manual_ids()
                run_id=dispatch_one(before)
                progress["active_run_id"]=run_id
                progress["status"]="RUNNING_VERIFIED_MANUAL_CPU"
                save(progress)
                confirmed_run(run_id)
                current=counts_from_public(run_id,originals,temp,expected_code=PINNED_CPU_SHA)
                if (current["new_read_batch_run"]!=run_id
                        or not 0 < current["new_cpu_windows"]<=24):
                    raise ValueError("S4_ACTUAL_READ_BATCH_UNPROVEN")
                increase, drop=snapshots_match(previous,current)
                if increase<1 or increase>24 or drop!=increase:
                    raise ValueError("S4_NO_VERIFIED_24_WINDOW_PROGRESS_IN_EXACT_11_SOURCES")
                progress["batches"].append({
                    "batch":batch,"run_id":run_id,
                    "source_completed_delta":increase,
                    "source_pending_delta":-drop,
                    "total_run_new_cpu_windows":current["new_cpu_windows"],
                    "source_counts":current["counts"],
                    "source_review_states":{x["document_id"]:x["review_state"]
                                            for x in current["source_status"]}})
                progress["current"]={"run_id":run_id,
                                     "counts":current["counts"],
                                     "source_status":current["source_status"]}
                progress.pop("active_run_id",None)
                progress["status"]="PASS_BOUNDED_COHORT_PROGRESS" if current["counts"]["unread"] else "PASS_EXACT_11_ORIGINAL_CPU_WINDOWS_DRAINED"
                save(progress)
                print("BCT_S4_WINDOW_PROGRESS "+json.dumps({
                    "run_id":run_id,"batch":batch,
                    "exact_source_windows_read":current["counts"]["success"],
                    "exact_source_windows_unread":current["counts"]["unread"],
                    "new_verified_source_windows":increase,
                    "no_qualified_pair_or_s_stage_claim":True
                    },sort_keys=True),flush=True)
                previous=current
            if previous["counts"]["unread"]!=0:
                raise ValueError("S4_BATCH_LIMIT_REACHED_WITH_REMAINING_CPU_WINDOWS")
            progress["status"]="PASS_EXACT_11_ORIGINAL_CPU_WINDOWS_DRAINED"
            progress["complete_reading_is_not_qualified_supply_demand_pair"]=True
            save(progress)
            print("BCT_S4_CPU_SOURCE_COHORT_DRAIN_PASS",flush=True)
    except BaseException as exc:
        progress["status"]="PARTIAL_STOPPED_FAIL_CLOSED"
        progress["stop_reason"]=type(exc).__name__+":"+str(exc)[:180]
        save(progress)
        raise


if __name__=="__main__":
    main()
