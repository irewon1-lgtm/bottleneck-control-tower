"""Source-free, fail-closed Session 4 private storage epoch handoff preflight.

Inputs are TWO independently verified READ-ONLY Actions artifacts:
 - authenticated previous vs sealed unpublished CPU source-window receipt
 - exact Git-history object-byte accounting with a verified archive anchor

No checkout of private content, decryption, token, model, or Git ref mutations.
This code is a proposal/acceptance manifest, NOT permission to activate v2.
"""
import argparse
import hashlib
import json
from math import ceil
from pathlib import Path
import re

FORMAT="bct-s4-safe-private-storage-epoch-preflight-v1"
OLD_REF="refs/heads/codex/bct-v4-cpu-research-state"
ARCHIVE_REF="refs/heads/archive/bct-v4-cpu-pre-64m-20261116"
OLD_ACK="8493ce906aea1c4ef14693873ba016e708d30245"
SEALED_SHA="b330cdf20ebfe479bedcbe929dfbfe65b2df48639d04dfdfa7d6250082f9a572"
OLD_RUN=43782542564
FAILED_RUN=43783049883
WINDOW_BUDGET=24
HISTORY_CAP=64*1024*1024

def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def assemble(capacity,unpublished):
    if (capacity.get("format")!="bct-s4-private-history-pressure-v1"
            or capacity.get("status")!="PASS_READONLY_PRIVATE_HISTORY_MEASURED"
            or capacity.get("cpu_ref")!=OLD_REF
            or capacity.get("archive_ref")!=ARCHIVE_REF
            or capacity.get("latest_confirmed_private_ack")!=OLD_ACK
            or capacity.get("archive_fully_anchors_current_head") is not True
            or capacity.get("private_ref_writes")!=0
            or capacity.get("public_ref_writes")!=0
            or capacity.get("history_limit_bytes")!=HISTORY_CAP
            or type(capacity.get("history_unique_object_bytes")) is not int
            or not 0<capacity["history_unique_object_bytes"]<HISTORY_CAP
            or capacity.get("headroom_bytes")!=HISTORY_CAP-capacity["history_unique_object_bytes"]):
        raise ValueError("S4_EPOCH_ARCHIVED_PRIVATE_HISTORY_NOT_VERIFIED")
    counts=unpublished.get("counts",{})
    required={"prior_success":35,"sealed_success":59,"sealed_pending":181,
              "unpublished_added":24,"total":240}
    if (unpublished.get("format")!="bct-s4-authenticated-unpublished-cpu-v1"
            or unpublished.get("status")!="SEALED_VERIFIED_UNPUBLISHED_DO_NOT_COUNT_AS_DURABLE"
            or unpublished.get("last_durable_private_commit")!=OLD_ACK
            or unpublished.get("last_durable_run")!=OLD_RUN
            or unpublished.get("unpublished_run")!=FAILED_RUN
            or unpublished.get("authenticated_sealed_sqlite_sha256")!=SEALED_SHA
            or unpublished.get("target_original_sources")!=11
            or unpublished.get("durable_promotion") is not False
            or unpublished.get("requires_reviewed_storage_migration") is not True
            or unpublished.get("new_model_calls")!=0
            or unpublished.get("private_ref_writes")!=0
            or counts!=required):
        raise ValueError("S4_EPOCH_SEALED_UNPUBLISHED_CHECKPOINT_NOT_VERIFIED")
    details=unpublished.get("per_source")
    if not isinstance(details,list) or len(details)!=11:
        raise ValueError("S4_EPOCH_ORIGINAL_SOURCE_ROWS_NOT_11")
    seen=set()
    for row in details:
        identity=tuple(row.get(k) for k in ("document_id","body_sha256","raw_sha256"))
        if (not all(isinstance(x,str) and x for x in identity)
                or not all(re.fullmatch(r"[a-f0-9]{64}",x)
                           for x in identity[1:])
                or identity in seen
                or type(row.get("unpublished_added")) is not int
                or row["unpublished_added"]<0
                or row["sealed_success"]<row["prior_success"]
                or row["total"]!=row["sealed_success"]+row["sealed_pending"]):
            raise ValueError("S4_EPOCH_SOURCE_VERSION_OR_WINDOW_PROOF_INVALID")
        seen.add(identity)
    if sum(x["unpublished_added"] for x in details)!=24:
        raise ValueError("S4_EPOCH_SOURCE_WINDOW_SUM_MISMATCH")
    if capacity["headroom_bytes"]>=5*1024*1024:
        raise ValueError("S4_EPOCH_CAP_PRESSURE_NOT_IN_PROVEN_RANGE")
    result={
        "format":FORMAT,
        "status":"PASS_READONLY_GATES_FOR_REVIEWED_STORAGE_EPOCH_DESIGN",
        "activation_status":"NOT_APPROVED_NOT_EXECUTED",
        "private_old_ref":OLD_REF,
        "private_archived_ref":ARCHIVE_REF,
        "anchored_previous_ack":OLD_ACK,
        "archive_integrity":"PASS",
        "old_ref_mutations":0,
        "private_history_cap_bytes":HISTORY_CAP,
        "private_history_used_bytes":capacity["history_unique_object_bytes"],
        "private_history_headroom_bytes":capacity["headroom_bytes"],
        "last_durable_publisher_run":OLD_RUN,
        "sealed_unpublished_producer_run":FAILED_RUN,
        "sealed_unpublished_sqlite_sha256":SEALED_SHA,
        "original_exact_source_versions":11,
        "total_target_windows":240,
        "durably_persisted_windows":35,
        "authenticated_unpublished_windows":24,
        "verified_read_windows":59,
        "verified_unread_windows":181,
        "additional_bounded_CPU_batches_required":ceil(181/WINDOW_BUDGET),
        "CPU_windows_per_batch_limit":WINDOW_BUDGET,
        "pending_qualified_demand_supply_pair_status":"UNVERIFIED",
        "automatic_S1_S2_S3_or_LIVE_promotions":0,
        "source_text_or_private_key_exported":False,
        "new_model_calls":0,
        "new_remote_ref_writes":0,
        "planned_migration":{
            "phase_A":"CREATE_NEW_PRIVATE_STORAGE_EPOCH_STAGED_REF_AND_KEEP_OLD_ARCHIVE_IMMUTABLE",
            "phase_B":"RECOVER_EXACT_59-WINDOW_SEALED_CHECKPOINT_TO_NEW_EPOCH_WITH_NO_CPU_REREAD",
            "phase_C":"PROVE_REMOTE_CHECKPOINT_DB_AND_ALL_EIGHT_TABLE_HASHES_PLUS_EXACT_11_SOURCE_IDS",
            "phase_D":"COMMIT_SOURCE_FREE_CROSS_EPOCH_LINK_OLD_ACK_NEW_ACK_AND_MONOTONE_LINEAGE",
            "phase_E":"VERIFY_PUBLIC_DASHBOARD_LINEAGE_NO_REGRESSION_BEFORE_ANY_SCHEDULED_ACTIVATION",
            "phase_F":"ACTIVATE_EXPLICITLY_REVIEWED_NEW_EPOCH_AND_DRAIN_181_WITH_BOUNDED_CAS"
        },
        "hard_stop_if":[
            "OLD_PRIVATE_REF_OR_ARCHIVE_SHA_CHANGED",
            "SEALED_ORIGINAL_SOURCE_ID_VERSION_OR_CHECKPOINT_HASH_MISMATCH",
            "UNVERIFIED_CROSS_EPOCH_SOURCE_FREE_LINEAGE_OR_ACK_SEQUENCE",
            "PRIVATE_CAS_WRITE_OR_REMOTE_RESTORE_FAILURE",
            "CHECKPOINT_OR_HISTORY_CAP_EXCEEDED",
            "AUTOMATIC_STAGE_PROMOTION_OR_OLD_HISTORY_DELETION_REQUESTED"
        ],
    }
    result["plan_sha256"]=digest(encoded(result))
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--capacity",type=Path,required=True)
    parser.add_argument("--sealed-proof",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        raise ValueError("S4_EPOCH_PLAN_OUTPUT_EXISTS")
    result=assemble(json.loads(args.capacity.read_bytes()),
                    json.loads(args.sealed_proof.read_bytes()))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(encoded(result)+b"\n")
    print("BCT_S4_EPOCH_PREFLIGHT="+json.dumps({
        "status":result["status"],
        "durable":result["durably_persisted_windows"],
        "sealed_additional":result["authenticated_unpublished_windows"],
        "remaining":result["verified_unread_windows"],
        "batches":result["additional_bounded_CPU_batches_required"],
        "headroom_bytes":result["private_history_headroom_bytes"],
        "refs_written":0},sort_keys=True))

if __name__=="__main__":
    main()
