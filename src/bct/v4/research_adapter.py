"""Explicit opt-in BACKFILL adapter to the unchanged domain engine.

AI facts remain attributed to AI; neither source text nor the operating parser
is rewritten. This module is not called by the LIVE collection/alert path.
"""
from copy import deepcopy
import re

from bct import precursor_collection as collection, precursor_evidence_graph as graph
from bct import precursor_scope_reader as scope, precursor_temporal as temporal
from bct import precursor_discovery as discovery
from bct.objective_lock import stamp_export
from .free_ai import validate_reading, APIError
from .store import sha

VERSION = "bct-v4-research-adapter-2"


def _literal_field(doc, fact):
    value = fact.get("value")
    if not value:
        return None
    quote = fact["quote"]
    index = quote.find(value)
    if index < 0 or quote.find(value, index+1) >= 0:
        return None
    start = fact["start"] + index
    return scope.field(doc, start, start+len(value))


def _proposal_events(doc, proposal):
    reading = validate_reading(proposal["text"], doc, proposal["source"])
    native = collection.structure(doc)
    added, held, products = [], [], []
    for item in reading["items"]:
        if not item["physical_exploration_lead"]:
            continue
        products.append({"product": item["entity"]["value"], "reference": item["entity"]["reference"],
                         "origin": "GROQ_SOURCE_BOUND_ADVISORY", "s_stage": "UNKNOWN"})
        entity = _literal_field(doc, item["entity"])
        matches = [e for e in native["retained_collection_events"] if entity
                   and e["locator"]["start"] <= entity["locator"]["start"] < entity["locator"]["end"] <= e["locator"]["end"]
                   and e["locator"]["start"] < item["context"]["end"] and item["context"]["start"] < e["locator"]["end"]]
        if len(matches) != 1:
            held.append({"item": item["input_item_index"], "reason": "NO_UNIQUE_EXISTING_EVENT_CONTRACT"})
            continue
        original = matches[0]
        # Re-evaluate against the entire source event, not a model-picked
        # sentence that might omit a condition, negation or relief statement.
        expanded = {k: deepcopy(item[k]) for k in ("kind", "role", "actuality")}
        expanded["entity"] = {k: item["entity"][k] for k in ("value", "quote", "start", "end")}
        expanded["facts"] = [{k: f[k] for k in ("field", "value", "quote", "start", "end")} for f in item["facts"]]
        a = doc["body"].rfind("\n", 0, original["locator"]["start"])+1
        b = doc["body"].find("\n", original["locator"]["end"])
        b = len(doc["body"]) if b < 0 else b
        expanded["context"] = {"quote": doc["body"][a:b], "start": a, "end": b}
        try:
            from .store import encode
            complete = validate_reading(encode({"items": [expanded]}), doc, proposal["source"])
            if not complete["items"]:
                raise ValueError("FULL_EVENT_NOT_IN_AI_INPUT")
            checked = complete["items"][0]
            from .public_input import COUNTER, LINK
            outside = doc["body"][a:original["locator"]["start"]] + doc["body"][original["locator"]["end"]:b]
            if COUNTER.search(outside) or LINK.search(outside.strip()):
                raise ValueError("MEANING_OR_COMMITMENT:ADJACENT_COUNTEREVIDENCE_REQUIRES_RELATION_REVIEW")
            if (checked["role"] == "UNKNOWN" or checked["actuality"] in ("NEGATED", "UNKNOWN")
                    or checked["role"] == "DEMAND_INCREASE" and checked["actuality"] != "ACTUAL"):
                raise ValueError("MEANING_OR_COMMITMENT_NOT_ESTABLISHED")
            expected_role = "DEMAND" if checked["role"] == "DEMAND_INCREASE" else "SUPPLY"
            if original["role"] != expected_role and checked["role"] != "RELIEF":
                raise ValueError("AI_ROLE_CONFLICTS_WITH_SOURCE_EVENT")
            event = deepcopy(original)
            proposed = {"product": checked["entity"], **{f["field"]: f for f in checked["facts"] if f["field"] in scope.FIELDS}}
            conflicts = []
            for field, fact in proposed.items():
                literal = _literal_field(doc, fact)
                if literal is None:
                    continue
                if field == "product" and not scope.valid_product(literal["value"]):
                    raise ValueError("EXISTING_PHYSICAL_TARGET_GRAMMAR_UNSUPPORTED")
                old = event["scope"].get(field)
                if old and graph.norm(old["value"]) != graph.norm(literal["value"]):
                    conflicts.append(field)
                else:
                    event["scope"][field] = literal
            if conflicts:
                raise ValueError("CONFLICTING_SOURCE_SCOPE:" + ",".join(sorted(conflicts)))
            # No model booleans/quantities/coverage flags are copied. Existing
            # source-bound extraction and validators own these contracts.
            event.update(event_id="ai-" + sha([doc["document_id"], original["locator"], event["scope"], checked["role"]]),
                         adapter_origin="GROQ_EXACT_AND_MEANING_GUARDED", advisory_item=item["input_item_index"],
                         advisory_role=checked["role"], source_event_id=original["event_id"])
            if checked["role"] == "RELIEF":
                # Keep the source's legal kind; relief is independently carried
                # in temporal_facts and a conservative hold below.
                event["adapter_relief"] = True
            discovery._validate(doc, event)
            event["temporal_facts"] = temporal.extract(doc, event)
            added.append(event)
        except (ValueError, APIError) as exc:
            held.append({"item": item["input_item_index"], "source_event_id": original["event_id"], "reason": str(exc)})
    # Duplicated model items cannot multiply facts or first observations.
    unique = {e["event_id"]: e for e in added}
    return native, list(unique.values()), held, products, reading


