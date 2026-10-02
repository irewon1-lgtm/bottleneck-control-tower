"""Request-driven review queues over the existing JSON sidecars.

No model is called here. A reviewer reads source documents, then submits actual
reading ranges and evidence-backed decisions. Completion is derived from saved
reviews; opening a bundle or sending a notification never completes a document.
"""
import argparse
import calendar
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .future_store import LocalJSONTransport, PatchError, apply_owned_patch, store_patch, validate_version_refs


READER_VERSION = "bct-v33-reader-1"
FINAL_DISPOSITIONS = frozenset({"CHANGE", "RELIEF", "DEEP_NEEDED", "IRRELEVANT", "DATA_INSUFFICIENT"})


def _now(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _hash(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def progress_key(document_id, body_sha256, reader_version=READER_VERSION):
    return f"{document_id}:{body_sha256}:{reader_version}"


def _status(value):
    # Legacy BODY_OK used length-based extraction and never established FULL.
    return {"BODY_OK": "PARTIAL", "BODY_UNAVAILABLE": "UNAVAILABLE"}.get(value, value or "UNAVAILABLE")


def _records(candidates):
    for document_id, record in candidates.get("results", {}).items():
        current = record.get("current_body_sha256") or record.get("body_sha256")
        versions = record.get("versions", {})
        versions = versions if isinstance(versions, dict) else {}
        hashes = list(versions)
        if current and current not in hashes:
            hashes.append(current)
        for body_hash in hashes:
            version = deepcopy(versions.get(body_hash, {}))
            if body_hash == current:
                version = {**record, **version}
            version.update(version.get("screening", {}))
            yield {**version, "document_id": document_id, "body_sha256": body_hash,
                   "url": record.get("url"), "title": record.get("title"),
                   "body_status": _status(version.get("body_status")),
                   "queue_entered_at": version.get("queue_entered_at") or record.get("queue_entered_at") or record.get("collected_at"),
                   "source_version": version.get("source_version") or record.get("source_version")}
        if not hashes or _status(record.get("body_status")) == "UNAVAILABLE":
            yield {**record, "document_id": document_id, "body_sha256": None, "body_status": "UNAVAILABLE",
                   "queue_entered_at": record.get("queue_entered_at") or record.get("collected_at")}


def _matching_reviews(tracking, item, reader_version):
    return [r for r in tracking.get("reviews", {}).values() if isinstance(r, dict)
            and r.get("document_id") == item["document_id"]
            and r.get("body_sha256") == item["body_sha256"]
            and r.get("reader_version") == reader_version
            and r.get("kind") in ("quick", "deep")]


def _review_order(review):
    # A bulk execution can legitimately timestamp quick and deep records at
    # the same instant. The deeper terminal judgment then supersedes quick.
    return (review.get("reviewed_at", ""), review.get("kind") == "deep", review.get("review_id", ""))


def _coverage(reviews, body_chars):
    ranges = sorted((r.get("read_start"), r.get("read_end")) for r in reviews
                    if all(isinstance(r.get(k), int) and not isinstance(r.get(k), bool) for k in ("read_start", "read_end"))
                    and 0 <= r["read_start"] <= r["read_end"] <= body_chars)
    position = 0
    for start, end in ranges:
        if start > position:
            break
        position = max(position, end)
    return position


def reading_position(tracking, item, reader_version=READER_VERSION):
    chars = item.get("body_chars", 0)
    chars = chars if isinstance(chars, int) and chars >= 0 else 0
    return _coverage(_matching_reviews(tracking, item, reader_version), chars)


def _access_status(tracking, item, reader_version):
    records = [r for r in tracking.get("reviews", {}).values() if isinstance(r, dict)
               and r.get("kind") == "access" and r.get("document_id") == item["document_id"]
               and r.get("body_sha256") == item["body_sha256"] and r.get("reader_version") == reader_version]
    if records:
        return max(records, key=lambda r: (r.get("reviewed_at", ""), r.get("review_id", ""))).get("access_status")
    # Only an explicit acquisition/reaccess outcome is used here; a different
    # current body hash by itself does not prove that the old body is inaccessible.
    status = item.get("reaccess_status") or item.get("access_status")
    return "BLOCKED" if status == "UNAVAILABLE" else status


def document_complete(tracking, item, reader_version=READER_VERSION):
    chars = item.get("body_chars", 0)
    if not item.get("body_sha256") or not isinstance(chars, int) or chars <= 0:
        return False
    reviews = _matching_reviews(tracking, item, reader_version)
    return (_coverage(reviews, chars) == chars
            and any(r.get("disposition") in FINAL_DISPOSITIONS and r.get("read_end") == chars for r in reviews))


def _wait_hours(item, now):
    try:
        return round(max(0, (now - _now(item.get("queue_entered_at"))).total_seconds() / 3600), 2)
    except (TypeError, ValueError, AttributeError):
        return None


def queue_items(candidates, tracking, *, now=None, reader_version=READER_VERSION):
    clock = _now(now)
    quick, material, completed = [], [], []
    for raw in _records(candidates):
        eligible = bool(raw.get("candidate") or raw.get("tracked_matches") or raw["body_status"] in ("PARTIAL", "UNAVAILABLE"))
        if not eligible:
            continue
        item = {**raw, "reader_version": reader_version, "wait_hours": _wait_hours(raw, clock),
                "resume_at": reading_position(tracking, raw, reader_version)}
        item["access_status"] = _access_status(tracking, item, reader_version)
        blocked = item["access_status"] in ("BLOCKED", "SOURCE_CHANGED")
        if raw["body_status"] in ("PARTIAL", "UNAVAILABLE") or blocked:
            material.append(item)
        if document_complete(tracking, item, reader_version):
            completed.append(item)
        elif not blocked and item.get("body_sha256") and isinstance(item.get("body_chars"), int) and item["body_chars"] > 0:
            quick.append(item)
    quick.sort(key=lambda x: (x.get("queue_entered_at") or "", x["document_id"], x["body_sha256"]))
    deep, data_wait = [], []
    for item in completed:
        reviews = _matching_reviews(tracking, item, reader_version)
        semantic = [r for r in reviews if r.get("disposition") in FINAL_DISPOSITIONS]
        latest = max(semantic, key=_review_order)
        deep_reviews = [r for r in reviews if r.get("kind") == "deep"]
        latest_deep = max(deep_reviews, key=_review_order) if deep_reviews else None
        deep_unfinished = latest_deep and latest_deep.get("analysis_complete") is not True
        requested_after_completion = (latest.get("disposition") == "DEEP_NEEDED" and
            (not latest_deep or latest_deep.get("reviewed_at", "") < latest.get("reviewed_at", "")))
        if deep_unfinished or requested_after_completion:
            deep.append(item)
        if latest.get("disposition") == "DATA_INSUFFICIENT" or latest.get("candidate_state") == "DATA_WAIT":
            data_wait.append(item)
    return {"quick": quick, "material": material, "completed": completed, "deep": deep, "data_wait": data_wait}


def _canonical_url(value):
    try:
        parsed = urlsplit(value or "")
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            return None
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, ""))
    except ValueError:
        return None


