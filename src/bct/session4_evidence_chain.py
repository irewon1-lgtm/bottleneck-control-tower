"""Session 4 evidence handoff: actual source -> held, traceable research record.

This is a source-only BACKFILL/SHADOW projection, not an approved forecast,
an AI model caller or an alternate operating sidecar. No article body/quotes
or private CPU output may enter its durable ledger or dashboard projection.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from . import precursor_evidence_graph as graph
from . import precursor_scope_reader as reader

FORMAT = "bct-session4-held-evidence-v1"
UNKNOWN = "UNKNOWN"
FIELDS = reader.FIELDS


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _source(document):
    required = ("document_id", "body", "body_sha256", "raw_sha256", "version",
                "origin_url", "origin_publisher", "published_at", "acquired_at")
    if any(not isinstance(document.get(k), str) or not document[k] for k in required):
        raise ValueError("SESSION4_EXACT_SOURCE_REQUIRED")
    if (sha(document["body"]) != document["body_sha256"]
            or document["version"] != document["body_sha256"]):
        raise ValueError("SESSION4_BODY_VERSION_HASH_MISMATCH")
    if document["provenance"] != "PASS" or document.get("provenance_verified") is not True:
        raise ValueError("SESSION4_ORIGINAL_PROVENANCE_NOT_VERIFIED")
    if not document["origin_url"].startswith("https://"):
        raise ValueError("SESSION4_ORIGIN_URL_INVALID")
    for k in ("published_at", "acquired_at"):
        dt = datetime.fromisoformat(document[k].replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("SESSION4_ORIGINAL_CLOCK_UNVERIFIED")
    return {k: document[k] for k in ("document_id", "body_sha256", "raw_sha256",
                                      "origin_url", "origin_publisher", "published_at", "acquired_at")}


def _cpu(trace, source):
    if not isinstance(trace, dict):
        return {"status": "NOT_OBSERVED", "blocker": "CPU_RECEIPT_NOT_AVAILABLE"}
    if any(trace.get(k) != source[k] for k in
           ("document_id", "body_sha256", "raw_sha256")):
        raise ValueError("SESSION4_CPU_SOURCE_IDENTITY_MISMATCH")
    counts = trace.get("window_counts", {})
    if (not isinstance(counts, dict)
            or any(type(counts.get(k)) is not int or counts[k] < 0
                   for k in ("total", "success", "failed", "unread"))
            or counts["success"] + counts["failed"] + counts["unread"] != counts["total"]):
        raise ValueError("SESSION4_CPU_WINDOW_COUNTS_INVALID")
    if trace.get("source_verification") != "EXACT_NATIVE_AND_BODY_HASHES":
        raise ValueError("SESSION4_CPU_SOURCE_VERIFICATION_MISSING")
    if trace.get("read_state") == "UNREAD" or counts["unread"]:
        blocker = "CPU_WINDOW_UNREAD"
    elif counts["failed"]:
        blocker = "CPU_WINDOW_FAILED"
    elif trace.get("read_state") != "COMPLETE" or not trace.get("model_read_producer"):
        # Completed window counts alone do not establish a fully verified
        # product/event judgment or an auditable model producer.
        blocker = "CPU_REVIEW_NOT_VERIFIED"
    else:
        blocker = None
    return {"status": "READ_RECEIPT_ONLY" if blocker is None else "HOLD",
            "blocker": blocker, "read_state": trace.get("read_state", UNKNOWN),
            "window_counts": {k: counts[k] for k in ("total", "success", "failed", "unread")},
            "analysis_sha256": trace.get("analysis_sha256"),
            "window_binding_sha256": trace.get("window_binding_sha256"),
            "source_verification": "EXACT_NATIVE_AND_BODY_HASHES"}


def _extent(reference, document):
    if not isinstance(reference, dict):
        raise ValueError("SESSION4_SOURCE_LOCATOR_REQUIRED")
    locator = reference.get("locator")
    if not isinstance(locator, dict):
        raise ValueError("SESSION4_SOURCE_LOCATOR_REQUIRED")
    start, end = locator.get("start"), locator.get("end")
    body = document["body"]
    if (type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(body)):
        raise ValueError("SESSION4_SOURCE_LOCATOR_INVALID")
    # Store only coordinates and the digest of the exact literal span.
    return {"start": start, "end": end,
            "span_sha256": sha(body[start:end])}


def _quantities(event, document):
    facts = event.get("temporal_facts") or {}
    out = []
    for q in facts.get("quantities", []):
        if isinstance(q, dict):
            out.append({"kind": q.get("fact_kind", UNKNOWN),
                        "unit": q.get("unit", UNKNOWN),
                        "basis": q.get("basis", UNKNOWN),
                        "coverage": q.get("coverage", UNKNOWN),
                        "qualification_status": q.get("qualification_status", UNKNOWN),
                        "locator": _extent(q.get("reference"), document)})
    return out


def _periods(event, document):
    out = []
    for p in (event.get("temporal_facts") or {}).get("periods", []):
        if isinstance(p, dict):
            out.append({"kind": p.get("fact_kind", UNKNOWN),
                        "precision": p.get("precision", UNKNOWN),
                        "start": p.get("start", UNKNOWN),
                        "end": p.get("end", UNKNOWN),
                        "unknown_reason": p.get("unknown_reason"),
                        "locator": _extent(p.get("reference"), document)})
    return out


def build(document, trace=None):
    """Re-evaluate exact provenance-held source with existing protected graph.

    An actual source may be newly collected but its CPU receipt can be UNREAD;
    that remains a valid saved HOLD, never a false model completion. Source
    reference locations and all existing evidence retain original identities.
    """
    source = _source(document)
    # Validate stored event locators against the unchanged source bytes.
    reader.validate_references(document, document.get("retained_collection_events", []))
    g = graph.analyze([deepcopy(document)], mode="BACKFILL")
    cpu = _cpu(trace, source)
    held = {x.get("event_id"): x for x in g["blocked"] if x.get("event_id")}
    events = []
    for event in document.get("retained_collection_events", []):
        blocker = held.get(event["event_id"], {})
        known = sorted(k for k in FIELDS if k in event.get("scope", {}))
        missing = list(blocker.get("missing_fields", [k for k in FIELDS if k not in known]))
        if len(known) != len(FIELDS) and not missing:
            raise ValueError("SESSION4_INCOMPLETE_SCOPE_WITHOUT_BLOCKER")
        events.append({"event_id": event["event_id"],
                       "document_id": source["document_id"],
                       "body_sha256": source["body_sha256"],
                       "role": event["role"], "kind": event["kind"],
                       "source_locator": _extent({"locator": event["locator"]}, document),
                       "graph_observation_id": blocker.get("observation_id"),
                       "known_fields": known, "missing_fields": missing,
                       "first_blocker": blocker.get("first_blocker") or blocker.get("reason")
                            or ("NO_INDEPENDENT_QUALIFIED_OPPOSITE_SIDE" if len(known) == len(FIELDS)
                                else "INCOMPLETE_TARGET_SCOPE"),
                       "quantity_path": _quantities(event, document),
                       "timing_path": _periods(event, document)})
    # Never save full original text/quotes, CPU outputs or prospective firsts.
    result = {"format": FORMAT, "mode": "SOURCE_REVIEW_SHADOW_NOT_LIVE",
              "source": source, "cpu": cpu,
              "events": events, "graph_reference_checks": g["reference_checks"],
              "independent_pairs": g["independent_pairs"],
              "protected_signals_seen_not_promoted": len(g["protected_batch"]["signals"]),
              "decision": "HOLD", "auto_promoted": False,
              "prediction_performance": "UNVERIFIED",
              "reason": cpu.get("blocker") or (
                  "NO_STRUCTURED_SOURCE_EVENT" if not events
                  else "NO_INDEPENDENT_QUALIFIED_SUPPLY_DEMAND_PAIR")}
    # The same source/window can gain a later immutable CPU receipt. Keep
    # old UNREAD evidence, never rewrite it as COMPLETE in the same case ID.
    result["case_id"] = sha(canonical([FORMAT, graph.VERSION, reader.VERSION,
                                     source["document_id"], source["body_sha256"],
                                     sha(canonical(cpu))]))
    return result


def persist(path, rows):
    """Immutable ID-keyed SQLite records; no in-place overwrite or body write."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, "
                   "document_id TEXT NOT NULL, body_sha256 TEXT NOT NULL, "
                   "payload_sha256 TEXT NOT NULL, payload TEXT NOT NULL)")
        with db:
            for row in rows:
                if (row.get("format") != FORMAT or row.get("decision") != "HOLD"
                        or row.get("auto_promoted") is not False):
                    raise ValueError("SESSION4_ONLY_HELD_RESEARCH_RECORDS")
                payload = canonical(row)
                if any(k in payload for k in ('"body":', '"source_quote":', '"raw_html":')):
                    raise ValueError("SESSION4_RAW_SOURCE_PUBLICATION_FORBIDDEN")
                record = (row["case_id"], row["source"]["document_id"], row["source"]["body_sha256"], sha(payload), payload)
                previous = db.execute("SELECT payload_sha256,payload FROM cases WHERE id=?", (record[0],)).fetchone()
                if previous and previous != (record[3], record[4]):
                    raise ValueError("SESSION4_IMMUTABLE_CASE_CHANGED")
                if not previous:
                    db.execute("INSERT INTO cases VALUES(?,?,?,?,?)", record)
    finally:
        db.close()
    return readback(path)


