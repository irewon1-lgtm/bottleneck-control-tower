from copy import deepcopy
import json
import subprocess
import sys

import pytest

from bct.future_review import (READER_VERSION, build_bundle, document_complete,
                               delivery_patch, ensure_bundle, event_confirmation_patch, event_groups, full_queue_entries,
                               notification_patch, queue_items, queue_summary, review_patch,
                               save_review, validate_review)
from bct.future_store import LocalJSONTransport, PatchError, Snapshot, StoreConflict, apply_owned_patch


def documents(count=1, chars=100):
    return {"results": {f"d{i}": {"id": f"d{i}", "body_status": "FULL", "body_chars": chars,
        "body_sha256": f"hash{i}", "candidate": True, "url": f"https://example.com/{i}",
        "collected_at": f"2026-10-01T00:00:{i:02d}+00:00", "discovery_paths": ["DEMAND"]}
        for i in range(count)}}


def saved_review(doc="d0", body="hash0", start=0, end=100, disposition="CHANGE", reader=READER_VERSION):
    return {"review_id": "r", "document_id": doc, "body_sha256": body, "reader_version": reader,
            "kind": "quick", "read_start": start, "read_end": end, "disposition": disposition,
            "reviewed_at": "2026-10-02T00:00:00+00:00"}


def failed_attempt(**changes):
    return {"id": "failed-d0", "type": "queue_resolution", "state": "FAIL", "document_id": "d0",
            "body_sha256": "hash0", "source_version": "v1", "reader_version": READER_VERSION,
            "lanes": ["quick", "material"], "reason": "DNS_FAILED", "evidence": {"errno": -3},
            "resume_condition": "new accessible source", "finished_at": "2026-10-03T00:00:00Z", **changes}


def test_failed_attempt_archive_preserves_unresolved_and_frozen_bundle_without_completion():
    candidates = documents()
    candidates['results']['d0'].update(source_version='v1', body_status='PARTIAL')
    fixed = ensure_bundle(candidates, {})
    candidates.update(fixed)
    before = deepcopy(candidates)
    tracking = {'runs': [failed_attempt()]}
    summary = queue_summary(candidates, tracking)
    assert summary['quick_pending'] == summary['material_pending'] == summary['completed_documents'] == 0
    assert summary['failed_versions'] == summary['unresolved_versions'] == summary['review_list_versions'] == 1
    assert len(full_queue_entries(candidates, tracking)) == 1
    assert not ensure_bundle(candidates, tracking).get('bundles')
    assert candidates == before


@pytest.mark.parametrize('change', [{'evidence': {}}, {'source_version': 'old'}, {'reader_version': 'old'}])
def test_failure_does_not_hide_unproven_or_different_version_attempts(change):
    candidates = documents()
    candidates['results']['d0']['source_version'] = 'v1'
    assert queue_summary(candidates, {'runs': [failed_attempt(**change)]})['quick_pending'] == 1


def test_verified_later_access_reopens_failed_reading():
    candidates = documents(); candidates['results']['d0']['source_version'] = 'v1'
    tracking = {'runs': [failed_attempt()], 'reviews': {'access': {
        'kind': 'access', 'access_status': 'AVAILABLE', 'reader_version': READER_VERSION,
        'document_id': 'd0', 'body_sha256': 'hash0', 'reviewed_at': '2026-10-04T00:00:00Z'}}}
    assert queue_summary(candidates, tracking)['quick_pending'] == 1
    assert queue_summary(candidates, tracking)['completed_documents'] == 0


def test_phase3_queue_has_no_candidate_cap_and_separates_material_wait():
    candidates = documents(51)
    candidates["results"]["partial"] = {"body_status": "PARTIAL", "body_sha256": "p", "body_chars": 10, "candidate": False}
    candidates["results"]["unavailable"] = {"body_status": "UNAVAILABLE", "candidate": False, "url": "https://example.com/fail"}
    summary = queue_summary(candidates, {}, now="2026-10-02T00:00:00Z")
    assert summary["quick_pending"] == 52 and summary["automatic_candidates"] == 51
    assert summary["material_pending"] == 2 and summary["review_list_versions"] == 53
    assert len(summary["preview"]) == 5
    assert len(build_bundle(candidates, {}, now="2026-10-02T00:00:00Z")["documents"]) == 10
    entries = full_queue_entries(candidates, {})
    assert len(entries) == 53
    assert next(x for x in entries if x["document_id"] == "unavailable")["kind"] == "MATERIAL"


