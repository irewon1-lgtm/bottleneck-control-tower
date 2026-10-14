"""Research-only official-source collection queue. Never loads AI or sends alerts.

Uses the existing SourceClient and append-only Ledger. Failed URLs are isolated
from new work; an unchanged failed URL requires explicit investigation, not an
automatic retry. Native sources remain unmodified and unapproved for inference.
"""
from datetime import datetime, timedelta, timezone
import argparse
import fcntl
import json
from pathlib import Path
import time
from urllib.parse import urljoin, urlsplit
import uuid

from lxml import html

from bct.objective_lock import stamp_export
from .adapters import SourceClient
from .public_input import PUBLISHERS, valid_article_url
from .store import Ledger, now, sha


def valid_index_url(url):
    if valid_article_url(url):
        return True
    # Exact public press-release listing filter observed at the official index.
    # This is not an exception for article inputs, auth/session or arbitrary queries.
    return url == "https://www.gevernova.com/news/media-hub?type%5Bpress_release%5D=press_release"


def check_config(config):
    if type(config.get("document_limit")) is not int or not 1 <= config["document_limit"] <= 3:
        raise ValueError("RESEARCH_CAPTURE_LIMIT_1_TO_3")
    if not 600 <= config.get("interval_seconds", 0) <= 86400:
        raise ValueError("RESEARCH_TIMER_INTERVAL_600_TO_86400")
    if not 1 <= len(config.get("sources", [])) <= 3:
        raise ValueError("RESEARCH_OFFICIAL_INDEX_LIMIT_1_TO_3")
    for source in config["sources"]:
        p, prefix = urlsplit(source["index_url"]), urlsplit(source["article_prefix"])
        if (p.hostname not in PUBLISHERS or p.hostname != prefix.hostname
                or not valid_index_url(source["index_url"]) or not valid_article_url(source["article_prefix"])):
            raise ValueError("UNAPPROVED_OFFICIAL_INDEX")


def discover(raw, source):
    """Narrow same-host article paths; query, fragment and credential URLs stay out."""
    urls = set()
    for href in html.fromstring(raw).xpath("//a/@href"):
        url = urljoin(source["index_url"], href)
        if (url.startswith(source["article_prefix"]) and url != source["index_url"]
                and valid_article_url(url) and not urlsplit(url).query):
            urls.add(url)
    return sorted(urls)


def queue(ledger):
    discovered, attempted = {}, {}
    for kind, payload in ledger.db.execute("SELECT kind,payload FROM events WHERE kind IN ('INTAKE_DISCOVERED','INTAKE_FETCH_RESULT') ORDER BY seq"):
        item = json.loads(payload)
        if kind == "INTAKE_DISCOVERED":
            discovered.setdefault(item["url"], item)
        else:
            attempted[item["url"]] = item
    captured = {r[0] for r in ledger.db.execute("SELECT url FROM documents")}
    pending = [x for url, x in discovered.items() if url not in attempted and url not in captured]
    failed = [x for x in attempted.values() if x["status"] == "FAILED"]
    return pending, failed


def fair_batch(pending, limit):
    """Give each discovery role a slot before a large index fills the batch."""
    groups = {}
    for item in pending:
        groups.setdefault(item["source_role_hint"], []).append(item)
    selected = []
    while len(selected) < limit and any(groups.values()):
        for items in groups.values():
            if items and len(selected) < limit:
                selected.append(items.pop(0))
    return selected