def event_groups(candidates):
    """Only exact bodies or an explicitly confirmed event identity are joined.

    A URL with a changed body and a cancellation/correction remains a distinct
    change. No title similarity or inferred company/product relation is used.
    """
    records = list(_records(candidates))
    by_reference = {(x["document_id"], x.get("body_sha256")): x for x in records}
    confirmations, assignments = {}, {}
    # The bundle writer owns events, so persisted confirmations are the normal
    # reachable path. Recollection can update results without deleting these.
    for event_id, stored in candidates.get("events", {}).items():
        if not isinstance(stored, dict) or stored.get("confirmed") is not True or not stored.get("event_key"):
            continue
        refs = stored.get("documents", [])
        if not isinstance(refs, list) or not refs:
            continue
        try:
            validate_version_refs(candidates, refs)
        except PatchError:
            continue  # An invalid/ambiguous confirmation cannot merge events.
        token = (str(stored["event_key"]), str(stored.get("change_kind", "ORIGINAL")))
        confirmations.setdefault(token, []).append((event_id, stored))
        for ref in refs:
            key = (ref["document_id"], ref["body_sha256"])
            if key in by_reference:
                assignments.setdefault(key, set()).add(token)
    body_tokens = {}
    for reference, tokens in assignments.items():
        if len(tokens) == 1:
            body_tokens.setdefault(reference[1], set()).update(tokens)
    groups = {}
    for item in records:
        body_hash = item.get("body_sha256")
        tokens = assignments.get((item["document_id"], body_hash), set())
        if not tokens and body_hash:
            tokens = body_tokens.get(body_hash, set())
        authoritative = next(iter(tokens)) if len(tokens) == 1 else None
        confirmed = item.get("event_confirmed") is True and item.get("event_key")
        if authoritative:
            key = ["CONFIRMED_EVENT", *authoritative]
        elif confirmed and not tokens:
            key = ["CONFIRMED_EVENT", item["event_key"], item.get("change_kind", "ORIGINAL")]
        elif body_hash:
            key = ["EXACT_BODY", body_hash]
        else:
            canonical = _canonical_url(item.get("canonical_url") or item.get("url"))
            key = ["UNREAD_DOCUMENT", canonical or item["document_id"], item.get("source_version")]
        event_id = "event-" + _hash(key)[:24]
        prior = {}
        if authoritative:
            event_id, prior = min(confirmations[authoritative], key=lambda x: x[0])
        event = groups.setdefault(event_id, {**deepcopy(prior), "id": event_id, "basis": key[0], "documents": []})
        if key[0] == "CONFIRMED_EVENT":
            event.update(confirmed=True, event_key=key[1], change_kind=key[2])
        ref = {"document_id": item["document_id"], "body_sha256": body_hash}
        if not body_hash:
            ref["source_version"] = item.get("source_version")
        if ref not in event["documents"]:
            event["documents"].append(ref)
    return groups


