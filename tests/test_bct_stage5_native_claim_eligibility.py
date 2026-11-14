"""Regression for real Stage 5 interruption: SOURCE_CHANGED is material hold, not a claim.

This tests source selection + queue parity without pretending to execute a CPU
model. Production Stage 5 must still run the real native worker and reconcile
its independently stopped owner before PASS.
"""
from copy import deepcopy
from pathlib import Path
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github/scripts"))

import bct_native_claim_probe as native
import bct_local_reader_probe as pilot

from bct.future_review import _records, queue_items
from bct.future_store import LocalJSONTransport
from bct.future_worker import run_worker
from tests.test_future_worker import sources


def prepared(tmp_path):
    _, candidates, tracking, cache = sources(tmp_path, count=2)
    original = json.loads(candidates.read_text())
    mapped = {(r["document_id"], r["body_sha256"]): r for r in _records(original)}
    inputs = []
    for key, rec in sorted(mapped.items()):
        body = (cache / (rec["body_sha256"] + ".txt")).read_text()
        inputs.append({
            "document_id": key[0], "title": rec.get("title"),
            "body_sha256": key[1], "body_status": "FULL",
            "read_start": 0, "expected_read_end": len(body), "body": body,
        })
    return candidates, tracking, cache, mapped, inputs


def test_native_claim_eligibility_must_match_the_real_quick_queue(tmp_path):
    _, _, _, mapped, inputs = prepared(tmp_path)
    assert all(native.native_claim_eligible(item, mapped[(item["document_id"], item["body_sha256"])])
               for item in inputs)
    bad = deepcopy(mapped[(inputs[0]["document_id"], inputs[0]["body_sha256"])])
    bad["reaccess_status"] = "SOURCE_CHANGED"
    bad["version_access"] = {}
    assert not native.native_claim_eligible(inputs[0], bad)
    seeded = deepcopy(bad)
    seeded.pop("versions", None)
    seeded.update(body_sha256=inputs[0]["body_sha256"],
                  current_body_sha256=inputs[0]["body_sha256"])
    queues = queue_items({"results": {inputs[0]["document_id"]: seeded}}, {})
    assert queues["quick"] == []
    assert len(queues["material"]) == 1


def test_order_real_native_candidate_first_without_erasing_material_hold(tmp_path):
    _, _, _, mapped, inputs = prepared(tmp_path)
    prior = inputs[0]
    blocked = deepcopy(mapped[(prior["document_id"], prior["body_sha256"])])
    blocked["reaccess_status"] = "SOURCE_CHANGED"
    blocked["version_access"] = {}
    mapped[(prior["document_id"], prior["body_sha256"])] = blocked
    before = deepcopy(mapped)
    original_input = deepcopy(inputs)
    ordered, due = pilot.prioritize_native_claim_source(inputs, mapped)
    assert due == 1
    assert ordered[0]["document_id"] == inputs[1]["document_id"]
    assert ordered[1]["document_id"] == prior["document_id"]
    assert inputs == original_input
    assert mapped == before
    assert mapped[(prior["document_id"], prior["body_sha256"])]["reaccess_status"] == "SOURCE_CHANGED"


@pytest.mark.parametrize("blocked", ["UNAVAILABLE", "BLOCKED", "SOURCE_CHANGED"])
def test_all_explicit_blocked_states_are_never_claimed(tmp_path, blocked):
    _, _, _, mapped, items = prepared(tmp_path)
    rec = deepcopy(mapped[(items[0]["document_id"], items[0]["body_sha256"])])
    rec["reaccess_status"] = blocked
    rec["version_access"] = {}
    assert not native.native_claim_eligible(items[0], rec)
    with pytest.raises(ValueError, match="unblocked exact FULL quick-queue"):
        native.execute(tmp_path, items[0], rec, {}, lambda _: None)


def test_invalid_or_already_read_source_cannot_be_promoted_to_native_claim(tmp_path):
    _, _, _, mapped, items = prepared(tmp_path)
    rec = deepcopy(mapped[(items[0]["document_id"], items[0]["body_sha256"])])
    assert native.native_claim_eligible(items[0], rec)
    for changed in (
        {**rec, "body_status": "PARTIAL"},
        {**rec, "candidate": False, "tracked_matches": []},
        {**rec, "body_sha256": "b" * 64},
        {**rec, "body_chars": rec["body_chars"] + 1},
    ):
        assert not native.native_claim_eligible(items[0], changed)


def test_no_unblocked_pilot_source_is_never_called_verified(tmp_path):
    _, _, _, mapped, items = prepared(tmp_path)
    for rec in mapped.values():
        rec["reaccess_status"] = "SOURCE_CHANGED"
        rec["version_access"] = {}
    unchanged, due = pilot.prioritize_native_claim_source(items, mapped)
    assert due == 0
    assert unchanged == items
    source = (ROOT / ".github/scripts/bct_local_reader_probe.py").read_text()
    assert "no unblocked exact-version FULL source eligible for native claim" in source
    assert "real interrupted native claim was not verified before pilot PASS" in source
    assert "if not report.get('native_claim_verified')" in source


def test_actual_worker_respects_blocked_access_without_native_execution(tmp_path):
    candidates, tracking, cache, mapped, items = prepared(tmp_path)
    raw = json.loads(candidates.read_text())
    document_id = items[0]["document_id"]
    raw["results"][document_id]["reaccess_status"] = "SOURCE_CHANGED"
    candidates.write_text(json.dumps(raw))
    first_item = mapped[(document_id, items[0]["body_sha256"])]
    assert not native.native_claim_eligible(items[0], {**first_item, "reaccess_status": "SOURCE_CHANGED"})
    calls = []
    outcome = run_worker(LocalJSONTransport(), str(candidates), str(tracking),
                         reader=lambda payload: calls.append(payload), cache_dir=cache,
                         limit=2, review_mode="API_REVIEW", input_rate=0, output_rate=0)
    assert document_id not in calls
    assert outcome["model_calls"] <= 1
