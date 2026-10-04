from copy import deepcopy
import hashlib
import json

import pytest

from bct.future_store import (LocalJSONTransport, PatchError, Snapshot, StoreConflict,
                              apply_owned_patch, patch_json, store_patch, validate_version_refs)


class MemoryTransport:
    def __init__(self, document):
        self.document = deepcopy(document)
        self.revision = 0
        self.writes = 0
        self.on_write = None
        self.fail_readback = False
        self.corrupt_readback = False

    def read(self, path):
        if self.fail_readback and self.writes:
            raise OSError("read unavailable")
        document = deepcopy(self.document)
        if self.corrupt_readback and self.writes:
            document["notifications"] = {}
        return Snapshot(document, str(self.revision))

    def write(self, path, document, expected_sha):
        self.writes += 1
        if self.on_write:
            callback, self.on_write = self.on_write, None
            callback(self)
        if expected_sha != str(self.revision):
            raise StoreConflict("concurrent writer")
        self.document = deepcopy(document)
        self.revision += 1
        return str(self.revision)


def test_collection_patch_preserves_unknown_fields_history_and_review_progress():
    before = {"version": "v2", "unknown": {"retain": True}, "results": {"d": {
        "id": "d", "candidate": False, "unknown": 3,
        "history": [{"review_id": "r0", "status": "S1"}], "progress": 31,
    }}, "bundles": {"b": {"documents": [{"document_id": "d", "body_sha256": "old"}]}}}
    result = apply_owned_patch(before, owner="collection", patch={"results": {"d": {"candidate": True}}}, operation_id="c1")
    assert result["results"]["d"] == {**before["results"]["d"], "candidate": True}
    assert result["unknown"] == before["unknown"] and result["bundles"] == before["bundles"]
    assert before["results"]["d"]["candidate"] is False


def test_history_append_keeps_native_tracking_targets_and_baseline():
    before = {"version": 1, "policy": {"preserve_history": True}, "targets": [{
        "id": "t", "target": "laser", "baseline_frozen": True,
        "history": [{"review_id": "old", "status": "S1"}], "extra": "keep",
    }]}
    change = {"targets": [{"id": "t", "history": [{"review_id": "new", "status": "S2"}]}]}
    merged = apply_owned_patch(before, owner="review", patch=change, operation_id="r1")
    assert len(merged["targets"]) == 1
    assert [h["review_id"] for h in merged["targets"][0]["history"]] == ["old", "new"]
    assert merged["targets"][0]["baseline_frozen"] and merged["targets"][0]["extra"] == "keep"
    assert merged["policy"] == before["policy"]


def test_operations_are_idempotent_and_cannot_be_reused_for_different_changes():
    transport = MemoryTransport({})
    args = dict(owner="notification", patch={"notifications": {"n": {"sent": True}}}, operation_id="n1")
    assert store_patch(transport, "sidecar", **args).status == "APPLIED"
    assert store_patch(transport, "sidecar", **args).status == "ALREADY_APPLIED"
    assert transport.writes == 1
    args["patch"] = {"notifications": {"n": {"sent": False}}}
    result = store_patch(transport, "sidecar", **args)
    assert result.status == "PENDING" and "operation ID reused" in result.reason
    assert transport.document["notifications"]["n"]["sent"] is True


def test_conflict_rebases_independent_fields_once_without_losing_other_writer():
    transport = MemoryTransport({"results": {"d": {"id": "d", "candidate": False}}})
    def competing_write(t):
        t.document["bundles"] = {"b": {"documents": ["d"]}}
        t.revision += 1
    transport.on_write = competing_write
    result = store_patch(transport, "sidecar", owner="collection", patch={"results": {"d": {"candidate": True}}}, operation_id="c1")
    assert result.status == "APPLIED" and result.attempts == 2
    assert transport.document["bundles"]["b"]["documents"] == ["d"]
    assert transport.document["results"]["d"]["candidate"]


def test_concurrent_same_judgment_is_pending_even_for_different_fields():
    transport = MemoryTransport({"reviews": {}})
    def competing_write(t):
        t.document["reviews"]["r"] = {"stage": "S2", "note": "theirs"}
        t.revision += 1
    transport.on_write = competing_write
    result = store_patch(transport, "sidecar", owner="review", patch={"reviews": {"r": {"stage": "S1", "note": "mine"}}}, operation_id="r1")
    assert result.status == "PENDING" and result.reason == "SAME_ITEM_CONFLICT"
    assert transport.document["reviews"]["r"] == {"stage": "S2", "note": "theirs"}
    assert "operations" not in transport.document