def event_confirmation_patch(candidates, event_id, document_refs, *, event_key=None,
                             change_kind="ORIGINAL", evidence=None):
    """A reviewed same-event relationship, stored through the bundle owner."""
    if not isinstance(event_id, str) or not event_id or change_kind not in ("ORIGINAL", "CORRECTION", "CANCELLATION", "INCREASE", "DECREASE"):
        raise PatchError("invalid confirmed event identity/change kind")
    refs = [{"document_id": ref.get("document_id"), "body_sha256": ref.get("body_sha256")} for ref in document_refs]
    if not refs:
        raise PatchError("confirmed event requires document references")
    validate_version_refs(candidates, refs)
    prior = candidates.get("events", {}).get(event_id, {})
    identity = event_key or event_id
    if prior.get("confirmed") is True and (prior.get("event_key") != identity or prior.get("change_kind", "ORIGINAL") != change_kind):
        raise PatchError("existing confirmed event cannot be rebound to another change")
    event = {"id": event_id, "confirmed": True, "event_key": identity,
             "change_kind": change_kind, "documents": refs}
    if evidence is not None:
        event["evidence"] = deepcopy(evidence)
    return {"events": {event_id: event}}


def queue_summary(candidates, tracking, *, now=None, reader_version=READER_VERSION):
    clock = _now(now)
    queues = queue_items(candidates, tracking, now=clock, reader_version=reader_version)
    records = list(_records(candidates))
    waits = [x["wait_hours"] for name in ("quick", "material", "deep", "data_wait") for x in queues[name] if x["wait_hours"] is not None]
    preview = [{k: item.get(k) for k in ("document_id", "body_sha256", "url", "title", "body_status", "discovery_paths", "wait_hours", "resume_at")}
               | {"kind": "quick"} for item in queues["quick"][:5]]
    if len(preview) < 5:
        shown = {(x["document_id"], x["body_sha256"]) for x in preview}
        preview.extend({k: item.get(k) for k in ("document_id", "body_sha256", "url", "title", "body_status", "discovery_paths", "wait_hours", "resume_at")}
                       | {"kind": "material"} for item in queues["material"] if (item["document_id"], item["body_sha256"]) not in shown)
        preview = preview[:5]
    return {"computed_at": clock.isoformat(), "reader_version": reader_version,
            "documents_total": len(candidates.get("results", {})), "preserved_versions": len(records),
            "automatic_candidates": sum(bool(x.get("candidate")) for x in records),
            "review_list_versions": len({(x["document_id"], x.get("body_sha256") or x.get("source_version")) for name in ("quick", "completed", "material") for x in queues[name]}),
            "quick_pending": len(queues["quick"]), "completed_documents": len(queues["completed"]),
            "deep_pending": len(queues["deep"]), "candidate_data_wait": len(queues["data_wait"]),
            "material_pending": len(queues["material"]), "oldest_wait_hours": max(waits) if waits else 0,
            "event_count": len(event_groups(candidates)), "preview": preview}


