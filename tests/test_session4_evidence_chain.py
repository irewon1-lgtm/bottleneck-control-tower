"""Session 4: source, CPU receipt, graph hold, immutable storage, readback."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import sqlite3

import pytest

from bct import precursor_collection as collection
from bct import session4_evidence_chain as s4


def article(body="Signed firm new orders for military-grade tungsten in United States, delivery required in 2028."):
    digest = hashlib.sha256(body.encode()).hexdigest()
    d = {
        "document_id": "session4-source-001", "body": body,
        "body_sha256": digest, "version": digest,
        "raw_sha256": "f" * 64, "origin_id": "session4-company",
        "origin_url": "https://example.gov/research/source-001",
        "origin_publisher": "session4-company",
        "published_at": "2026-11-14T00:00:00+00:00",
        "available_at": "2026-11-14T00:00:00+00:00",
        "acquired_at": "2026-11-14T01:00:00+00:00",
        "provenance": "PASS", "provenance_verified": True,
    }
    return collection.structure(d)


def cpu(d, *, read="UNREAD"):
    success = 0 if read == "UNREAD" else 1
    return {
        "document_id": d["document_id"], "body_sha256": d["body_sha256"],
        "raw_sha256": d["raw_sha256"],
        "source_verification": "EXACT_NATIVE_AND_BODY_HASHES",
        "read_state": read,
        "model_read_producer": None if read == "UNREAD" else "verified-native-receipt",
        "window_counts": {"total": 1, "success": success, "failed": 0, "unread": 1 - success},
        "window_binding_sha256": "a" * 64, "analysis_sha256": "b" * 64,
    }


def test_real_source_hash_identity_and_missing_counterpart_are_held():
    d = article()
    result = s4.build(d, cpu(d))
    assert result["decision"] == "HOLD" and not result["auto_promoted"]
    assert result["reason"] == "CPU_WINDOW_UNREAD"
    assert result["source"]["document_id"] == d["document_id"]
    assert result["source"]["body_sha256"] == d["body_sha256"]
    assert result["events"] and result["independent_pairs"] == 0
    assert all("first_blocker" in e and "missing_fields" in e for e in result["events"])
    raw = s4.canonical(result)
    assert d["body"] not in raw
    assert '"body":' not in raw and '"source_quote":' not in raw
    assert result["prediction_performance"] == "UNVERIFIED"


def test_exact_held_source_offsets_and_separate_quantity_period_paths():
    d = article("Signed firm new orders for military-grade tungsten in United States; "
                "delivery required in 2028; nominal capacity expansion of 500 units planned for 2029.")
    result = s4.build(d, cpu(d))
    for event in result["events"]:
        loc = event["source_locator"]
        assert loc["span_sha256"] == s4.sha(d["body"][loc["start"]:loc["end"]])
        assert isinstance(event["quantity_path"], list)
        assert isinstance(event["timing_path"], list)
        for q in event["quantity_path"]:
            assert q["kind"] != "QUALIFIED_OUTPUT" or q["qualification_status"] != "PENDING"
        assert event["source_locator"]["end"] <= len(d["body"])
    assert result["decision"] == "HOLD"
    assert result["protected_signals_seen_not_promoted"] == 0


def test_full_count_is_not_fact_verification_or_automatic_promotion():
    d = article()
    result = s4.build(d, cpu(d, read="COMPLETE"))
    assert result["cpu"]["status"] == "READ_RECEIPT_ONLY"
    assert result["decision"] == "HOLD"
    assert result["independent_pairs"] == 0
    assert result["protected_signals_seen_not_promoted"] == 0


@pytest.mark.parametrize("change", [
    lambda d, t: d.update(body=d["body"] + "corruption"),
    lambda d, t: d.update(version="0" * 64),
    lambda d, t: d.update(provenance="BLOCKED"),
    lambda d, t: t.update(document_id="other"),
    lambda d, t: t.update(body_sha256="0" * 64),
    lambda d, t: t.update(source_verification="UNVERIFIED"),
    lambda d, t: t["window_counts"].update(unread=2),
])
def test_source_cpu_tampering_fails_closed(change):
    d = article()
    trace = cpu(d)
    change(d, trace)
    with pytest.raises((ValueError, KeyError)):
        s4.build(d, trace)


def test_storage_new_process_readback_no_body_duplicate_or_mutation(tmp_path):
    d = article()
    saved = s4.build(d, cpu(d))
    db = tmp_path / "session4.sqlite3"
    first = s4.persist(db, [saved])
    second = s4.persist(db, [saved])
    assert len(first) == len(second) == 1
    assert first == second and s4.dashboard(first)["candidate_count"] == 0
    assert s4.dashboard(first)["cpu_unread_sources"] == 1
    assert d["body"] not in db.read_bytes().decode("utf-8", "ignore")
    altered = deepcopy(saved)
    altered["reason"] = "FORGED_SUCCESS"
    with pytest.raises(ValueError, match="IMMUTABLE_CASE_CHANGED"):
        s4.persist(db, [altered])
    assert s4.readback(db) == first
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM cases").fetchone()[0] == 1


def test_bad_source_locator_never_persists():
    d = article()
    d["retained_collection_events"][0]["locator"]["end"] += 10000
    with pytest.raises((ValueError, IndexError, KeyError)):
        s4.build(d, cpu(d))
