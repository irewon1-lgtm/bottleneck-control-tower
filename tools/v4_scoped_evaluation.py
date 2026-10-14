"""Replay a new, frozen source-window evaluation using the existing gold policy.

No network, inference, source repair, or score-threshold changes occur here.
CPU comparison is limited to source-located product entities, its common field.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from bct.v4.event_evaluation import assess, check_gold, metrics, norm
from bct.v4.free_ai import APIError, exact_quote_range, validate_reading
from bct.v4.semantics import PHYSICAL


def product_assess(predictions, gold):
    """One reviewed physical target/event, with frozen literal aliases only."""
    events = [(t, e) for t in gold["targets"] for e in t["events"]]
    expected, observed, seen = set(), set(), set()
    counts = Counter()
    for _, event in events:
        facts = [f for f in event["facts"] if f["field"] == "product"]
        statuses = {f["status"] for f in facts}
        if statuses & {"UNVERIFIED", "AMBIGUOUS"} or not statuses:
            counts["unreviewed_events"] += 1
        elif "VERIFIED_PRESENT" in statuses:
            expected.add(event["event_id"])
    for p in predictions:
        found = [(t, e) for t, e in events
                 if norm(p["value"]) in {norm(t["entity"]), *(norm(x) for x in t.get("entity_aliases", []))}
                 and e["reference"]["start"] < p["span"]["end"]
                 and p["span"]["start"] < e["reference"]["end"]]
        if len(found) > 1:
            counts["unscored_ambiguous_event"] += 1
        elif found:
            event = found[0][1]
            if event["event_id"] in expected:
                counts["duplicate_predictions"] += int(event["event_id"] in observed)
                observed.add(event["event_id"])
            else:
                facts = [f for f in event["facts"] if f["field"] == "product"]
                statuses = {f["status"] for f in facts}
                if "VERIFIED_ABSENT" in statuses and not statuses & {"UNVERIFIED", "AMBIGUOUS"}:
                    key = (event["event_id"], norm(p["value"]))
                    counts["duplicate_predictions" if key in seen else "FP"] += 1
                    seen.add(key)
                else:
                    counts["unreviewed_predictions"] += 1
        else:
            key = (norm(p["value"]), p["span"]["start"], p["span"]["end"])
            counts["duplicate_predictions" if key in seen else "FP"] += 1
            seen.add(key)
    counts.update(TP=len(expected & observed), FN=len(expected-observed))
    return metrics(counts)


def literal_products(items, doc, source):
    result, rejected = [], Counter()
    for item in items:
        if item.get("kind") not in PHYSICAL:
            continue
        try:
            a, b = exact_quote_range(item["entity"]["quote"], doc, source)
            ca, cb = exact_quote_range(item["context"]["quote"], doc, source)
            value = item["entity"]["value"]
            if not value or value not in item["entity"]["quote"] or not ca <= a < b <= cb:
                raise APIError("VALUE_NOT_LITERAL_OR_OUTSIDE_CONTEXT")
            result.append({"value": value, "span": {"start": a, "end": b}})
        except APIError as e:
            rejected[e.kind] += 1
    return result, dict(rejected)


def score_document(row, gold, cpu, text):
    doc, source = row["doc"], row["source"]
    check_gold(gold, doc, source["windows"])
    if not gold["review_complete"]:
        return {"status": "BLOCKED_TRUTH_UNREVIEWED"}
    if cpu["selected_windows"] != source["windows"]:
        raise ValueError("CPU_INPUT_SCOPE_CHANGED")
    for span in cpu["spans"]:
        a, b = span["locator"]["start"], span["locator"]["end"]
        if doc["body"][a:b] != span["text"] or not any(w["start"] <= a < b <= w["end"] for w in source["windows"]):
            raise ValueError("CPU_SPAN_SOURCE_MISMATCH")
    checked = validate_reading(text, doc, source)
    raw = json.loads(text)["items"]
    if source.get("response_protocol") == "context-reference-v1":
        from bct.v4.source_references import expand
        raw = expand({"items": raw}, source)["items"]
    bound, failed_contexts = [], []
    for i, item in enumerate(raw):
        try:
            a, b = exact_quote_range(item["context"]["quote"], doc, source)
            item = deepcopy(item)
            item["context"].update(start=a, end=b)
            bound.append(item)
        except APIError as e:
            failed_contexts.append({"index": i, "reason": e.kind})
    raw_products, rejected_products = literal_products(raw, doc, source)
    adopted_products, _ = literal_products(checked["items"], doc, source)
    cpu_products = [{"value": s["text"], "span": s["locator"]} for s in cpu["spans"] if s["label"] == "product"]
    return {"status": "MEASURED_FROZEN_WINDOWS_AI_REVIEW_NOT_HUMAN",
            "source_status": checked["source_status"], "rejected_items": checked["rejected_items"],
            "accepted_items": len(checked["items"]), "raw_items": len(raw),
            "adopted": assess(checked["items"], gold, doc, source["windows"]),
            "raw_context_only": None if failed_contexts else assess(bound, gold, doc, source["windows"]),
            "raw_context_failures": failed_contexts,
            "common_product": {"CPU": product_assess(cpu_products, gold),
                               "Groq_source_adopted": product_assess(adopted_products, gold),
                               "Groq_context_entity_only": product_assess(raw_products, gold)},
            "raw_entity_refusals": rejected_products,
            "raw_context_or_entity_scores_do_not_adopt_rejected_items": True}


def verify_freeze(root):
    freeze = json.loads((Path(root)/"freeze.json").read_text())
    for path, expected in freeze["file_sha256"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("FROZEN_EVALUATION_CONTRACT_CHANGED:" + path)
    return freeze