def test_phase3_completion_requires_saved_exact_version_reader_and_full_contiguous_read():
    candidates = documents()
    item = queue_items(candidates, {})["quick"][0]
    assert not document_complete({"progress": {"d0:hash0:" + READER_VERSION: {"read_end": 100}}}, item)
    for review in (saved_review(end=50), saved_review(body="old"), saved_review(reader="old"), saved_review(start=30), saved_review(disposition="INCOMPLETE")):
        assert not document_complete({"reviews": {"r": review}}, item)
    assert document_complete({"reviews": {"r": saved_review()}}, item)


def test_phase3_resume_uses_saved_actual_ranges_and_fixed_bundle_is_immutable():
    candidates = documents(chars=30000)
    first = build_bundle(candidates, {}, now="2026-10-02T00:00:00Z")
    assert len(first["documents"]) == 1 and first["documents"][0]["end"] == 12000
    fixed = apply_owned_patch(candidates, owner="bundle", patch={"bundles": {first["id"]: first}}, operation_id="b1")
    partial = {"reviews": {"r": saved_review(end=5000, disposition="INCOMPLETE")}}
    reused = ensure_bundle(fixed, partial)
    assert reused["bundles"][first["id"]]["documents"] == first["documents"]
    assert queue_summary(fixed, partial)["preview"][0]["resume_at"] == 5000
    first_read = {"reviews": {"r": saved_review(end=12000, disposition="INCOMPLETE")}}
    next_patch = ensure_bundle(fixed, first_read)
    next_bundle = next(iter(next_patch["bundles"].values()))
    assert next_bundle["id"] != first["id"]
    assert next_bundle["documents"][0]["start"] == 12000 and next_bundle["documents"][0]["end"] == 24000


def test_phase3_urgent_relief_always_leaves_fifo_slot():
    candidates = documents(6)
    for record in list(candidates["results"].values())[2:]:
        record["discovery_paths"] = ["RELIEF"]
    bundle = build_bundle(candidates, {}, max_documents=3)
    assert [ref["document_id"] for ref in bundle["documents"]] == ["d0", "d2", "d3"]
    assert build_bundle(candidates, {}, max_documents=1)["documents"][0]["document_id"] == "d0"


def test_phase3_partial_document_read_is_complete_but_material_wait_survives():
    candidates = documents()
    candidates["results"]["d0"]["body_status"] = "PARTIAL"
    tracking = {"reviews": {"r": saved_review(disposition="DATA_INSUFFICIENT")}}
    summary = queue_summary(candidates, tracking)
    assert summary["completed_documents"] == 1 and summary["quick_pending"] == 0
    assert summary["material_pending"] == summary["candidate_data_wait"] == 1


def test_phase3_changed_body_keeps_old_unread_version_and_old_bundle():
    candidates = documents()
    old_bundle = build_bundle(candidates, {})
    candidates["bundles"] = {old_bundle["id"]: old_bundle}
    record = candidates["results"]["d0"]
    record["versions"] = {"hash0": {"body_sha256": "hash0", "body_chars": 100, "body_status": "FULL", "screening": {"candidate": True}}}
    record["current_body_sha256"] = record["body_sha256"] = "new"
    tracking = {"reviews": {"r": saved_review()}}
    summary = queue_summary(candidates, tracking)
    assert summary["completed_documents"] == 1 and summary["quick_pending"] == 1
    assert summary["preview"][0]["body_sha256"] == "new"
    assert candidates["bundles"][old_bundle["id"]]["documents"][0]["body_sha256"] == "hash0"


