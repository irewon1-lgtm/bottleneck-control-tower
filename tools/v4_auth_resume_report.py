"""Additional immutable report with the existing frozen scoring functions.

Previous responses, truth, scores and all frozen files are read-only inputs.
No model, network, semantic repair or downstream candidate promotion occurs.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

from bct.v4.free_ai import APIError, validate_reading
from bct.v4.quote_diagnostics import diagnose
from bct.v4.store import now
from v4_round2_replay import add
from v4_scoped_evaluation import score_document, verify_freeze

ROOT = Path("docs/v4/stage4-corpus/round2")
OUT = ROOT / "auth-resume"


def read(path):
    return json.loads(path.read_text())


def main():
    freeze = verify_freeze(ROOT)
    old = read(ROOT / "groq-responses.json")
    new = [read(p) for p in sorted((OUT / "documents").glob("*.json"))]
    rows = {r["document_id"]: r for r in read(ROOT / "inputs.json")["documents"]}
    gold = {r["document_id"]: r for r in read(ROOT / "event-gold.json")["documents"]}
    cpu = {r["document_id"]: r for r in read(ROOT / "cpu-baseline.json")["documents"]}
    combined = old["documents"] + new
    assert len({r["document_id"] for r in combined}) == len(combined), "INPUT_RETRIED"
    received = [r for r in combined if r["response"]]
    documents, errors, diagnostics, format_failures = [], [], [], []
    raw_roles, adopted_roles = Counter(), Counter()
    for item in received:
        did = item["document_id"]
        assert item["attempt"]["request_contract"] == freeze["request_contract"]
        try:
            raw = json.loads(item["response"]["text"])["items"]
        except (ValueError, KeyError, TypeError):
            format_failures.append({"document_id": did, "reason": "UNSCORABLE_MODEL_JSON"})
            continue
        try:
            scored = score_document(rows[did], gold[did], cpu[did], item["response"]["text"])
            checked = validate_reading(item["response"]["text"], rows[did]["doc"], rows[did]["source"])
            diagnostic = diagnose(item["response"]["text"], rows[did]["doc"], rows[did]["source"])
        except APIError as error:
            format_failures.append({"document_id": did, "error_type": type(error).__name__,
                                    "reason": error.kind})
            continue
        raw_roles.update(x["role"] for x in raw)
        adopted_roles.update(x["role"] for x in checked["items"])
        errors.extend(x["reason"] for x in checked["rejected_items"])
        documents.append({"document_id": did, "new_this_resume": item in new, **scored,
                          "raw_model": raw, "source_and_meaning_advisory": checked["items"]})
        diagnostics.append({"document_id": did, **diagnostic})
    common = {name: add(d["common_product"][name] for d in documents)
              for name in ("CPU", "Groq_source_adopted", "Groq_context_entity_only")}
    fields = sorted({k for d in documents for k in d["adopted"]["by_field"]})
    raw_fields = sorted({k for d in documents if d["raw_context_only"] for k in d["raw_context_only"]["by_field"]})
    selected = sum(rows[r["document_id"]]["source"]["selected_characters"] for r in received)
    body = sum(len(r["doc"]["body"]) for r in rows.values())
    path = Path("var/v4/sequential/api-ledger/v4.sqlite3").resolve()
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as ledger:
        states = [json.loads(p) for p, in ledger.execute("SELECT payload FROM events WHERE kind='API_PROVIDER_STATE' ORDER BY seq")]
        attempts = [json.loads(p) for p, in ledger.execute("SELECT payload FROM events WHERE kind='API_ATTEMPT' ORDER BY seq")]
    usage = Counter()
    for x in new:
        if x["response"]:
            usage.update(x["response"]["usage"])
    report = {"at": now(), "status": "MEASURED_SAME_FROZEN_EVALUATION_AFTER_AUTH_RECOVERY",
        "auth": {"external_GET_evidence": str(OUT/"auth-evidence.json"),
                 "fresh_generation_probe": str(OUT/"probe.json"), "latest_provider_state": states[-1],
                 "old401_attempt_retried": False, "root_cause_of_past401": "UNKNOWN", "key_or_settings_changed": False},
        "freeze_sha256": hashlib.sha256((ROOT/"freeze.json").read_bytes()).hexdigest(),
        "inference_code_model_prompt_inputs_and_scoring_unchanged": True,
        "previous_responses_gold_and_scores_preserved": True,
        "gold": {"method": "Existing two blind source-only AI reviews plus source-only adjudication; unchanged",
                 "human_verified": False, "reviewed_bounded_inputs": sum(g["review_complete"] for g in gold.values()),
                 "sha256": hashlib.sha256((ROOT/"event-gold.json").read_bytes()).hexdigest()},
        "processing": {"frozen_documents": len(rows), "eligible": sum(r["status"] == "ELIGIBLE" for r in rows.values()),
            "new_generation_attempted_documents": len(new), "new_generation_received_documents": sum(bool(x["response"]) for x in new),
            "cumulative_evaluation_attempted_documents": len(combined), "cumulative_evaluation_received_documents": len(received),
            "not_attempted_eligible": [did for did,r in rows.items() if r["status"] == "ELIGIBLE" and did not in {c["document_id"] for c in combined}],
            "failed_HTTP_no_model_output": [x["document_id"] for x in combined if not x["response"]],
            "transfer_blocked_or_context_held": [{"document_id": did, "reason": r["status"]} for did,r in rows.items() if r["status"] != "ELIGIBLE"],
            "strict_source_PASS_documents_including_empty": sum(d["source_status"] == "PASS" for d in documents),
            "empty_model_responses": sum(d["raw_items"] == 0 for d in documents),
            "returned_items": sum(d["raw_items"] for d in documents),
            "source_and_meaning_advisory_items": sum(d["accepted_items"] for d in documents),
            "source_rejected_items": len(errors), "source_rejection_counts": dict(Counter(errors)),
            "format_unscored_documents": format_failures,
            "format_unscored_are_not_transport_failures_or_correct_unknowns": True},
        "coverage": {"all20_body_characters": body, "actual_Groq_selected_characters": selected,
            "actual_Groq_fraction_of_all20": selected/body,
            "received_body_characters": sum(len(rows[x["document_id"]]["doc"]["body"]) for x in received),
            "scope": "EXACT_FROZEN_BOUNDED_INPUT_WINDOWS_ONLY", "whole_document_accuracy": "NOT_MEASURED"},
        "common_product_comparison": {"documents": len(documents), "unit": "REVIEWED_PRODUCT_TARGET_EVENT", **common,
            "CPU_role_quantity_period": "UNSUPPORTED_NOT_DIRECTLY_COMPARED"},
        "Groq_adopted": {"metrics": add(d["adopted"]["metrics"] for d in documents),
            "by_field": {f: add(d["adopted"]["by_field"].get(f,{}) for d in documents) for f in fields}},
        "Groq_raw_context_only": {"metrics": add(d["raw_context_only"]["metrics"] for d in documents if d["raw_context_only"]),
            "by_field": {f: add(d["raw_context_only"]["by_field"].get(f,{}) for d in documents if d["raw_context_only"]) for f in raw_fields},
            "scored_documents": sum(d["raw_context_only"] is not None for d in documents),
            "exact_context_scoring_does_not_adopt_invalid_quotes_or_override_source_rejections": True},
        "roles": {"raw_model": dict(raw_roles), "source_and_meaning_advisory": dict(adopted_roles)},
        "usage_this_resume": {"generation_POST_attempts": len(new), "generations_received": sum(bool(x["response"]) for x in new),
            "reported_tokens": dict(usage), "attempts_without_usage": sum(not x["response"] for x in new),
            "API_cost_KRW": 0, "billing_basis": "Existing user-confirmed Free Plan, no paid path/upgrade; no billing dashboard audit",
            "new_auth_GET_requests": 0, "prior_auth_GET_requests": 1, "platform_usage_cost": "UNKNOWN_SEPARATE"},
        "adoption_gate": {"product_FP_decreased": common["Groq_source_adopted"]["FP"] < common["CPU"]["FP"],
            "product_FN_not_increased": common["Groq_source_adopted"]["FN"] <= common["CPU"]["FN"],
            "status": "HOLD_UNTIL_ALL_QUALITY_CONDITIONS_MET", "AI_Shadow_enabled": False, "operating_automation_enabled": False},
        "S1_S2_S3": {"new_promotions": 0, "existing_research_S1": 1, "S2": 0, "S3": 0,
            "scope": "No downstream evaluation promotion executed; known development FOX-XP count reused, not rediscovered"},
        "prediction_performance": "NOT_RUN", "documents": documents,
        "limitations": ["Frozen literal aliases and source-only AI gold; not human or full-document accuracy.",
            "Prior401 without response and transfer/context holds are not model misses.",
            "This resumes the same consumed round2, not a newly unused holdout.",
            "Source binding, product identity, model event roles and downstream promotion are separate."]}
    for filename,data in (("scores.json", report), ("quote-diagnostics.json", diagnostics)):
        with (OUT/filename).open("x") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"processing":report["processing"],"common_product":common,
                      "Groq_adopted":report["Groq_adopted"]["metrics"],"usage":report["usage_this_resume"]}))


if __name__ == "__main__":
    main()
