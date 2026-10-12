"""Bounded quick-review consumer using existing JSON runs/reviews and CAS writes.

The shared run claim has no automatic expiry: a crashed owner must be confirmed
stopped before its claim is released. This avoids overlapping paid model calls.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
import uuid

from .future_body import cache_body, extract_document, read_cached_body
from .future_bottleneck import fetch_html
from .future_reader import OpenAIQuickReader, estimated_cost, validate_output
from .future_review import (READER_VERSION, event_groups, queue_items, queue_summary,
                            save_review)
from .future_store import LocalJSONTransport, JSONTransport, store_patch


LOCK_ID = "future-quick-worker-lock"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _key(*values):
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()[:32]


def _runs(document):
    runs = document.get("runs", {})
    if isinstance(runs, list):
        return {r["id"]: r for r in runs if isinstance(r, dict) and r.get("id")}
    if not isinstance(runs, dict):
        raise ValueError("invalid run history")
    return runs


def _run_patch(patch, baseline):
    if isinstance(baseline.get("runs"), list) and isinstance(patch.get("runs"), dict):
        return {**patch, "runs": [{**value, "id": key} for key, value in patch["runs"].items()]}
    return patch


def _patch(transport, path, patch, operation, baseline):
    patch = _run_patch(patch, baseline)
    result = store_patch(transport, path, owner="review", patch=patch,
                         operation_id=operation, prepared_document=baseline)
    if result.status not in ("APPLIED", "ALREADY_APPLIED"):
        raise RuntimeError("SIDECAR_WRITE_UNCONFIRMED:" + str(result.reason or "UNKNOWN"))
    return result.document


def claim(transport, path, run_id):
    latest = transport.read(path).document
    if _runs(latest).get(LOCK_ID, {}).get("state") == "RUNNING":
        return False
    result = store_patch(transport, path, owner="review",
                         patch=_run_patch({"runs": {LOCK_ID: {"state": "RUNNING", "owner": run_id, "claimed_at": _now()}}}, latest),
                         operation_id="claim-" + run_id, prepared_document=latest)
    return (result.status in ("APPLIED", "ALREADY_APPLIED")
            and _runs(result.document)[LOCK_ID].get("owner") == run_id)


def _owned(transport, path, run_id):
    latest = transport.read(path).document
    lock = _runs(latest).get(LOCK_ID, {})
    if lock.get("state") != "RUNNING" or lock.get("owner") != run_id:
        raise RuntimeError("WORKER_CLAIM_LOST")
    return latest


def recover_body(item, cache_dir, fetcher=fetch_html):
    body = read_cached_body(cache_dir, item["body_sha256"])
    if body is not None:
        return body, None
    try:
        fetched = fetcher(item["url"])
        extracted = extract_document(fetched["html"], http_status=fetched.get("status", 200),
                                     content_type=fetched.get("content_type", "text/html"))
    except Exception as exc:
        return None, {"access_status": "BLOCKED", "reason": "SOURCE_REACCESS_FAILED:" + type(exc).__name__}
    observed = extracted.get("body_sha256")
    if not observed:
        return None, {"access_status": "BLOCKED", "reason": "NO_READABLE_SOURCE_BODY"}
    if observed != item["body_sha256"]:
        return None, {"access_status": "SOURCE_CHANGED", "observed_body_sha256": observed,
                      "reason": "REACCESSED_BODY_HASH_DIFFERS"}
    cache_body(cache_dir, extracted["body"])
    return extracted["body"], None


def run_worker(transport, candidates_path, tracking_path, *, reader, cache_dir,
               limit=10, max_input_chars=12000, retry_failed=False,
               input_rate=None, output_rate=None, fetcher=fetch_html, require_pilot_gates=False,
               review_mode="MANUAL_REVIEW", source_eligible=None):
    if not 1 <= limit <= 50 or not 1 <= max_input_chars <= 12000:
        raise ValueError("invalid worker batch/input limit")
    # Validate explicit prices before claims or API calls.
    estimated_cost({"input_tokens": 0, "output_tokens": 0}, input_rate, output_rate)
    run_id = "quick-worker-" + uuid.uuid4().hex
    report = {"id": run_id, "started_at": _now(), "state": "BLOCKED", "limit": limit,
              "max_input_chars": max_input_chars, "results": [], "model_calls": 0,
              "execution_mode": "LIVE_PILOT" if require_pilot_gates else "LOCAL_ONLY"}
    if review_mode != "API_REVIEW":
        return {**report, "reason": "API_WORKER_DISABLED", "review_mode": "MANUAL_REVIEW", "attempted": 0}
    blocked = reader.preflight() if hasattr(reader, "preflight") else None
    if blocked:
        return {**report, "reason": blocked, "attempted": 0}
    if require_pilot_gates:
        if limit not in (1, 10, 50):
            raise ValueError("live pilot limits are 1, 10, 50 only")
        required = {10: 1, 50: 10}.get(limit)
        if required is not None:
            history = _runs(transport.read(tracking_path).document).values()
            passed = any(r.get("execution_mode") == "LIVE_PILOT" and r.get("limit") == required
                         and r.get("state") == "FINISHED" and r.get("summary_saved") is True
                         and r.get("attempted") == required and r.get("counts") == {"SUCCESS": required}
                         and r.get("model_calls", 0) > 0
                         and r.get("completed_delta", 0) > 0 and r.get("quick_pending_delta", 0) < 0
                         and r.get("source_records_unchanged") is True and r.get("duplicate_auto_reviews") == 0
                         and all(x.get("input_tokens") is not None and x.get("output_tokens") is not None
                                 for x in r.get("results", [])) for r in history)
            if not passed:
                return {**report, "reason": f"PRIOR_LIVE_{required}_BATCH_REQUIRED", "attempted": 0}
    if not claim(transport, tracking_path, run_id):
        return {**report, "state": "BUSY", "reason": "WORKER_ALREADY_CLAIMED", "attempted": 0}
    started = perf_counter()
    try:
        candidates = transport.read(candidates_path).document
        tracking = _owned(transport, tracking_path, run_id)
        report["before"] = queue_summary(candidates, tracking)
        event_by_version = {(ref["document_id"], ref.get("body_sha256")): event_id
                            for event_id, event in event_groups(candidates).items() for ref in event["documents"]}
        pending = []
        held_states: Counter[str] = Counter()
        for item in queue_items(candidates, tracking)["quick"]:
            if source_eligible is not None and not source_eligible(item):
                continue
            work_id = "quick-version-" + _key(item["document_id"], item["body_sha256"], READER_VERSION)
            previous = _runs(tracking).get(work_id, {})
            # A stopped process can leave an uncertain in-flight reading. Keep
            # that version claimed until its stopped owner/result is reconciled.
            if previous.get("state") == "RUNNING":
                held_states['RUNNING'] += 1
                continue
            if previous.get("state") in ("ERROR", "BLOCKED") and not retry_failed:
                held_states[previous['state']] += 1
                continue
            pending.append((item, work_id))
            if len(pending) == limit:
                break
        report['held_prior_version_states'] = dict(held_states)
        for original, work_id in pending:
            case_started = perf_counter()
            result = {"document_id": original["document_id"], "body_sha256": original["body_sha256"],
                      "event_id": event_by_version[(original["document_id"], original["body_sha256"])],
                      "state": "ERROR", "input_tokens": None, "output_tokens": None}
            tracking = _owned(transport, tracking_path, run_id)
            # A saved result (including an incomplete checkpoint) changes the
            # next input range. Never reuse the stale queue captured at startup.
            item = next((x for x in queue_items(candidates, tracking)["quick"]
                         if x["document_id"] == original["document_id"] and x["body_sha256"] == original["body_sha256"]), None)
            if item is None:
                continue
            tracking = _patch(transport, tracking_path, {"runs": {work_id: {
                "state": "RUNNING", "run_id": run_id,
                "document_id": item["document_id"], "body_sha256": item["body_sha256"],
                "read_start": item["resume_at"], "claimed_at": _now(),
            }}}, run_id + "-claim-" + work_id, tracking)
            review_id = "auto-quick-" + _key(item["document_id"], item["body_sha256"], READER_VERSION, item["resume_at"])
            decision, metadata = None, {}
            try:
                prior = next((r for r in tracking.get("reviews", {}).values()
                              if r.get("worker_event_id") == result["event_id"]
                              and r.get("body_sha256") == item["body_sha256"]
                              and r.get("reader_version") == READER_VERSION
                              and r.get("kind") == "quick" and r.get("read_complete") is True
                              and r.get("disposition") != "INCOMPLETE"), None)
                if prior:
                    decision = {k: prior[k] for k in ("disposition", "reason", "read_end")}
                    metadata = {"worker_reused_review_id": prior["review_id"]}
                    result.update(input_tokens=0, output_tokens=0)
                else:
                    body, access = recover_body(item, cache_dir, fetcher)
                    if access:
                        review = {"review_id": "access-" + run_id + "-" + work_id,
                                  "document_id": item["document_id"], "body_sha256": item["body_sha256"],
                                  "reader_version": READER_VERSION, "kind": "access", "reviewed_at": _now(), **access}
                        saved = save_review(transport, tracking_path, candidates, review)
                        if saved.status not in ("APPLIED", "ALREADY_APPLIED"):
                            raise RuntimeError("ACCESS_SAVE_UNCONFIRMED")
                        result.update(state="BLOCKED", reason=access["reason"], review_id=review["review_id"])
                    elif len(body) != item["body_chars"]:
                        result.update(state="BLOCKED", reason="BODY_EXTENT_MISMATCH")
                    elif len(body) > max_input_chars:
                        # Never silently truncate a FULL/PARTIAL body to fit.
                        result.update(state="BLOCKED", reason="INPUT_BUDGET_EXCEEDED")
                    else:
                        payload = {"document_id": item["document_id"], "title": item.get("title"),
                                   "body_sha256": item["body_sha256"], "body_status": item["body_status"],
                                   "read_start": item["resume_at"], "expected_read_end": len(body), "body": body}
                        input_chars = (reader.input_characters(payload) if hasattr(reader, "input_characters")
                                       else len(json.dumps(payload, ensure_ascii=False)))
                        result["input_characters"] = input_chars
                        if input_chars > max_input_chars:
                            result.update(state="BLOCKED", reason="INPUT_BUDGET_EXCEEDED")
                        else:
                            report["model_calls"] += 1
                            response = reader(payload)
                            decision = validate_output(response["review"], payload)
                            metadata = {"worker_provider": response.get("provider"), "worker_model": response.get("model")}
                            result.update(response.get("usage", {}))
                if decision is not None:
                    # Metadata/identities come from the worker, never model JSON.
                    review = {**decision, **metadata, "review_id": review_id,
                              "document_id": item["document_id"], "body_sha256": item["body_sha256"],
                              "reader_version": READER_VERSION, "kind": "quick", "read_start": item["resume_at"],
                              "reviewed_at": _now(), "worker_event_id": result["event_id"]}
                    _owned(transport, tracking_path, run_id)
                    saved = save_review(transport, tracking_path, candidates, review)
                    if saved.status not in ("APPLIED", "ALREADY_APPLIED"):
                        raise RuntimeError("REVIEW_SAVE_UNCONFIRMED")
                    result.update(state="SUCCESS", disposition=decision["disposition"], review_id=review_id,
                                  reused=bool(prior))
            except Exception as exc:
                # Provider errors may contain source text or credentials; only
                # the exception class is retained, never its message/body.
                result.update(state="ERROR", reason=type(exc).__name__)
            result["elapsed_seconds"] = perf_counter() - case_started
            result["estimated_cost_usd"] = estimated_cost(result, input_rate, output_rate)
            tracking = _owned(transport, tracking_path, run_id)
            _patch(transport, tracking_path, {"runs": {work_id: {**result, "run_id": run_id, "finished_at": _now()}}},
                   run_id + "-result-" + work_id, tracking)
            report["results"].append(result)
        report.update(state="FINISHED", attempted=len(report["results"]), elapsed_seconds=perf_counter() - started,
                      finished_at=_now(), counts=dict(Counter(x["state"] for x in report["results"])))
        report["mean_seconds"] = report["elapsed_seconds"] / report["attempted"] if report["attempted"] else None
        report["rates"] = {state: report["counts"].get(state, 0) / report["attempted"]
                           if report["attempted"] else None for state in ("SUCCESS", "ERROR", "BLOCKED")}
        report["token_totals"] = {key: sum(x[key] for x in report["results"])
                                  if report["results"] and all(x.get(key) is not None for x in report["results"]) else None
                                  for key in ("input_tokens", "output_tokens")}
        costs = [x["estimated_cost_usd"] for x in report["results"]]
        report["estimated_cost_usd"] = sum(costs) if costs and all(x is not None for x in costs) else None
        # Extrapolation is meaningful only for a batch of successful judgments.
        measured = bool(report["attempted"] and report["counts"].get("SUCCESS") == report["attempted"])
        report["projections"] = {str(size): {
            "seconds": report["mean_seconds"] * size if measured else None,
            "estimated_cost_usd": report["estimated_cost_usd"] / report["attempted"] * size
            if measured and report["estimated_cost_usd"] is not None else None,
            "basis": "THIS_BATCH_ONLY_NOT_A_BACKLOG_GUARANTEE" if measured else "UNMEASURED",
        } for size in (10, 50, 1278)}
        tracking = _owned(transport, tracking_path, run_id)
        # Re-read collection to preserve concurrent new candidates in the summary.
        current = transport.read(candidates_path).document
        report["after"] = queue_summary(current, tracking)
        report["source_records_unchanged"] = all(current.get("results", {}).get(key) == value
                                                 for key, value in candidates.get("results", {}).items())
        report["completed_delta"] = report["after"]["completed_documents"] - report["before"]["completed_documents"]
        report["quick_pending_delta"] = report["after"]["quick_pending"] - report["before"]["quick_pending"]
        report["pending_event_delta"] = report["after"]["pending_events"] - report["before"]["pending_events"]
        auto_keys = Counter((r.get("document_id"), r.get("body_sha256"), r.get("reader_version"), r.get("read_start"))
                            for r in tracking.get("reviews", {}).values()
                            if r.get("review_id", "").startswith("auto-quick-"))
        report["duplicate_auto_reviews"] = sum(n - 1 for n in auto_keys.values() if n > 1)
        report["distinct_events_attempted"] = len({r["event_id"] for r in report["results"]})
        saved_summary = store_patch(transport, candidates_path, owner="collection",
                                   patch={"summary": {"review_queue": report["after"]}},
                                   operation_id="summary-" + run_id, prepared_document=current)
        report["summary_saved"] = saved_summary.status in ("APPLIED", "ALREADY_APPLIED")
        _patch(transport, tracking_path, {"runs": {run_id: report}}, "finish-" + run_id, tracking)
        return report
    finally:
        latest = _owned(transport, tracking_path, run_id)
        _patch(transport, tracking_path, {"runs": {LOCK_ID: {"state": "IDLE", "owner": run_id, "released_at": _now()}}},
               "release-" + run_id, latest)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="future-candidates.json")
    parser.add_argument("--tracking", default="future-tracking.json")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-input-chars", type=int, default=12000)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--repository")
    parser.add_argument("--branch", default="future-bottleneck-data")
    parser.add_argument("--provider", default=os.environ.get("BCT_REVIEW_PROVIDER", "openai"))
    parser.add_argument("--model", default=os.environ.get("BCT_REVIEW_MODEL", "gpt-5-mini"))
    parser.add_argument("--base-url", default=os.environ.get("BCT_REVIEW_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--input-usd-per-million", type=float)
    parser.add_argument("--output-usd-per-million", type=float)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--review-mode", choices=["MANUAL_REVIEW", "API_REVIEW"],
                        default=os.environ.get("BCT_REVIEW_MODE", "MANUAL_REVIEW"))
    args = parser.parse_args(argv)
    reader = None
    if args.review_mode == "API_REVIEW":
        reader = OpenAIQuickReader(api_key=os.environ.get("BCT_REVIEW_API_KEY") or os.environ.get("OPENAI_API_KEY"),
                                  model=args.model, provider=args.provider, base_url=args.base_url)
    transport: JSONTransport
    if args.repository and reader is not None and not reader.preflight():
        from .future_github import GitHubTransport
        transport = GitHubTransport(args.repository, args.branch,
                                    os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    else:
        transport = LocalJSONTransport()
    report = run_worker(transport, args.candidates, args.tracking, reader=reader, cache_dir=args.cache_dir,
                        limit=args.limit, max_input_chars=args.max_input_chars, retry_failed=args.retry_failed,
                        input_rate=args.input_usd_per_million, output_rate=args.output_usd_per_million,
                        require_pilot_gates=bool(args.repository), review_mode=args.review_mode)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text)
    print(text, end="")
    passed = (report["state"] == "FINISHED" and report.get("summary_saved")
              and not report.get("counts", {}).get("ERROR") and not report.get("counts", {}).get("BLOCKED")
              and (not args.repository or (report.get("attempted") == args.limit and report.get("completed_delta", 0) > 0)))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
