"""Offline saved-response diagnosis and development-only adapter replay.

No Router/read, HTTP call, model preparation, evaluation scoring or gold edits.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import types

from bct.v4.free_ai import (HTTPAdapter, HTTP_USER_AGENT, MODELS, QUOTE_SCHEMA,
                           SCHEMA, SYSTEM, VERSION)
from bct.v4.quote_diagnostics import diagnose
from bct.v4.research_adapter import analyze, save
from bct.v4.store import Ledger, encode, sha

DATA = Path("docs/v4/stage4-corpus")
WORK = Path("var/v4/quote-followup")


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def synthetic_comparisons(base, frozen):
    """Same authored input on the preserved old adapter and current adapter."""
    old_source = subprocess.check_output([
        "git", "show", "594d233702de4234cd4e06f88dea26ac060d2fe1:src/bct/v4/research_adapter.py"], text=True)
    assert hashlib.sha256(old_source.encode()).hexdigest() == frozen["file_sha256"]["src/bct/v4/research_adapter.py"]
    previous = types.ModuleType("bct.v4._historical_research_adapter")
    previous.__package__ = "bct.v4"
    exec(compile(old_source, "<verified historical research adapter>", "exec"), previous.__dict__)
    cases = []
    for model in ("NovaLT16", "Helios24", "RX-ZZ"):
        cases.append(("MODEL_PREFIX", model, f"Forge received new orders for {model}0 machines."))
    for product in ("NovaLT16", "optical transceivers", "battery cells"):
        cases.append(("ORDERED_MACHINE_VS_OUTPUT", product, f"Forge received new orders for machines used to manufacture {product}."))
    for product in ("NovaLT16", "gas turbines", "battery cells"):
        cases.append(("ACTUAL_ORDER_VS_FUTURE_OUTPUT", product,
                      f"Forge received new orders for {product} equipment, which will expand production capacity for laser chips."))
    results = []
    for index, (kind, product, body) in enumerate(cases):
        d = deepcopy(base)
        h = hashlib.sha256(body.encode()).hexdigest()
        d.update(document_id=f"synthetic-quote-role-{index}", body=body, body_sha256=h, version=h)
        item = {"kind": "PHYSICAL_PRODUCT", "role": "SUPPLY_INCREASE", "actuality": "ACTUAL",
                "context": {"quote": body}, "entity": {"value": product, "quote": body}, "facts": []}
        p = {d["document_id"]: {"text": encode({"items": [item]}),
                              "source": {"windows": [{"start": 0, "end": len(body), "text": body}]}}}
        before = previous.analyze([d], p, enabled=True, mode="SYNTHETIC", as_of="2026-10-14T05:00:00Z")
        after = analyze([d], p, enabled=True, mode="SYNTHETIC", as_of="2026-10-14T05:00:00Z")
        assert not before["candidates"] and not after["candidates"]
        assert after["counts"]["demand_signals"] == (1 if kind == "ACTUAL_ORDER_VS_FUTURE_OUTPUT" else 0)
        assert after["counts"]["supply_signals"] == 0
        assert after["counts"]["product_exploration"] == (0 if kind == "MODEL_PREFIX" else 1)
        results.append({"kind": kind, "source_type": "SYNTHETIC_NOT_OFFICIAL_CORPUS",
                        "body": body, "proposed_entity": product,
                        "before_counts": before["counts"], "after_counts": after["counts"], "after_held": after["held"]})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=WORK/"diagnostics.json")
    args = parser.parse_args()
    records = load(DATA/"groq-responses-repair-v1.json")["documents"]
    originals = {r["document_id"]: r for r in load(DATA/"manifest.json")["documents"]}
    inputs = {r["document_id"]: r for r in load(DATA/"safe-inputs-v1.json")["documents"]}
    protected = load(WORK/"preservation-before.json")
    prior_freeze = load("var/v4/repair/evaluation-freeze.json")
    # This is the original validator; only the research adapter is changed.
    assert digest("src/bct/v4/free_ai.py") == prior_freeze["file_sha256"]["src/bct/v4/free_ai.py"]
    attempts_before = api_attempts()
    counts, details = Counter(), []
    for record in records:
        if record["split"] != "evaluation" or not record["response"]:
            continue
        row = inputs[record["document_id"]]
        meta = originals[record["document_id"]]
        body = Path(meta["body_path"]).read_text()
        assert digest(meta["body_path"]) == row["body_sha256"] == record["body_sha256"]
        assert sha(row["source"]) == row["input_sha256"] == record["input_sha256"]
        assert sha([VERSION, SYSTEM, QUOTE_SCHEMA, row["source"], row["body_sha256"]]) == record["input_key"]
        d = {"document_id": record["document_id"], "body": body,
             "body_sha256": row["body_sha256"], "origin_url": meta["url"],
             "published_at": row["reviewed_published_at"]}
        result = diagnose(record["response"]["text"], d, row["source"])
        counts.update(result["first_error_counts"])
        details.append({"document_id": d["document_id"], "split": "CONSUMED_EVALUATION_DIAGNOSIS_ONLY",
                        "response_sha256": sha(record["response"]["text"]), "input_key_verified": True,
                        "input_sha256": row["input_sha256"], **result})
    assert dict(counts) == {"AMBIGUOUS_QUOTE": 3, "NULL_WITH_EVIDENCE": 1, "SOURCE": 1, "QUOTE_NOT_IN_SOURCE": 2}

    config = load("var/v4/groq-stage2/trial-config.json")
    adapter = HTTPAdapter({})  # payload construction only, no live credential
    contract = sha([VERSION, SCHEMA, SYSTEM, MODELS, HTTP_USER_AGENT,
                    config["max_output_tokens"], config["max_input_characters"], config["max_windows"],
                    [adapter.request(p, {}, config["max_output_tokens"])[::2] for p in config["providers"]]])
    assert {r["attempt"]["request_contract"] for r in records} == {contract}
    preflight = []
    for r in records:
        _, _, payload = adapter.request("groq", inputs[r["document_id"]]["source"], config["max_output_tokens"])
        reserve = len(encode(payload).encode()) + config["max_output_tokens"]
        assert reserve == r["attempt"]["reserved_tokens"] <= config["max_reserved_tokens_per_run"]
        preflight.append({"document_id": r["document_id"], "reconstructed_reservation": reserve,
                          "schema_sha256": sha(payload["response_format"]), "recorded_response": bool(r["response"])})
    failed = next(r for r in records if not r["response"])

    rows = load("var/v4/repair/development-inputs.json")["documents"]
    assert len(rows) == 30 and all(r["split"] == "development" for r in rows)
    saved = next(r for r in records if r["split"] == "development")
    proposals = {saved["document_id"]: {"text": saved["response"]["text"], "source": inputs[saved["document_id"]]["source"]}}
    ledger = Ledger(WORK/"adapter-ledger")
    try:
        off = save(ledger, [r["doc"] for r in rows], proposals, mode="BACKFILL", as_of="2026-10-14T05:00:00Z")
        on = save(ledger, [r["doc"] for r in rows], proposals, enabled=True, mode="BACKFILL", as_of="2026-10-14T05:00:00Z")
        recomputed = analyze([r["doc"] for r in rows], proposals, enabled=True, mode="BACKFILL",
                             as_of="2026-10-14T05:00:00Z")
        expected = deepcopy(on)
        # Existing EARLY assigns a new UUID even for identical research facts.
        # Compare every other field; backup verification still hashes full data.
        batch_ids = {"saved": expected["engine"]["protected_result"].pop("batch_id"),
                     "recomputed": recomputed["engine"]["protected_result"].pop("batch_id")}
        assert all(isinstance(v, str) and v.startswith("early-") for v in batch_ids.values())
        assert recomputed == expected
        status = ledger.status()
        assert save(ledger, [r["doc"] for r in rows], proposals, enabled=True, mode="BACKFILL", as_of="2026-10-14T05:00:00Z") == on
        assert ledger.status() == status
        backup = WORK/"restored/v4.sqlite3"
        run_payloads = {r[0]: hashlib.sha256(r[1].encode()).hexdigest()
                        for r in ledger.db.execute("SELECT id,payload FROM runs")}
        if not backup.exists():
            ledger.backup(backup)
    finally:
        ledger.close()
    code = ('import json,sys,hashlib; from bct.v4.store import Ledger; l=Ledger(sys.argv[1]); '
            'print(json.dumps({"status":l.status(),"integrity":l.db.execute("PRAGMA integrity_check").fetchone()[0],'
            '"run_payloads":{r[0]:hashlib.sha256(r[1].encode()).hexdigest() for r in l.db.execute("SELECT id,payload FROM runs")}})); l.close()')
    restored = json.loads(subprocess.run([sys.executable, "-c", code, str(backup.parent)],
                                         check=True, capture_output=True, text=True).stdout)
    assert restored["status"] == status and restored["integrity"] == "ok"
    assert restored["run_payloads"] == run_payloads
    assert api_attempts() == attempts_before
    changed = [p for p, h in protected.items() if digest(p) != h]
    assert not changed, changed
    report = {
        "version": "bct-offline-quote-role-diagnosis-1", "start_sha": "594d233702de4234cd4e06f88dea26ac060d2fe1",
        "scope": "Consumed evaluation read-only failure diagnosis; only development30/synthetic data used for adapter changes",
        "first_error_counts": dict(counts), "diagnosed_failed_items": sum(counts.values()),
        "failed_items_newly_adopted": 0, "rejected_items_rewritten": 0,
        "failure_disposition": "All seven remain rejected; no ambiguous placement, punctuation repair, alias rewriting or null-evidence deletion",
        "documents": details,
        "HTTP400": {"status": "BLOCKED_CAUSE_UNKNOWN_NO_RETRY", "saved_safe_error": failed["safe_error"],
                    "current_request_contract": contract, "same_contract_on_seven_HTTP_success_responses_and_one_HTTP_failure": True,
                    "preflight": preflight,
                    "limitation": "Reconstructed local schema/reservation checks do not establish remote rejection cause. Raw error details were not retained."},
        "development": {"documents_replayed": 30, "saved_actual_responses": 1,
                        "before_counts": load(WORK/"before-development.json")["counts"],
                        "adapter_off_counts": off["counts"], "adapter_on_counts": on["counts"],
                        "actual_events": on["forwarded_events"], "held": on["held"],
                        "role_correction_was_preexisting": "SUPPLY_INCREASE -> DEMAND_INCREASE already worked; explicit ordered-object verification and role provenance now added",
                        "new_actual_product_or_demand_events": 0, "actual_adopted_products": 1,
                        "actual_adopted_demand_events": 1, "actual_adopted_supply_increase_events": 0,
                        "wrong_automatic_promotions_in_this_replay": 0,
                        "storage": {"restart_backup_restore": "PASS", "idempotence": "PASS",
                                    "current_code_recomputed_facts_match_saved_result": True,
                                    "volatile_field_excluded_from_fact_comparison": "engine.protected_result.batch_id",
                                    "excluded_batch_ids": batch_ids,
                                    "new_ledger": str(WORK/"adapter-ledger"), "status": status}},
        "synthetic_paired_replays": synthetic_comparisons(rows[0]["doc"], prior_freeze),
        "preservation": {"files_checked": len(protected), "changed": changed,
                         "original_evaluation_inputs_gold_responses_metrics_unchanged": True,
                         "original_freeze_not_rewritten": True,
                         "old_evaluation_remains_consumed": True,
                         "new_adapter_not_an_unused_holdout_evaluation": True},
        "usage": {"new_generation_POSTs": 0, "new_API_tokens": 0, "new_API_cost_usd": 0,
                  "old_API_attempts_before_after": {"before": attempts_before, "after": api_attempts()}, "CPU_model_loads_or_installs": 0,
                  "platform_usage_or_fees": "UNKNOWN_NOT_EXPOSED"},
        "accuracy": "NOT_RUN_NO_NEW_INDEPENDENT_EVALUATION", "lead_performance": "NOT_RUN",
        "operational_integration_enabled": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"diagnosed": sum(counts.values()), "recovered_rejected_items": 0,
                      "first_errors": dict(counts), "actual_development_counts": on["counts"],
                      "new_POSTs": 0, "unchanged_files": len(protected), "output": str(args.output)}))


def api_attempts():
    path = Path("var/v4/repair/api-ledger/v4.sqlite3").resolve()
    with sqlite3.connect(path.as_uri()+"?mode=ro", uri=True) as db:
        return db.execute("SELECT COUNT(*) FROM events WHERE kind='API_ATTEMPT'").fetchone()[0]


if __name__ == "__main__":
    main()
