"""Read-only, exact-match diagnostics; never repairs or adopts rejected facts."""
from collections import Counter
import hashlib
import json

from .free_ai import (APIError, QUOTE_SCHEMA, SCHEMA, no_duplicate_keys, shape,
                      validate_reading)


def occurrences(body, quote):
    if not quote:
        return []
    out, cursor = [], 0
    while (a := body.find(quote, cursor)) >= 0:
        out.append({"start": a, "end": a+len(quote)})
        cursor = a+1
    return out


def diagnose(text, doc, source):
    """Enumerate secondary violations without changing first-error semantics.

    A unique enclosing context is diagnostic evidence, not authorization to
    choose one of several globally repeated quotations. No normalized/fuzzy
    match or historical model offset is used for acceptance.
    """
    verified = validate_reading(text, doc, source)
    data = json.loads(text, object_pairs_hook=no_duplicate_keys)
    try:
        shape(data, QUOTE_SCHEMA)
    except APIError:
        shape(data, SCHEMA)
    failures = {x["input_item_index"]: x["reason"] for x in verified["rejected_items"]}
    rows = []
    body = doc["body"]
    for index, item in enumerate(data["items"]):
        context_positions = occurrences(body, item["context"]["quote"])
        checks = []
        entries = [("context", item["context"]), ("entity", item["entity"])]
        entries += [(f"facts[{n}].{f['field']}", f) for n, f in enumerate(item["facts"])]
        for path, fact in entries:
            positions = occurrences(body, fact["quote"])
            in_input = [p for p in positions if any(w["start"] <= p["start"] < p["end"] <= w["end"] for w in source["windows"])]
            in_context = [p for p in positions if len(context_positions) == 1
                          and context_positions[0]["start"] <= p["start"] < p["end"] <= context_positions[0]["end"]]
            issues = []
            if path != "context" and fact["value"] is None:
                if fact["quote"]:
                    issues.append("NULL_WITH_EVIDENCE")
            else:
                if not positions:
                    issues.append("QUOTE_NOT_IN_SOURCE")
                elif len(positions) > 1:
                    issues.append("AMBIGUOUS_QUOTE")
                elif not in_input:
                    issues.append("QUOTE_OUTSIDE_INPUT")
                if path != "context" and (not fact["value"] or fact["value"] not in fact["quote"]):
                    issues.append("VALUE_NOT_LITERAL")
                if path != "context" and len(context_positions) == 1 and positions and not in_context:
                    issues.append("FACT_OUTSIDE_EVENT_CONTEXT")
            checks.append({"path": path, "quote": fact["quote"], "value": fact.get("value"),
                           "body_occurrences": positions, "transmitted_occurrences": in_input,
                           "exact_context_occurrences": in_context, "issues": issues,
                           "model_coordinates_used": False})
        fields = Counter(f["field"] for f in item["facts"])
        duplicate = sorted(f for f, n in fields.items() if n > 1)
        identity = [f["value"] for f in item["facts"] if f["field"] == "product"
                    and item["entity"]["value"] and f["value"] not in (None, item["entity"]["value"])]
        rows.append({"input_item_index": index, "first_error": failures.get(index),
                     "source_status": "REJECTED" if index in failures else "SOURCE_VALID",
                     "kind": item["kind"], "model_role": item["role"],
                     "duplicate_fields": duplicate, "conflicting_product_fact_values": identity,
                     "exact_product_alias_substitution_allowed": False, "quote_checks": checks})
    return {"body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "rejected_items": verified["rejected_items"], "items": rows,
            "accepted_count": len(verified["items"]),
            "first_error_counts": dict(Counter(failures.values())),
            "policy": "READ_ONLY_DIAGNOSIS_NOT_FACT_RECOVERY_OR_NEW_HOLDOUT_EVALUATION"}
