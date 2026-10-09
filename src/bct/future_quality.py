"""v3.3 measurements from frozen references and actual queue/operation records.

This module never labels documents, tunes filters, or writes canonical SQLite.
The reference reader must freeze event membership before seeing automatic output.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

SIGNALS = ("DEMAND", "SUPPLY", "RELIEF")
QUEUE_KINDS = {"QUICK", "MATERIAL", "DEEP", "FAST_REVIEW", "MATERIAL_CHECK", "DEEP_REVIEW"}


def _time(value: str | datetime) -> datetime:
    result = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamps must include timezone")
    return result.astimezone(timezone.utc)


def _label(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value", value.get("status"))
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    value = str(value).upper()
    return value if value in {"TRUE", "FALSE", "UNKNOWN"} else "UNKNOWN"


def _id(value: dict) -> str:
    return str(value.get("document_id", value.get("doc_id", value.get("id", ""))))


def _version(value: dict) -> str | None:
    return value.get("current_body_sha256") or value.get("body_sha256") or value.get("source_version") or value.get("fingerprint")


def _metric(captured: list[str], positive: list[str], unknown: list[str]) -> dict:
    return {
        "numerator": len(captured), "denominator": len(positive),
        "rate": len(captured) / len(positive) if positive else None,
        "captured_ids": sorted(captured),
        "missed_ids": sorted(set(positive) - set(captured)),
        "unmeasured_count": len(unknown), "unmeasured_ids": sorted(unknown),
    }


def _documents(value: dict | list) -> list[dict]:
    return value if isinstance(value, list) else value.get("documents", [])


def evaluate(
    manifest: dict,
    reference: dict | list,
    candidates: dict,
    queue_entries: list[dict] | None = None,
    *,
    reference_sufficient: bool | None = None,
    threshold: float = .8,
    minimum_positive: int = 1,
) -> dict:
    """Count preserved signals using an explicit, current-version review queue.

    ``minimum_positive`` only prevents empty-denominator PASS by default. The
    design sets no numeric minimum event count. A trial review must explicitly
    assess reference/sample sufficiency before the report can claim PASS.
    Raw storage, retry records, previews and notification delivery are never
    substitutes for ``queue_entries``.
    """
    if not 0 < threshold <= 1 or minimum_positive < 1:
        raise ValueError("invalid measurement bounds")
    sample = _documents(manifest)
    ids = [_id(row) for row in sample]
    if not ids or any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("manifest needs unique, nonempty document IDs")
    if isinstance(reference, dict) and reference.get("sample_id") not in (None, manifest.get("sample_id")):
        raise ValueError("reference/manifest sample mismatch")
    if isinstance(reference, dict) and reference.get("automatic_results_seen") is True:
        raise ValueError("reference labels must precede automatic results")
    references = {}
    for row in _documents(reference):
        doc_id = _id(row)
        if doc_id in references:
            raise ValueError("duplicate reference document")
        if row.get("automatic_results_seen") is True:
            raise ValueError("reference labels must precede automatic results")
        references[doc_id] = row
    results = candidates.get("results", {})
    if isinstance(results, list):
        results = {_id(row): row for row in results}
    queued = set()
    ignored_queue_entries = []
    for entry in queue_entries or []:
        doc_id = _id(entry)
        result = results.get(doc_id, {})
        kind = str(entry.get("kind", entry.get("queue", ""))).upper()
        actual_entry = bool(entry.get("entered_at", entry.get("queue_entered_at")))
        if doc_id in ids and kind in QUEUE_KINDS and actual_entry and _version(entry) and _version(entry) == _version(result):
            queued.add(doc_id)
        elif doc_id in ids:
            ignored_queue_entries.append({"document_id": doc_id, "reason": "missing, invalid or outdated queue/version reference"})

    mapping_frozen = isinstance(reference, dict) and (
        reference.get("event_mapping_status") == "FROZEN_BEFORE_AUTO_RESULTS"
        or reference.get("event_mapping_frozen") is True
    )
    metrics: dict[str,Any] = {}
    uncertain_events: list[dict[str,Any]] = []
    full_claims_needing_confirmation = []
    for doc_id in ids:
        result = results.get(doc_id, {})
        status = result.get("body_status")
        ref_status = references.get(doc_id, {}).get("reference_status", "UNAVAILABLE")
        if status == "FULL" and ref_status in {"PARTIAL", "UNAVAILABLE"}:
            full_claims_needing_confirmation.append(doc_id)
    for signal in SIGNALS:
        labels = {doc_id: _label(references.get(doc_id, {}).get("labels", {}).get(signal)) for doc_id in ids}
        positive = [doc_id for doc_id in ids if labels[doc_id] == "TRUE"]
        negative = [doc_id for doc_id in ids if labels[doc_id] == "FALSE"]
        unknown = [doc_id for doc_id in ids if labels[doc_id] == "UNKNOWN"]
        full_positive = [doc_id for doc_id in positive if results.get(doc_id, {}).get("body_status") == "FULL"]
        full_unknown = [doc_id for doc_id in unknown if results.get(doc_id, {}).get("body_status") == "FULL"]
        full_captured = [doc_id for doc_id in full_positive if doc_id in queued and results[doc_id].get("candidate") is True]
        captured = [doc_id for doc_id in positive if doc_id in queued]
        event_documents = defaultdict(set)
        for doc_id in positive:
            row = references[doc_id]
            events = row.get("events", [])
            if not events:
                uncertain_events.append({"document_id": doc_id, "signal": signal, "reason": "reference event identity unavailable"})
            matching_signal = False
            for event in events:
                if not isinstance(event, dict):
                    uncertain_events.append({"document_id": doc_id, "signal": signal, "reason": "event must contain frozen identity and signal membership"})
                    continue
                event_id = event.get("event_id")
                if signal not in event.get("signals", []):
                    continue
                matching_signal = True
                if not event_id or str(event.get("certainty", "UNKNOWN")).upper() not in {"CERTAIN", "CONFIRMED"}:
                    uncertain_events.append({"document_id": doc_id, "signal": signal, "reason": "uncertain event grouping", "event_id": event_id})
                    continue
                event_documents[str(event_id)].add(doc_id)
            if events and not matching_signal:
                uncertain_events.append({"document_id": doc_id, "signal": signal, "reason": "positive reference signal lacks frozen event membership"})
        event_ids = list(event_documents)
        event_captured = [event_id for event_id, docs in event_documents.items() if docs & queued]
        event_unknown = [item["document_id"] for item in uncertain_events if item["signal"] == signal]
        known_unknown_events = set()
        for doc_id in ids:
            for event in references.get(doc_id, {}).get("events", []):
                if not isinstance(event, dict):
                    continue
                event_id = event.get("event_id")
                if event_id and str(event.get("certainty", "UNKNOWN")).upper() in {"CERTAIN", "CONFIRMED"} and _label(event.get("labels", {}).get(signal)) == "UNKNOWN" and signal in event.get("labels", {}):
                    known_unknown_events.add(str(event_id))
        known_unknown_events -= set(event_ids)
        # Unknown documents may contain unknown events: their event count is
        # not invented by counting each inaccessible article as an event.
        event_measure = _metric(event_captured, event_ids, list(dict.fromkeys(event_unknown)))
        event_measure["unread_document_ids_with_unknown_events"] = unknown
        event_measure["known_unmeasured_event_ids"] = sorted(known_unknown_events)
        event_measure["total_unmeasured_event_count"] = None if unknown or event_unknown else len(known_unknown_events)
        event_measure["event_documents"] = {key: sorted(value) for key, value in sorted(event_documents.items())}
        predicted = [doc_id for doc_id in ids if signal in results.get(doc_id, {}).get("evidence", {})]
        known_predicted = [doc_id for doc_id in predicted if labels[doc_id] != "UNKNOWN"]
        true_predicted = [doc_id for doc_id in known_predicted if labels[doc_id] == "TRUE"]
        metrics[signal] = {
            "full_document_recall": _metric(full_captured, full_positive, full_unknown),
            "whole_path_document_capture": _metric(captured, positive, unknown),
            "whole_path_event_capture": event_measure,
            "precision": {"numerator": len(true_predicted), "denominator": len(known_predicted), "rate": len(true_predicted) / len(known_predicted) if known_predicted else None},
            "reference_positive": len(positive), "reference_negative": len(negative),
            "positive_hits": len(captured), "positive_misses": len(positive) - len(captured),
            "negative_queued": len(set(negative) & queued),
            "unmeasured_document_share": len(unknown) / len(ids),
        }
        if queue_entries is None:
            for name in ("full_document_recall", "whole_path_document_capture", "whole_path_event_capture"):
                measure = metrics[signal][name]
                measure.update(measurement_available=False, numerator=None, rate=None, missed_ids=[])

    failures, pending = [], []
    for signal in ("DEMAND", "RELIEF"):
        for name in ("full_document_recall", "whole_path_document_capture", "whole_path_event_capture"):
            measure = metrics[signal][name]
            if measure["denominator"] < minimum_positive:
                pending.append(f"{signal}.{name}: insufficient measurable positives ({measure['denominator']})")
            elif measure["rate"] is not None and measure["rate"] < threshold:
                failures.append(f"{signal}.{name}: {measure['numerator']}/{measure['denominator']} below {threshold:.0%}")
    if queue_entries is None:
        pending.append("Actual review queue was not provided")
    if not mapping_frozen:
        pending.append("Reference event correspondence was not frozen before automatic results")
    if reference_sufficient is not True:
        pending.append("Trial review has not confirmed reference/event sample sufficiency")
    filter_freeze = manifest.get("filter_freeze")
    if not isinstance(filter_freeze, dict) or not filter_freeze.get("sha256"):
        pending.append("Filter version/digest was not frozen")
    status = "FAIL" if failures else "PENDING" if pending else "PASS"
    return {
        "version": "bct-v33-quality-v1", "sample_id": manifest.get("sample_id"),
        "status": status, "label_kind": "AI_REFERENCE_NOT_HUMAN_GOLD",
        "sample_document_count": len(ids), "threshold": threshold,
        "minimum_positive": minimum_positive, "reference_sufficient": reference_sufficient,
        "metrics": metrics, "failures": failures, "pending_reasons": pending,
        "body_status_counts": {status: sum(results.get(doc_id, {}).get("body_status") == status for doc_id in ids) for status in ("FULL", "PARTIAL", "UNAVAILABLE")},
        "missing_automatic_document_ids": [doc_id for doc_id in ids if doc_id not in results],
        "queue_entered_document_count": len(queued), "ignored_queue_entries": ignored_queue_entries,
        "full_claims_needing_reference_confirmation": full_claims_needing_confirmation,
        "uncertain_event_membership": uncertain_events,
        "limits": ["Queue entry is distinct from actual reading completion.", "Observed proportions are small-trial adoption evidence, not guaranteed field performance.", "Unknown documents can contain unknown events; no missing event denominator is fabricated.", "Original baseline disjointness is unknown when its historical manifest is unavailable."],
    }


def observation_status(samples: list[dict], *, start_at: str | None = None, now: str | datetime | None = None) -> dict:
    """Assess seven elapsed days from preserved real operating snapshots.

    Required snapshot values are inflow/completed totals (cumulative within
    this observation), retries, material wait, total pending, oldest wait and
    separate user/system waits. Missing records remain PENDING.
    """
    current = _time(now) if now else datetime.now(timezone.utc)
    pending, invalid = [], []
    rows = []
    for sample in samples:
        try:
            stamp = _time(sample.get("recorded_at", sample.get("checked_at", "")))
        except (ValueError, TypeError, AttributeError):
            invalid.append("invalid or missing observation timestamp")
            continue
        if stamp > current or sample.get("synthetic") is True or sample.get("actual_execution") is not True:
            invalid.append("future, synthetic or unconfirmed execution record")
            continue
        rows.append((stamp, sample))
    rows.sort(key=lambda item: item[0])
    if not rows:
        return {"status": "PENDING", "elapsed_seconds": 0, "sample_count": 0, "pending_reasons": ["No real operating observations"], "invalid_observations": invalid}
    start = _time(start_at) if start_at else rows[0][0]
    rows = [row for row in rows if row[0] >= start]
    if not rows:
        return {"status": "PENDING", "elapsed_seconds": 0, "sample_count": 0, "pending_reasons": ["No observations at or after observation start"], "invalid_observations": invalid}
    end = rows[-1][0]
    elapsed = (end - start).total_seconds()
    if elapsed < timedelta(days=7).total_seconds():
        pending.append("Seven actual elapsed days have not been observed")
    days = {int((stamp - start).total_seconds() // 86400) for stamp, _ in rows}
    missing_days = sorted(set(range(7)) - days)
    if missing_days:
        pending.append("Missing operating snapshots within observation days")
    required = ("inflow_total", "completed_total", "retries", "material_wait", "pending_total", "oldest_wait_seconds", "user_wait", "system_wait")
    incomplete = []
    for stamp, sample in rows:
        missing = [key for key in required if not isinstance(sample.get(key), (int, float)) or isinstance(sample.get(key), bool) or sample[key] < 0]
        if missing:
            incomplete.append({"recorded_at": stamp.isoformat(), "missing_or_invalid": missing})
    if incomplete:
        pending.append("Required burden or delay-cause observations are incomplete")
    if invalid:
        pending.append("Unverified execution observations were excluded")
    usable = [(stamp, row) for stamp, row in rows if all(isinstance(row.get(key), (int, float)) and not isinstance(row[key], bool) and row[key] >= 0 for key in required)]
    hold = []
    if rows[-1][1].get("failed_total", 0) > 0:
        hold.append("Archived failed attempts remain unresolved; archive is not completion")
    if len(usable) >= 2:
        first, last = usable[0][1], usable[-1][1]
        inflow = last["inflow_total"] - first["inflow_total"]
        completed = last["completed_total"] - first["completed_total"]
        if inflow < 0 or completed < 0:
            pending.append("Cumulative observation counters were reset or decreased")
        # Each consecutive daily endpoint is inspected, rather than treating
        # two snapshots or repeated immediate executions as a seven-day run.
        daily = {}
        for stamp, row in usable:
            daily[int((stamp - start).total_seconds() // 86400)] = row
        endpoints = [daily[key] for key in sorted(daily)]
        growth = [b["pending_total"] - a["pending_total"] for a, b in zip(endpoints, endpoints[1:])]
        continued_growth = len(growth) >= 2 and all(value > 0 for value in growth[-3:])
        if inflow > completed and continued_growth:
            hold.append("Inflow persistently exceeds completion and daily backlog continues growing")
        if last["system_wait"] > 0:
            hold.append("System-caused waiting remains unresolved")
    else:
        inflow = completed = None
        pending.append("Insufficient comparable operating snapshots")
        continued_growth = False
    return {
        "version": "bct-v33-operation-observation-v1", "status": "HOLD" if hold else "PENDING" if pending else "PASS",
        "start_at": start.isoformat(), "last_observed_at": end.isoformat(),
        "expected_earliest_finish": (start + timedelta(days=7)).isoformat(),
        "elapsed_seconds": elapsed, "sample_count": len(rows), "observed_day_buckets": sorted(days),
        "missing_day_buckets": missing_days, "inflow_change": inflow, "completed_change": completed,
        "continued_backlog_growth": continued_growth, "latest": rows[-1][1],
        "pending_reasons": list(dict.fromkeys(pending)), "hold_reasons": hold,
        "invalid_observations": invalid, "incomplete_observations": incomplete,
        "limits": ["User waiting and system delays are reported separately.", "Seven-day PASS does not establish long-term stability or prediction accuracy."],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    quality = sub.add_parser("evaluate")
    quality.add_argument("--manifest", required=True)
    quality.add_argument("--reference", required=True)
    quality.add_argument("--candidates", required=True)
    quality.add_argument("--queue")
    quality.add_argument("--reference-sufficient", action="store_true", default=None)
    quality.add_argument("--output", required=True)
    operation = sub.add_parser("observe")
    operation.add_argument("--samples", required=True)
    operation.add_argument("--start-at")
    operation.add_argument("--output", required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(Path(path).read_text())
    if args.command == "evaluate":
        queue = read(args.queue) if args.queue else None
        if isinstance(queue, dict):
            queue = queue.get("entries", queue.get("queue_entries", []))
        report = evaluate(read(args.manifest), read(args.reference), read(args.candidates), queue, reference_sufficient=args.reference_sufficient)
    else:
        samples = read(args.samples)
        if isinstance(samples, dict):
            samples = samples.get("samples", [])
        report = observation_status(samples, start_at=args.start_at)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "output": args.output}))


if __name__ == "__main__":
    main()