def full_queue_entries(candidates, tracking, *, now=None, reader_version=READER_VERSION):
    """All real review-list entries, including inaccessible material tasks."""
    queues = queue_items(candidates, tracking, now=now, reader_version=reader_version)
    entries = {}
    for name, kind in (("quick", "QUICK"), ("completed", "QUICK"), ("material", "MATERIAL"), ("deep", "DEEP")):
        for item in queues[name]:
            key = (item["document_id"], item.get("body_sha256"), item.get("source_version"))
            entries.setdefault(key, {"document_id": item["document_id"], "body_sha256": item.get("body_sha256"),
                "source_version": item.get("source_version"), "kind": kind,
                "entered_at": item.get("queue_entered_at")})
    return list(entries.values())


def build_bundle(candidates, tracking, *, bundle_id=None, max_documents=10, max_chars=12000,
                 now=None, reader_version=READER_VERSION):
    if not 1 <= max_documents <= 10 or not 1 <= max_chars <= 12000:
        raise PatchError("invalid lightweight bundle bounds")
    pending = queue_items(candidates, tracking, now=now, reader_version=reader_version)["quick"]
    if not pending:
        return None
    # One FIFO slot is always reserved; urgent relief gets at most two slots.
    selected = [pending[0]]
    urgent = [x for x in pending[1:] if "RELIEF" in x.get("discovery_paths", []) or x.get("important_refutation")]
    selected.extend(urgent[:min(2, max_documents - 1)])
    selected.extend(x for x in pending[1:] if x not in selected)
    refs, budget = [], max_chars
    selected = selected[:max_documents]
    for index, item in enumerate(selected):
        if len(refs) >= max_documents or budget <= 0:
            break
        start, chars = item["resume_at"], item["body_chars"]
        if start >= chars:
            # A full read without a final decision needs a zero-length decision
            # checkpoint, rather than silently becoming completed.
            end = start
        else:
            remaining = selected[index + 1:]
            reserve = sum(min(1000, max(0, x["body_chars"] - x["resume_at"])) for x in remaining)
            allowance = max(1, budget - min(budget - 1, reserve))
            end = min(chars, start + allowance)
        refs.append({"document_id": item["document_id"], "body_sha256": item["body_sha256"],
                     "reader_version": reader_version, "start": start, "end": end,
                     "url": item.get("url"), "body_status": item["body_status"]})
        budget -= end - start
    frozen_id = bundle_id or "bundle-" + _hash(refs)[:24]
    return {"id": frozen_id, "created_at": _now(now).isoformat(), "documents": refs,
            "max_documents": max_documents, "max_chars": max_chars}


def ensure_bundle(candidates, tracking, **kwargs):
    reader = kwargs.get("reader_version", READER_VERSION)
    queues = queue_items(candidates, tracking, reader_version=reader)
    blocked = {(x["document_id"], x.get("body_sha256")) for x in queues["material"] if x.get("access_status") in ("BLOCKED", "SOURCE_CHANGED")}
    for bundle in candidates.get("bundles", {}).values():
        refs = bundle.get("documents", [])
        if not refs or any(ref.get("reader_version") != reader for ref in refs):
            continue
        if any((ref["document_id"], ref.get("body_sha256")) in blocked for ref in refs):
            continue
        try:
            validate_version_refs(candidates, refs)
        except PatchError:
            continue
        pending = False
        for ref in refs:
            item = _version_item(candidates, ref["document_id"], ref["body_sha256"])
            position = reading_position(tracking, item, reader)
            pending |= position < ref["end"] or (ref["start"] == ref["end"] and not document_complete(tracking, item, reader))
        if pending:
            return {"bundles": {bundle["id"]: deepcopy(bundle)}, "events": event_groups(candidates)}
    bundle = build_bundle(candidates, tracking, **kwargs)
    return {"bundles": {bundle["id"]: bundle} if bundle else {}, "events": event_groups(candidates)}


