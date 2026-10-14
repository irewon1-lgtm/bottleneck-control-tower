"""Offline reporting wrapper for the unchanged, pre-prediction frozen scorer.

Run: .venv/bin/python tools/v4_round2_replay.py
Only round2/scores.json is written; no requests, models, repair or new criteria.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

from bct.v4.event_evaluation import check_gold, metrics
from bct.v4.store import now
from v4_scoped_evaluation import product_assess, score_document, verify_freeze


ROOT = Path("docs/v4/stage4-corpus/round2")


def read(name):
    return json.loads((ROOT/name).read_text())


def add(values):
    counts = Counter()
    for v in values:
        counts.update({k: x for k, x in v.items() if type(x) is int and k not in ("precision_denominator", "recall_denominator")})
    return metrics(counts)


def main():
    freeze = verify_freeze(ROOT)
    rows = {r["document_id"]: r for r in read("inputs.json")["documents"]}
    cpu = {r["document_id"]: r for r in read("cpu-baseline.json")["documents"]}
    gold = {g["document_id"]: g for g in read("event-gold.json")["documents"]}
    assert set(gold) == set(rows), "GOLD_DOCUMENT_SET_CHANGED"
    received = [r for r in read("groq-responses.json")["documents"] if r["response"]]
    all_cpu, documents = [], []
    for did, row in rows.items():
        windows = (row["source"] or {}).get("windows", [])
        check_gold(gold[did], row["doc"], windows)
        if did not in cpu or not gold[did]["review_complete"]:
            continue
        c = cpu[did]
        assert c["selected_windows"] == windows and c["body_sha256"] == row["body_sha256"]
        assert c["model"] == freeze["models"]["cpu"] and c["revision"] == freeze["models"]["cpu_revision"]
        for span in c["spans"]:
            a, b = span["locator"]["start"], span["locator"]["end"]
            assert row["doc"]["body"][a:b] == span["text"] and any(w["start"] <= a < b <= w["end"] for w in windows)
        p = [{"value": s["text"], "span": s["locator"]} for s in c["spans"] if s["label"] == "product"]
        all_cpu.append({"document_id": did, "metrics": product_assess(p, gold[did]), "product_spans": len(p)})
    for response in received:
        did = response["document_id"]
        documents.append({"document_id": did, **score_document(rows[did], gold[did], cpu[did], response["response"]["text"])})
    common = {name: add(d["common_product"][name] for d in documents)
              for name in ("CPU", "Groq_source_adopted", "Groq_context_entity_only")}
    eligible = [r for r in rows.values() if r["status"] == "ELIGIBLE"]
    fields = sorted({k for d in documents for k in d["adopted"]["by_field"]})
    selected = sum(r["source"]["selected_characters"] for r in eligible)
    total = sum(len(r["doc"]["body"]) for r in rows.values())
    actual_AI = sum(rows[r["document_id"]]["source"]["selected_characters"] for r in received)
    cpu_common, ai_common = common["CPU"], common["Groq_source_adopted"]
    report = {"at": now(), "status": "MEASURED_PARTIAL_GROQ2_CPU14_AUTH_BLOCKED",
        "inference_freeze_sha256": hashlib.sha256((ROOT/"freeze.json").read_bytes()).hexdigest(),
        "scorer_frozen_before_predictions": True, "aggregation_only_wrapper_added_after_predictions": True,
        "gold_review": {"method": "Two blind source-only AI sessions plus separate source-only adjudication", "human_verified": False,
                        "completed_window_reviews": sum(g["review_complete"] for g in gold.values()),
                        "unreviewed_empty_window_documents": sum(not g["review_complete"] for g in gold.values()),
                        "adjudicated_gold_sha256": hashlib.sha256((ROOT/"event-gold.json").read_bytes()).hexdigest()},
        "processing": {"new_frozen_documents": len(rows), "transfer_eligible": len(eligible),
            "source_transfer_blocked": 4, "context_held": 2, "CPU_actual_documents": len(cpu),
            "Groq_attempted_documents": len(read("groq-responses.json")["documents"]),
            "Groq_received_documents": len(received), "HTTP401_failed_without_generation": 1,
            "eligible_unattempted_after_AUTH_block": len(read("groq-responses.json")["remaining"]),
            "strict_source_PASS_documents_including_empty_response": sum(d["source_status"] == "PASS" for d in documents),
            "returned_items": sum(d["raw_items"] for d in documents),
            "accepted_source_and_meaning_advisory_items": sum(d["accepted_items"] for d in documents),
            "rejected_items": sum(len(d["rejected_items"]) for d in documents),
            "no_claim_is_not_a_correct_TRUE_NEGATIVE": True},
        "coverage": {"frozen_body_characters_20": total, "CPU_actual_characters_14": selected,
            "CPU_fraction_of_all20_body": selected/total, "Groq_actual_characters_2": actual_AI,
            "Groq_fraction_of_all20_body": actual_AI/total, "outside_frozen_input_not_reviewed_characters": total-selected,
            "whole_document_accuracy": "NOT_MEASURED", "complex_tables_OCR_attachments": "NOT_VERIFIED"},
        "CPU_all14_product_only": {"metrics": add(x["metrics"] for x in all_cpu), "documents": all_cpu,
            "documents_with_zero_CPU_product_candidates": sum(x["product_spans"] == 0 for x in all_cpu),
            "new_same_input_baseline_not_past_restoration": True,
            "cpu_seconds": sum(c["cpu_seconds"] for c in cpu.values()),
            "wall_seconds_model_extraction": sum(c["wall_seconds"] for c in cpu.values()), "model_installs": 0},
        "common_product_comparison": {"documents": len(documents), "unit": "REVIEWED_PRODUCT_TARGET_EVENT", **common,
            "CPU_role_quantity_period_relation_accuracy": "UNSUPPORTED_NOT_DIRECTLY_COMPARED"},
        "Groq_adopted": {"metrics": add(d["adopted"]["metrics"] for d in documents),
            "by_field": {f: add(d["adopted"]["by_field"].get(f, {}) for d in documents) for f in fields},
            "pipeline_stage": "SOURCE_AND_MEANING_ADVISORY_NOT_EXISTING_ENGINE_FORWARDING"},
        "Groq_raw_context_only": {"metrics": add(d["raw_context_only"]["metrics"] for d in documents if d["raw_context_only"]),
            "scored_documents": sum(d["raw_context_only"] is not None for d in documents),
            "context_scores_do_not_adopt_invalid_entities_or_facts": True},
        "adoption_gate": {"status": "HOLD_INCOMPLETE_EVALUATION_AND_AUTH",
            "product_FP_decreased_in_common_sample": ai_common["FP"] < cpu_common["FP"],
            "product_FN_not_increased_in_common_sample": ai_common["FN"] <= cpu_common["FN"],
            "remaining11_needed_before_completeness_judgment": True,
            "full_system_improvement": "NOT_ESTABLISHED", "operating_AI_enabled": False},
        "usage": read("usage.json"), "S3_or_leading_prediction_performance": "NOT_RUN",
        "documents": documents,
        "limitations": ["Small source-window sample; AI source review is not human ground truth.",
            "Frozen literal aliases measure scoped extraction, not all semantically equivalent language.",
            "HTTP failure, transfer block, unrun, ambiguous truth and unread body are excluded and reported separately from model misses.",
            "The old evaluated20 and seven rejected items are unchanged; this is a separate partially consumed new20 evaluation.",
            "CPU14 and Groq2 totals have different denominators; direct product comparison uses the common2 only.",
            "Raw-context/source-adopted entities/advisories/engine signals/candidates are separate stages."]}
    (ROOT/"scores.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"status": report["status"], "common_product": common,
                      "adopted": report["Groq_adopted"]["metrics"], "coverage": report["coverage"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