def intake(root, config, *, client=None, trigger="manual"):
    check_config(config)
    client, ledger = client or SourceClient(), Ledger(root)
    run_id = "intake-" + uuid.uuid4().hex
    captured, failures, inflow = [], [], 0
    try:
        with ledger.worker():
            with ledger.db:
                ledger.event("RUN_STARTED", {"run_id": run_id, "mode": "LIVE", "scope": "COLLECTION_ONLY_NO_AI", "trigger": trigger})
            known = {json.loads(p)["url"] for p, in ledger.db.execute("SELECT payload FROM events WHERE kind='INTAKE_DISCOVERED'")}
            existing = {r[0] for r in ledger.db.execute("SELECT url FROM documents")}
            blocked_indexes = {json.loads(p)["url"] for p, in ledger.db.execute("SELECT payload FROM events WHERE kind='INTAKE_INDEX_FAILURE'")}
            for source in config["sources"]:
                if source["index_url"] in blocked_indexes:
                    failures.append({"phase": "INDEX", "url": source["index_url"], "type": "PRIOR_FAILURE_ISOLATED_REQUIRES_INVESTIGATION"})
                    continue
                try:
                    raw, final, status, _ = client.fetch(source["index_url"])
                    if final != source["index_url"] or status != 200:
                        raise ValueError("INDEX_IDENTITY_OR_HTTP_STATUS")
                    with ledger.db:
                        ledger.db.execute("INSERT OR IGNORE INTO blobs VALUES(?,?)", (sha(raw), raw))
                        ledger.event("INTAKE_INDEX", {"run_id": run_id, "url": final, "raw_sha256": sha(raw)})
                        for url in discover(raw, source):
                            if url not in known and url not in existing:
                                ledger.event("INTAKE_DISCOVERED", {"url": url, "at": now(), "source_role_hint": source["role"], "index_sha256": sha(raw)})
                                known.add(url)
                                inflow += 1
                except Exception as exc:
                    # Safe codes only; neither credential-bearing URLs nor server bodies enter diagnostics.
                    failures.append({"phase": "INDEX", "url": source["index_url"], "type": type(exc).__name__, "http_status": getattr(exc, "code", None),
                                     "code": str(exc) if str(exc) == "INDEX_IDENTITY_OR_HTTP_STATUS" else None})
                    with ledger.db:
                        ledger.event("INTAKE_INDEX_FAILURE", failures[-1])
            pending, _ = queue(ledger)
            for item in fair_batch(pending, config["document_limit"]):
                at, url = now(), item["url"]
                try:
                    doc, raw, views = client.document(url)
                    if doc["origin_url"] != url:
                        raise ValueError("ARTICLE_IDENTITY_CHANGED")
                    added = ledger.capture(doc, raw, {"AI_status": "NOT_RUN_QUALITY_GATE_HOLD", "parser_comparison": views})
                    with ledger.db:
                        ledger.event("INTAKE_FETCH_RESULT", {"url": url, "at": at, "status": "CAPTURED", "document_id": doc["document_id"], "body_sha256": doc["body_sha256"]})
                        if added:
                            ledger.event("READ_QUEUE", {"document_id": doc["document_id"], "state": "PENDING", "source_role_hint": item["source_role_hint"], "source_version": doc["body_sha256"], "AI_gate": "HOLD_PENDING_INDEPENDENT_QUALITY"})
                    captured.append(doc["document_id"])
                except Exception as exc:
                    failure = {"phase": "DOCUMENT", "url": url, "at": at, "status": "FAILED", "type": type(exc).__name__, "http_status": getattr(exc, "code", None)}
                    failures.append(failure)
                    with ledger.db:
                        ledger.event("INTAKE_FETCH_RESULT", failure)
            pending, failed = queue(ledger)
            oldest = min((x["at"] for x in pending), default=None)
            result = stamp_export({"run_id": run_id, "scope": "RESEARCH_COLLECTION_ONLY_NOT_AI_SHADOW", "trigger": trigger,
                "discovered_new_URLs": inflow, "live_captured": len(captured), "new_document_ids": captured,
                "pending_source_fetch": len(pending), "isolated_failed_URLs": len(failed),
                "oldest_pending_at": oldest, "failures": failures, "candidates": [],
                "intake_backlog_change": inflow-len(captured)-sum(f.get("phase")=="DOCUMENT" for f in failures),
                "read_queue": ledger.db.execute("SELECT count(*) FROM events WHERE kind='READ_QUEUE'").fetchone()[0],
                "AI_requests": 0, "API_cost": 0, "S1": 0, "S2": 0, "S3": 0,
                "forecast_performance": "NOT_RUN", "AI_analysis_automation": "HOLD"})
            return ledger.save_run(run_id, result, "LIVE")
    finally:
        ledger.close()


def watch(root, config, *, first_delay=60, max_days=7):
    """Actual bounded local timer; survives worker restart while this host exists.

    This process is neither a hosted scheduler nor proof of seven days. Persisted
    next-due/stop times and a separate lock prevent duplicate timers on restart.
    """
    check_config(config)
    if not 1 <= max_days <= 7 or not 30 <= first_delay <= 600:
        raise ValueError("RESEARCH_TIMER_BOUNDS")
    root = Path(root)
    ledger = Ledger(root)
    ledger.close()
    with (root/".timer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger = Ledger(root)
        previous = ledger.db.execute("SELECT payload FROM events WHERE kind='RESEARCH_TIMER_SCHEDULED' ORDER BY seq DESC LIMIT 1").fetchone()
        current = datetime.now(timezone.utc)
        state = json.loads(previous[0]) if previous else {"started_at": current.isoformat(), "next_due": (current+timedelta(seconds=first_delay)).isoformat(), "stop_at": (current+timedelta(days=max_days)).isoformat()}
        if previous and state.get("config_sha256") != sha(config):
            state["next_due"] = (current+timedelta(seconds=first_delay)).isoformat()
            state["restart_reason"] = "VALIDATED_COLLECTION_CONFIG_CHANGED"
        state["config_sha256"] = sha(config)
        with ledger.db:
            ledger.event("RESEARCH_TIMER_SCHEDULED", state)
        ledger.close()
        while datetime.now(timezone.utc) < datetime.fromisoformat(state["stop_at"]):
            delay = (datetime.fromisoformat(state["next_due"])-datetime.now(timezone.utc)).total_seconds()
            if delay > 0:
                time.sleep(min(delay, 30))
                continue
            # Claim and persist the next slot before IO. A crash is visible, not a same-slot retry.
            due = state["next_due"]
            state["next_due"] = (datetime.now(timezone.utc)+timedelta(seconds=config["interval_seconds"])).isoformat()
            ledger = Ledger(root)
            with ledger.db:
                ledger.event("RESEARCH_TIMER_TICK", {"scheduled_at": due, "actual_at": now()})
                ledger.event("RESEARCH_TIMER_SCHEDULED", state)
            ledger.close()
            try:
                result = intake(root, config, trigger="timer")
                print(json.dumps({k: result[k] for k in ("run_id", "trigger", "live_captured", "read_queue", "pending_source_fetch")}), flush=True)
            except Exception as exc:
                ledger = Ledger(root)
                with ledger.db:
                    ledger.event("RESEARCH_TIMER_ERROR", {"at": now(), "type": type(exc).__name__})
                ledger.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("var/v4/research-intake"))
    p.add_argument("--config", type=Path, default=Path("config/v4-research-intake.json"))
    p.add_argument("--watch", action="store_true")
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[3]
    if not args.root.resolve().is_relative_to(repo/"var/v4"):
        raise ValueError("RESEARCH_ROOT_MUST_BE_WITHIN_VAR_V4")
    config = json.loads(args.config.read_text())
    if args.watch:
        watch(args.root, config)
    else:
        print(json.dumps(intake(args.root, config), ensure_ascii=False))


if __name__ == "__main__":
    main()