def _version_item(candidates, document_id, body_hash):
    item = next((x for x in _records(candidates) if x["document_id"] == document_id and x["body_sha256"] == body_hash), None)
    if not item:
        raise PatchError("reviewed body version is not preserved")
    return item


def _gate_value(gate):
    if not isinstance(gate, dict) or gate.get("value") not in ("TRUE", "FALSE", "UNKNOWN"):
        raise PatchError("gate requires TRUE/FALSE/UNKNOWN")
    if gate["value"] in ("TRUE", "FALSE"):
        evidence = gate.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            raise PatchError("confirmed or refuted gate requires evidence locations")
        for source in evidence:
            if not isinstance(source, dict) or not source.get("locator"):
                raise PatchError("gate evidence requires a locator")
            if "url" in source and not _canonical_url(source["url"]):
                raise PatchError("invalid evidence source URL")
    return gate["value"]


def _earned_stage(review):
    gates = review.get("gates", {})
    values = {key: _gate_value(value) for key, value in gates.items()}
    change = values.get("change", "UNKNOWN")
    stage = "S1" if change == "TRUE" else "NONE"
    if stage == "S1" and values.get("target_relation") == "TRUE" and review.get("target"):
        stage = "S2"
    path = review.get("discovery_path")
    if path not in ("DEMAND", "SUPPLY"):
        raise PatchError("deep review requires DEMAND or SUPPLY discovery path")
    needed = ("future_demand", "supply_constraint") if path == "DEMAND" else ("remaining_demand", "supply_gap")
    if stage != "S2" or not all(values.get(key) == "TRUE" for key in (*needed, "future_period", "relief_reviewed")):
        return stage
    period = review.get("period", {})
    try:
        start, end = date.fromisoformat(period["start"]), date.fromisoformat(period["end"])
        as_of = date.fromisoformat(review["as_of"])
    except (KeyError, TypeError, ValueError):
        return stage
    if not as_of < start <= end or review.get("temporal_status") != "FUTURE":
        return stage
    relief = review.get("relief", {})
    if not isinstance(relief, dict) or not relief:
        return stage
    for check in relief.values():
        if not isinstance(check, dict) or check.get("status") not in ("FOUND", "NOT_FOUND_IN_SCOPE", "INACCESSIBLE", "NOT_APPLICABLE") or not check.get("reason"):
            raise PatchError("relief checks require status and reason; search failure is not absence")
        if check.get("important", False) and (check["status"] == "INACCESSIBLE" or check.get("resolved") is not True):
            return stage
    return "S3"