def test_concurrent_append_of_different_history_entries_is_preserved():
    transport = MemoryTransport({"targets": [{"id": "t", "history": [{"review_id": "old"}]}]})
    def competing_write(t):
        t.document["targets"][0]["history"].append({"review_id": "other"})
        t.revision += 1
    transport.on_write = competing_write
    result = store_patch(transport, "sidecar", owner="review", patch={"targets": [{"id": "t", "history": [{"review_id": "mine"}]}]}, operation_id="r1")
    assert result.status == "APPLIED"
    assert [x["review_id"] for x in transport.document["targets"][0]["history"]] == ["old", "other", "mine"]


@pytest.mark.parametrize("failure", ["fail_readback", "corrupt_readback"])
def test_readback_failure_does_not_report_applied_and_retry_is_idempotent(failure):
    transport = MemoryTransport({})
    setattr(transport, failure, True)
    args = dict(owner="notification", patch={"notifications": {"n": {"sent": True}}}, operation_id="n1")
    first = store_patch(transport, "sidecar", **args)
    assert first.status == "PENDING" and "READBACK" in first.reason
    setattr(transport, failure, False)
    assert store_patch(transport, "sidecar", **args).status == "ALREADY_APPLIED"
    assert transport.writes == 1


def test_version_references_accept_preserved_version_and_reject_wrong_hash_or_range():
    state = {"results": {"d": {"current_body_sha256": "new", "versions": {"old": {"body_sha256": "old"}}}}}
    ref = {"document_id": "d", "body_sha256": "old", "reader_version": "r1", "start": 0, "end": 100}
    validate_version_refs(state, [ref])
    with pytest.raises(PatchError):
        validate_version_refs(state, [ref], current_only=True)
    for change in ({"body_sha256": "absent"}, {"document_id": "absent"}, {"start": 101}):
        with pytest.raises(PatchError):
            validate_version_refs(state, [{**ref, **change}])
    transport = MemoryTransport({"version": 1})
    result = store_patch(transport, "tracking", owner="review", patch={"reviews": {"r": {"stage": "S1"}}}, operation_id="r1", version_refs=[ref], reference_document=state)
    assert result.status == "APPLIED"


def test_invalid_ownership_immutable_bundle_and_body_version_are_rejected():
    with pytest.raises(PatchError):
        apply_owned_patch({}, owner="collection", patch={"reviews": {}}, operation_id="c1")
    with pytest.raises(PatchError):
        apply_owned_patch({}, owner="collection", patch={"results": {"d": {"progress": 99}}}, operation_id="c1")
    before = {"bundles": {"b": {"documents": [{"document_id": "d", "body_sha256": "old"}]}}}
    with pytest.raises(PatchError):
        apply_owned_patch(before, owner="bundle", patch={"bundles": {"b": {"documents": [{"document_id": "d", "body_sha256": "new"}]}}}, operation_id="b1")
    before = {"results": {"d": {"versions": {"old": {"body_sha256": "old", "source_version": "v1"}}}}}
    with pytest.raises(PatchError):
        apply_owned_patch(before, owner="collection", patch={"results": {"d": {"versions": {"old": {"body_sha256": "new"}}}}}, operation_id="c1")


def test_existing_history_entry_cannot_be_silently_rewritten():
    before = {"targets": [{"id": "t", "history": [{"review_id": "r0", "status": "S1"}]}]}
    with pytest.raises(PatchError):
        apply_owned_patch(before, owner="review", patch={"targets": [{"id": "t", "history": [{"review_id": "r0", "status": "S3"}]}]}, operation_id="r1")
    assert before["targets"][0]["history"][0]["status"] == "S1"


def test_twice_conflicting_transport_stops_after_one_retry():
    class AlwaysConflict(MemoryTransport):
        def write(self, path, document, expected_sha):
            self.writes += 1
            self.revision += 1
            raise StoreConflict("continually changing")
    transport = AlwaysConflict({})
    result = store_patch(transport, "sidecar", owner="notification", patch={"notifications": {"n": {"sent": True}}}, operation_id="n1")
    assert result.status == "PENDING" and result.reason == "SHA_CONFLICT_AFTER_RETRY"
    assert transport.writes == result.attempts == 2


def test_local_sha_atomic_write_and_stale_write_preserve_file(tmp_path):
    path = tmp_path / "future-tracking.json"
    path.write_text(json.dumps({"version": 1, "unknown": [1, 2]}))
    transport = LocalJSONTransport()
    stale = transport.read(path)
    result = patch_json(path, owner="review", patch={"reviews": {"r": {"stage": "S1"}}}, operation_id="r1")
    assert result.status == "APPLIED" and json.loads(path.read_text())["unknown"] == [1, 2]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(StoreConflict):
        transport.write(path, {"replace": True}, stale.sha)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert not list(tmp_path.glob("*.tmp"))