def readback(path):
    db = sqlite3.connect("file:" + str(Path(path).resolve()) + "?mode=ro", uri=True)
    try:
        values = []
        for id, document_id, version, digest, raw in db.execute(
                "SELECT id,document_id,body_sha256,payload_sha256,payload FROM cases ORDER BY id"):
            row = json.loads(raw)
            if (sha(raw) != digest or row["case_id"] != id
                    or row["source"]["document_id"] != document_id
                    or row["source"]["body_sha256"] != version
                    or row["decision"] != "HOLD"):
                raise ValueError("SESSION4_RELOADED_RECORD_CHANGED")
            values.append(row)
        return values
    finally:
        db.close()


def dashboard(rows):
    """Private/owner research-only projection, not proof of deployed UI."""
    return {"format": "bct-session4-dashboard-readonly-v1",
            "source": "IMMUTABLE_SESSION4_LEDGER",
            "candidate_count": 0,
            "held_cases": len(rows),
            "held_sources": len({(x["source"]["document_id"], x["source"]["body_sha256"]) for x in rows}),
            "cpu_unread_sources": len({(x["source"]["document_id"], x["source"]["body_sha256"])
                                      for x in rows if x["cpu"].get("blocker") == "CPU_WINDOW_UNREAD"}),
            "trace": [{"case_id": x["case_id"], "document_id": x["source"]["document_id"],
                       "body_sha256": x["source"]["body_sha256"],
                       "status": "HOLD", "reason": x["reason"],
                       "missing_fields": sorted({m for e in x["events"] for m in e["missing_fields"]})}
                      for x in rows]}
