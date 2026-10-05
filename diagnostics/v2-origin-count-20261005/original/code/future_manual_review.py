"""Private manual-review exports and validated row-by-row imports.

Bodies are retained only in the private export/cache. Existing sidecar runs hold
the export digest and reservations, not source text or new analysis state.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid
from urllib.parse import urlsplit

from .future_bottleneck import fetch_html
from .future_reader import INSTRUCTIONS, SCHEMA, validate_output
from .future_review import event_groups, queue_items, queue_summary, save_review, validate_review, _records, READER_VERSION
from .future_store import PatchError, store_patch
from .future_worker import LOCK_ID, claim, recover_body, _owned, _patch, _runs


FORMAT = "bct-manual-review-v1"
REFERENCE_FIELDS = ("event_id", "document_id", "body_sha256", "source_version", "reader_version", "read_start")
RESULT_FIELDS = frozenset((*REFERENCE_FIELDS, "read_end", "disposition", "reason"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _existing_guidance():
    # Copy the repository's existing rules verbatim, rather than inventing a
    # manual-reader policy. The installed repository CLI is the export owner.
    guide = (Path(__file__).resolve().parents[2] / "docs" / "bct-v33-review.md").read_text(encoding="utf-8")
    return (guide.split("## 읽을 파일과 고정 참조", 1)[0]
            + "## 실제 본문과 읽은 범위" + guide.split("## 실제 본문과 읽은 범위", 1)[1].split("## 저장·검증 명령", 1)[0])


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _binding(candidates, item):
    record = candidates["results"][item["document_id"]]
    return _digest({"document_id": item["document_id"], "body_sha256": item["body_sha256"],
                    "source_version": item.get("source_version"), "body_chars": item["body_chars"],
                    "body_status": item["body_status"], "url": item.get("url"),
                    "current_hash": record.get("current_body_sha256") or record.get("body_sha256"),
                    "fingerprint": record.get("fingerprint"), "updated_at": record.get("updated_at")})


def _event_map(candidates):
    return {(ref["document_id"], ref.get("body_sha256")): event_id
            for event_id, event in event_groups(candidates).items() for ref in event["documents"]}


def _snapshot_item(candidates, row, case, manifest):
    """Check preserved local version, without treating reaccess as evidence."""
    record = candidates.get("results", {}).get(row["document_id"], {})
    current_hash = record.get("current_body_sha256") or record.get("body_sha256")
    item = next((x for x in _records(candidates)
                 if x["document_id"] == row["document_id"] and x["body_sha256"] == row["body_sha256"]), None)
    expected_current = manifest.get("current_body_sha256", row["body_sha256"])
    # Older export manifests contain only a digest of the original binding.
    # An unchanged binding may legitimately refer to a historical body version.
    if current_hash and current_hash != expected_current and (
            "current_body_sha256" in manifest or item is None
            or _binding(candidates, item) != manifest["binding_sha256"]):
        raise PatchError("SOURCE_CHANGED: current stored document hash differs from export")
    if item is None or item.get("source_version") != row["source_version"]:
        raise PatchError("preserved document/version mismatch")
    if item.get("body_chars") != len(case["body"]):
        raise PatchError("preserved document body length mismatch")
    if _event_map(candidates).get((row["document_id"], row["body_sha256"])) != row["event_id"]:
        raise PatchError("current event identity mismatch")
    return item


def _reviewed_events(candidates, tracking):
    mapping = _event_map(candidates)
    return {mapping[(r.get("document_id"), r.get("body_sha256"))]
            for r in tracking.get("reviews", {}).values() if isinstance(r, dict)
            and (r.get("document_id"), r.get("body_sha256")) in mapping}


def _reserved_events(tracking):
    events = set()
    for run in _runs(tracking).values():
        if not isinstance(run, dict):
            continue
        if run.get("state") == "EXPORTED_FOR_REVIEW":
            events.update(set(run.get("event_ids", [])) - set(run.get("imported_event_ids", [])))
        elif run.get("state") == "RUNNING" and run.get("event_id"):
            events.add(run["event_id"])
    return events


def _private_write(output, document):
    from .objective_lock import stamp_export
    document = stamp_export(document)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    fd, name = tempfile.mkstemp(dir=output.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Refuse to overwrite an existing user/export file.
        os.link(name, output)
    finally:
        Path(name).unlink(missing_ok=True)


def _release(transport, path, owner):
    latest = _owned(transport, path, owner)
    _patch(transport, path, {"runs": {LOCK_ID: {"state": "IDLE", "owner": owner, "released_at": _now()}}},
           "release-" + owner, latest)


def export_review_batch(transport, candidates_path, tracking_path, *, cache_dir, output,
                        limit=10, fetcher=fetch_html):
    from .objective_lock import objective_binding
    objective = objective_binding()
    if not 1 <= limit <= 50:
        raise ValueError("manual batch limit must be 1..50")
    if Path(output).exists():
        raise FileExistsError(output)
    batch_id = "manual-export-" + uuid.uuid4().hex
    properties = deepcopy(SCHEMA["properties"])
    for key in REFERENCE_FIELDS:
        properties[key] = {"type": "integer" if key == "read_start" else ["string", "null"] if key == "source_version" else "string"}
    batch = {**objective, "layer": "CONFIRMATION", "format": FORMAT, "batch_id": batch_id, "mode": "MANUAL_REVIEW", "exported_at": _now(),
             "existing_bct_v33_guidance": _existing_guidance(),
             "instructions": INSTRUCTIONS + "\nReturn one JSON object with batch_id and a results array. "
             "Copy each case's review_reference exactly. Read the full supplied body. "
             "Return only the allowed result fields; never invent a review for an inaccessible case.",
             "result_schema": {"type": "object", "properties": {
                 "batch_id": {"type": "string", "const": batch_id},
                 "results": {"type": "array", "items": {"type": "object", "properties": properties,
                             "required": sorted(RESULT_FIELDS), "additionalProperties": False}}},
                             "required": ["batch_id", "results"], "additionalProperties": False},
             "cases": [], "export_count": 0, "unreadable_count": 0}
    if not claim(transport, tracking_path, batch_id):
        batch["blocked_reason"] = "REVIEW_ALREADY_CLAIMED"
        _private_write(output, batch)
        return batch
    try:
        candidates = transport.read(candidates_path).document
        tracking = _owned(transport, tracking_path, batch_id)
        mapping = _event_map(candidates)
        excluded = _reviewed_events(candidates, tracking) | _reserved_events(tracking)
        examined = 0
        manifests = []
        items = queue_items(candidates, tracking)["quick"]
        # Existing verified caches make an export usable even when source DNS
        # or access is unavailable. Preserve queue order within each group.
        items.sort(key=lambda item: not (Path(cache_dir) / (item["body_sha256"] + ".txt")).is_file())
        for item in items:
            event_id = mapping[(item["document_id"], item["body_sha256"])]
            if event_id in excluded:
                continue
            examined += 1
            body, blocked = recover_body(item, cache_dir, fetcher)
            if blocked or body is None or len(body) != item["body_chars"]:
                batch["unreadable_count"] += 1
            else:
                excluded.add(event_id)  # An unreadable sibling does not hide a readable version.
                reference = {"event_id": event_id, "document_id": item["document_id"],
                             "body_sha256": item["body_sha256"], "source_version": item.get("source_version"),
                             "reader_version": READER_VERSION, "read_start": item["resume_at"]}
                metadata = {k: item.get(k) for k in ("published_at", "collected_at", "publication_precision",
                            "publication_verified", "targets", "tracked_matches", "discovery_paths",
                            "scope_facts", "supply_relationships", "evidence_locations", "completeness", "reasons")}
                case = {"review_reference": reference, "body_status": item["body_status"],
                        "title": item.get("title"), "url": item.get("url"),
                        "source": item.get("source") or urlsplit(item.get("url") or "").hostname,
                        "body_chars": len(body), "body": body, "metadata": metadata}
                batch["cases"].append(case)
                record = candidates["results"][item["document_id"]]
                manifests.append({**reference, "binding_sha256": _binding(candidates, item),
                                  "current_body_sha256": record.get("current_body_sha256") or record.get("body_sha256")})
            if len(batch["cases"]) == limit or examined == 1000:
                break
        batch["export_count"] = len(batch["cases"])
        if manifests:
            # Register the trusted file digest before releasing its reservations.
            latest = _owned(transport, tracking_path, batch_id)
            _patch(transport, tracking_path, {"runs": {batch_id: {
                "state": "EXPORTED_FOR_REVIEW", "export_sha256": _digest(batch), "exported_at": batch["exported_at"],
                "event_ids": [x["event_id"] for x in manifests], "cases": manifests,
            }}}, "register-" + batch_id, latest)
        try:
            _private_write(output, batch)
        except Exception:
            if manifests:
                latest = _owned(transport, tracking_path, batch_id)
                _patch(transport, tracking_path, {"runs": {batch_id: {"state": "ERROR"}}}, "file-failed-" + batch_id, latest)
            raise
        return batch
    finally:
        _release(transport, tracking_path, batch_id)


def import_review_results(transport, candidates_path, tracking_path, *, batch_path, results_path,
                          fetcher=fetch_html):
    # fetcher remains a compatible argument for existing callers, but manual
    # imports deliberately make no source requests. The export is immutable.
    batch = json.loads(Path(batch_path).read_text(encoding="utf-8"))
    from .objective_lock import require_objective
    require_objective(batch)
    # JSONL preserves row isolation even when one line is malformed JSON.
    path = Path(results_path)
    if path.suffix == ".jsonl":
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    rows.append(None)
    else:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or set(document) != {"batch_id", "results"} or document["batch_id"] != batch.get("batch_id"):
            raise PatchError("invalid result envelope/batch ID")
        rows = document["results"]
    if not isinstance(rows, list) or len(rows) > 50:
        raise PatchError("import expects at most 50 result rows")
    owner = "manual-import-" + uuid.uuid4().hex
    if not claim(transport, tracking_path, owner):
        return {"state": "BLOCKED", "reason": "REVIEW_ALREADY_CLAIMED", "saved": 0}
    report = {"state": "FINISHED", "saved": 0, "duplicates": 0, "rejected": 0, "rows": []}
    try:
        tracking = _owned(transport, tracking_path, owner)
        registered = _runs(tracking).get(batch.get("batch_id"), {})
        if (batch.get("format") != FORMAT or registered.get("export_sha256") != _digest(batch)
                or registered.get("state") not in {"EXPORTED_FOR_REVIEW", "FINISHED"}):
            raise PatchError("unregistered or altered export")
        manifests = {r["event_id"]: r for r in registered["cases"]}
        exported = {c["review_reference"]["event_id"]: c for c in batch["cases"]}
        for index, row in enumerate(rows, 1):
            result = {"row": index, "status": "REJECTED"}
            try:
                if not isinstance(row, dict) or set(row) != RESULT_FIELDS:
                    raise PatchError("invalid result fields")
                manifest = manifests.get(row["event_id"])
                if not manifest or any(row[k] != manifest[k] for k in REFERENCE_FIELDS):
                    raise PatchError("case/document/version mismatch")
                case = exported[row["event_id"]]
                if any(row[k] != case["review_reference"][k] for k in REFERENCE_FIELDS):
                    raise PatchError("export review reference mismatch")
                if (not isinstance(case["body"], str) or hashlib.sha256(case["body"].encode()).hexdigest() != row["body_sha256"]):
                    raise PatchError("exported body hash mismatch")
                if len(case["body"]) != case["body_chars"]:
                    raise PatchError("exported body length mismatch")
                decision = validate_output({k: row[k] for k in SCHEMA["required"]},
                                           {"read_start": row["read_start"], "expected_read_end": len(case["body"])})
                candidates = transport.read(candidates_path).document
                tracking = _owned(transport, tracking_path, owner)
                review_id = "manual-review-" + _digest([batch["batch_id"], row["event_id"], row["document_id"], row["body_sha256"]])[:32]
                reviewed = _reviewed_events(candidates, tracking)
                if review_id in tracking.get("reviews", {}) or row["event_id"] in reviewed:
                    result.update(status="DUPLICATE", reason="review already exists")
                    report["duplicates"] += 1
                else:
                    _snapshot_item(candidates, row, case, manifest)
                    item = next((x for x in queue_items(candidates, tracking)["quick"]
                                 if x["document_id"] == row["document_id"] and x["body_sha256"] == row["body_sha256"]), None)
                    if item is None:
                        raise PatchError("document is no longer pending quick review")
                    review = {**decision, "review_id": review_id, "document_id": row["document_id"],
                              "body_sha256": row["body_sha256"], "reader_version": READER_VERSION, "kind": "quick",
                              "read_start": row["read_start"], "reviewed_at": _now(),
                              "manual_event_id": row["event_id"], "manual_batch_id": batch["batch_id"]}
                    validate_review(candidates, tracking, review)
                    # Recheck the stored hash/version immediately before save.
                    latest_candidates = transport.read(candidates_path).document
                    _snapshot_item(latest_candidates, row, case, manifest)
                    saved = save_review(transport, tracking_path, latest_candidates, review)
                    if saved.status not in {"APPLIED", "ALREADY_APPLIED"}:
                        raise PatchError("review save not confirmed")
                    result.update(status="SAVED", review_id=review_id)
                    report["saved"] += 1
                if result["status"] in {"SAVED", "DUPLICATE"}:
                    tracking = _owned(transport, tracking_path, owner)
                    _patch(transport, tracking_path, {"runs": {batch["batch_id"]: {"imported_event_ids": [row["event_id"]]}}},
                           owner + "-row-" + str(index), tracking)
            except Exception as exc:
                # Only fixed validator errors or exception types are reported;
                # never provider/source responses or article text.
                result["reason"] = str(exc) if isinstance(exc, PatchError) else type(exc).__name__
                report["rejected"] += 1
            report["rows"].append(result)
        tracking = _owned(transport, tracking_path, owner)
        done = _runs(tracking)[batch["batch_id"]].get("imported_event_ids", [])
        if set(done) == set(manifests):
            tracking = _patch(transport, tracking_path, {"runs": {batch["batch_id"]: {"state": "FINISHED"}}},
                              owner + "-finished", tracking)
        candidates = transport.read(candidates_path).document
        summary = queue_summary(candidates, tracking)
        refreshed = store_patch(transport, candidates_path, owner="collection", patch={"summary": {"review_queue": summary}},
                                operation_id=owner + "-summary", prepared_document=candidates)
        report["summary_saved"] = refreshed.status in {"APPLIED", "ALREADY_APPLIED"}
        report["queue"] = summary
        return report
    finally:
        _release(transport, tracking_path, owner)