def test_phase3_event_groups_are_conservative_and_cancellation_is_a_change():
    candidates = documents(5)
    rows = candidates["results"]
    rows["d1"]["body_sha256"] = "hash0"  # An exact reprint is reusable.
    rows["d2"].update(event_key="contractA", event_confirmed=True)
    rows["d3"].update(event_key="contractA", event_confirmed=True)
    rows["d4"].update(event_key="contractA", event_confirmed=True, change_kind="CANCELLATION")
    groups = event_groups(candidates)
    assert sorted(len(group["documents"]) for group in groups.values()) == [1, 2, 2]
    rows["d3"]["event_confirmed"] = False
    assert len(event_groups(candidates)) == 4
    rows["d4"]["url"] = rows["d0"]["url"]
    assert len(event_groups(candidates)) == 4  # Same URL cannot erase a changed hash.


def test_phase3_opening_bundle_or_notification_never_completes_a_document():
    candidates = documents()
    patch = ensure_bundle(candidates, {})
    candidates = apply_owned_patch(candidates, owner="bundle", patch=patch, operation_id="b1")
    candidates = apply_owned_patch(candidates, owner="notification", patch={"notifications": {"n": {"received": True}}}, operation_id="n1")
    assert queue_summary(candidates, {})["quick_pending"] == 1
    assert queue_summary(candidates, {})["completed_documents"] == 0


def test_phase3_legacy_body_ok_is_material_wait_until_explicit_full_extraction():
    candidates = documents()
    candidates["results"]["d0"]["body_status"] = "BODY_OK"
    summary = queue_summary(candidates, {})
    assert summary["material_pending"] == 1 and summary["preview"][0]["body_status"] == "PARTIAL"


def gate(value="TRUE"):
    return {"value": value, "evidence": [{"url": "https://example.com/source", "locator": "paragraph 2"}]} if value != "UNKNOWN" else {"value": "UNKNOWN", "reason": "not disclosed"}


def deep_review(path="DEMAND", stage="S3"):
    base = saved_review()
    needed = ("future_demand", "supply_constraint") if path == "DEMAND" else ("remaining_demand", "supply_gap")
    return {**base, "kind": "deep", "discovery_path": path, "target": "qualified laser output",
        "s_stage": stage, "temporal_status": "FUTURE", "as_of": "2026-10-02",
        "period": {"start": "2027-10-01", "end": "2028-09-30"},
        "gates": {key: gate() for key in ("change", "target_relation", *needed, "future_period", "relief_reviewed")},
        "relief": {"capacity": {"status": "NOT_FOUND_IN_SCOPE", "reason": "official suppliers' capacity statements reviewed", "important": True, "resolved": True}},
        "comparison": {"facts": [dict(role=role, target="qualified laser output", specification="A", region="US",
            supply_pool="all qualified suppliers", period={"start": "2027-10-01", "end": "2028-09-30"},
            basis="total", quantity=quantity, unit="units", actual_statement=True, coverage_complete=True,
            document_id="d0", body_sha256="hash0", locator={"start": 0, "end": 100})
            for role, quantity in (("DEMAND", 11), ("SUPPLY", 10))]},
        "analysis_complete": True}


def test_phase4_supply_path_can_reach_s3_without_a_demand_increase():
    review = deep_review("SUPPLY")
    result = validate_review(documents(), {}, review)
    assert result["s_stage"] == "S3" and result["discovery_path"] == "SUPPLY"
    assert "future_demand" not in result["gates"] and result["read_complete"]


def test_s3_boolean_gates_without_matched_comparison_are_rejected():
    review = deep_review()
    del review['comparison']
    with pytest.raises(PatchError, match='exceeds supported gates'):
        validate_review(documents(), {}, review)


@pytest.mark.parametrize("path,key", [("DEMAND", "future_demand"), ("SUPPLY", "remaining_demand"), ("SUPPLY", "supply_gap"), ("DEMAND", "future_period")])
def test_phase4_unknown_essential_evidence_cannot_reach_s3(path, key):
    review = deep_review(path)
    review["gates"][key] = gate("UNKNOWN")
    with pytest.raises(PatchError, match="exceeds supported gates"):
        validate_review(documents(), {}, review)
    review["s_stage"] = "S2"
    assert validate_review(documents(), {}, review)["s_stage"] == "S2"


