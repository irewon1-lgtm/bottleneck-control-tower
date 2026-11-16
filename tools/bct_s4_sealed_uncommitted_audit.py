"""Read-only attestation of saved but unpublished Session 4 CPU work.

Only the existing reviewed V4 unseal command decrypts the packet. This code
receives an already authenticated checkpoint and reads it using SQLite in RO
mode. Writes a source-free receipt; never reads article bodies from the DB.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

EXPECTED_SUCCESS_RUN = 43782542564
EXPECTED_FAILED_RUN = 43783049883
EXPECTED_CPU_SHA = "1cf2b3aea3046c73f7d9a65c627b485f63c4a305"
TOTAL_WINDOWS = 240

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def encoded(data):
    return json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def targets(folder):
    folder=Path(folder)
    dbfile=folder/"session4.sqlite3"
    receipt=json.loads((folder/"receipt.json").read_bytes())
    if (receipt.get("status")!="PASS_BACKFILL_HOLD_ONLY"
            or receipt.get("source_verified_documents")!=11
            or receipt.get("pending_cpu_windows_in_exact_documents")!=TOTAL_WINDOWS
            or receipt.get("ledger_sha256")!=digest(dbfile.read_bytes())):
        raise ValueError("S4_HELD_LEDGER_NOT_AUTHENTICATED")
    db=sqlite3.connect(dbfile.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("S4_HELD_SQLITE_BAD")
        out=[]
        for (case_id,sha,payload) in db.execute(
                "SELECT id,payload_sha256,payload FROM cases ORDER BY id"):
            if digest(payload.encode())!=sha:
                raise ValueError("S4_HELD_PAYLOAD_HASH")
            data=json.loads(payload)
            if data["case_id"]!=case_id or data["decision"]!="HOLD" or data["auto_promoted"] is not False:
                raise ValueError("S4_HELD_CASE_STATUS")
            src=data["source"]
            out.append(tuple(src[name] for name in ("document_id","body_sha256","raw_sha256")))
        if len(out)!=11 or len(set(out))!=11:
            raise ValueError("S4_HELD_TARGETS_NOT_11")
        return out
    finally:
        db.close()

def last_ack(folder, targets):
    folder=Path(folder)
    raw=(folder/"snapshot.json").read_bytes()
    manifest=json.loads((folder/"manifest.json").read_bytes())
    doc=json.loads(raw)
    gen=doc["generation"]
    if (manifest["file_sha256"]!=digest(raw)
            or manifest["snapshot_sha256"]!=doc["snapshot_sha256"]
            or digest(encoded({k:v for k,v in doc.items() if k!="snapshot_sha256"}))!=doc["snapshot_sha256"]
            or manifest["generation"]!=gen or manifest["transport_run_id"]!=EXPECTED_SUCCESS_RUN
            or gen["producer_run_id"]!=EXPECTED_SUCCESS_RUN or gen["execution_sha"]!=EXPECTED_CPU_SHA
            or doc["proof"]["remote_restore_verified"] is not True
            or doc["proof"]["new_process_restore_verified"] is not True):
        raise ValueError("S4_LAST_ACK_UNVERIFIED")
    lookup={(x["document_id"],x["body_sha256"],x["raw_sha256"]):x for x in doc["trace"]}
    if len(lookup)!=len(doc["trace"]):
        raise ValueError("S4_PRIOR_SOURCE_IDENTITY_DUPLICATE")
    before={}
    for key in targets:
        row=lookup.get(key)
        if not row or row["source_verification"]!="EXACT_NATIVE_AND_BODY_HASHES":
            raise ValueError("S4_PRIOR_SOURCE_NO_HASH_PROOF")
        before[key]=row["window_counts"]
    if {k:sum(v[k] for v in before.values()) for k in ("total","success","failed","unread")} != {
        "total":240,"success":35,"failed":0,"unread":205}:
        raise ValueError("S4_35_WINDOW_PERSISTED_BASELINE_MISMATCH")
    return gen,before

def sealed_checkpoint(folder):
    folder=Path(folder)
    proof=json.loads((folder/"checkpoint.json").read_bytes())
    archive=folder/"checkpoint.sqlite3.gz"
    if (proof.get("archive")!=archive.name
            or digest(archive.read_bytes())!=proof["archive_sha256"]):
        raise ValueError("S4_UNPUBLISHED_ARCHIVE_HASH_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="s4-ro-sqlite-") as t:
        path=Path(t)/"sqlite3"
        size=0
        with gzip.open(archive,"rb") as stream,path.open("xb") as out:
            while True:
                chunk=stream.read(1024*1024)
                if not chunk:
                    break
                size+=len(chunk)
                if size>128*1024*1024:
                    raise ValueError("S4_UNPUBLISHED_SQLITE_BUDGET")
                out.write(chunk)
        if digest(path.read_bytes())!=proof["sqlite_sha256"]:
            raise ValueError("S4_UNPUBLISHED_DB_HASH_MISMATCH")
        db=sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)
        try:
            if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("S4_UNPUBLISHED_DB_INTEGRITY")
            latest={};done=set();failed=set()
            for kind,raw in db.execute("SELECT kind,payload FROM events WHERE kind IN "
                                       "('CPU_RESUME_SOURCE','CPU_RESUME_WINDOW','CPU_RESUME_FAILURE') ORDER BY seq"):
                item=json.loads(raw)
                if kind=="CPU_RESUME_SOURCE":
                    latest[item["body_key"]]=item
                elif kind=="CPU_RESUME_WINDOW":
                    done.add(item["key"])
                else:
                    failed.add(item["key"])
            return proof,latest,done,failed
        finally:
            db.close()

def inspect(held_folder,prior_folder,sealed_folder):
    selected=targets(held_folder)
    prior,before=last_ack(prior_folder,selected)
    sealed_folder=Path(sealed_folder)
    parent=json.loads((sealed_folder/"parent.json").read_bytes())
    if parent.get("producer_job")!="publish":
        raise ValueError("S4_UNPUBLISHED_PARENT_JOB_NOT_PUBLISHER")
    if str(parent.get("producer_run_id"))!=str(EXPECTED_SUCCESS_RUN):
        raise ValueError("S4_UNPUBLISHED_PARENT_PRODUCER_RUN_MISMATCH")
    if str(parent.get("producer_attempt"))!=str(prior["producer_attempt"]):
        raise ValueError("S4_UNPUBLISHED_PARENT_PRODUCER_ATTEMPT_MISMATCH")
    if parent.get("expected_parent")!=prior["private_commit"]:
        raise ValueError("S4_UNPUBLISHED_PARENT_COMMIT_MISMATCH")
    proof,sources,done,failed=sealed_checkpoint(sealed_folder)
    if done & failed:
        raise ValueError("S4_CONFLICTING_WINDOW_RECEIPT")
    lookup={}
    for row in sources.values():
        k=(row.get("document_id"),row.get("body_sha256"),row.get("raw_sha256"))
        if k in lookup:
            raise ValueError("S4_DUPLICATE_UNPUBLISHED_SOURCE_VERSION")
        lookup[k]=row
    rows=[]
    for identity in selected:
        row=lookup.get(identity)
        if row is None:
            raise ValueError("S4_SOURCE_MISSING_FROM_SAVED_SEALED_CHECKPOINT")
        keys=[item["key"] for item in row["tasks"]]
        if len(keys)!=len(set(keys)) or len(keys)!=before[identity]["total"]:
            raise ValueError("S4_UNPUBLISHED_TASK_KEYS_CHANGED")
        success=sum(k in done for k in keys)
        failures=sum(k in failed for k in keys)
        if (failures!=0 or success<before[identity]["success"]
                or success>len(keys)):
            raise ValueError("S4_UNPUBLISHED_PROGRESS_REGRESSION_OR_FAIL")
        rows.append({"document_id":identity[0],"body_sha256":identity[1],
                     "raw_sha256":identity[2],
                     "total":len(keys),"prior_success":before[identity]["success"],
                     "sealed_success":success,"sealed_pending":len(keys)-success,
                     "unpublished_added":success-before[identity]["success"]})
    sums={k:sum(x[k] for x in rows) for k in
          ("total","prior_success","sealed_success","sealed_pending","unpublished_added")}
    if (sums["total"]!=240 or sums["prior_success"]!=35
            or sums["sealed_success"]+sums["sealed_pending"]!=240
            or not 0<sums["unpublished_added"]<=24):
        raise ValueError("S4_SAVED_UNPUBLISHED_WINDOW_COUNTS_INVALID")
    return {"format":"bct-s4-authenticated-unpublished-cpu-v1",
            "status":"SEALED_VERIFIED_UNPUBLISHED_DO_NOT_COUNT_AS_DURABLE",
            "last_durable_run":EXPECTED_SUCCESS_RUN,
            "unpublished_run":EXPECTED_FAILED_RUN,
            "last_durable_private_commit":prior["private_commit"],
            "authenticated_sealed_sqlite_sha256":proof["sqlite_sha256"],
            "target_original_sources":11,"counts":sums,"per_source":rows,
            "new_model_calls":0,"private_ref_writes":0,
            "durable_promotion":False,"requires_reviewed_storage_migration":True}

def main():
    parser=argparse.ArgumentParser()
    for key in ("targets","prior_public","sealed","output"):
        parser.add_argument("--"+key.replace("_","-"),type=Path,required=True)
    opts=parser.parse_args()
    if opts.output.exists():
        raise ValueError("S4_RECEIPT_OUTPUT_EXISTS")
    result=inspect(opts.targets,opts.prior_public,opts.sealed)
    opts.output.write_bytes(encoded(result)+b"\n")
    print("BCT_S4_UNPUBLISHED_SEALED_READBACK="+json.dumps({
        "status":result["status"],"counts":result["counts"],
        "new_model_calls":0,"private_ref_writes":0},sort_keys=True))

if __name__=="__main__":
    main()
