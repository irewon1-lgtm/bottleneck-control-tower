"""Storage epoch preflight must never auto-promote or mutate private refs."""
import importlib.util
from copy import deepcopy
from pathlib import Path
import pytest
p=Path(__file__).resolve().parents[1]/"tools/bct_s4_storage_epoch_preflight.py"
spec=importlib.util.spec_from_file_location("bct_s4_epoch_preflight",p)
s=importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

def fixtures():
    cap={"format":"bct-s4-private-history-pressure-v1",
         "status":"PASS_READONLY_PRIVATE_HISTORY_MEASURED",
         "cpu_ref":s.OLD_REF,"archive_ref":s.ARCHIVE_REF,
         "latest_confirmed_private_ack":s.OLD_ACK,
         "archive_fully_anchors_current_head":True,
         "private_ref_writes":0,"public_ref_writes":0,
         "history_limit_bytes":s.HISTORY_CAP,
         "history_unique_object_bytes":64131202,
         "headroom_bytes":2977662}
    sources=[{"document_id":f"target-{i:02d}","body_sha256":f"{i+1:064x}",
              "raw_sha256":f"{i+50:064x}",
              "total":24 if i<9 else 12,
              "prior_success":3 if i<2 else 2,
              "sealed_success":5 if i<2 else 4,
              "sealed_pending":19 if i<9 else 8,
              "unpublished_added":2} for i in range(11)]
    # Explicit synthetic test-only reconciliation to the canonical 240/35/59 counts.
    for x in sources:
        x["total"]=20
        x["prior_success"]=3
        x["sealed_success"]=5
        x["unpublished_added"]=2
        x["sealed_pending"]=x["total"]-x["sealed_success"]
    for i in range(2):
        sources[i]["total"]+=10
        sources[i]["sealed_pending"]+=10
    for i in range(2):
        sources[i]["prior_success"]+=1
        sources[i]["sealed_success"]+=1
        sources[i]["sealed_pending"]-=1
    # Sums: total=240, prior=35, sealed=57, added=22; append two source-safe successes.
    for i in (2,3):
        sources[i]["sealed_success"]+=1
        sources[i]["unpublished_added"]+=1
        sources[i]["sealed_pending"]-=1
    proof={"format":"bct-s4-authenticated-unpublished-cpu-v1",
           "status":"SEALED_VERIFIED_UNPUBLISHED_DO_NOT_COUNT_AS_DURABLE",
           "last_durable_private_commit":s.OLD_ACK,
           "last_durable_run":s.OLD_RUN,"unpublished_run":s.FAILED_RUN,
           "authenticated_sealed_sqlite_sha256":s.SEALED_SHA,
           "target_original_sources":11,"durable_promotion":False,
           "requires_reviewed_storage_migration":True,"new_model_calls":0,
           "private_ref_writes":0,
           "counts":{"total":240,"prior_success":35,
                     "sealed_success":59,"sealed_pending":181,"unpublished_added":24},
           "per_source":sources}
    return cap,proof


def test_real_guard_requires_reviewed_epoch_without_mutating_any_ref():
    cap,proof=fixtures()
    result=s.assemble(cap,proof)
    assert result["status"]=="PASS_READONLY_GATES_FOR_REVIEWED_STORAGE_EPOCH_DESIGN"
    assert result["activation_status"]=="NOT_APPROVED_NOT_EXECUTED"
    assert result["durably_persisted_windows"]==35
    assert result["authenticated_unpublished_windows"]==24
    assert result["additional_bounded_CPU_batches_required"]==8
    assert result["new_remote_ref_writes"]==0
    assert result["automatic_S1_S2_S3_or_LIVE_promotions"]==0
    assert len(result["plan_sha256"])==64


@pytest.mark.parametrize("corrupt",[
    lambda c,p:c.update(latest_confirmed_private_ack="f"*40),
    lambda c,p:c.update(archive_fully_anchors_current_head=False),
    lambda c,p:c.update(headroom_bytes=0),
    lambda c,p:c.update(history_limit_bytes=128*1024*1024),
    lambda c,p:p.update(authenticated_sealed_sqlite_sha256="0"*64),
    lambda c,p:p.update(durable_promotion=True),
    lambda c,p:p.update(new_model_calls=1),
    lambda c,p:p["counts"].update(unpublished_added=25),
    lambda c,p:p["per_source"][0].update(unpublished_added=3),
    lambda c,p:p["per_source"][0].update(body_sha256="new version"),
])
def test_unverified_ledger_archive_rollback_or_source_integrity_fails_closed(corrupt):
    c,p=fixtures()
    corrupt(c,p)
    with pytest.raises(ValueError):
        s.assemble(c,p)