def test_phase4_unknown_relation_blocks_s2_false_one_path_does_not_delete_other():
    demand = deep_review("DEMAND", "S2")
    demand["gates"]["target_relation"] = gate("UNKNOWN")
    with pytest.raises(PatchError):
        validate_review(documents(), {}, demand)
    demand["s_stage"] = "S1"
    assert validate_review(documents(), {}, demand)["s_stage"] == "S1"
    demand["gates"]["change"] = gate("FALSE")
    demand["s_stage"] = "NONE"
    tracking = apply_owned_patch({}, owner="review", patch=review_patch(documents(), {}, demand), operation_id="r0")
    supply = deep_review("SUPPLY")
    supply["review_id"] = "supply-r"
    tracking = apply_owned_patch(tracking, owner="review", patch=review_patch(documents(), tracking, supply), operation_id="r1")
    assert tracking["reviews"]["r"]["gates"]["change"]["value"] == "FALSE"
    assert tracking["reviews"]["supply-r"]["s_stage"] == "S3"


def test_phase4_important_relief_unresolved_blocks_s3_and_search_failure_is_not_none():
    review = deep_review()
    review["relief"]["capacity"] = {"status": "INACCESSIBLE", "reason": "filing unavailable", "important": True, "resolved": False}
    with pytest.raises(PatchError):
        validate_review(documents(), {}, review)
    review["s_stage"] = "S2"
    normalized = validate_review(documents(), {}, review)
    assert normalized["relief"]["capacity"]["status"] == "INACCESSIBLE"
    review["relief"]["capacity"]["status"] = "NONE"
    review["s_stage"] = "S3"
    with pytest.raises(PatchError, match="search failure is not absence"):
        validate_review(documents(), {}, review)


def test_phase4_current_shortage_and_missing_evidence_locations_do_not_become_s3():
    review = deep_review()
    review["period"]["start"] = "2026-01-01"
    review["temporal_status"] = "CURRENT"
    with pytest.raises(PatchError):
        validate_review(documents(), {}, review)
    review = deep_review()
    review["gates"]["change"] = {"value": "TRUE", "evidence": []}
    with pytest.raises(PatchError, match="evidence locations"):
        validate_review(documents(), {}, review)


def test_phase4_partial_read_checkpoint_resume_and_final_decision_are_saved(tmp_path):
    candidates, path = documents(), tmp_path / "tracking.json"
    path.write_text(json.dumps({"version": 1}))
    partial = saved_review(end=40, disposition="INCOMPLETE")
    assert save_review(LocalJSONTransport(), path, candidates, partial).status == "APPLIED"
    tracking = json.loads(path.read_text())
    assert queue_summary(candidates, tracking)["quick_pending"] == 1
    assert queue_summary(candidates, tracking)["preview"][0]["resume_at"] == 40
    final = {**saved_review(start=40), "review_id": "r-final"}
    assert save_review(LocalJSONTransport(), path, candidates, final).status == "APPLIED"
    tracking = json.loads(path.read_text())
    assert queue_summary(candidates, tracking)["completed_documents"] == 1
    assert save_review(LocalJSONTransport(), path, candidates, final).status == "ALREADY_APPLIED"
    with pytest.raises(PatchError, match="skip an unread"):
        validate_review(candidates, {}, saved_review(start=40))


def test_phase4_full_document_read_and_missing_supply_data_remain_separate():
    candidates = documents()
    patch = review_patch(candidates, {}, saved_review(disposition="DATA_INSUFFICIENT"))
    tracking = apply_owned_patch({}, owner="review", patch=patch, operation_id="r1")
    summary = queue_summary(candidates, tracking)
    assert summary["completed_documents"] == 1 and summary["candidate_data_wait"] == 1
    assert summary["quick_pending"] == 0
    assert len(full_queue_entries(candidates, tracking)) == 1


