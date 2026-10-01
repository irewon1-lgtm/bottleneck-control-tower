"""Acceptance checks for measurement boundaries, not guessed source labels."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
from pathlib import Path
import re
import runpy
import sqlite3
import subprocess
import sys

import pytest

from bct.future_quality import evaluate, observation_status


def fixture():
    manifest = {
        "sample_id": "fixture-not-live-performance", "filter_freeze": {"sha256": "frozen-filter"},
        "documents": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
    }
    reference = {
        "sample_id": manifest["sample_id"], "automatic_results_seen": False,
        "event_mapping_status": "FROZEN_BEFORE_AUTO_RESULTS", "documents": [],
    }
    for name in ("a", "b", "c"):
        positive = name != "c"
        reference["documents"].append({
            "id": name, "reference_status": "FULL",
            "labels": {signal: "TRUE" if positive else "FALSE" for signal in ("DEMAND", "SUPPLY", "RELIEF")},
            "events": [{"event_id": "event-" + name, "certainty": "CERTAIN", "signals": ["DEMAND", "SUPPLY", "RELIEF"] if positive else []}],
        })
    candidates = {"results": {name: {"body_sha256": "version-" + name, "body_status": "FULL", "candidate": name != "c", "evidence": {"DEMAND": [], "RELIEF": []}} for name in ("a", "b", "c")}}
    queue = [{"document_id": name, "body_sha256": "version-" + name, "kind": "QUICK", "entered_at": "2026-01-01T00:00:00+00:00"} for name in ("a", "b")]
    return manifest, reference, candidates, queue


def test_metrics_require_actual_queue_not_raw_preservation():
    manifest, reference, candidates, queue = fixture()
    assert evaluate(manifest, reference, candidates, queue, reference_sufficient=True)["status"] == "PASS"
    report = evaluate(manifest, reference, candidates, [], reference_sufficient=True)
    assert report["status"] == "FAIL"
    assert report["metrics"]["DEMAND"]["whole_path_document_capture"]["numerator"] == 0
    missing = evaluate(manifest, reference, candidates, reference_sufficient=True)
    assert missing["status"] == "PENDING"
    assert missing["metrics"]["DEMAND"]["whole_path_document_capture"]["rate"] is None


def test_stale_body_version_and_preview_without_entry_cannot_count():
    manifest, reference, candidates, queue = fixture()
    queue[0]["body_sha256"] = "old-body"
    queue[1].pop("entered_at")
    report = evaluate(manifest, reference, candidates, queue, reference_sufficient=True)
    assert report["status"] == "FAIL"
    assert report["queue_entered_document_count"] == 0
    assert len(report["ignored_queue_entries"]) == 2


def test_current_body_version_takes_precedence_over_preserved_legacy_hash():
    manifest, reference, candidates, queue = fixture()
    candidates["results"]["a"].update(current_body_sha256="new-body", body_sha256="version-a")
    stale = evaluate(manifest, reference, candidates, queue, reference_sufficient=True)
    assert stale["metrics"]["DEMAND"]["whole_path_document_capture"]["numerator"] == 1
    queue[0]["body_sha256"] = "new-body"
    current = evaluate(manifest, reference, candidates, queue, reference_sufficient=True)
    assert current["status"] == "PASS"


def test_partial_and_failed_materials_count_whole_path_not_full_recall():
    manifest, reference, candidates, queue = fixture()
    candidates["results"]["b"].update(body_status="UNAVAILABLE", candidate=False, body_sha256=None, source_version="source-b")
    queue[1].update(body_sha256=None, source_version="source-b", kind="MATERIAL")
    report = evaluate(manifest, reference, candidates, queue, reference_sufficient=True)
    assert report["status"] == "PASS"
    assert report["metrics"]["DEMAND"]["full_document_recall"]["denominator"] == 1
    assert report["metrics"]["DEMAND"]["whole_path_document_capture"]["denominator"] == 2
    assert report["metrics"]["DEMAND"]["whole_path_document_capture"]["numerator"] == 2


def test_duplicate_article_cannot_increase_event_performance():
    manifest, reference, candidates, queue = fixture()
    queue.pop()
    initial = evaluate(manifest, reference, candidates, queue, reference_sufficient=True)
    manifest["documents"].append({"id": "a-copy"})
    duplicate = deepcopy(reference["documents"][0]); duplicate["id"] = "a-copy"
    reference["documents"].append(duplicate)
    candidates["results"]["a-copy"] = deepcopy(candidates["results"]["a"])
    queue.append({**queue[0], "document_id": "a-copy"})
    repeated = evaluate(manifest, reference, candidates, queue, reference_sufficient=True)
    before = initial["metrics"]["DEMAND"]["whole_path_event_capture"]
    after = repeated["metrics"]["DEMAND"]["whole_path_event_capture"]
    assert (before["numerator"], before["denominator"], before["rate"]) == (1, 2, .5)
    assert (after["numerator"], after["denominator"], after["rate"]) == (1, 2, .5)
    assert repeated["metrics"]["DEMAND"]["whole_path_document_capture"]["rate"] == pytest.approx(2 / 3)


def test_retraction_is_separate_event_and_needs_its_own_signal_document():
    manifest, reference, candidates, queue = fixture()
    reference["documents"][0]["labels"]["RELIEF"] = "FALSE"
    reference["documents"][0]["events"][0]["signals"].remove("RELIEF")
    reference["documents"][1]["events"] = [{"event_id": "later-cancellation", "certainty": "CERTAIN", "signals": ["RELIEF", "DEMAND", "SUPPLY"]}]
    queue.pop()
    report = evaluate(manifest, reference, candidates, queue, reference_sufficient=True)
    measure = report["metrics"]["RELIEF"]["whole_path_event_capture"]
    assert (measure["numerator"], measure["denominator"]) == (0, 1)
    assert measure["missed_ids"] == ["later-cancellation"]


def test_unknown_is_excluded_with_explicit_unmeasured_scope_not_negative():
    manifest, reference, candidates, queue = fixture()
    reference["documents"][1]["labels"]["DEMAND"] = "UNKNOWN"
    reference["documents"][1]["reference_status"] = "UNAVAILABLE"
    report = evaluate(manifest, reference, candidates, queue, reference_sufficient=True)
    measure = report["metrics"]["DEMAND"]["whole_path_document_capture"]
    assert (measure["numerator"], measure["denominator"]) == (1, 1)
    assert measure["unmeasured_ids"] == ["b"]
    assert report["metrics"]["DEMAND"]["whole_path_event_capture"]["total_unmeasured_event_count"] is None


def test_positive_document_without_matching_event_signal_is_unmeasured():
    manifest, reference, candidates, queue = fixture()
    reference["documents"][1]["events"][0]["signals"].remove("DEMAND")
    report = evaluate(manifest, reference, candidates, queue, reference_sufficient=True)
    events = report["metrics"]["DEMAND"]["whole_path_event_capture"]
    assert (events["numerator"], events["denominator"]) == (1, 1)
    assert events["unmeasured_ids"] == ["b"]
    assert events["total_unmeasured_event_count"] is None
    assert any(row["document_id"] == "b" and row["signal"] == "DEMAND" for row in report["uncertain_event_membership"])


def test_unknown_membership_of_distinct_known_event_is_reported():
    manifest, reference, candidates, queue = fixture()
    reference["documents"][0]["events"].append({
        "event_id": "additional-policy-change", "certainty": "CERTAIN",
        "signals": ["RELIEF"], "labels": {"DEMAND": "UNKNOWN", "RELIEF": "TRUE", "SUPPLY": "FALSE"},
    })
    report = evaluate(manifest, reference, candidates, queue, reference_sufficient=True)
    events = report["metrics"]["DEMAND"]["whole_path_event_capture"]
    assert events["known_unmeasured_event_ids"] == ["additional-policy-change"]
    assert events["total_unmeasured_event_count"] == 1
    assert (events["numerator"], events["denominator"]) == (2, 2)


def test_positive_reference_and_event_sufficiency_must_be_reviewed():
    manifest, reference, candidates, queue = fixture()
    assert evaluate(manifest, reference, candidates, queue)["status"] == "PENDING"
    for row in reference["documents"]:
        row["labels"]["RELIEF"] = "FALSE"
    report = evaluate(manifest, reference, candidates, queue, reference_sufficient=True)
    assert report["status"] == "PENDING"
    assert report["metrics"]["RELIEF"]["whole_path_event_capture"]["rate"] is None
    reference["automatic_results_seen"] = True
    with pytest.raises(ValueError, match="precede automatic"):
        evaluate(manifest, reference, candidates, queue)


def observations(*, growth=False, system_wait=0):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for day in range(8):
        rows.append({
            "recorded_at": (start + timedelta(days=day)).isoformat(), "actual_execution": True,
            "inflow_total": 10 * day, "completed_total": (8 if growth else 10) * day,
            "pending_total": 2 * day if growth else 0, "retries": 0, "material_wait": 0,
            "oldest_wait_seconds": 86400 * day if growth else 0, "user_wait": 2 * day if growth else 0,
            "system_wait": system_wait,
        })
    return rows, start + timedelta(days=7)


def test_immediate_repeated_runs_are_not_seven_days():
    rows, now = observations()
    for row in rows:
        row["recorded_at"] = rows[0]["recorded_at"]
    report = observation_status(rows, now=now)
    assert report["status"] == "PENDING"
    assert report["elapsed_seconds"] == 0
    assert report["missing_day_buckets"] == list(range(1, 7))


def test_real_span_and_coverage_pass_without_claiming_prediction_accuracy():
    rows, now = observations()
    report = observation_status(rows, now=now)
    assert report["status"] == "PASS"
    assert report["elapsed_seconds"] == 7 * 86400
    assert report["inflow_change"] == report["completed_change"] == 70
    sparse = observation_status([rows[0], rows[-1]], now=now)
    assert sparse["status"] == "PENDING"


def test_persistent_backlog_growth_holds_even_when_user_causes_waiting():
    rows, now = observations(growth=True)
    report = observation_status(rows, now=now)
    assert report["status"] == "HOLD"
    assert report["continued_backlog_growth"] is True
    assert report["latest"]["system_wait"] == 0
    assert report["latest"]["user_wait"] == 14


def test_system_delay_and_invalid_execution_are_visible():
    rows, now = observations(system_wait=1)
    assert observation_status(rows, now=now)["status"] == "HOLD"
    rows, now = observations()
    rows[3]["synthetic"] = True
    rows[4].pop("oldest_wait_seconds")
    report = observation_status(rows, now=now)
    assert report["status"] == "PENDING"
    assert report["invalid_observations"]
    assert report["incomplete_observations"]


def test_local_trial_snapshot_and_evaluation_keep_actual_version_counts(tmp_path, monkeypatch):
    """One synthetic source fixture exercises the real CLI/helper boundaries."""
    from bct import future_bottleneck as frozen_filter
    from bct.future_bottleneck import run as collect
    from bct.future_review import READER_VERSION

    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "canonical-fixture.sqlite3"
    stamp = "2026-01-01T00:00:00+00:00"
    documents = [{"id": name, "url": f"https://example.com/fixture-{name}", "updated_at": stamp} for name in ("a", "b")]
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE radar_items(id,title,url,source,collected_at,updated_at,status,source_type)")
        db.executemany("INSERT INTO radar_items VALUES(?,?,?,?,?,?,?,?)", [
            (row["id"], "Synthetic contract fixture", row["url"], "example.com", stamp, stamp, "active", "NEWS")
            for row in documents
        ])
    db_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    filter_proof = {"filter_version": frozen_filter.FILTER_VERSION,
                    "screen_source": inspect.getsource(frozen_filter.screen), "categories": frozen_filter.CATEGORIES,
                    "patterns": {name: {"pattern": value.pattern, "flags": value.flags}
                                 for name, value in vars(frozen_filter).items() if isinstance(value, re.Pattern)}}
    filter_sha = hashlib.sha256(json.dumps(filter_proof, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = {"sample_id": "fixture-not-live-performance", "database_sha256": db_hash,
                "filter_freeze": {"version": frozen_filter.FILTER_VERSION, "sha256": filter_sha}, "documents": documents}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    candidates_path, tracking_path = tmp_path / "candidates.json", tmp_path / "tracking.json"
    output = tmp_path / "queue"
    private_cache = tmp_path / "private-runtime-cache"

    fetch_calls = []

    def source_fixture(url):
        fetch_calls.append(url)
        name = url.rsplit("-", 1)[-1]
        return {"body": f"Fixture Company {name} signed a contract and placed orders for equipment. It will expand production capacity with a new factory.",
                "body_status": "FULL" if name == "a" else "PARTIAL", "reasons": ["SYNTHETIC_TEST_SOURCE"], "extraction_method": "FIXTURE"}

    trial = runpy.run_path(str(root / ".github/scripts/future_quality_trial.py"))
    monkeypatch.setitem(trial["main"].__globals__, "run", lambda *a, **kw: collect(*a, fetcher=source_fixture, **kw))
    monkeypatch.setattr(sys, "argv", ["future_quality_trial.py", "--db", str(source), "--manifest", str(manifest_path),
                                     "--output", str(candidates_path), "--cache-dir", str(private_cache)])
    for changed_field, message in (("database_sha256", "source database SHA"), ("filter_freeze", "filter SHA")):
        changed_manifest = deepcopy(manifest)
        if changed_field == "filter_freeze":
            changed_manifest[changed_field]["sha256"] = "0" * 64
        else:
            changed_manifest[changed_field] = "0" * 64
        manifest_path.write_text(json.dumps(changed_manifest))
        with pytest.raises(RuntimeError, match=message):
            trial["main"]()
        assert not fetch_calls and not candidates_path.exists()
    manifest_path.write_text(json.dumps(manifest))
    trial["main"]()
    assert len(fetch_calls) == 2
    assert hashlib.sha256(source.read_bytes()).hexdigest() == db_hash
    candidates = json.loads(candidates_path.read_text())
    body = candidates["results"]["a"]
    tracking_path.write_text(json.dumps({"reviews": {"read-a": {
        "review_id": "read-a", "document_id": "a", "body_sha256": body["body_sha256"], "reader_version": READER_VERSION,
        "kind": "quick", "read_start": 0, "read_end": body["body_chars"], "disposition": "DATA_INSUFFICIENT", "reviewed_at": stamp,
    }}}))
    snapshot = runpy.run_path(str(root / ".github/scripts/future_queue_snapshot.py"))
    monkeypatch.setattr(sys, "argv", ["future_queue_snapshot.py", "--candidates", str(candidates_path),
                                     "--tracking", str(tracking_path), "--output-dir", str(output)])
    snapshot["main"]()
    state = json.loads(candidates_path.read_text())
    sample = state["operation_samples"][-1]
    assert sample["quick_pending"] == sample["material_pending"] == sample["candidate_data_wait"] == 1
    assert sample["pending_total"] == 2  # b is both QUICK and MATERIAL.
    assert sample["actual_execution"] is True and sample["recorded_at"] == sample["observed_at"]
    assert sample["retries"] == sample["retry_attempts"]
    assert sample["material_wait"] == sample["material_pending"]
    assert sample["oldest_wait_seconds"] == sample["oldest_wait_hours"] * 3600
    assert state["summary"]["operation_observation"]["status"] == "PENDING"

    # RSS arrivals remain separate from incoming review-version work. Neither
    # a new collection timestamp nor repeated snapshots reread known versions.
    state["summary"].update(checked_at="2026-01-02T00:00:00+00:00", new_documents_this_run=3)
    candidates_path.write_text(json.dumps(state))
    snapshot["main"]()
    snapshot["main"]()
    state = json.loads(candidates_path.read_text())
    assert [s["inflow_total"] for s in state["operation_samples"]] == [0, 0, 0]
    assert [s["new_documents"] for s in state["operation_samples"]] == [0, 3, 0]
    assert all(s["pending_total"] == 2 for s in state["operation_samples"])

    # A changed body preserves the old version and adds exactly one review job,
    # even when this is the same RSS document and the script runs twice.
    from bct.future_store import patch_json
    old_b = state["results"]["b"]
    new_b_hash = "changed-fixture-body-b"
    patch_json(candidates_path, owner="collection", operation_id="fixture-body-change", patch={"results": {"b": {
        "current_body_sha256": new_b_hash, "body_sha256": new_b_hash,
        "versions": {new_b_hash: {"body_sha256": new_b_hash, "body_status": "PARTIAL", "body_chars": old_b["body_chars"],
                                 "source_version": old_b["source_version"], "candidate": True, "queue_entered_at": stamp}},
    }}})
    snapshot["main"]()
    snapshot["main"]()
    state = json.loads(candidates_path.read_text())
    assert [s["inflow_total"] for s in state["operation_samples"]] == [0, 0, 0, 1, 1]
    assert [s["pending_total"] for s in state["operation_samples"]] == [2, 2, 2, 3, 3]
    assert len(state["operation_samples"][-1]["review_version_refs"]) == 3

    reference = {"sample_id": manifest["sample_id"], "automatic_results_seen": False,
                 "event_mapping_status": "FROZEN_BEFORE_AUTO_RESULTS", "documents": [
        {"id": name, "reference_status": "FULL" if name == "a" else "PARTIAL",
         "labels": {"DEMAND": "TRUE", "RELIEF": "TRUE", "SUPPLY": "FALSE"},
         "events": [{"event_id": "fixture-contract-" + name, "certainty": "CERTAIN", "signals": ["DEMAND", "RELIEF"]}]}
        for name in ("a", "b")
    ]}
    reference_path, report_path = tmp_path / "reference.json", tmp_path / "quality-report.json"
    reference_path.write_text(json.dumps(reference))
    command = [sys.executable, "-m", "bct.future_quality", "evaluate", "--manifest", str(manifest_path),
               "--reference", str(reference_path), "--candidates", str(candidates_path),
               "--queue", str(output / "review-queue.json"), "--reference-sufficient", "--output", str(report_path)]
    subprocess.run(command, cwd=root, check=True, capture_output=True, text=True)
    report = json.loads(report_path.read_text())
    assert report["sample_id"] == "fixture-not-live-performance" and report["status"] == "PASS"
    assert report["metrics"]["DEMAND"]["whole_path_document_capture"]["numerator"] == 2
    assert report["metrics"]["DEMAND"]["full_document_recall"]["denominator"] == 1
    assert report["queue_entered_document_count"] == 2  # The saved completed a still entered review.
    assert hashlib.sha256(source.read_bytes()).hexdigest() == db_hash
    assert all(source_fixture(row["url"])["body"] not in candidates_path.read_text() for row in documents)
    assert all(not {"body", "body_text", "full_text"} & set(row) for row in state["results"].values())
    samples_path, observation_path = tmp_path / "samples.json", tmp_path / "observation.json"
    samples_path.write_text(json.dumps({"samples": state["operation_samples"]}))
    subprocess.run([sys.executable, "-m", "bct.future_quality", "observe", "--samples", str(samples_path),
                    "--output", str(observation_path)], cwd=root, check=True, capture_output=True, text=True)
    observation = json.loads(observation_path.read_text())
    assert observation["status"] == "PENDING" and observation["sample_count"] == 5
    assert observation["latest"]["pending_total"] == 3 and observation["inflow_change"] == 1
