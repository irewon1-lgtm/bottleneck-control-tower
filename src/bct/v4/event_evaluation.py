"""Frozen, event-aware accounting; unreviewed truth is never source absence."""
from collections import Counter, defaultdict
import hashlib

from .semantics import PHYSICAL

VERSION = "bct-event-evaluation-1"
FIELDS = ("product", "role", "actuality", "quantity", "unit", "period", "customer_group",
          "supply_pool", "specification", "region", "need_time", "ready_time", "lead_time", "relief", "alternative")
STATUSES = ("VERIFIED_PRESENT", "VERIFIED_ABSENT", "UNVERIFIED", "AMBIGUOUS")


def norm(value):
    return " ".join(value.split()).casefold() if isinstance(value, str) else value


def metrics(counts):
    tp, fp, fn = (counts.get(k, 0) for k in ("TP", "FP", "FN"))
    return {**dict(counts), "TP": tp, "FP": fp, "FN": fn,
            "precision_denominator": tp+fp, "recall_denominator": tp+fn,
            "precision": tp/(tp+fp) if tp+fp else None,
            "recall": tp/(tp+fn) if tp+fn else None,
            "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}


def check_gold(gold, doc, windows):
    if gold["document_id"] != doc["document_id"] or gold["body_sha256"] != doc["body_sha256"]:
        raise ValueError("GOLD_DOCUMENT_MISMATCH")
    if hashlib.sha256(doc["body"].encode()).hexdigest() != doc["body_sha256"]:
        raise ValueError("GOLD_BODY_HASH_MISMATCH")
    if gold.get("review_complete") and gold["reviewed_ranges"] != [{"start": w["start"], "end": w["end"]} for w in windows]:
        raise ValueError("GOLD_REVIEW_SCOPE_MISMATCH")
    seen = set()
    def reference(ref):
        if (not ref or not 0 <= ref["start"] < ref["end"] <= len(doc["body"])
                or doc["body"][ref["start"]:ref["end"]] != ref["quote"]
                or not any(w["start"] <= ref["start"] < ref["end"] <= w["end"] for w in windows)):
            raise ValueError("GOLD_REFERENCE_MISMATCH")
    for target in gold["targets"]:
        for event in target["events"]:
            if event["event_id"] in seen:
                raise ValueError("DUPLICATE_GOLD_EVENT")
            seen.add(event["event_id"])
            reference(event["reference"])
            facts = set()
            for fact in event["facts"]:
                if fact["field"] not in FIELDS or fact["status"] not in STATUSES or not fact.get("reason"):
                    raise ValueError("GOLD_FACT_CONTRACT")
                if fact["status"] == "VERIFIED_PRESENT":
                    reference(fact["reference"])
                    if fact["field"] not in ("role", "actuality") and fact["value"] not in fact["reference"]["quote"]:
                        raise ValueError("GOLD_NONLITERAL_VALUE")
                    if not (event["reference"]["start"] <= fact["reference"]["start"] < fact["reference"]["end"] <= event["reference"]["end"]):
                        raise ValueError("GOLD_FACT_OUTSIDE_EVENT")
                elif fact["status"] == "VERIFIED_ABSENT" and fact["value"] is not None:
                    raise ValueError("ABSENT_GOLD_CANNOT_HAVE_VALUE")
                key = (fact["field"], norm(fact["value"]), fact["status"])
                if key in facts:
                    raise ValueError("DUPLICATE_GOLD_FACT")
                facts.add(key)
    return True


def claims(item):
    result = []
    if item.get("kind") in PHYSICAL and item["entity"].get("value"):
        result.append(("product", item["entity"]["value"]))
    if item.get("role") not in (None, "UNKNOWN"):
        result.append(("role", item["role"]))
    if item.get("actuality") not in (None, "UNKNOWN"):
        result.append(("actuality", item["actuality"]))
    result.extend((f["field"], f["value"]) for f in item.get("facts", [])
                  if f["field"] != "product" and f.get("value") is not None)
    return list(dict.fromkeys(result))


def assess(items, gold, doc, windows):
    check_gold(gold, doc, windows)
    if not gold.get("review_complete"):
        return {"status": "BLOCKED_TRUTH_UNREVIEWED", "metrics": None}
    totals, fields = Counter(), defaultdict(Counter)
    events = [(t, e) for t in gold["targets"] for e in t["events"]]
    predictions, duplicate_count, unmatched = defaultdict(list), 0, []
    for item in items:
        value = item["entity"].get("value")
        context = item["context"]
        matches = [(t, e) for t, e in events
                   if norm(value) in {norm(t["entity"]), *(norm(x) for x in t.get("entity_aliases", []))}
                   and e["reference"]["start"] < context["end"] and context["start"] < e["reference"]["end"]]
        if len(matches) != 1:
            unmatched.append({"reason": "AMBIGUOUS_EVENT" if matches else "NO_REVIEWED_TARGET_EVENT", "claims": claims(item)})
            continue
        event_id = matches[0][1]["event_id"]
        for claim in claims(item):
            if claim in predictions[event_id]:
                duplicate_count += 1
            else:
                predictions[event_id].append(claim)
    details = []
    for target, event in events:
        positive = defaultdict(set)
        statuses = defaultdict(set)
        for fact in event["facts"]:
            statuses[fact["field"]].add(fact["status"])
            if fact["status"] == "VERIFIED_PRESENT":
                positive[fact["field"]].add(norm(fact["value"]))
        actual = defaultdict(set)
        for field, value in predictions[event["event_id"]]:
            actual[field].add(norm(value))
        per_event = {}
        for field in set(statuses) | set(actual):
            counts = Counter()
            known = statuses[field] & {"VERIFIED_PRESENT", "VERIFIED_ABSENT"}
            if not known or statuses[field] & {"UNVERIFIED", "AMBIGUOUS"}:
                counts["truth_unverified_claims"] = len(actual[field])
                counts["truth_unverified_fields"] = 1
            else:
                expected, observed = positive[field], actual[field]
                counts.update(TP=len(expected & observed), FP=len(observed-expected), FN=len(expected-observed))
                if not observed:
                    counts["UNKNOWN"] = 1
                    counts["known_truth_missed" if expected else "truth_absent_unknown"] = 1
            fields[field].update(counts); totals.update(counts)
            per_event[field] = dict(counts)
        details.append({"event_id": event["event_id"], "fields": per_event})
    for extra in unmatched:
        for field, value in extra["claims"]:
            # Full declared input has been reviewed; invented extra events are
            # FP. An ambiguous multi-event association is unscored and explicit.
            counts = Counter({"unmatched_predictions": 1})
            counts["unscored_ambiguous_event" if extra["reason"] == "AMBIGUOUS_EVENT" else "FP"] += 1
            totals.update(counts); fields[field].update(counts)
    return {"status": "MEASURED_SCOPED_AI_REVIEW_ONLY", "metrics": metrics(totals),
            "by_field": {k: metrics(v) for k, v in fields.items()}, "events": details,
            "duplicate_predictions": duplicate_count, "unmatched": unmatched,
            "reviewed_events": len(events), "reviewed_characters": sum(w["end"]-w["start"] for w in windows),
            "body_characters": len(doc["body"]), "scope": "FROZEN_INPUT_WINDOWS_NOT_FULL_DOCUMENT"}