def test_phase4_prediction_initial_is_frozen_and_changes_are_appended():
    candidates = documents()
    first = deep_review()
    first["prediction"] = {"target_id": "laser", "target": "qualified laser output", "hypothesis": "2027 qualified output constrained", "next_check_at": "2027-01-02"}
    tracking = apply_owned_patch({}, owner="review", patch=review_patch(candidates, {}, first), operation_id="r1")
    initial = deepcopy(tracking["prediction_ledger"]["laser"]["initial"])
    second = deep_review(stage="S2")
    second["review_id"] = "r2"
    second["gates"]["supply_constraint"] = gate("UNKNOWN")
    second["prediction"] = {**first["prediction"], "hypothesis": "capacity confirmation pending"}
    tracking = apply_owned_patch(tracking, owner="review", patch=review_patch(candidates, tracking, second), operation_id="r2")
    assert tracking["prediction_ledger"]["laser"]["initial"] == initial
    assert len(tracking["prediction_ledger"]["laser"]["entries"]) == 2
    assert len(tracking["targets"][0]["history"]) == 2


def test_prediction_save_retry_is_idempotent_with_initial_and_first_s3(tmp_path):
    path = tmp_path / 'tracking.json'
    path.write_text('{}')
    review = deep_review()
    review['prediction'] = {'target_id': 'laser', 'hypothesis': 'fixed original prediction'}
    transport = LocalJSONTransport()
    assert save_review(transport, str(path), documents(), review).status == 'APPLIED'
    first = path.read_bytes()
    assert save_review(transport, str(path), documents(), review).status == 'ALREADY_APPLIED'
    assert path.read_bytes() == first


def test_phase4_notification_dedup_daily_bound_and_real_receipt_separation():
    candidates, now = documents(), "2026-10-02T03:00:00Z"
    patch = notification_patch(candidates, {}, now=now)
    candidates = apply_owned_patch(candidates, owner="notification", patch=patch, operation_id="n1")
    identity = next(iter(patch["notifications"]))
    assert candidates["notifications"][identity]["state"] == "READY"
    assert notification_patch(candidates, {}, now=now) is None
    sent = delivery_patch(candidates, identity, state="SENT", at=now)
    candidates = apply_owned_patch(candidates, owner="notification", patch=sent, operation_id="sent1")
    accepted = delivery_patch(candidates, identity, state="ACCEPTED", at=now)
    candidates = apply_owned_patch(candidates, owner="notification", patch=accepted, operation_id="accepted1")
    assert candidates["notifications"][identity]["state"] == "ACCEPTED"
    assert "received_at" not in candidates["notifications"][identity]
    with pytest.raises(PatchError):
        delivery_patch(candidates, identity, state="RECEIVED", at=now)
    receipt = delivery_patch(candidates, identity, state="RECEIVED", at=now, receipt="user confirmed receipt")
    candidates = apply_owned_patch(candidates, owner="notification", patch=receipt, operation_id="received1")
    candidates["notifications"]["second"] = {"state": "SENT", "sent_at": now, "fingerprint": "another"}
    candidates["results"]["new"] = documents()["results"]["d0"] | {"body_sha256": "new"}
    assert notification_patch(candidates, {}, now=now) is None
    assert notification_patch(candidates, {}, now="2026-10-03T03:00:00Z") is not None
    assert queue_summary(candidates, {})["completed_documents"] == 0


def test_phase4_cli_review_patch_emits_owner_refs_without_modifying_inputs(tmp_path):
    candidates, tracking, review, output = [tmp_path / name for name in ("candidates.json", "tracking.json", "review.json", "patch.json")]
    candidates.write_text(json.dumps(documents()))
    tracking.write_text(json.dumps({"version": 1}))
    review.write_text(json.dumps(saved_review()))
    before = tracking.read_bytes()
    subprocess.run([sys.executable, "-m", "bct.future_review", "review-patch", "--candidates", str(candidates), "--tracking", str(tracking), "--review", str(review), "--output", str(output)], check=True)
    value = json.loads(output.read_text())
    assert value["owner"] == "review" and value["version_refs"][0]["end"] == 100
    assert value["prepared_document"] == {"version": 1}
    assert tracking.read_bytes() == before


