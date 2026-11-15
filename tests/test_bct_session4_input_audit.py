"""Session 4 private queue audit tests: metadata-only, fail closed."""
import hashlib
import json
import sqlite3
from types import SimpleNamespace
import pytest

from tools.bct_session4_input_audit import classify,read_targets


def ids(name="id-1"):
    return {"document_id":name,"body_sha256":"a"*64,"raw_sha256":"b"*64}


def sample_source(doc=None,artifact=77,task_count=3):
    doc=doc or ids()
    return {**doc,"body_key":"body-key-"+doc["document_id"],
            "complete":False,
            "tasks":[{"key":doc["document_id"]+"-win-"+str(i)} for i in range(task_count)],
            "input_artifact":({"artifact_id":artifact} if artifact is not None else None)}


def test_source_not_selected_under_eight_artifact_bound_is_explicit_hold():
    row=ids();s=sample_source(row,task_count=4)
    plan={"sources":{s["body_key"]:s},"descriptors":[{"artifact_id":n} for n in range(8)],
          "holds":[{"body_key":s["body_key"],"reason_code":"PRIOR_INPUT_ARTIFACT_BUDGET_HELD"}]}
    out=classify([row],plan,set())
    assert out["source_count"]==1 and out["pending_windows"]==4
    assert out["sources"][0]["status"]=="PRIOR_INPUT_ARTIFACT_BUDGET_HELD"
    assert out["prior_artifacts_selected"]==8
    assert out["new_CPU_calls"]==out["production_writes"]==0


def test_selected_input_is_not_falsely_marked_as_read():
    row=ids();s=sample_source(row)
    plan={"sources":{s["body_key"]:s},"descriptors":[{"artifact_id":77}],"holds":[]}
    out=classify([row],plan,{row["document_id"]+"-win-0"})
    assert out["pending_windows"]==2
    assert out["sources"][0]["status"]=="SELECTED_BUT_READING_NOT_PROVEN_BY_INPUT_PLAN"
    assert out["can_mark_session4_complete"] is False


@pytest.mark.parametrize("source_change",[
    {"body_sha256":"0"*64}, {"raw_sha256":"0"*64},
    {"document_id":"id-other"},
])
def test_different_exact_source_cannot_inherit_an_old_result(source_change):
    row=ids();s=sample_source({**row,**source_change})
    plan={"sources":{s["body_key"]:s},"descriptors":[{"artifact_id":77}],"holds":[]}
    result=classify([row],plan,set())
    assert result["sources"][0]["status"]=="EXACT_VERSION_ABSENT_FROM_LATEST_CHECKPOINT"
    assert result["sources"][0]["pending_windows"] is None


def test_multiple_exact_sources_fail_closed():
    row=ids();s=sample_source(row)
    plan={"sources":{"a":s,"b":s},"descriptors":[],"holds":[]}
    with pytest.raises(ValueError,match="EXACT_SOURCE_DUPLICATE"):
        classify([row],plan,set())


def test_source_missing_artifact_descriptor_is_not_selected():
    row=ids();s=sample_source(row,artifact=None)
    plan={"sources":{"a":s},"descriptors":[],"holds":[]}
    assert classify([row],plan,set())["sources"][0]["status"]=="EXACT_INPUT_ARTIFACT_DESCRIPTOR_MISSING"


def test_only_hashed_held_ledger_is_accepted(tmp_path):
    row=ids();source={"source":row,"case_id":"case-1","decision":"HOLD","auto_promoted":False}
    payload=json.dumps(source,sort_keys=True,separators=(",",":"))
    sha=lambda v:hashlib.sha256(v).hexdigest()
    db=tmp_path/"session4.sqlite3"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE cases (id TEXT PRIMARY KEY, document_id TEXT, body_sha256 TEXT, payload_sha256 TEXT,payload TEXT)")
        c.execute("INSERT INTO cases VALUES(?,?,?,?,?)",("case-1",row["document_id"],row["body_sha256"],sha(payload.encode()),payload))
    receipt=tmp_path/"receipt.json"
    receipt.write_text(json.dumps({"status":"PASS_BACKFILL_HOLD_ONLY","source_verified_documents":1,"ledger_sha256":sha(db.read_bytes())}))
    assert read_targets(db,receipt)==[row]
    receipt.write_text(json.dumps({"status":"PASS_BACKFILL_HOLD_ONLY","source_verified_documents":1,"ledger_sha256":"0"*64}))
    with pytest.raises(ValueError,match="HASH_OR_RECEIPT_MISMATCH"):
        read_targets(db,receipt)