def validate_review(candidates, tracking, review):
    """Validate submitted reading/evidence records, not the truth of source claims."""
    result = deepcopy(review)
    for key in ("review_id", "document_id", "body_sha256", "reader_version"):
        if not isinstance(result.get(key), str) or not result[key]:
            raise PatchError(f"review requires {key}")
    if any(key in result for key in ("body", "article_body", "full_text")):
        raise PatchError("article bodies do not belong in public review records")
    if result.get("kind") == "access":
        validate_version_refs(candidates, [{"document_id": result["document_id"], "body_sha256": result["body_sha256"], "reader_version": result["reader_version"]}])
        if result.get("access_status") not in ("BLOCKED", "SOURCE_CHANGED", "AVAILABLE") or not result.get("reason"):
            raise PatchError("access result requires explicit status and attempted-access reason")
        observed = result.get("observed_body_sha256")
        if result["access_status"] == "SOURCE_CHANGED" and (not observed or observed == result["body_sha256"]):
            raise PatchError("SOURCE_CHANGED requires the actually observed different hash")
        if result["access_status"] == "AVAILABLE" and observed != result["body_sha256"]:
            raise PatchError("AVAILABLE requires the actually recovered expected body hash")
        if any(key in result for key in ("read_start", "read_end", "read_complete", "analysis_complete")):
            raise PatchError("access attempts do not establish reading completion")
        previous = tracking.get("reviews", {}).get(result["review_id"])
        result["reviewed_at"] = result.get("reviewed_at") or (previous or {}).get("reviewed_at") or _now().isoformat()
        if previous and previous != result:
            raise PatchError("review IDs are immutable; append a new access record")
        return result
    if result.get("kind") not in ("quick", "deep"):
        raise PatchError("review kind must be quick, deep, or access")
    if result.get("disposition") not in FINAL_DISPOSITIONS | {"INCOMPLETE"}:
        raise PatchError("invalid quick-review disposition")
    ref = {"document_id": result["document_id"], "body_sha256": result["body_sha256"],
           "reader_version": result["reader_version"], "start": result.get("read_start"), "end": result.get("read_end")}
    validate_version_refs(candidates, [ref])
    item = _version_item(candidates, result["document_id"], result["body_sha256"])
    chars = item.get("body_chars")
    if not isinstance(chars, int) or chars <= 0 or result["read_end"] > chars:
        raise PatchError("review must reference a known readable body extent")
    position = reading_position(tracking, item, result["reader_version"])
    if result["read_start"] > position:
        raise PatchError("reading progress cannot skip an unread range")
    previous = tracking.get("reviews", {}).get(result["review_id"])
    result["reviewed_at"] = result.get("reviewed_at") or (previous or {}).get("reviewed_at") or _now().isoformat()
    result["as_of"] = result.get("as_of") or _now(result["reviewed_at"]).date().isoformat()
    result["read_complete"] = _coverage([*_matching_reviews(tracking, item, result["reader_version"]), result], chars) == chars
    result["source_access"] = {"url": item.get("url"), "body_sha256": result["body_sha256"],
                               "reproducibility_limit": item.get("reproducibility_limit") or "Source reaccess or runtime cache may be required."}
    if result.get("candidate_state") is None:
        result["candidate_state"] = "DATA_WAIT" if result["disposition"] == "DATA_INSUFFICIENT" else "REVIEWED"
    if result["kind"] == "deep":
        earned = _earned_stage(result)
        requested = result.get("s_stage", earned)
        if requested not in ("NONE", "S1", "S2", "S3") or ("NONE", "S1", "S2", "S3").index(requested) > ("NONE", "S1", "S2", "S3").index(earned):
            raise PatchError("requested S stage exceeds supported gates")
        result["s_stage"] = requested
        if result.get("analysis_complete") is True and (not result["read_complete"] or result["disposition"] == "INCOMPLETE"):
            raise PatchError("incomplete reading/analysis cannot be marked complete")
    elif result.get("s_stage") not in (None, "NONE"):
        raise PatchError("S stages belong to an evidence-backed deep review")
    if previous and previous != result:
        raise PatchError("review IDs are immutable; append a new review")
    return result