@pytest.mark.parametrize('race', ['between_reads', 'at_write'])
def test_save_review_keeps_preparation_context_for_concurrent_distinct_judgments(race):
    candidates = documents()
    baseline = {'prediction_ledger': {'laser': {'initial': {'hypothesis': 'first', 'frozen': True}, 'entries': []}}}
    ours = deep_review(stage='NONE')
    ours.update(review_id='negative', reviewed_at='2026-10-02T03:00:00Z',
                prediction={'target_id': 'laser', 'hypothesis': 'connection refuted'})
    ours['gates']['change'] = gate('FALSE')
    other = deep_review()
    other.update(review_id='positive', reviewed_at='2026-10-02T03:00:01Z',
                 prediction={'target_id': 'laser', 'hypothesis': 'future constraint supported'})
    competing_patch = review_patch(candidates, baseline, other)

    class Transport:
        def __init__(self):
            self.document = deepcopy(baseline)
            self.revision = self.reads = self.writes = 0

        def compete(self):
            self.document = apply_owned_patch(self.document, owner='review',
                                              patch=competing_patch, operation_id='competing')
            self.revision += 1

        def read(self, path):
            self.reads += 1
            if race == 'between_reads' and self.reads == 2:
                self.compete()
            return Snapshot(deepcopy(self.document), str(self.revision))

        def write(self, path, document, expected_sha):
            self.writes += 1
            if race == 'at_write' and self.writes == 1:
                self.compete()
            if expected_sha != str(self.revision):
                raise StoreConflict('concurrent judgment')
            self.document = deepcopy(document)
            self.revision += 1

    transport = Transport()
    result = save_review(transport, 'tracking', candidates, ours)
    assert result.status == 'PENDING' and result.reason == 'SAME_ITEM_CONFLICT'
    assert transport.writes == (0 if race == 'between_reads' else 1)
    assert set(transport.document['reviews']) == {'positive'}
    assert next(iter(transport.document['progress'].values()))['last_review_id'] == 'positive'
    # A later intentional reassessment prepared from the latest record appends.
    ours['reviewed_at'] = '2026-10-02T04:00:00Z'
    assert save_review(transport, 'tracking', candidates, ours).status == 'APPLIED'
    assert set(transport.document['reviews']) == {'positive', 'negative'}
    assert transport.document['prediction_ledger']['laser']['initial'] == baseline['prediction_ledger']['laser']['initial']


def test_phase4_blocked_historical_bundle_preserves_unread_ref_and_serves_new_available_documents():
    candidates = documents()
    original_bundle = build_bundle(candidates, {})
    candidates["bundles"] = {original_bundle["id"]: deepcopy(original_bundle)}
    record = candidates["results"]["d0"]
    record["versions"] = {"hash0": {"body_sha256": "hash0", "body_chars": 100, "body_status": "FULL", "candidate": True}}
    record["current_body_sha256"] = record["body_sha256"] = "new"
    candidates["results"]["newdoc"] = documents()["results"]["d0"] | {"id": "newdoc", "body_sha256": "available"}
    access = {"review_id": "access-old", "document_id": "d0", "body_sha256": "hash0", "reader_version": READER_VERSION,
        "kind": "access", "access_status": "SOURCE_CHANGED", "observed_body_sha256": "new",
        "reason": "runtime cache missing; direct source reaccess returned a different body hash", "reviewed_at": "2026-10-02T01:00:00Z"}
    tracking = apply_owned_patch({}, owner="review", patch=review_patch(candidates, {}, access), operation_id="access-old")
    queues = queue_items(candidates, tracking)
    assert len(queues["quick"]) == 2
    assert any(x["body_sha256"] == "hash0" for x in queues["material"])
    old = next(x for x in queues["material"] if x["body_sha256"] == "hash0")
    assert not document_complete(tracking, old)
    new_bundle = next(iter(ensure_bundle(candidates, tracking)["bundles"].values()))
    assert new_bundle["id"] != original_bundle["id"]
    assert {ref["body_sha256"] for ref in new_bundle["documents"]} == {"new", "available"}
    assert candidates["bundles"][original_bundle["id"]]["documents"] == original_bundle["documents"]
    available = {**access, "review_id": "access-recovered", "access_status": "AVAILABLE", "observed_body_sha256": "hash0", "reason": "expected old body was recovered and hash verified", "reviewed_at": "2026-10-02T02:00:00Z"}
    tracking = apply_owned_patch(tracking, owner="review", patch=review_patch(candidates, tracking, available), operation_id="access-recovered")
    assert any(x["body_sha256"] == "hash0" for x in queue_items(candidates, tracking)["quick"])


