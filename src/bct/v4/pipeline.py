"""Bounded single-worker shadow runs, using unchanged V3.3 domain engines."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import time
import uuid

from bct import precursor_collection, precursor_evidence_graph, precursor_scope_reader
from bct.objective_lock import stamp_export, require_objective
from . import VERSION
from .adapters import CPUExtractor, SourceClient, rss_leads
from .store import Ledger, now, sha


def analyze(documents, *, mode="LIVE", as_of=None, new_ids=None):
    if mode not in ("LIVE", "BACKFILL", "SYNTHETIC") or (mode == "LIVE" and as_of):
        raise ValueError("LIVE_CANNOT_BACKDATE")
    if len({d["document_id"] for d in documents}) != len(documents):
        raise ValueError("DUPLICATE_DOCUMENT_ID")
    ready, withheld = [], []
    for doc in documents:
        # The old engine accepts observed public snapshots without a publish
        # date. V4 keeps those as leads, never EARLY success evidence.
        if not doc.get("published_at") or doc.get("provenance") != "PASS":
            withheld.append({"document_id": doc["document_id"], "reason": "ORIGINAL_PUBLICATION_OR_PROVENANCE_UNVERIFIED"})
        else:
            ready.append(precursor_collection.structure(doc, fresh=mode == "LIVE"))
    graph = precursor_evidence_graph.analyze(ready, mode=mode, now=as_of, new_document_ids=new_ids)
    import networkx as nx
    network = nx.Graph()
    network.add_nodes_from(x["observation_id"] for x in graph["observations"])
    network.add_edges_from((e["left"], e["right"]) for e in graph["edges"])
    result = deepcopy(graph["protected_result"])
    result.update(format=VERSION, withheld_documents=withheld,
                  graph={"nodes": network.number_of_nodes(), "edges": network.number_of_edges(),
                         "components": nx.number_connected_components(network),
                         "reference_checks": graph["reference_checks"], "pairs": graph["pairs"],
                         "blocked": graph["blocked"], "rejected_links": graph["rejected_links"]},
                  retained_leads=[{"document_id": d["document_id"], "origin_url": d["origin_url"],
                                   "published_at": d.get("published_at"), "body_status": d.get("body_status", "UNKNOWN"),
                                   "provenance": d.get("provenance", "UNKNOWN"),
                                   "events": precursor_collection.structure(d).get("retained_collection_events", [])}
                                  for d in documents],
                  s_stage="UNKNOWN", s_stage_policy="Existing S1/S2/S3 meanings and records unchanged",
                  forecast_performance="BLOCKED", early_success_cases=0)
    for candidate in result.get("candidates", []):
        candidate.update(s_stage="UNKNOWN", industry="UNKNOWN", subindustry="UNKNOWN",
                         total_qualified_supply="UNKNOWN", early_success_verified=False)
    return stamp_export(result)


def cycle(root, config, *, use_ai=True, client=None, api_config=None, api_adapter=None, mode="LIVE"):
    """One bounded pass. Failed sources remain failures; no automatic retry loop."""
    ledger = Ledger(root)
    if mode not in ("LIVE", "BACKFILL"):
        ledger.close()
        raise ValueError("COLLECTION_MODE_MUST_BE_LIVE_OR_BACKFILL")
    client = client or SourceClient()
    limit = config.get("document_limit", 10)
    if type(limit) is not int or not 1 <= limit <= 100:
        ledger.close()
        raise ValueError("document_limit must be 1..100")
    started_cpu = time.process_time()
    started_wall = time.monotonic()
    run_id = "v4-" + uuid.uuid4().hex
    failures, new_ids, readings, exploration = [], [], [], []
    unchanged = []
    def failure(kind, url, exc):
        from bct.precursor_source_search import error_status
        item = {"kind": kind, "url": url, "status": "BLOCKED" if isinstance(exc, ValueError) else error_status(exc),
                "reason": str(exc)[:240]}
        failures.append(item)
        with ledger.db:
            ledger.event("FAILURE", {"run_id": run_id, **item})
    try:
        with ledger.worker():
            api_router = None
            if api_config is not None:
                from .free_ai import Router
                api_router = Router(ledger, api_config, run_id=run_id, adapter=api_adapter)
            with ledger.db:
                ledger.event("RUN_STARTED", {"run_id": run_id, "mode": mode, "config_sha256": sha(config)})
            urls = list(config.get("urls", []))
            for cik in config.get("ciks", []):
                try:
                    urls.extend(f["url"] for f in client.filings(cik))
                    record, raw = client.listing(cik)
                    with ledger.db:
                        ledger.db.execute("INSERT OR IGNORE INTO blobs VALUES(?,?)", (sha(raw), raw))
                        ledger.event("SEC_LISTING_CAPTURED", {"run_id": run_id, **record})
                except Exception as exc:
                    failure("SEC_DISCOVERY", "CIK:" + str(cik), exc)
            for feed in config.get("feeds", []):
                try:
                    raw, _, _, _ = client.fetch(feed)
                    for lead in rss_leads(raw):
                        if len(urls) >= limit:
                            break
                        urls.append(lead["url"])
                    with ledger.db:
                        raw_id = sha(raw)
                        ledger.db.execute("INSERT OR IGNORE INTO blobs VALUES(?,?)", (raw_id, raw))
                        ledger.event("FEED_CAPTURED", {"run_id": run_id, "url": feed, "raw_sha256": raw_id})
                except Exception as exc:
                    failure("RSS", feed, exc)
            extractor = CPUExtractor(root) if use_ai else None
            captured = 0
            for url in list(dict.fromkeys(urls))[:limit]:
                try:
                    doc, raw, views = client.document(url)
                    previous = ledger.db.execute("SELECT payload FROM documents WHERE id=?", (doc["document_id"],)).fetchone()
                    if previous and all(json.loads(previous[0]).get(k) == doc.get(k) for k in ("origin_url", "raw_sha256", "body_sha256")):
                        # A real refresh established identical content. Reuse its
                        # reading instead of repeating CPU/API work or captures.
                        unchanged.append(doc["document_id"])
                        readings.append({"document_id": doc["document_id"], "ai_status": "NOT_RUN_UNCHANGED_CONTENT"})
                        with ledger.db:
                            ledger.event("SOURCE_REFRESH_UNCHANGED", {"run_id": run_id, "document_id": doc["document_id"]})
                        captured += 1
                        continue
                    reading = {"parser_comparison": views}
                    if extractor:
                        try:
                            reading["ai"] = extractor.extract(doc, max_windows=config.get("ai_windows_per_document", 4))
                            for span in reading["ai"]["spans"]:
                                if span["label"] == "product":
                                    physical = precursor_scope_reader.valid_product(span["text"])
                                    exploration.append({"product": span["text"], "source_reference": span,
                                                        "origin_url": doc["origin_url"], "published_at": doc.get("published_at"),
                                                        "industry": "UNKNOWN", "subindustry": "UNKNOWN",
                                                        "specification": "UNKNOWN", "region": "UNKNOWN",
                                                        "qualified_supply_pool": "UNKNOWN",
                                                        "status": "EXPLORATION_LEAD" if physical else "PHYSICAL_TARGET_UNKNOWN_REQUIRES_REVIEW",
                                                        "novelty_vs_V33": "UNKNOWN", "forecast_candidate": False})
                        except Exception as exc:
                            reading["ai"] = {"status": "BLOCKED", "reason": str(exc)[:240]}
                            failure("CPU_EXTRACTION", url, exc)
                            # Failed model prerequisite is common to this run;
                            # preserve the first diagnosis and avoid repeated load.
                            extractor = None
                    elif use_ai:
                        reading["ai"] = {"status": "BLOCKED", "reason": "model prerequisite failed earlier in run"}
                    else:
                        reading["ai"] = {"status": "NOT_RUN", "reason": "explicit --no-ai"}
                    if ledger.capture(doc, raw, reading):
                        new_ids.append(doc["document_id"])
                        with ledger.db:
                            ledger.event("READ_QUEUE", {"document_id": doc["document_id"], "state": "PENDING",
                                "source_role": config.get("source_roles", {}).get(url, "BROAD_EXPLORATION"),
                                "source_version": doc["body_sha256"]})
                    if api_router and len(readings) < api_router.config["document_limit"]:
                        # Raw and CPU reading are committed first. API WAIT/denial
                        # cannot erase a captured source or mark it analyzed.
                        api_router.read(doc)
                    readings.append({"document_id": doc["document_id"], "ai_status": reading["ai"]["status"]})
                    captured += 1
                except Exception as exc:
                    failure("DOCUMENT_CAPTURE", url, exc)
            result = analyze(ledger.latest_documents(), mode=mode, new_ids=new_ids)
            result.update(run_id=run_id, live_captured=captured if mode == "LIVE" else 0,
                          acquired_or_reused_documents=captured, new_document_ids=new_ids, failures=failures,
                          unchanged_document_ids=unchanged,
                          readings=readings, exploration_targets=exploration,
                          known_target_check_count=len(result.get("outcomes", [])),
                          new_verified_target_discoveries=0,
                          integration_status="BLOCKED" if failures or not captured else
                          "PASS" if all(r["ai_status"] in ("PASS", "NOT_RUN_UNCHANGED_CONTENT") for r in readings) else "PARTIAL",
                          cpu_seconds=time.process_time()-started_cpu, wall_seconds=time.monotonic()-started_wall,
                          process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                          paid_api_calls=0, additional_api_cost=0,
                          warning="LIVE captures are observation logs, not validated EARLY performance")
            if api_router:
                from .free_ai import api_status
                result["api_annotations"] = api_status(ledger)
                result["api_calls_this_run"] = api_router.calls
                result["api_semantic_accuracy"] = "UNKNOWN"
            return ledger.save_run(run_id, result, mode)
    finally:
        ledger.close()


def replay(root, batch, as_of, *, mode="BACKFILL"):
    require_objective(batch)
    if mode not in ("BACKFILL", "SYNTHETIC"):
        raise ValueError("Imported data cannot be LIVE")
    result = analyze(batch["documents"], mode=mode, as_of=as_of)
    ledger = Ledger(root)
    try:
        with ledger.worker():
            run_id = "replay-" + sha([batch, as_of, mode])
            result.update(input_sha256=sha(batch), integration_status="FUNCTIONAL_ONLY",
                          public_confirmation_evaluation="NOT_RUN: require independent frozen evaluation corpus")
            return ledger.save_run(run_id, result, mode)
    finally:
        ledger.close()

