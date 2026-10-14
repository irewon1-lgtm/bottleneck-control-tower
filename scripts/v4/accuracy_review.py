"""Offline, scoped stage-4 accounting of a hash-bound historical response.

No API calls or CPU-model stand-ins. This small development audit is not the
30/20 corpus evaluation; unadjudicated and unavailable inputs remain BLOCKED.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import resource
import sqlite3
import time

from bct.v4.free_ai import validate_reading
from bct.v4.semantics import PHYSICAL, VERSION as SEMANTIC_VERSION
from bct.v4.store import Ledger


GROUP = {"product": "product", "role": "demand_supply_role",
         "quantity": "quantity_unit_period", "unit": "quantity_unit_period",
         "period": "quantity_unit_period", "customer_group": "customer",
         "supply_pool": "qualified_supplier", "specification": "specification",
         "region": "region", "need_time": "time", "ready_time": "time",
         "lead_time": "time"}


def ratios(counts):
    tp, fp, fn = (counts.get(k, 0) for k in ("TP", "FP", "FN"))
    return {**{k: counts.get(k, 0) for k in ("TP", "FP", "FN", "UNKNOWN",
            "truth_absent_unknown", "known_truth_missed", "unreturned_record_field_slots",
            "truth_absent_no_record", "unreturned_record_positive_fields")},
            "precision_denominator": tp + fp, "recall_denominator": tp + fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}


def observation(expected, actual):
    """Wrong known values incur both FP and FN; no-answer is not a positive."""
    out = Counter()
    if actual is None:
        out["UNKNOWN"] += 1
        out["truth_absent_unknown" if expected is None else "known_truth_missed"] += 1
    if expected is not None and actual == expected:
        out["TP"] += 1
    else:
        if actual is not None:
            out["FP"] += 1
        if expected is not None:
            out["FN"] += 1
    return out


def value(item, field):
    if item is None:
        return None
    if field == "product":
        return item["entity"]["value"] if item["kind"] in PHYSICAL else None
    if field == "role":
        return None if item["role"] == "UNKNOWN" else [item["role"], item["actuality"]]
    return next((f["value"] for f in item["facts"] if f["field"] == field), None)


def assess(items, gold):
    grouped, total, observations = defaultdict(Counter), Counter(), []
    unreturned, used = [], set()
    for row in gold["rows"]:
        # These three historical contexts are the declared annotation scope.
        matches = [(i, x) for i, x in enumerate(items) if x["context"]["quote"] == row["quote"] and
                   ("match_entity" not in row or x["entity"]["value"] == row["match_entity"])]
        if len(matches) > 1:
            raise ValueError("AMBIGUOUS_GOLD_CONTEXT_ASSOCIATION")
        item = matches[0][1] if matches else None
        if matches:
            used.add(matches[0][0])
        if item is None:
            unreturned.append(row["id"])
        for field, expected in row["expected"].items():
            actual = value(item, field)
            counts = observation(expected, actual)
            if item is None:
                # An absent entity/event record is not an engine assertion of
                # UNKNOWN. Keep its missed positives, without crediting nulls.
                counts["UNKNOWN"] -= 1
                counts["unreturned_record_field_slots"] += 1
                if expected is None:
                    counts["truth_absent_unknown"] -= 1
                    counts["truth_absent_no_record"] += 1
                else:
                    counts["unreturned_record_positive_fields"] += 1
            total.update(counts); grouped[GROUP[field]].update(counts)
            observations.append({"row_id": row["id"], "field": field,
                "expected": expected, "actual": actual, "record_returned": item is not None,
                "counts": dict(counts)})
    contexts = {r["quote"] for r in gold["rows"]}
    unscored = []
    for index, item in enumerate(items):
        if index in used:
            continue
        if item["context"]["quote"] not in contexts:
            unscored.append(item)  # Truth outside annotation scope is unknown.
            continue
        # Extra claims inside adjudicated contexts count as FP, rather than
        # disappearing when an incorrect product misses an exact gold anchor.
        for field in GROUP:
            actual = value(item, field)
            if actual is None:
                continue
            counts = observation(None, actual)
            total.update(counts); grouped[GROUP[field]].update(counts)
            observations.append({"row_id": "UNEXPECTED_RECORD", "field": field,
                "expected": None, "actual": actual, "input_item_index": index,
                "record_returned": True, "counts": dict(counts)})
    mentions = []
    for truth in gold["exploration_mentions"]:
        extracted = any(x["context"]["quote"] == truth["quote"] and
                        x["entity"]["value"] == truth["value"] for x in items)
        mentions.append({**truth, "extracted": extracted})
    return {"micro": ratios(total), "by_field": {k: ratios(v) for k, v in grouped.items()},
            "observations": observations, "unreturned_records": unreturned,
            "exploration_mentions": mentions,
            "exploration_mention_recall": sum(x["extracted"] for x in mentions) / len(mentions) if mentions else None,
            "unscored_predictions": unscored,
            "scope": "DECLARED_DEVELOPMENT_CONTEXTS_ONLY_NOT_WHOLE_DOCUMENT_OR_HOLDOUT"}


def check_gold(gold, doc):
    if hashlib.sha256(doc["body"].encode()).hexdigest() != gold["source_body_sha256"]:
        raise ValueError("GOLD_SOURCE_HASH_MISMATCH")
    for row in [*gold["rows"], *gold["outside_input_audit"]]:
        if doc["body"][row["start"]:row["end"]] != row["quote"]:
            raise ValueError("GOLD_QUOTE_MISMATCH")
    for row in gold["rows"]:
        if not any(w["start"] <= row["start"] < row["end"] <= w["end"] for w in gold["selected_input"]["windows"]):
            raise ValueError("GOLD_OUTSIDE_DECLARED_INPUT")
        if any(v is not None and isinstance(v, str) and v not in row["quote"] for v in row["expected"].values()):
            raise ValueError("NONLITERAL_GOLD_VALUE")


def grounding(items, doc):
    passed = total = 0
    for item in items:
        facts = [item["context"], item["entity"], *item["facts"],
                 *(r["source_fact"] for r in item.get("semantic_review", []))]
        for fact in facts:
            if not fact["quote"]:
                continue
            total += 1
            passed += doc["body"][fact["start"]:fact["end"]] == fact["quote"] and bool(fact.get("reference"))
    return {"passed": passed, "total": total, "rate": passed / total if total else None,
            "meaning": "LITERAL_SOURCE_REFERENCES_INCLUDING_HELD_FACT_AUDITS_NOT_SEMANTIC_ACCURACY"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path("var/v4/groq-stage2/live"))
    parser.add_argument("--gold", type=Path, default=Path("docs/v4/STAGE4_GOLD.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--store-root", type=Path)
    args = parser.parse_args()
    gold = json.loads(args.gold.read_text())
    fixture = json.loads(Path("tests/fixtures/v4_stage3_official_source.json").read_text())
    source_path = (args.source_root / "v4.sqlite3").resolve()
    source_digest_before = hashlib.sha256(source_path.read_bytes()).hexdigest()
    with sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True) as db:
        doc = json.loads(db.execute("SELECT payload FROM documents WHERE id=?", (gold["document_id"],)).fetchone()[0])
        raw = db.execute("SELECT data FROM blobs WHERE id=?", (gold["source_raw_sha256"],)).fetchone()[0]
        responses = [json.loads(r[0]) for r in db.execute("SELECT payload FROM events WHERE kind='API_RESPONSE'")]
    if hashlib.sha256(raw).hexdigest() != gold["source_raw_sha256"]:
        raise ValueError("NATIVE_SOURCE_HASH_MISMATCH")
    response = next(r for r in responses if hashlib.sha256(r["text"].encode()).hexdigest() == fixture["response_sha256"])
    check_gold(gold, doc)
    if gold["selected_input"] != fixture["selected_input"]:
        raise ValueError("INPUT_SCOPE_CHANGED")
    cpu, wall = time.process_time(), time.perf_counter()
    result = validate_reading(response["text"], doc, gold["selected_input"])
    resource_use = {"offline_validation_cpu_seconds": time.process_time() - cpu,
                    "offline_validation_wall_seconds": time.perf_counter() - wall,
                    "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                    "CPU_model_inference": "BLOCKED_NO_WEIGHTS_OR_MATCHING_SAVED_OUTPUT",
                    "historical_Groq_generation_seconds": "UNKNOWN_NOT_RECORDED"}
    report = {"semantic_policy_version": SEMANTIC_VERSION,
        "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
        "body_sha256": gold["source_body_sha256"], "raw_sha256": gold["source_raw_sha256"],
        "response_sha256": fixture["response_sha256"], "document_id": gold["document_id"],
        "published_at": doc["published_at"], "source_body_status": doc["body_status"],
        "source_provenance": doc["provenance"], "source_status": result["source_status"],
        "metrics": assess(result["items"], gold),
        "raw_model_metrics": assess(json.loads(response["text"])["items"], gold),
        "grounding": grounding(result["items"], doc), "coverage": result["coverage"],
        "outside_input_audit": gold["outside_input_audit"], "resource": resource_use,
        "generation_calls": 0, "tokens": 0, "API_cost_USD": 0,
        "historical_usage_reused_not_new": fixture["usage"],
        "independent_evaluation": "NOT_RUN_INSUFFICIENT_FROZEN_CORPUS",
        "whole_document_recall": "BLOCKED_NOT_EXHAUSTIVE_GOLD_AND_PARTIAL_SOURCE",
        "CPU_improvement": "BLOCKED", "bottleneck_early_detection": "NOT_RUN_STAGE6",
        "automatic_S_promotions": sum(x["s_stage"] != "UNKNOWN" or x["forecast_candidate"] for x in result["items"]),
        "result": result}
    if args.store_root:
        if (args.store_root / "v4.sqlite3").resolve() == source_path:
            raise ValueError("SOURCE_LEDGER_MUST_STAY_READ_ONLY")
        ledger = Ledger(args.store_root)
        ledger.capture(doc, raw)
        with ledger.db:
            ledger.event("STAGE4_ACCURACY_REVIEW", report)
        ledger.close()
        with sqlite3.connect((args.store_root / "v4.sqlite3").resolve().as_uri() + "?mode=ro", uri=True) as db:
            saved = json.loads(db.execute("SELECT payload FROM events WHERE kind='STAGE4_ACCURACY_REVIEW' ORDER BY seq DESC LIMIT 1").fetchone()[0])
            if saved != report or db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("REVIEW_PERSISTENCE_MISMATCH")
        report["storage"] = "PASS_SEPARATE_STAGE4_SQLITE_REOPENED"
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != source_digest_before:
        raise ValueError("SOURCE_LEDGER_CHANGED")
    report["source_ledger_sha256_unchanged"] = source_digest_before
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"micro": report["metrics"]["micro"], "grounding": report["grounding"],
                      "generation_calls": 0, "source_status": result["source_status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