def test_phase4_access_failure_never_establishes_read_completion():
    access = {"review_id": "a", "document_id": "d0", "body_sha256": "hash0", "reader_version": READER_VERSION,
        "kind": "access", "access_status": "BLOCKED", "reason": "actual source request returned 403", "read_complete": True}
    with pytest.raises(PatchError, match="do not establish"):
        validate_review(documents(), {}, access)


@pytest.mark.parametrize("disposition", ["DEEP_NEEDED", "DATA_INSUFFICIENT"])
def test_phase4_incomplete_deep_review_keeps_previous_deep_or_data_wait(disposition):
    candidates = documents()
    first = saved_review(disposition=disposition)
    first["reviewed_at"] = "2026-10-02T00:00:00Z"
    tracking = apply_owned_patch({}, owner="review", patch=review_patch(candidates, {}, first), operation_id="q1")
    incomplete = deep_review(stage="NONE")
    incomplete.update(review_id="deep-part", disposition="INCOMPLETE", analysis_complete=False,
                      read_end=50, reviewed_at="2026-10-02T01:00:00Z", gates={})
    tracking = apply_owned_patch(tracking, owner="review", patch=review_patch(candidates, tracking, incomplete), operation_id="d1")
    summary = queue_summary(candidates, tracking)
    assert summary["completed_documents"] == 1 and summary["deep_pending"] == 1
    if disposition == "DATA_INSUFFICIENT":
        assert summary["candidate_data_wait"] == 1
    finished = deep_review()
    finished.update(review_id="deep-finished", reviewed_at="2026-10-02T02:00:00Z")
    tracking = apply_owned_patch(tracking, owner="review", patch=review_patch(candidates, tracking, finished), operation_id="d2")
    assert queue_summary(candidates, tracking)["deep_pending"] == 0


def test_phase4_due_checkpoint_notifies_once_without_new_documents_or_automatic_analysis():
    tracking = {"prediction_ledger": {"laser": {"initial": {"next_check_dates": ["2027-01-02", "2027-04-02"]}, "entries": []}}}
    assert notification_patch({}, tracking, now="2027-01-01T00:00:00Z") is None
    patch = notification_patch({}, tracking, now="2027-01-02T00:00:00Z")
    assert patch and next(iter(patch["notifications"].values()))["state"] == "READY"
    assert next(iter(patch["notifications"].values()))["due_checks"] == [{"target_id": "laser", "check_at": "2027-01-02"}]
    candidates = apply_owned_patch({}, owner="notification", patch=patch, operation_id="due1")
    assert notification_patch(candidates, tracking, now="2027-01-03T00:00:00Z") is None
    assert notification_patch(candidates, tracking, now="2027-04-02T00:00:00Z") is not None
    assert "reviews" not in candidates and "reviews" not in tracking


def test_phase4_long_fifo_document_does_not_consume_urgent_relief_reading_budget():
    candidates = documents(3, chars=30000)
    candidates["results"]["d1"]["discovery_paths"] = ["RELIEF"]
    bundle = build_bundle(candidates, {}, max_documents=2)
    assert len(bundle["documents"]) == 2
    assert sum(ref["end"] - ref["start"] for ref in bundle["documents"]) == 12000
    assert bundle["documents"][1]["end"] > bundle["documents"][1]["start"]