def review_patch(candidates, tracking, review):
    normalized = validate_review(candidates, tracking, review)
    if normalized["kind"] == "access":
        return {"reviews": {normalized["review_id"]: normalized}, "updated_at": normalized["reviewed_at"]}
    key = progress_key(normalized["document_id"], normalized["body_sha256"], normalized["reader_version"])
    item = _version_item(candidates, normalized["document_id"], normalized["body_sha256"])
    reviews = [*_matching_reviews(tracking, item, normalized["reader_version"]), normalized]
    patch = {"reviews": {normalized["review_id"]: normalized},
             "progress": {key: {"document_id": normalized["document_id"], "body_sha256": normalized["body_sha256"],
                                "reader_version": normalized["reader_version"], "read_end": _coverage(reviews, item["body_chars"]),
                                "last_review_id": normalized["review_id"]}},
             "updated_at": normalized["reviewed_at"]}
    prediction = normalized.get("prediction")
    if prediction is not None:
        if not isinstance(prediction, dict) or not prediction.get("target_id") or not prediction.get("hypothesis"):
            raise PatchError("prediction requires a stable TARGET ID and hypothesis")
        target_id = prediction["target_id"]
        entry = {**prediction, "id": normalized["review_id"], "recorded_at": normalized["reviewed_at"],
                 "document_id": normalized["document_id"], "body_sha256": normalized["body_sha256"],
                 "s_stage": normalized.get("s_stage", "NONE"), "discovery_path": normalized.get("discovery_path")}
        if "next_check_dates" not in entry:
            anchor = date.fromisoformat(normalized["as_of"])
            dates = []
            for months in (3, 6):
                year, zero_month = divmod(anchor.year * 12 + anchor.month - 1 + months, 12)
                month = zero_month + 1
                dates.append(anchor.replace(year=year, month=month, day=min(anchor.day, calendar.monthrange(year, month)[1])).isoformat())
            entry["next_check_dates"] = dates
        ledger = {"entries": [entry]}
        if not tracking.get("prediction_ledger", {}).get(target_id, {}).get("initial"):
            ledger["initial"] = {**entry, "first_discovered_at": normalized["reviewed_at"], "frozen": True}
        patch["prediction_ledger"] = {target_id: ledger}
        patch["targets"] = [{"id": target_id, "target": prediction.get("target", normalized.get("target", "미분류")),
            "history": [{"review_id": normalized["review_id"], "reviewed_on": normalized["as_of"],
                         "mode": "on_demand", "status": normalized.get("temporal_status", "UNRESOLVED"),
                         "s_stage": normalized.get("s_stage", "NONE"), "reason": prediction["hypothesis"],
                         "next_check": prediction.get("next_check_at"), "sources": prediction.get("sources", [])}]}]
    return patch


def save_review(transport, path, candidates, review, *, operation_id=None):
    latest = transport.read(path)
    patch = review_patch(candidates, latest.document, review)
    normalized = patch["reviews"][review["review_id"]]
    ref = {"document_id": normalized["document_id"], "body_sha256": normalized["body_sha256"], "reader_version": normalized["reader_version"]}
    if normalized["kind"] != "access":
        ref.update(start=normalized["read_start"], end=normalized["read_end"])
    return store_patch(transport, path, owner="review", patch=patch,
                       operation_id=operation_id or "review-" + normalized["review_id"],
                       version_refs=[ref], reference_document=candidates,
                       prepared_document=latest.document)


def notification_patch(candidates, tracking, *, now=None, notification_id=None):
    """Create a summary only for new versions/important changes, at most 2/day.

    Returns None when suppressed. READY/SENT/ACCEPTED/RECEIVED are distinct; this
    function neither sends anything nor asserts the user's actual receipt.
    """
    clock = _now(now)
    versions = sorted((x["document_id"], x.get("body_sha256") or x.get("source_version") or x.get("fingerprint") or "UNAVAILABLE")
                      for x in _records(candidates) if x.get("candidate") or x["body_status"] in ("PARTIAL", "UNAVAILABLE"))
    important = sorted(r.get("review_id", key) for key, r in tracking.get("reviews", {}).items() if r.get("important_refutation") is True)
    due_checks = set()
    for target_id, ledger in tracking.get("prediction_ledger", {}).items():
        for entry in [ledger.get("initial", {}), *ledger.get("entries", [])]:
            dates = [entry.get("next_check_at"), *entry.get("next_check_dates", [])]
            for value in dates:
                if not value:
                    continue
                try:
                    due = _now(value)
                except (TypeError, ValueError, AttributeError):
                    continue
                if due <= clock:
                    due_checks.add((target_id, str(value)))
    if not versions and not important and not due_checks:
        return None
    fingerprint = _hash({"versions": versions, "important_changes": important, "due_checks": sorted(due_checks)})
    prior = candidates.get("notifications", {})
    if any(n.get("fingerprint") == fingerprint for n in prior.values()):
        return None
    local = timezone(timedelta(hours=9))
    today = clock.astimezone(local).date()
    sent = 0
    for record in prior.values():
        if record.get("state") in ("SENT", "ACCEPTED", "RECEIVED") and record.get("sent_at"):
            if _now(record["sent_at"]).astimezone(local).date() == today:
                sent += 1
    if sent >= 2:
        return None
    notification_id = notification_id or "notification-" + fingerprint[:24]
    return {"notifications": {notification_id: {"id": notification_id, "created_at": clock.isoformat(),
        "fingerprint": fingerprint, "state": "READY", "summary": queue_summary(candidates, tracking, now=clock),
        "collection_completed_at": candidates.get("summary", {}).get("checked_at"),
        "data_updated_at": candidates.get("summary", {}).get("checked_at"),
        "due_checks": [{"target_id": target, "check_at": check_at} for target, check_at in sorted(due_checks)],
        "bundle_ids": list(candidates.get("bundles", {}))}}}


