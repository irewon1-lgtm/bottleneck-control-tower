"""BCT S4 storage epoch: append-only old history, new root, authenticated recovery.

This is an explicit, one-time, manual migration tool. No CPU inference, old
ref movement, Github Actions schedule activation, deletion, or public original
source export. Source-free public proof is preview-only until read-only dashboard
lineage integration has independent CI.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

OLD_ACK = "8493ce906aea1c4ef14693873ba016e708d30245"
OLD_CHECKPOINT = "0061e9549985f59f79aeb91a1e05cfaaf5a4ea1c"
OLD_SQLITE = "27380e9ecaa807cc0de993d12acbc9bb155177f0ce035b5d13d77d2111ff79d0"
OLD_ROOT = "6f1914c532e9ed411af75e82192e1386c01e3c1b"
OLD_ACK_SEQUENCE = 68
NEW_DB = "b330cdf20ebfe479bedcbe929dfbfe65b2df48639d04dfdfa7d6250082f9a572"
ORIGINAL_CPU_CODE_SHA = "1cf2b3aea3046c73f7d9a65c627b485f63c4a305"
SOURCE_RUN = 43783049883
LAST_ACK_RUN = 43782542564
PRIVATE_REPO = "irewon1-lgtm/bct-v4-private-state"
PRIVATE_URL = "https://github.com/" + PRIVATE_REPO + ".git"
OLD_REF = "refs/heads/codex/bct-v4-cpu-research-state"
ARCHIVE_REF = "refs/heads/archive/bct-v4-cpu-pre-64m-20261116"
EPOCH_REF = "refs/heads/codex/bct-v4-cpu-research-epoch-20261116"
CAP = 64 * 1024 * 1024
FORMAT = "bct-v4-cpu-private-epoch-link-v1"

def encoded(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(value).hexdigest()

def secure_source_free_preflight(preflight, sealed):
    # The TWO independent existing proofs were produced by read-only workflows.
    expected = {"format":"bct-s4-safe-private-storage-epoch-preflight-v1",
                "status":"PASS_READONLY_GATES_FOR_REVIEWED_STORAGE_EPOCH_DESIGN",
                "anchored_previous_ack":OLD_ACK,
                "private_history_cap_bytes":CAP,
                "durably_persisted_windows":35,
                "authenticated_unpublished_windows":24,
                "verified_read_windows":59,
                "verified_unread_windows":181,
                "sealed_unpublished_sqlite_sha256":NEW_DB,
                "automatic_S1_S2_S3_or_LIVE_promotions":0,
                "new_remote_ref_writes":0}
    if any(preflight.get(k) != v for k,v in expected.items()):
        raise ValueError("EPOCH_SOURCE_FREE_PREFLIGHT_NOT_VERIFIED")
    supplied=preflight.get("plan_sha256")
    if supplied != digest(encoded({k:v for k,v in preflight.items() if k!="plan_sha256"})):
        raise ValueError("EPOCH_PREFLIGHT_DIGEST_MISMATCH")
    if (preflight.get("private_archived_ref") != ARCHIVE_REF
            or preflight.get("private_old_ref")!=OLD_REF
            or preflight.get("additional_bounded_CPU_batches_required")!=8):
        raise ValueError("EPOCH_ARCHIVE_OR_CPU_SCOPE_UNVERIFIED")
    proof = {"status":"SEALED_VERIFIED_UNPUBLISHED_DO_NOT_COUNT_AS_DURABLE",
             "authenticated_sealed_sqlite_sha256": NEW_DB,
             "last_durable_private_commit":OLD_ACK,
             "last_durable_run":LAST_ACK_RUN,
             "unpublished_run":SOURCE_RUN,
             "target_original_sources":11,"durable_promotion":False,
             "private_ref_writes":0,"new_model_calls":0}
    if any(sealed.get(k) != v for k,v in proof.items()):
        raise ValueError("EPOCH_SEALED_SOURCE_RECEIPT_UNVERIFIED")
    if sealed.get("counts") != {"total":240,"prior_success":35,
                                 "sealed_success":59,"sealed_pending":181,
                                 "unpublished_added":24}:
        raise ValueError("EPOCH_WINDOW_COUNTS_INCONSISTENT")
    if len(sealed.get("per_source",[]))!=11:
        raise ValueError("EPOCH_SOURCE_COUNT_MISMATCH")
    return True

def verify_checkpoint(checkpoint, sealed, *, restore=None, resume=None):
    checkpoint = Path(checkpoint)
    parent = json.loads((checkpoint/"parent.json").read_bytes())
    if (parent.get("producer_job")!="research"
            or str(parent.get("producer_run_id"))!=str(SOURCE_RUN)
            or str(parent.get("producer_attempt"))!="1"
            or parent.get("expected_parent")!=OLD_ACK):
        raise ValueError("EPOCH_SEALED_PRODUCER_OR_PRIOR_ACK_NOT_VERIFIED")
    proof=json.loads((checkpoint/"checkpoint.json").read_bytes())
    archive=checkpoint/"checkpoint.sqlite3.gz"
    if (proof.get("archive")!=archive.name
            or digest(archive.read_bytes())!=proof.get("archive_sha256")
            or proof.get("sqlite_sha256")!=NEW_DB
            or sealed.get("authenticated_sealed_sqlite_sha256")!=NEW_DB
            or archive.stat().st_size>16*1024**2):
        raise ValueError("EPOCH_SEALED_CHECKPOINT_HASH_OR_SIZE_INVALID")
    if restore is not None:
        with tempfile.TemporaryDirectory(prefix="bct-epoch-check-") as t:
            result=restore(checkpoint,Path(t)/"restored")
            if result.get("tables")!=8 or result.get("sqlite_sha256")!=NEW_DB:
                raise ValueError("EPOCH_SEALED_DB_EIGHT_TABLE_RESTORE_FAILED")
            dbpath=Path(t)/"restored/v4.sqlite3"
            if resume is not None:
                ledger=resume.Ledger(Path(t)/"restored")
                try: resume.audit(ledger)
                finally: ledger.close()
            with sqlite3.connect(dbpath.resolve().as_uri()+"?mode=ro",uri=True) as db:
                if (db.execute("PRAGMA integrity_check").fetchone()[0]!="ok"
                        or db.execute("SELECT count(*) FROM firsts").fetchone()[0]!=0
                        or any(db.execute("SELECT count(*) FROM "+n).fetchone()[0]!=0
                               for n in ("blobs","documents","captures","readings","runs"))):
                    raise ValueError("EPOCH_NO_SOURCE_SEPARATION_OR_SQLITE_INTEGRITY")
    return proof

def link(preflight, previous_public):
    gen=previous_public["generation"]
    if (gen.get("private_commit")!=OLD_ACK
            or gen.get("checkpoint_commit")!=OLD_CHECKPOINT
            or gen.get("sqlite_sha256")!=OLD_SQLITE
            or gen.get("lineage_root")!=OLD_ROOT
            or gen.get("ack_sequence")!=OLD_ACK_SEQUENCE
            or gen.get("producer_run_id")!=LAST_ACK_RUN):
        raise ValueError("EPOCH_OLD_PUBLIC_ACK_LINEAGE_MISMATCH")
    return {"format":FORMAT,
            "legacy_repository":PRIVATE_REPO,
            "old_cpu_ref":OLD_REF,
            "immutable_archive_ref":ARCHIVE_REF,
            "old_ack_commit":OLD_ACK,
            "old_checkpoint_commit":OLD_CHECKPOINT,
            "old_sqlite_sha256":OLD_SQLITE,
            "old_lineage_root":OLD_ROOT,
            "old_ack_sequence":OLD_ACK_SEQUENCE,
            "new_epoch_ref":EPOCH_REF,
            "seed_sqlite_sha256":NEW_DB,
            "seed_producer_run_id":SOURCE_RUN,
            "original_cohort_documents":11,
            "original_cohort_success_windows":59,
            "original_cohort_unread_windows":181,
            "source_free_preflight_digest":preflight["plan_sha256"],
            "new_model_inference_count":0,
            "old_ref_modified":False,
            "new_epoch_independent_root_required":True,
            "public_schedule_activated":False}

def validate_public_previous(snapshot, manifest):
    if (manifest.get("format")!="bct-public-research-artifact-1"
            or manifest.get("file_sha256")!=digest(encoded(snapshot)+b"\n")
            or manifest.get("generation")!=snapshot.get("generation")
            or manifest.get("snapshot_sha256")!=snapshot.get("snapshot_sha256")
            or digest(encoded({k:v for k,v in snapshot.items() if k!="snapshot_sha256"}))!=snapshot["snapshot_sha256"]):
        raise ValueError("EPOCH_PREVIOUS_SNAPSHOT_MANIFEST_INVALID")

def history_measure(git, new_ack):
    objects=git("rev-list","--objects",new_ack)
    ids=[line.split()[0] for line in objects.splitlines()]
    if len(ids)!=len(set(ids)) or not ids:
        raise ValueError("EPOCH_PRIVATE_GIT_HISTORY_NOT_UNIQUE")
    measures=git("cat-file","--batch-check=%(objectname) %(objecttype) %(objectsize)",
                 stdin="\n".join(ids)+"\n")
    sizes=[int(line.split()[2]) for line in measures.splitlines()]
    if len(sizes)!=len(ids) or not 0<sum(sizes)<CAP:
        raise ValueError("EPOCH_INDEPENDENT_HISTORY_CAP_EXCEEDED")
    return sum(sizes)

def publish_epoch(checkpoint, preflight, previous, token, *, run_id, workflow_sha,
                  output_root, public_research, op, resume):
    if (not re.fullmatch(r"[A-Za-z0-9_-]{20,512}",token or "")
            or not re.fullmatch("[a-f0-9]{40}",workflow_sha)
            or type(run_id) is not int or run_id<=SOURCE_RUN):
        raise ValueError("EPOCH_AUTHORIZED_RUN_OR_TOKEN_MISSING")
    if (os.environ.get("GITHUB_REPOSITORY")!="irewon1-lgtm/bottleneck-control-tower"
            or os.environ.get("GITHUB_EVENT_NAME")!="push"
            or os.environ.get("GITHUB_REF")!="refs/heads/ops/bct-s4-private-epoch-migrate-20261116"):
        raise ValueError("EPOCH_EXPLICIT_SINGLE_WORKFLOW_IDENTITY_REQUIRED")
    secure_source_free_preflight(preflight,output_root["sealed"])
    verify_checkpoint(checkpoint,output_root["sealed"],restore=op.restore,resume=resume)
    old=output_root["previous_snapshot"]
    validate_public_previous(old,output_root["previous_manifest"])
    epoch_link=link(preflight,old)
    auth=base64.b64encode(("x-access-token:"+token).encode()).decode()
    env={**os.environ,"GIT_CONFIG_COUNT":"2",
         "GIT_CONFIG_KEY_0":"http.https://github.com/.extraheader",
         "GIT_CONFIG_VALUE_0":"AUTHORIZATION: basic "+auth,
         "GIT_CONFIG_KEY_1":"credential.helper","GIT_CONFIG_VALUE_1":"",
         "GIT_TERMINAL_PROMPT":"0"}
    with tempfile.TemporaryDirectory(prefix="bct-s4-epoch-migrate-") as t:
        t=Path(t); repo=t/"repo";repo.mkdir()
        def git(*args, stdin=None, extra=None):
            c=subprocess.run(["git","-C",str(repo),*args],input=stdin,
                 capture_output=True,text=True,timeout=65,env={**env,**(extra or {})})
            if c.returncode:
                raise ValueError("EPOCH_PRIVATE_GIT_VERIFICATION_OR_CAS_FAILED")
            return c.stdout.strip()
        git("init","-q")
        git("remote","add","origin",PRIVATE_URL)
        refs=git("ls-remote","origin",OLD_REF,ARCHIVE_REF,EPOCH_REF)
        found=dict((parts[1],parts[0]) for row in refs.splitlines()
                   if len(parts:=(row.split()))==2)
        if found.get(OLD_REF)!=OLD_ACK or found.get(ARCHIVE_REF)!=OLD_ACK:
            raise ValueError("EPOCH_PRIOR_PRIVATE_AND_ARCHIVE_REF_CHANGED")
        if EPOCH_REF in found:
            raise ValueError("EPOCH_NEW_PRIVATE_REF_ALREADY_EXISTS_NEVER_OVERWRITE")
        work=t/"staged";work.mkdir()
        for name in ("checkpoint.json","checkpoint.sqlite3.gz"):
            (work/name).write_bytes((Path(checkpoint)/name).read_bytes())
        (work/"epoch-link.json").write_bytes(encoded(epoch_link)+b"\n")
        staging={"GIT_INDEX_FILE":str(t/"index")}
        git("read-tree","--empty",extra=staging)
        for name in ("checkpoint.json","checkpoint.sqlite3.gz","epoch-link.json"):
            blob=git("hash-object","-w",str((work/name).resolve()))
            git("update-index","--add","--cacheinfo",f"100644,{blob},{name}",extra=staging)
        tree=git("write-tree",extra=staging)
        root=git("-c","user.name=BCT CPU epoch","-c",
                 "user.email=bct-epoch@users.noreply.github.com",
                 "commit-tree",tree,stdin="Start distinct CPU storage epoch; old history frozen\n")
        if git("rev-list","--parents","-n","1",root).split()!=[root]:
            raise ValueError("EPOCH_ROOT_HAS_PARENT_OLD_HISTORY_WOULD_REMAIN_UNBOUNDED")
        receipt={"version":"bct-private-persistence-1",
                 "checkpoint_commit":root,
                 "sqlite_sha256":NEW_DB,
                 "remote_restored_at":op.now() if hasattr(op,"now") else "2026-11-16T00:00:00+00:00",
                 "seven_day_start":None,
                 "seven_day_status":"NOT_STARTED_EPOCH_BRIDGE_REQUIRES_CONTINUITY_REVIEW",
                 "new_validated_windows":0,
                 "complete_analyzed_new_CPU_documents":0,
                 "analysis_status":"HISTORICAL_SEALED_24_WINDOWS_MIGRATED_NOT_NEW_INFERENCE",
                 "analysis_errors":0,
                 "publisher_run_id":run_id,
                 "publisher_attempt":1,
                 "publisher_workflow_sha":workflow_sha,
                 "publisher_execution_sha":ORIGINAL_CPU_CODE_SHA,
                 "API_calls":0,
                 "LIVE_registration":False}
        (work/"private-persistence.json").write_bytes(encoded(receipt)+b"\n")
        blob=git("hash-object","-w",str((work/"private-persistence.json").resolve()))
        git("update-index","--add","--cacheinfo",f"100644,{blob},private-persistence.json",extra=staging)
        acktree=git("write-tree",extra=staging)
        ack=git("-c","user.name=BCT CPU epoch","-c",
                "user.email=bct-epoch@users.noreply.github.com",
                "commit-tree",acktree,"-p",root,
                stdin="Acknowledge migrated research without new CPU inference\n")
        if git("rev-list","--parents","-n","1",ack).split()!=[ack,root]:
            raise ValueError("EPOCH_ACK_NOT_CHILD_OF_CHECKPOINT_ROOT")
        bytes_used=history_measure(git,ack)
        # A new no-parent epoch root cannot fast-forward an existing ref. Any
        # concurrent remote write rejects this push without -f.
        git("push","origin",ack+":"+EPOCH_REF)
        git("fetch","--no-tags","origin",EPOCH_REF)
        if git("rev-parse","FETCH_HEAD")!=ack:
            raise ValueError("EPOCH_NEW_PRIVATE_ACK_NOT_READ_BACK")
        after=git("ls-remote","origin",OLD_REF,ARCHIVE_REF,EPOCH_REF)
        check={row.split()[1]:row.split()[0] for row in after.splitlines()
               if len(row.split())==2}
        if check!={OLD_REF:OLD_ACK,ARCHIVE_REF:OLD_ACK,EPOCH_REF:ack}:
            raise ValueError("EPOCH_OLD_REF_MOVED_OR_NEW_REF_IDENTITY_FAILED")
        if (json.loads(git("show",ack+":epoch-link.json"))!=epoch_link
                or json.loads(git("show",ack+":private-persistence.json"))!=receipt):
            raise ValueError("EPOCH_REMOTE_ACK_OR_LINEAGE_LINK_CHANGED")
        refetch=t/"refetched";refetch.mkdir()
        for name in ("checkpoint.json","checkpoint.sqlite3.gz"):
            (refetch/name).write_bytes(subprocess.run(
                ["git","-C",str(repo),"show",ack+":"+name],check=True,
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=25).stdout)
        verified=op.restore(refetch,t/"verified")
        if verified.get("sqlite_sha256")!=NEW_DB or verified.get("tables")!=8:
            raise ValueError("EPOCH_NEW_REMOTE_DB_TABLE_HASH_RESTORE_FAILED")
        ledger=resume.Ledger(t/"verified")
        try:resume.audit(ledger)
        finally:ledger.close()
        # Old public lineage is kept on the new read-only PREVIEW ONLY;
        # live display adoption requires separately reviewed cursor semantics.
        with sqlite3.connect((t/"verified/v4.sqlite3").resolve().as_uri()+"?mode=ro",uri=True) as db:
            preview=public_research.build_snapshot(
                db,{"commit":ack,"remote_restore_verified":True,"persistence_receipt":receipt},
                verified,{"lineage_root":OLD_ROOT,"ack_sequence":OLD_ACK_SEQUENCE+2})
        if (preview["generation"]["private_commit"]!=ack
                or preview["generation"]["checkpoint_commit"]!=root
                or preview["generation"]["lineage_root"]!=OLD_ROOT
                or preview["generation"]["ack_sequence"]!=OLD_ACK_SEQUENCE+2
                or preview["generation"]["sqlite_sha256"]!=NEW_DB
                or preview["counts"]["new_CPU_windows"]!=0):
            raise ValueError("EPOCH_PUBLIC_PREVIEW_LINEAGE_OR_INFERENCE_UNVERIFIED")
        outdir=Path(output_root["destination"])
        outdir.mkdir(parents=True,exist_ok=False)
        (outdir/"preview-snapshot.json").write_bytes(encoded(preview)+b"\n")
        report={"format":"bct-s4-independent-private-epoch-migration-v1",
                "status":"PASS_SEPARATE_PRIVATE_EPOCH_ROOT_RESTORED_SOURCE_FREE_PREVIEW",
                "previous_private_ref":OLD_REF,"previous_ack_commit":OLD_ACK,
                "previous_archive_ref":ARCHIVE_REF,
                "previous_lineage_root":OLD_ROOT,
                "new_private_ref":EPOCH_REF,"new_root_commit":root,
                "new_ack_commit":ack,"new_sqlite_sha256":NEW_DB,
                "eight_table_restore_verified":True,
                "new_private_epoch_history_bytes":bytes_used,
                "new_epoch_64mib_cap_preserved":True,
                "old_history_archive_unchanged":True,
                "user_dashboard_auto_activation":False,
                "prior_ack_sequence":OLD_ACK_SEQUENCE,
                "source_free_preview_ack_sequence":OLD_ACK_SEQUENCE+2,
                "old_ref_writes":0,"new_cpu_inferences":0,"new_private_refs":1,
                "original_source_cohort_windows_read":59,
                "original_source_cohort_windows_pending":181,
                "S1_S2_S3_LIVE_promotions":0}
        (outdir/"migration-proof.json").write_bytes(encoded(report)+b"\n")
        return report

def main():
    a=argparse.ArgumentParser()
    for name in ("checkpoint","preflight","sealed-proof","previous-public","previous-manifest","destination"):
        a.add_argument("--"+name,type=Path,required=True)
    args=a.parse_args()
    from bct.v4 import cpu_operations as op, cpu_resume as resume, public_research
    preview=json.loads(args.previous_public.read_bytes())
    out={"sealed":json.loads(args.sealed_proof.read_bytes()),
         "previous_snapshot":preview,
         "previous_manifest":json.loads(args.previous_manifest.read_bytes()),
         "destination":args.destination}
    result=publish_epoch(
        args.checkpoint,json.loads(args.preflight.read_bytes()),preview,
        os.environ.get("BCT_V4_PRIVATE_STATE_TOKEN",""),
        run_id=int(os.environ.get("GITHUB_RUN_ID") or "0"),
        workflow_sha=os.environ.get("GITHUB_SHA",""),
        output_root=out,public_research=public_research,op=op,resume=resume)
    print("BCT_S4_EPOCH_MIGRATION="+json.dumps({
        k:result[k] for k in ("status","new_private_ref","new_ack_commit",
            "eight_table_restore_verified","new_private_epoch_history_bytes",
            "old_ref_writes","new_cpu_inferences",
            "original_source_cohort_windows_read","original_source_cohort_windows_pending")},sort_keys=True))
if __name__=="__main__":
    main()