@pytest.mark.parametrize("status", ["SOURCE_CHANGED", "UNAVAILABLE"])
def test_phase4_explicit_collection_reaccess_failure_moves_old_hash_to_material(status):
    candidates = documents()
    first = build_bundle(candidates, {})
    candidates["bundles"] = {first["id"]: first}
    record = candidates["results"]["d0"]
    record["versions"] = {"hash0": {"body_sha256": "hash0", "body_chars": 100, "body_status": "FULL",
        "candidate": True, "reaccess_status": status, "access_checked_at": "2026-10-02T00:00:00Z"}}
    record["current_body_sha256"] = record["body_sha256"] = "new"
    queues = queue_items(candidates, {})
    assert [item["body_sha256"] for item in queues["quick"]] == ["new"]
    assert any(item["body_sha256"] == "hash0" for item in queues["material"])
    next_bundle = next(iter(ensure_bundle(candidates, {})["bundles"].values()))
    assert next_bundle["documents"][0]["body_sha256"] == "new"
    assert candidates["bundles"][first["id"]]["documents"][0]["body_sha256"] == "hash0"


def test_phase4_confirmed_same_event_with_different_bodies_uses_common_bundle_store(tmp_path):
    candidates = documents(3)
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(candidates))
    refs = [{"document_id": "d0", "body_sha256": "hash0"}, {"document_id": "d1", "body_sha256": "hash1"}]
    patch = event_confirmation_patch(candidates, "verified-contract", refs, event_key="contract-42", evidence=[{"locator": "matching contract award 42"}])
    from bct.future_store import store_patch
    result = store_patch(LocalJSONTransport(), path, owner="bundle", patch=patch, operation_id="confirm-contract", version_refs=refs)
    assert result.status == "APPLIED"
    saved = json.loads(path.read_text())
    assert len(event_groups(saved)) == 2
    group = event_groups(saved)["verified-contract"]
    assert group["documents"] == refs and group["confirmed"]
    saved = apply_owned_patch(saved, owner="collection", patch={"results": {"d0": {"checked_at": "2026-10-03"}}}, operation_id="recollect")
    saved = apply_owned_patch(saved, owner="bundle", patch=ensure_bundle(saved, {}), operation_id="bundle-next")
    assert event_groups(saved)["verified-contract"]["documents"] == refs
    cancellation = event_confirmation_patch(saved, "cancelled-contract", [{"document_id": "d2", "body_sha256": "hash2"}], event_key="contract-42", change_kind="CANCELLATION")
    saved = apply_owned_patch(saved, owner="bundle", patch=cancellation, operation_id="confirm-cancel")
    groups = event_groups(saved)
    assert len(groups) == 2 and groups["cancelled-contract"]["change_kind"] == "CANCELLATION"
    assert groups["verified-contract"]["change_kind"] == "ORIGINAL"


def test_phase4_ambiguous_or_invalid_persisted_event_confirmation_does_not_join_bodies():
    candidates = documents(2)
    assert len(event_groups(candidates)) == 2
    with pytest.raises(PatchError):
        event_confirmation_patch(candidates, "bad", [{"document_id": "d1", "body_sha256": "absent"}])
    candidates["events"] = {"bad": {"confirmed": True, "event_key": "bad", "documents": [{"document_id": "d0", "body_sha256": "absent"}, {"document_id": "d1", "body_sha256": "hash1"}]}}
    assert len(event_groups(candidates)) == 2


def test_phase4_same_instant_deep_data_wait_supersedes_quick_even_with_smaller_review_id():
    candidates = documents()
    quick = saved_review(disposition="DEEP_NEEDED")
    quick.update(review_id="z-quick", reviewed_at="2026-10-02T03:00:00Z")
    tracking = apply_owned_patch({}, owner="review", patch=review_patch(candidates, {}, quick), operation_id="quick")
    deep = deep_review(stage="S2")
    deep.update(review_id="a-deep", reviewed_at=quick["reviewed_at"], disposition="DATA_INSUFFICIENT",
                candidate_state="DATA_WAIT", analysis_complete=True)
    deep["gates"]["supply_constraint"] = gate("UNKNOWN")
    tracking = apply_owned_patch(tracking, owner="review", patch=review_patch(candidates, tracking, deep), operation_id="deep")
    summary = queue_summary(candidates, tracking)
    assert summary["completed_documents"] == 1
    assert summary["candidate_data_wait"] == 1 and summary["deep_pending"] == 0