def delivery_patch(candidates, notification_id, *, state, at=None, receipt=None):
    record = candidates.get("notifications", {}).get(notification_id)
    if not record or state not in ("SENT", "ACCEPTED", "RECEIVED"):
        raise PatchError("unknown notification or delivery state")
    before = record.get("state", "READY")
    allowed = {"READY": {"SENT"}, "SENT": {"SENT", "ACCEPTED", "RECEIVED"},
               "ACCEPTED": {"ACCEPTED", "RECEIVED"}, "RECEIVED": {"RECEIVED"}}
    if state not in allowed[before] or (state == "RECEIVED" and not receipt):
        raise PatchError("actual receipt requires evidence; delivery states cannot regress")
    timestamp = {"SENT": "sent_at", "ACCEPTED": "accepted_at", "RECEIVED": "received_at"}[state]
    change = {"state": state, timestamp: record.get(timestamp) or _now(at).isoformat()}
    if receipt:
        change["receipt"] = receipt
    return {"notifications": {notification_id: change}}


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}


def _write_output(value, output=None):
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("summary", "bundle", "review-patch", "save-review", "notification"):
        option = sub.add_parser(command)
        option.add_argument("--candidates", required=True)
        option.add_argument("--tracking", required=True)
        option.add_argument("--output")
        if command in ("review-patch", "save-review"):
            option.add_argument("--review", required=True)
    args = parser.parse_args()
    candidates, tracking = _read(args.candidates), _read(args.tracking)
    if args.command == "summary":
        value = queue_summary(candidates, tracking)
    elif args.command == "bundle":
        patch = ensure_bundle(candidates, tracking)
        refs = [ref for bundle in patch["bundles"].values() for ref in bundle["documents"]]
        value = {"owner": "bundle", "patch": patch,
                 "operation_id": "bundle-" + _hash(patch)[:32], "version_refs": refs,
                 "prepared_document": candidates}
    elif args.command == "notification":
        patch = notification_patch(candidates, tracking)
        value = {"owner": "notification", "patch": patch, "operation_id": "notification-" + _hash(patch)[:32],
                 "prepared_document": candidates} if patch else {"suppressed": True}
    elif args.command == "save-review":
        result = save_review(LocalJSONTransport(), args.tracking, candidates, _read(args.review))
        value = {"status": result.status, "reason": result.reason, "sha": result.sha}
        _write_output(value, args.output)
        if result.status not in ("APPLIED", "ALREADY_APPLIED"):
            raise SystemExit(1)
        return
    else:
        review = _read(args.review)
        patch = review_patch(candidates, tracking, review)
        normalized = patch["reviews"][review["review_id"]]
        ref = {"document_id": normalized["document_id"], "body_sha256": normalized["body_sha256"], "reader_version": normalized["reader_version"]}
        if normalized["kind"] != "access":
            ref.update(start=normalized["read_start"], end=normalized["read_end"])
        value = {"owner": "review", "patch": patch, "operation_id": "review-" + review["review_id"], "version_refs": [ref],
                 "prepared_document": tracking}
    _write_output(value, args.output)


if __name__ == "__main__":
    main()
