"""Offline replay of the committed repair evidence; no API or model loading.

The inference code/rubric remain frozen. This reporting wrapper reproduces the
isolated evaluator from the public source hashes, immutable responses and gold.
Literal/alias scores are not general semantic or independent forecast accuracy.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from bct.v4.event_evaluation import assess, metrics, norm
from bct.v4.free_ai import (APIError, VERSION, SYSTEM, QUOTE_SCHEMA, SCHEMA,
                           exact_quote_range, no_duplicate_keys, shape, validate_reading)
from bct.v4.semantics import PHYSICAL
from bct.v4.store import sha

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/v4/stage4-corpus"


def read(name):
    return json.loads((DATA / name).read_text())


def counts(result):
    return Counter({k: v for k, v in result.items() if isinstance(v, int)
                    and k not in ("precision_denominator", "recall_denominator")})


def event_rows(gold):
    return [(target, event) for target in gold["targets"] for event in target["events"]]

def known_field(event, field):
    facts = [f for f in event["facts"] if f["field"] == field]
    statuses = {f["status"] for f in facts}
    known = bool(statuses & {"VERIFIED_PRESENT", "VERIFIED_ABSENT"})
    scorable = known and not statuses & {"UNVERIFIED", "AMBIGUOUS"}
    positive = {norm(f["value"]) for f in facts if f["status"] == "VERIFIED_PRESENT"}
    return scorable, positive

def overlap(a, b):
    return a["start"] < b["end"] and b["start"] < a["end"]

def raw_items(text):
    data = json.loads(text, object_pairs_hook=no_duplicate_keys,
                      parse_constant=lambda _: (_ for _ in ()).throw(APIError("FORMAT")))
    try:
        shape(data, QUOTE_SCHEMA)
    except APIError:
        shape(data, SCHEMA)
    return data["items"]

def bind_contexts(items, doc, source):
    good, failures = [], []
    for index, item in enumerate(items):
        try:
            a, b = exact_quote_range(item["context"]["quote"], doc, source)
            bound = deepcopy(item)
            bound["context"] = {"quote": item["context"]["quote"], "start": a, "end": b}
            good.append(bound)
        except APIError as error:
            failures.append({"input_item_index": index, "reason": error.kind})
    return good, failures

def groq_product_predictions(items, doc, source):
    """Verify context+entity only; never repair a rejected item or its facts."""
    predictions, rejected = [], Counter()
    for item in items:
        if item.get("kind") not in PHYSICAL or not item["entity"].get("value"):
            continue
        try:
            ca, cb = exact_quote_range(item["context"]["quote"], doc, source)
            entity = item["entity"]
            if entity["value"] not in entity["quote"]:
                raise APIError("VALUE_NOT_LITERAL")
            a, b = exact_quote_range(entity["quote"], doc, source)
            if not ca <= a < b <= cb:
                raise APIError("ENTITY_OUTSIDE_CONTEXT")
            predictions.append({"value": entity["value"], "span": {"start": a, "end": b},
                                "context": {"start": ca, "end": cb}})
        except APIError as error:
            rejected[error.kind] += 1
    return predictions, rejected

def product_assess(predictions, gold):
    """Product extraction only: one reviewed physical target/event is one unit.

    Surface equivalence is restricted to frozen target.entity/entity_aliases.
    Matching requires source-span and context overlap with the same gold event.
    Ambiguous event associations and product truth are explicitly unscored.
    """
    events = event_rows(gold)
    expected, observed = set(), set()
    counts = Counter()
    for target, event in events:
        known, positive = known_field(event, "product")
        if known and positive:
            expected.add(event["event_id"])
        elif not known:
            counts["truth_unverified_events_excluded"] += 1
    seen_predictions = set()
    for prediction in predictions:
        found = [(target, event) for target, event in events
                 if norm(prediction["value"]) in
                    {norm(target["entity"]), *(norm(a) for a in target.get("entity_aliases", []))}
                 and overlap(prediction["span"], event["reference"])
                 and overlap(prediction.get("context", prediction["span"]), event["reference"])]
        if len(found) > 1:
            counts["unscored_ambiguous_event"] += 1
            continue
        if not found:
            counts["no_frozen_alias_event_match"] += 1
            key = (norm(prediction["value"]), prediction["span"]["start"], prediction["span"]["end"])
            if key in seen_predictions:
                counts["duplicate_predictions"] += 1
            else:
                seen_predictions.add(key)
                counts["FP"] += 1
            continue
        _, event = found[0]
        known, positive = known_field(event, "product")
        if not known:
            counts["truth_unverified_predictions_excluded"] += 1
        elif positive:
            if event["event_id"] in observed:
                counts["duplicate_predictions"] += 1
            observed.add(event["event_id"])
        else:
            key = (event["event_id"], norm(prediction["value"]))
            if key in seen_predictions:
                counts["duplicate_predictions"] += 1
            else:
                seen_predictions.add(key)
                counts["FP"] += 1
    counts.update(TP=len(expected & observed), FN=len(expected - observed))
    return metrics(counts)

def main():
    manifest = read("manifest.json")
    original = {x["document_id"]: x for x in manifest["documents"]}
    safe = {x["document_id"]: x for x in read("safe-inputs-v1.json")["documents"]}
    gold = {x["document_id"]: x for x in read("event-gold-evaluation-v1.json")["documents"]}
    cpu = {x["document_id"]: x for x in read("cpu-baseline-repair-v1.json")["evaluation"]["documents"]}
    records = read("groq-responses-repair-v1.json")["documents"]
    frozen = json.loads((ROOT / "docs/v4/PROGRESS.json").read_text())["repair"]["evaluation_freeze"]
    for f, h in frozen["file_sha256"].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest() != h:
            raise ValueError("FROZEN_INFERENCE_OR_RUBRIC_CHANGED:"+f)
    adopted, raw, cpu_product, adopted_product, raw_product = (Counter() for _ in range(5))
    common, raw_scored, skipped_context, source_reasons = 0, 0, 0, Counter()
    span_count = 0
    for record in records:
        if record["split"] != "evaluation" or not record["response"]:
            continue
        did = record["document_id"]; metadata = original[did]; row = safe[did]
        body = (ROOT / metadata["body_path"]).read_text()
        if hashlib.sha256(body.encode()).hexdigest() != row["body_sha256"]:
            raise ValueError("FROZEN_BODY_CHANGED")
        doc = {"document_id": did, "body": body, "body_sha256": row["body_sha256"],
               "origin_url": row["review"]["origin_url"], "published_at": row["reviewed_published_at"]}
        source = row["source"]; windows = source["windows"]
        if (sha(source) != row["input_sha256"] or
                sha([VERSION, SYSTEM, QUOTE_SCHEMA, source, row["body_sha256"]]) != record["input_key"]):
            raise ValueError("ACTUAL_TRANSMISSION_INPUT_CHANGED")
        text = record["response"]["text"]
        validation = validate_reading(text, doc, source)
        source_reasons.update(x["reason"] for x in validation["rejected_items"])
        accepted = validation["items"]
        scored = assess(accepted, gold[did], doc, windows)
        adopted.update(counts(scored["metrics"]))
        items = raw_items(text)
        contexts, rejected_contexts = bind_contexts(items, doc, source)
        if rejected_contexts:
            skipped_context += 1
        else:
            raw_scored += 1
            raw.update(counts(assess(contexts, gold[did], doc, windows)["metrics"]))
        baseline = cpu[did]
        if baseline["selected_windows"] != windows or baseline["body_sha256"] != row["body_sha256"]:
            raise ValueError("CPU_NOT_SAME_INPUT")
        predictions = []
        for span in baseline["spans"]:
            loc = span["locator"]
            if body[loc["start"]:loc["end"]] != span["text"] or not any(w["start"] <= loc["start"] < loc["end"] <= w["end"] for w in windows):
                raise ValueError("CPU_SPAN_NOT_IN_ACTUAL_INPUT")
            span_count += 1
            if span["label"] == "product":
                predictions.append({"value": span["text"], "span": loc, "context": loc})
        cpu_product.update(counts(product_assess(predictions, gold[did])))
        adopted_product.update(counts(product_assess(groq_product_predictions(accepted, doc, source)[0], gold[did])))
        raw_product.update(counts(product_assess(groq_product_predictions(items, doc, source)[0], gold[did])))
        common += 1
    result = {"common_response_documents": common, "raw_scored_documents": raw_scored,
              "raw_unscored_context_documents": skipped_context, "cpu_spans_source_checked": span_count,
              "adopted": metrics(adopted), "raw": metrics(raw), "cpu_product": metrics(cpu_product),
              "adopted_product": metrics(adopted_product), "raw_product": metrics(raw_product),
              "source_rejections": dict(source_reasons), "new_API_calls": 0}
    expected = read("evaluation-scores-repair-v1.json")
    for actual, target in [(result["adopted"], expected["groq_adopted"]["metrics"]),
                           (result["raw"], expected["groq_raw_semantic"]["metrics"]),
                           (result["cpu_product"], expected["common_product_entity_comparison"]["cpu"])]:
        if any(actual[k] != target[k] for k in ("TP", "FP", "FN", "precision", "recall", "f1")):
            raise ValueError("PORTABLE_REPLAY_DIFFERS_FROM_FROZEN_EVALUATOR")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
