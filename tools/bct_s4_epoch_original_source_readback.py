"""Exact original-source CPU cohort readback from the *new* private epoch.

No model loading, no private Git ref writes. Input source set comes only from
the separately attested immutable Session 4 original HOLD ledger.
Never print or export article text, raw model output, credentials or source HTML.
"""
import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

REPO="irewon1-lgtm/bct-v4-private-state"
PRIVATE_URL="https://github.com/"+REPO+".git"
EPOCH="refs/heads/codex/bct-v4-cpu-research-epoch-20261116"
OLD="refs/heads/codex/bct-v4-cpu-research-state"
ARCHIVE="refs/heads/archive/bct-v4-cpu-pre-64m-20261116"
OLD_SHA="8493ce906aea1c4ef14693873ba016e708d30245"
ROOT_SHA="1fd5c95a7cafdd5b1fd7d87acf07f07950f3f1e2"
INITIAL_EPOCH_ACK="9dd255c99d382c4bd3b366474e30ed1e7cb2d1bf"
SOURCE_TOTAL=240


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def source_set(path):
    path=Path(path)
    dbfile=path/"session4.sqlite3"
    receipt=json.loads((path/"receipt.json").read_bytes())
    if (receipt.get("status")!="PASS_BACKFILL_HOLD_ONLY"
            or receipt.get("source_verified_documents")!=11
            or receipt.get("pending_cpu_windows_in_exact_documents")!=SOURCE_TOTAL
            or digest(dbfile.read_bytes())!=receipt.get("ledger_sha256")):
        raise ValueError("S4_ORIGINAL_HOLD_INTEGRITY_FAILED")
    db=sqlite3.connect(dbfile.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        out=[]
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("S4_ORIGINAL_HELD_SQLITE_FAILED")
        for case_id,sha,payload in db.execute(
                "SELECT id,payload_sha256,payload FROM cases ORDER BY id"):
            if digest(payload.encode())!=sha:
                raise ValueError("S4_ORIGINAL_CASE_HASH_FAILED")
            row=json.loads(payload)
            if row.get("case_id")!=case_id or row.get("decision")!="HOLD":
                raise ValueError("S4_ORIGINAL_NOT_HELD")
            source=row["source"]
            out.append(tuple(source[k] for k in
                             ("document_id","body_sha256","raw_sha256")))
    finally:
        db.close()
    if len(out)!=11 or len(set(out))!=11:
        raise ValueError("S4_ORIGINAL_COHORT_NOT_ELEVEN")
    return out


def verified_final_progress(path):
    p=json.loads(Path(path).read_bytes())
    if (p.get("format")!="bct-s4-epoch-bounded-cpu-progress-v1"
            or p.get("status")!="PASS_7_BOUNDED_PRIVATE_CPU_BATCHES_REQUIRES_EXACT_SOURCE_FINAL_RECHECK"
            or p.get("max_followon_batches")!=7
            or p.get("original_total_cpu_windows")!=SOURCE_TOTAL
            or p.get("original_exact_documents")!=11
            or p.get("already_verified_durable_window_count")!=83
            or p.get("manual_cpu_sha")!="aca2ccf56032c7841188997e857828142dadcb0a"
            or p.get("candidate_or_LIVE_promotions")!=0
            or p.get("new_external_model_api_calls")!=0
            or len(p.get("operations",[]))!=7
            or p.get("final_epoch_ack")!=p["operations"][-1]["epoch_ack"]):
        raise ValueError("S4_COHORT_FINAL_PROGRESS_NOT_ATTESTED")
    if any(x.get("batch")!=i+1
           or x.get("analysis_errors")!=0
           or x.get("remote_cas_restore_verified") is not True
           or type(x.get("new_successful_cpu_windows")) is not int
           or not 0<x["new_successful_cpu_windows"]<=24
           for i,x in enumerate(p["operations"])):
        raise ValueError("S4_BATCH_PROGRESS_NOT_MONOTONIC_PROVEN")
    if sum(x["new_successful_cpu_windows"] for x in p["operations"])!=p.get("total_new_successful_cpu_windows"):
        raise ValueError("S4_CPU_BATCH_AGGREGATE_NOT_PROVEN")
    if not re.fullmatch("[a-f0-9]{40}",p["final_epoch_ack"]):
        raise ValueError("S4_FINAL_EPOCH_ACK_UNVERIFIED")
    return p


def snapshot_commit(repo, expected_ack, dest):
    token=os.environ.get("BCT_V4_PRIVATE_STATE_TOKEN") or ""
    if not re.fullmatch("[A-Za-z0-9_-]{20,512}",token):
        raise ValueError("S4_READONLY_PRIVATE_TOKEN_MISSING")
    auth=base64.b64encode(("x-access-token:"+token).encode()).decode()
    env={**os.environ,"GIT_CONFIG_COUNT":"2",
         "GIT_CONFIG_KEY_0":"http.https://github.com/.extraheader",
         "GIT_CONFIG_VALUE_0":"AUTHORIZATION: basic "+auth,
         "GIT_CONFIG_KEY_1":"credential.helper",
         "GIT_CONFIG_VALUE_1":"","GIT_TERMINAL_PROMPT":"0"}
    repo=Path(repo)
    repo.mkdir()
    def git(*args):
        result=subprocess.run(["git","-C",str(repo),*args],
                              env=env,capture_output=True,timeout=75)
        if result.returncode:
            raise ValueError("S4_PRIVATE_GIT_READ_OR_AUTH_FAILED")
        return result.stdout
    git("init","-q")
    git("remote","add","origin",PRIVATE_URL)
    raw=git("ls-remote","origin",EPOCH,OLD,ARCHIVE).decode()
    loc={p[1]:p[0] for line in raw.splitlines() if len(p:=(line.split()))==2}
    if loc!={EPOCH:expected_ack,OLD:OLD_SHA,ARCHIVE:OLD_SHA}:
        raise ValueError("S4_LIVE_EPOCH_OR_HISTORY_ARCHIVE_REF_CHANGED")
    git("fetch","--no-tags","origin","+"+EPOCH+":refs/remotes/origin/s4-epoch")
    if git("rev-parse","refs/remotes/origin/s4-epoch").decode().strip()!=expected_ack:
        raise ValueError("S4_EPOCH_HEAD_NOT_EXACT_EXPECTED_ACK")
    roots=git("rev-list","--max-parents=0",expected_ack).decode().splitlines()
    if roots!=[ROOT_SHA]:
        raise ValueError("S4_EPOCH_MUST_HAVE_INDEPENDENT_ROOT")
    parent=git("rev-list","--parents","-n","1",expected_ack).decode().split()
    if len(parent)!=2 or parent[0]!=expected_ack:
        raise ValueError("S4_EPOCH_ACK_PARENT_INVALID")
    receipt=json.loads(git("show",expected_ack+":private-persistence.json"))
    if (receipt.get("checkpoint_commit")!=parent[1]
            or receipt.get("version")!="bct-private-persistence-1"
            or receipt.get("API_calls")!=0
            or receipt.get("LIVE_registration") is not False):
        raise ValueError("S4_PRIVATE_RECEIPT_INTEGRITY_FAILED")
    for name in ("checkpoint.json","checkpoint.sqlite3.gz"):
        (dest/name).write_bytes(git("show",expected_ack+":"+name))
    link=json.loads(git("show",expected_ack+":epoch-link.json"))
    if (link.get("old_ack_commit")!=OLD_SHA or link.get("old_lineage_root")!=
            "6f1914c532e9ed411af75e82192e1386c01e3c1b"
            or link.get("new_epoch_ref")!=EPOCH):
        raise ValueError("S4_EPOCH_ARCHIVED_LINK_INVALID")
    return receipt,expected_ack


def count_exact(ledger, identities):
    events=ledger.db.execute("SELECT kind,payload FROM events WHERE kind IN "
        "('CPU_RESUME_SOURCE','CPU_RESUME_WINDOW','CPU_RESUME_FAILURE',"
        "'CPU_ANALYSIS_RESULT','CPU_ANALYSIS_FAILURE') ORDER BY seq")
    source_by_body={}
    success=set()
    failure=set()
    analysis={}
    for kind,payload in events:
        row=json.loads(payload)
        if kind=="CPU_RESUME_SOURCE":
            # Rehydration may append the same byte-identical source receipt
            # during later manual batches. Keep the latest by immutable body key;
            # never claim two different exact source versions are interchangeable.
            body_key=row.get("body_key")
            if not isinstance(body_key,str) or not body_key:
                raise ValueError("S4_EPOCH_SOURCE_BODY_KEY_MISSING")
            prior=source_by_body.get(body_key)
            if prior is not None and any(prior.get(k)!=row.get(k)
               for k in ("document_id","body_sha256","raw_sha256")):
                raise ValueError("S4_EPOCH_SOURCE_VERSION_COLLISION")
            source_by_body[body_key]=row
        elif kind=="CPU_RESUME_WINDOW":
            success.add(row["key"])
        elif kind=="CPU_RESUME_FAILURE":
            failure.add(row["key"])
        elif kind in ("CPU_ANALYSIS_RESULT","CPU_ANALYSIS_FAILURE"):
            analysis[(row.get("document_id"),row.get("body_sha256"))]={"kind":kind,
                "raw_sha256":row.get("raw_sha256"),
                "read_state":row.get("read_state"),
                "review_state":row.get("review_state"),
                "source_validation":row.get("source_validation"),
                "target_review_performed":row.get("target_review_performed"),
                "reason_code":row.get("reason_code"),
                "source_bound_event_count":row.get("source_bound_event_count"),
                "graph_independent_pair_count":row.get("graph_independent_pair_count"),
                "strict_pair_count":row.get("strict_pair_count"),
                "strict_forecast_candidate_count":row.get("strict_forecast_candidate_count"),
                "LIVE_writes":row.get("LIVE_writes")}
    if success&failure:
        raise ValueError("S4_EPOCH_WINDOW_SUCCESS_FAILURE_COLLISION")
    sources={}
    for row in source_by_body.values():
        key=(row.get("document_id"),row.get("body_sha256"),row.get("raw_sha256"))
        if key in sources:
            raise ValueError("S4_EPOCH_SAME_ID_ACROSS_DISTINCT_BODY_KEYS")
        sources[key]=row
    data=[]
    for ident in identities:
        source=sources.get(ident)
        if source is None:
            raise ValueError("S4_EPOCH_ORIGINAL_SOURCE_VERSION_MISSING")
        keys=[x.get("key") for x in source.get("tasks",[])]
        if not keys or len(set(keys))!=len(keys):
            raise ValueError("S4_EPOCH_SOURCE_WINDOW_KEYS_INVALID")
        done=sum(x in success for x in keys)
        bad=sum(x in failure for x in keys)
        state=analysis.get((ident[0],ident[1]),{})
        if state.get("raw_sha256")!=ident[2]:
            raise ValueError("S4_SEMANTIC_RESULT_ORIGINAL_RAW_VERSION_MISMATCH")
        data.append({"document_id":ident[0],"body_sha256":ident[1],
                     "raw_sha256":ident[2],"total":len(keys),
                     "success":done,"failed":bad,
                     "unread":len(keys)-done-bad,
                     "read_state":state.get("read_state"),
                     "review_state":state.get("review_state"),
                     "meaning_analysis_failed":state.get("kind")=="CPU_ANALYSIS_FAILURE",
                     "source_validation":state.get("source_validation"),
                     "target_review_performed":state.get("target_review_performed"),
                     "reason_code":state.get("reason_code"),
                     "source_bound_event_count":state.get("source_bound_event_count"),
                     "graph_independent_pair_count":state.get("graph_independent_pair_count"),
                     "strict_independent_pair_count":state.get("strict_pair_count"),
                     "strict_forecast_candidate_count":state.get("strict_forecast_candidate_count"),
                     "LIVE_writes":state.get("LIVE_writes")})
    sums={key:sum(row[key] for row in data)
          for key in ("total","success","failed","unread")}
    if sums["total"]!=SOURCE_TOTAL or sums["success"]+sums["failed"]+sums["unread"]!=SOURCE_TOTAL:
        raise ValueError("S4_COHORT_COUNTS_NOT_CONSISTENT")
    return sums,data


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--held",type=Path,required=True)
    parser.add_argument("--progress",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        raise ValueError("S4_READBACK_OUTPUT_ALREADY_EXISTS")
    progress=verified_final_progress(args.progress)
    identities=source_set(args.held)
    from bct.v4 import cpu_operations as op, cpu_resume as resume
    with tempfile.TemporaryDirectory(prefix="bct-s4-epoch-source-readback-") as temp:
        base=Path(temp)
        checkpoint=base/"checkpoint";checkpoint.mkdir()
        ack,commit=snapshot_commit(base/"private",progress["final_epoch_ack"],checkpoint)
        restored=op.restore(checkpoint,base/"database")
        if (restored.get("restored") is not True
                or restored.get("tables")!=8
                or restored["sqlite_sha256"]!=ack["sqlite_sha256"]):
            raise ValueError("S4_CHECKPOINT_REMOTE_DB_EIGHT_TABLES_NOT_VERIFIED")
        ledger=resume.Ledger(base/"database")
        try:
            resume.audit(ledger)
            count,data=count_exact(ledger,identities)
            if ledger.db.execute("SELECT COUNT(*) FROM firsts").fetchone()[0]:
                raise ValueError("S4_RESEARCH_MUST_NOT_PROMOTE_TO_LIVE")
        finally:
            ledger.close()
    # Full CPU coverage is not enough: each original must also have a real
    # exact-source semantic review, not an absent/unknown result counted as zero.
    if any(
        row["read_state"]!="READ_COMPLETE"
        or row["review_state"] not in
           ("READ_EVIDENCE_HOLD","NO_VALIDATED_EVENT","RESEARCH_FORECAST_REVIEW")
        or row["source_validation"]!="EXACT_NATIVE_AND_BODY_HASHES"
        or row["target_review_performed"] is not True
        or row["meaning_analysis_failed"]
        or type(row["strict_independent_pair_count"]) is not int
        or type(row["graph_independent_pair_count"]) is not int
        or type(row["strict_forecast_candidate_count"]) is not int
        or type(row["source_bound_event_count"]) is not int
        or row["LIVE_writes"]!=0
        for row in data
    ):
        raise ValueError("S4_EXACT_SOURCE_SEMANTIC_REVIEW_NOT_FULLY_VERIFIED")
    review={
        "exact_source_semantic_reviews":len(data),
        "original_exact_body_validation":len(data),
        "read_evidence_hold":sum(x["review_state"]=="READ_EVIDENCE_HOLD" for x in data),
        "no_validated_event":sum(x["review_state"]=="NO_VALIDATED_EVENT" for x in data),
        "research_forecast_review":sum(x["review_state"]=="RESEARCH_FORECAST_REVIEW" for x in data),
        "source_bound_events":sum(x["source_bound_event_count"] for x in data),
        "graph_independent_pair_count":sum(x["graph_independent_pair_count"] for x in data),
        "strict_independent_pair_count":sum(x["strict_independent_pair_count"] for x in data),
        "strict_forecast_candidate_count":sum(x["strict_forecast_candidate_count"] for x in data),
        "semantic_review_failures":0,
        "automatic_LIVE_promotions":0,
        "public_dashboard_published":False,
    }
    receipt={"format":"bct-s4-final-11-source-cpu-readback-v1",
             "status":"PASS_SOURCE_BOUND_CPU_READBACK" if count["unread"]==count["failed"]==0
                 else "PARTIAL_SOURCE_BOUND_CPU_READBACK",
             "exact_original_sources":11,"counts":count,
             "source_versions":data,
             "semantic_review":review,
             "research_dashboard_readonly":{
                 "scope":"ORIGINAL_EXACT_11_SOURCES_ONLY",
                 "mode":"RESEARCH_ONLY_NOT_PUBLIC_DASHBOARD",
                 "read_complete":11,
                 "held":review["read_evidence_hold"],
                 "strict_independent_qualified_pairs":review["strict_independent_pair_count"],
                 "auto_registered_candidates":0,
                 "LIVE_publication":False},
             "new_epoch_private_ack":commit,
             "new_epoch_sqlite_sha256":ack["sqlite_sha256"],
             "previous_private_state_ref_untouched":True,
             "old_archive_ref_untouched":True,
             "eight_table_remote_restore":True,
             "new_model_calls":0,"private_ref_writes":0,
             "automatic_qualified_supply_demand_adoption":False,
             "forecast_accuracy":"UNVERIFIED"}
    args.out.write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("S4_FINAL_SOURCE_CPU_READBACK="+json.dumps({
        "status":receipt["status"],"sources":11,"counts":count,
        "model_calls":0,"remote_restore":True,
        "semantic_reviews":review["exact_source_semantic_reviews"],
        "evidence_hold":review["read_evidence_hold"],
        "strict_pairs":review["strict_independent_pair_count"]},sort_keys=True))

if __name__=="__main__":
    main()