def analyze(documents, proposals, *, enabled=False, mode="BACKFILL", as_of=None):
    if mode not in ("BACKFILL", "SYNTHETIC"):
        raise ValueError("RESEARCH_ADAPTER_CANNOT_BE_LIVE")
    if len({d["document_id"] for d in documents}) != len(documents):
        raise ValueError("DUPLICATE_DOCUMENT_ID")
    prepared, forwarded, held, products, readings = [], [], [], [], {}
    for doc in documents:
        if enabled and doc["document_id"] in proposals:
            native, events, holds, leads, reading = _proposal_events(doc, proposals[doc["document_id"]])
            unsafe = {h["source_event_id"] for h in holds if h.get("source_event_id")
                      and h["reason"].startswith(("MEANING_OR_COMMITMENT", "CONFLICTING_SOURCE_SCOPE", "AI_ROLE_CONFLICTS"))}
            # Do not let a rejected AI event re-enter through the older parser.
            # Raw parser observations remain retained for auditing/exploration.
            native["precursor_events"] = [e for e in native["precursor_events"] if e["event_id"] not in unsafe]
            # Attach AFTER structure(): structure would replace external events.
            native["retained_collection_events"].extend(deepcopy(events))
            native["precursor_events"].extend(deepcopy(events))
            forwarded.extend(events)
            held.extend({"document_id": doc["document_id"], **x} for x in holds)
            products.extend(leads)
            readings[doc["document_id"]] = reading
        else:
            native = collection.structure(doc)
        prepared.append(native)
    result = graph.analyze(prepared, mode=mode, now=as_of)
    # Relief missed by the old domain grammar remains a conservative research
    # hold, not permission to ignore the source and promote a candidate.
    relief_holds = [e["event_id"] for e in forwarded if e.get("adapter_relief")]
    candidates = [] if relief_holds else deepcopy(result["protected_result"]["candidates"])
    for candidate in candidates:
        candidate.update(research_only=True, s_stage="UNKNOWN", early_success_verified=False)
    decreases = []
    by_doc = {d["document_id"]: d for d in prepared}
    for supply in [e for e in forwarded if e.get("advisory_role") == "SUPPLY_DECREASE"]:
        for demand in [e for d in prepared for e in d["precursor_events"] if e["role"] == "DEMAND"]:
            independent, reason = graph._independent(demand, supply, by_doc)
            decreases.append({"demand_event": demand["event_id"], "supply_event": supply["event_id"],
                              "residual_demand": demand, "qualified_supply": supply,
                              "independent": independent, "independence_hold": reason,
                              "comparison": temporal.compare(demand, supply, require_complete_scope=True),
                              "total_qualified_supply": "UNKNOWN", "s_stage": "UNKNOWN"})
    return stamp_export({"version": VERSION, "mode": mode, "adapter_enabled": enabled,
        "operational_integration_enabled": False, "s_stage": "UNKNOWN",
        "original_advisory_sha256": sha(proposals), "validated_readings": readings,
        "forwarded_events": forwarded, "held": held, "product_exploration": products,
        "supply_decrease_reviews": decreases, "unreconciled_relief": relief_holds,
        "engine": result, "candidates": candidates,
        "counts": {"product_exploration": len(products),
                   "demand_signals": sum(e["role"] == "DEMAND" for e in forwarded),
                   "supply_signals": sum(e["role"] == "SUPPLY" for e in forwarded),
                   "engine_observations_with_AI_events": sum(bool(set(o.get("event_ids", [])) & {e["event_id"] for e in forwarded}) for o in result["observations"]),
                   "linked_pairs": len(result["pairs"]), "bottleneck_research_candidates": len(candidates)},
        "forecast_performance": "NOT_RUN", "scope": "BACKFILL_OR_SYNTHETIC_RESEARCH_ONLY"})


def save(ledger, documents, proposals, *, enabled=False, mode="BACKFILL", as_of=None):
    """Append raw advisory and downstream output separately; replay is idempotent."""
    run_id = "adapter-" + sha([VERSION, documents, proposals, enabled, mode, as_of])
    previous = ledger.db.execute("SELECT payload FROM runs WHERE id=?", (run_id,)).fetchone()
    if previous:
        import json
        return json.loads(previous[0])
    for doc in documents:
        ledger.capture(doc, reading={"original_advisory": proposals.get(doc["document_id"]),
                                    "kind": "ORIGINAL_ADVISORY_NOT_PARSER_FACTS"})
    result = analyze(documents, proposals, enabled=enabled, mode=mode, as_of=as_of)
    return ledger.save_run(run_id, result, mode)