def test_current_screen_fields_replace_stale_signals_without_deleting_old_body_versions():
    old = {"body_sha256": "old", "screening": {"discovery_paths": ["RELIEF"], "evidence": {"RELIEF": ["old expansion"]}}}
    before = {"results": {"d": {"current_body_sha256": "old", "discovery_paths": ["RELIEF"],
        "targets": [{"name": "old target"}], "evidence": {"RELIEF": ["old expansion"]},
        "unknown": ["retain"], "versions": {"old": old}}}}
    patch = {"results": {"d": {"current_body_sha256": "new", "discovery_paths": ["DEMAND"],
        "targets": [], "evidence": {"DEMAND": ["new order"]},
        "versions": {"new": {"body_sha256": "new", "screening": {"discovery_paths": ["DEMAND"]}}}}}}
    merged = apply_owned_patch(before, owner="collection", patch=patch, operation_id="c2")
    record = merged["results"]["d"]
    assert record["discovery_paths"] == ["DEMAND"] and record["targets"] == []
    assert record["evidence"] == {"DEMAND": ["new order"]}
    assert record["versions"]["old"] == old and record["unknown"] == ["retain"]


def test_same_body_rescreen_replaces_current_filter_evidence_only():
    before = {"results": {"d": {"versions": {"hash": {"body_sha256": "hash", "source_version": "v1",
        "screening": {"discovery_paths": ["RELIEF"], "evidence": {"RELIEF": ["old"]}},
        "screening_history": [{"filter_version": "old"}]}}}}}
    patch = {"results": {"d": {"versions": {"hash": {"screening": {"discovery_paths": ["DEMAND"], "evidence": {"DEMAND": ["new"]}}}}}}}
    record = apply_owned_patch(before, owner="collection", patch=patch, operation_id="c3")["results"]["d"]["versions"]["hash"]
    assert record["screening"] == {"discovery_paths": ["DEMAND"], "evidence": {"DEMAND": ["new"]}}
    assert record["source_version"] == "v1" and record["screening_history"] == [{"filter_version": "old"}]


def test_saved_reviews_and_initial_prediction_cannot_be_overwritten_by_generic_store():
    before = {"reviews": {"r": {"stage": "S1"}}, "prediction_ledger": {"t": {"initial": {"hypothesis": "first", "frozen": True}}}}
    for patch in ({"reviews": {"r": {"stage": "S3"}}}, {"prediction_ledger": {"t": {"initial": {"hypothesis": "overwrite"}}}}):
        result = store_patch(MemoryTransport(before), "tracking", owner="review", patch=patch, operation_id="new")
        assert result.status == "PENDING" and "immutable" in result.reason


@pytest.mark.parametrize('owner,prepared,latest,patch', [
    ('collection', {'results': {'d': {'current_body_sha256': 'old'}}},
     {'results': {'d': {'current_body_sha256': 'new'}}},
     {'results': {'d': {'current_body_sha256': 'old'}}}),
    ('notification', {'notifications': {'n': {'state': 'READY'}}},
     {'notifications': {'n': {'state': 'RECEIVED'}}},
     {'notifications': {'n': {'state': 'SENT'}}}),
])
def test_prepared_context_blocks_changes_that_became_stale_before_transport_read(owner, prepared, latest, patch):
    transport = MemoryTransport(latest)
    result = store_patch(transport, 'sidecar', owner=owner, patch=patch,
                         operation_id='stale', prepared_document=prepared)
    assert result.status == 'PENDING' and result.reason == 'SAME_ITEM_CONFLICT'
    assert transport.writes == 0 and transport.document == latest
    with pytest.raises(PatchError, match='SAME_ITEM_CONFLICT'):
        apply_owned_patch(latest, owner=owner, patch=patch, operation_id='stale',
                          prepared_document=prepared)


def test_prepared_context_preserves_independent_changes_and_one_cas_rebase():
    prepared = {'results': {'d': {'candidate': False}}}
    transport = MemoryTransport({**prepared, 'notifications': {'n': {'state': 'RECEIVED'}}})
    def competing_write(t):
        t.document['bundles'] = {'b': {'documents': ['d']}}
        t.revision += 1
    transport.on_write = competing_write
    result = store_patch(transport, 'sidecar', owner='collection',
                         patch={'results': {'d': {'candidate': True}}}, operation_id='collect',
                         prepared_document=prepared)
    assert result.status == 'APPLIED' and result.attempts == 2
    assert transport.document['results']['d']['candidate']
    assert transport.document['notifications']['n']['state'] == 'RECEIVED'
    assert transport.document['bundles']['b']['documents'] == ['d']
    assert 'prepared_document' not in transport.document
    repeated = store_patch(transport, 'sidecar', owner='collection',
                           patch={'results': {'d': {'candidate': True}}}, operation_id='collect',
                           prepared_document=prepared)
    assert repeated.status == 'ALREADY_APPLIED' and transport.writes == 2
