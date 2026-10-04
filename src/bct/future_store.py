"""Preserving JSON patches for the existing future sidecars; no database writes.

GitHub adapters supply read(path) -> Snapshot and write(path, document, sha).
write must reject a stale SHA with StoreConflict. Collection, bundles, reviews
and notifications share this merge/verify procedure instead of replacing records.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Mapping, Protocol


COLLECTION_FIELDS = frozenset({
    "id", "external_id", "snippet", "title", "url", "source", "source_type", "collected_at", "updated_at",
    "fingerprint", "attempts", "checked_at", "body_status", "extraction_method",
    "body_chars", "body_sha256", "candidate", "decision", "reason", "evidence",
    "targets", "target_status", "final_bottleneck", "error", "retry_after",
    "versions", "current_body_sha256", "acquisition", "source_version",
    "filter_version", "discovery_paths", "tracked_matches", "queue_entered_at",
    "body_versions", "body_history", "canonical_url", "last_seen_at",
    "reasons", "completeness", "cache_access", "reproducibility",
    "material_check_required", "reproducibility_limit", "acquisition_status",
    "context_review", "evidence_locations", "quoted_word_count", "tracked_matches",
    "tracking_terms_sha256", "pending_tracking_terms_sha256", "screening_pending_for", "reaccess_status",
    "bottleneck_tags",
    "scope_facts", "supply_relationships", "published_at", "publication_precision", "publication_verified",
    "first_candidate_at", "origin_id", "origin_url", "origin_publisher", "provenance_verified",
    "provenance_evidence", "publication_evidence", "available_at", "public_snapshot_observed_at",
})
OWNER_ROOTS = {
    "collection": frozenset({"version", "schema_version", "filter_version", "start_at", "summary", "results", "operation_samples"}),
    "bundle": frozenset({"bundles", "events", "hypotheses"}),
    "review": frozenset({"reviews", "progress", "prediction_ledger", "targets", "runs", "updated_at"}),
    "notification": frozenset({"notifications"}),
}
_MISSING = object()


class PatchError(ValueError):
    """Invalid ownership, references, or attempted immutable-record changes."""


class StoreConflict(RuntimeError):
    """The transport rejected a stale expected SHA."""


@dataclass(frozen=True)
class Snapshot:
    document: dict
    sha: str


@dataclass(frozen=True)
class StoreResult:
    status: str
    reason: str | None = None
    sha: str | None = None
    attempts: int = 0
    document: dict | None = None


class JSONTransport(Protocol):
    def read(self, path: str) -> Snapshot: ...
    def write(self, path: str, document: dict, expected_sha: str) -> str | None: ...


@dataclass
class CallbackTransport:
    reader: Callable[[str], Snapshot]
    writer: Callable[[str, dict, str], str | None]

    def read(self, path):
        return self.reader(path)

    def write(self, path, document, expected_sha):
        return self.writer(path, document, expected_sha)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(item):
    if isinstance(item, dict):
        for field in ("id", "review_id", "operation_id"):
            if isinstance(item.get(field), str) and item[field]:
                return field, item[field]
    return None


def _screen_field(path):
    if len(path) == 3 and path[0] == "hypotheses" and path[2] == "current":
        return True
    fields = {"discovery_paths", "targets", "tracked_matches", "reasons", "evidence_locations", "evidence",
              "scope_facts", "supply_relationships", "bottleneck_tags"}
    if len(path) >= 3 and path[0] == "results":
        if path[2] in fields:
            return True
        if len(path) >= 5 and path[2] == "versions":
            return path[4] in fields or (len(path) >= 6 and path[4] == "screening" and path[5] in fields)
    return False


def deep_merge(existing, changes, *, _path=()):
    """Merge mappings; append/deduplicate lists, merging matching identified items.

    In particular, history and unknown fields survive. Deletion is deliberately
    unsupported. A patch never supplies a replacement document or target object.
    """
    # Current screening is a replaceable owned field; appending old signals
    # would silently retain RELIEF/targets after a changed body or filter.
    if _screen_field(_path):
        return deepcopy(changes)
    if isinstance(existing, dict) and isinstance(changes, dict):
        merged = deepcopy(existing)
        for key, value in changes.items():
            merged[key] = deep_merge(existing[key], value, _path=(*_path, key)) if key in existing else deepcopy(value)
        return merged
    if isinstance(existing, list) and isinstance(changes, list):
        merged = deepcopy(existing)
        for item in changes:
            identity = _identity(item)
            index = next((i for i, prior in enumerate(merged) if identity and _identity(prior) == identity), None)
            if index is not None:
                if _path and _path[-1] in ("history", "entries"):
                    if not _contains(merged[index], item):
                        raise PatchError("existing history entries are immutable; append a new review")
                else:
                    merged[index] = deep_merge(merged[index], item, _path=_path)
            elif item not in merged:
                merged.append(deepcopy(item))
        return merged
    if isinstance(existing, (dict, list)) != isinstance(changes, (dict, list)):
        raise PatchError("container replacement is not a preserving patch")
    return deepcopy(changes)


def validate_ownership(owner, patch, *, extra_collection_fields=()):
    if isinstance(patch, dict) and any(k in patch for k in ('objective_version', 'objective_sha256')):
        from .objective_lock import require_objective
        require_objective(patch)
    if owner not in OWNER_ROOTS or not isinstance(patch, dict):
        raise PatchError("unknown owner or non-object patch")
    if not set(patch) <= OWNER_ROOTS[owner]:
        raise PatchError("patch touches another writer's fields")
    if owner == "collection" and "results" in patch:
        if not isinstance(patch["results"], dict):
            raise PatchError("results must be keyed by document ID")
        allowed = COLLECTION_FIELDS | frozenset(extra_collection_fields)
        for document_id, record in patch["results"].items():
            if not isinstance(document_id, str) or not document_id or not isinstance(record, dict):
                raise PatchError("invalid document patch")
            if not set(record) <= allowed or ("id" in record and record["id"] != document_id):
                raise PatchError("collection patch touches unowned fields or mismatched ID")
    _canonical(patch)  # Also reject non-JSON values and non-finite numbers.


def validate_version_refs(candidate_state, refs, *, current_only=False):
    results = candidate_state.get("results", {})
    for ref in refs:
        if not isinstance(ref, Mapping):
            raise PatchError("invalid document version reference")
        document_id, body_hash = ref.get("document_id"), ref.get("body_sha256")
        if not isinstance(document_id, str) or not isinstance(body_hash, str) or not body_hash:
            raise PatchError("reference requires document ID and body hash")
        record = results.get(document_id)
        if not isinstance(record, dict):
            raise PatchError("referenced document is absent")
        current = record.get("current_body_sha256") or record.get("body_sha256")
        versions = record.get("versions", {})
        if body_hash != current and (current_only or not isinstance(versions, dict) or body_hash not in versions):
            raise PatchError("referenced body version is absent or stale")
        version = versions.get(body_hash, {}) if isinstance(versions, dict) else {}
        if isinstance(version, dict) and version.get("body_sha256", body_hash) != body_hash:
            raise PatchError("version key and body hash disagree")
        if "reader_version" in ref and (not isinstance(ref["reader_version"], str) or not ref["reader_version"]):
            raise PatchError("invalid reader version")
        if "start" in ref or "end" in ref:
            start, end = ref.get("start"), ref.get("end")
            if any(isinstance(x, bool) or not isinstance(x, int) for x in (start, end)) or not 0 <= start <= end:
                raise PatchError("invalid document reading range")
            chars = version.get("body_chars") if isinstance(version, dict) else None
            if chars is None and current == body_hash:
                chars = record.get("body_chars")
            if isinstance(chars, int) and end > chars:
                raise PatchError("reading range exceeds preserved document body")


def _immutable_records(existing, patch):
    for event_id, changes in patch.get("hypotheses", {}).items():
        prior = existing.get("hypotheses", {}).get(event_id, {})
        for field in ("id", "first_detected_at", "first_hypothesis_at", "first_s3", "detection_mode"):
            if field in prior and field in changes and prior[field] != changes[field]:
                raise PatchError("initial hypothesis identity/times are immutable")
    for review_id, changes in patch.get("reviews", {}).items():
        prior = existing.get("reviews", {}).get(review_id)
        if prior is not None and not _contains(prior, changes):
            raise PatchError("saved review IDs are immutable; append a new review")
    for target_id, changes in patch.get("prediction_ledger", {}).items():
        prior = existing.get("prediction_ledger", {}).get(target_id, {}).get("initial")
        if prior is not None and "initial" in changes and not _contains(prior, changes["initial"]):
            raise PatchError("initial prediction is immutable")
        first_s3 = existing.get("prediction_ledger", {}).get(target_id, {}).get("first_s3")
        if first_s3 is not None and 'first_s3' in changes and first_s3 != changes['first_s3']:
            raise PatchError('first S3 prediction is immutable')
    for bundle_id, changes in patch.get("bundles", {}).items():
        prior = existing.get("bundles", {}).get(bundle_id, {})
        for field in ("documents", "document_refs"):
            if field in prior and field in changes and prior[field] != changes[field]:
                raise PatchError("fixed bundle document references cannot change")
    # Source body versions and prediction/review history are append-only records.
    for document_id, changes in patch.get("results", {}).items():
        prior = existing.get("results", {}).get(document_id, {})
        for body_hash, version in changes.get("versions", {}).items():
            old = prior.get("versions", {}).get(body_hash, {})
            for field in ("body_sha256", "source_version"):
                if field in old and field in version and old[field] != version[field]:
                    raise PatchError("preserved body version cannot be rebound")


def _contains(actual, patch):
    if isinstance(patch, dict):
        return isinstance(actual, dict) and all(k in actual and _contains(actual[k], v) for k, v in patch.items())
    if isinstance(patch, list):
        return isinstance(actual, list) and all(any(_contains(a, p) for a in actual) for p in patch)
    return actual == patch


def _changed_conflict(base, latest, patch, *, _path=()):
    if _screen_field(_path):
        return base != latest and latest != patch
    if isinstance(patch, dict):
        if not isinstance(base, dict):
            base = {}
        if not isinstance(latest, dict):
            latest = {}
        return any(_changed_conflict(base.get(k, _MISSING), latest.get(k, _MISSING), v, _path=(*_path, k)) for k, v in patch.items())
    if isinstance(patch, list):
        # Independent appended history entries are safe; an existing entry with
        # the same review ID still receives the normal field conflict check.
        for item in patch:
            identity = _identity(item)
            if not identity:
                continue
            find = lambda values: next((v for v in values if _identity(v) == identity), _MISSING) if isinstance(values, list) else _MISSING
            if _changed_conflict(find(base), find(latest), item, _path=_path):
                return True
        return False
    return base != latest and latest != patch


def _matches_patch(actual, patch, *, _path=()):
    if _screen_field(_path):
        return actual == patch
    if isinstance(patch, dict):
        return isinstance(actual, dict) and all(k in actual and _matches_patch(actual[k], v, _path=(*_path, k)) for k, v in patch.items())
    return _contains(actual, patch)


def _judgment_conflict(base, latest, patch):
    for field in ("reviews", "progress"):
        for key, change in patch.get(field, {}).items():
            old, new = base.get(field, {}).get(key, _MISSING), latest.get(field, {}).get(key, _MISSING)
            if old != new and not _contains(new, change):
                return True
    return _changed_conflict(base, latest, patch)


def apply_owned_patch(document, *, owner, patch, operation_id, version_refs=(),
                      reference_document=None, extra_collection_fields=(),
                      prepared_document=None):
    """Pure preserving merge, also usable when the connector handles transport."""
    validate_ownership(owner, patch, extra_collection_fields=extra_collection_fields)
    if not isinstance(document, dict) or not isinstance(operation_id, str) or not operation_id.strip():
        raise PatchError("document and operation ID are required")
    digest = hashlib.sha256(_canonical({"owner": owner, "patch": patch}).encode()).hexdigest()
    operations = document.get("operations", {})
    if not isinstance(operations, dict):
        raise PatchError("operations must be an object")
    if operation_id in operations:
        if operations[operation_id].get("patch_sha256") != digest:
            raise PatchError("operation ID reused with a different patch")
        return deepcopy(document)
    if prepared_document is not None:
        if not isinstance(prepared_document, dict):
            raise PatchError("preparation context must be an object")
        if _judgment_conflict(prepared_document, document, patch):
            raise PatchError("SAME_ITEM_CONFLICT")
    _immutable_records(document, patch)
    merged = deep_merge(document, patch)
    validate_version_refs(reference_document if reference_document is not None else merged, version_refs)
    merged.setdefault("operations", {})[operation_id] = {
        "owner": owner, "patch_sha256": digest,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }
    return merged


def store_patch(transport, path, *, owner, patch, operation_id, version_refs=(),
                reference_document=None, extra_collection_fields=(),
                prepared_document=None):
    """Read/merge/CAS/readback with one rebase retry. Uncertain writes stay pending."""
    try:
        validate_ownership(owner, patch, extra_collection_fields=extra_collection_fields)
        snapshot = transport.read(path)
    except Exception as exc:
        return StoreResult("PENDING", f"READ_OR_PATCH_FAILED: {type(exc).__name__}: {exc}")
    # The patch may have been prepared before this fresh transport read. Keep
    # that original context through both attempts instead of resetting its base.
    baseline = deepcopy(prepared_document) if prepared_document is not None else snapshot.document
    for attempt in (1, 2):
        try:
            merged = apply_owned_patch(snapshot.document, owner=owner, patch=patch,
                                       operation_id=operation_id, version_refs=version_refs,
                                       reference_document=reference_document,
                                       extra_collection_fields=extra_collection_fields,
                                       prepared_document=baseline)
            if operation_id in snapshot.document.get("operations", {}):
                return StoreResult("ALREADY_APPLIED", sha=snapshot.sha, attempts=attempt - 1, document=snapshot.document)
            transport.write(path, merged, snapshot.sha)
        except StoreConflict:
            if attempt == 2:
                return StoreResult("PENDING", "SHA_CONFLICT_AFTER_RETRY", attempts=attempt)
            try:
                snapshot = transport.read(path)
            except Exception as exc:
                return StoreResult("PENDING", f"REBASE_READ_FAILED: {type(exc).__name__}", attempts=attempt)
            continue
        except PatchError as exc:
            if str(exc) == "SAME_ITEM_CONFLICT":
                return StoreResult("PENDING", "SAME_ITEM_CONFLICT", sha=snapshot.sha, attempts=attempt - 1)
            return StoreResult("PENDING", f"WRITE_OR_PATCH_FAILED: {type(exc).__name__}: {exc}", attempts=attempt)
        except Exception as exc:
            return StoreResult("PENDING", f"WRITE_OR_PATCH_FAILED: {type(exc).__name__}: {exc}", attempts=attempt)
        try:
            confirmed = transport.read(path)
            marker = confirmed.document.get("operations", {}).get(operation_id)
            if marker != merged["operations"][operation_id] or not _matches_patch(confirmed.document, patch):
                return StoreResult("PENDING", "READBACK_MISMATCH", sha=confirmed.sha, attempts=attempt)
            return StoreResult("APPLIED", sha=confirmed.sha, attempts=attempt, document=confirmed.document)
        except Exception as exc:
            return StoreResult("PENDING", f"READBACK_FAILED: {type(exc).__name__}", attempts=attempt)


class LocalJSONTransport:
    """Atomic local JSON writes with an advisory lock and SHA check.

    Use on working copies; GitHub transport uses its own conditional blob SHA.
    """
    def read(self, path):
        path = Path(path)
        raw = path.read_bytes() if path.exists() else b""
        document = json.loads(raw) if raw else {}
        if not isinstance(document, dict):
            raise PatchError("JSON sidecar must be an object")
        return Snapshot(document, hashlib.sha256(raw).hexdigest())

    def write(self, path, document, expected_sha):
        import fcntl
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_name(path.name + ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.read(path).sha != expected_sha:
                raise StoreConflict("local sidecar changed")
            raw = (_canonical(document) + "\n").encode("utf-8")
            fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                Path(temporary).unlink(missing_ok=True)
            return hashlib.sha256(raw).hexdigest()


def patch_json(path, **kwargs):
    return store_patch(LocalJSONTransport(), str(path), **kwargs)
