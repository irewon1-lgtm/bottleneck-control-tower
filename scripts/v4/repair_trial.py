"""Explicit research commands; never imported by collection/alert workflows.

One invocation of run-one permits at most the existing one Groq POST. All
invocations share one persistent budget/WAIT ledger. No retries or fallback.
"""
import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

from bct.v4.free_ai import Router, source_input, HTTPAdapter, SYSTEM, QUOTE_SCHEMA, MODELS
from bct.v4.public_input import review_native, selected_input, VERSION as INPUT_VERSION
from bct.v4.store import Ledger, sha, encode, now

ROOT = Path("var/v4/repair")
MANIFEST = Path("docs/v4/stage4-corpus/manifest.json")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n")


def prepare(split):
    manifest = json.loads(MANIFEST.read_text())
    config = json.loads(Path("var/v4/groq-stage2/trial-config.json").read_text())
    rows = []
    captures = json.loads(Path("var/v4/stage4-recovery/native-source-records.json").read_text())
    access = json.loads(Path("var/v4/stage4-recovery/access-checks.json").read_text())
    recovery_path = ROOT / "native-recovery/results.json"
    recovered = json.loads(recovery_path.read_text()) if recovery_path.exists() else []
    # The frozen original ledger is strictly read-only; derived review metadata
    # belongs to a separate research ledger and cannot change the source corpus.
    with sqlite3.connect("file:var/v4/stage4-recovery/corpus-ledger/v4.sqlite3?mode=ro", uri=True) as db:
        for row in manifest["documents"]:
            if row["split"] != split:
                continue
            doc = json.loads(db.execute("SELECT payload FROM documents WHERE id=?", (row["document_id"],)).fetchone()[0])
            raw = gzip.decompress(Path(row["raw_path"]).read_bytes()) if row.get("raw_path") else None
            native_recovery = next((x for x in recovered if x["document_id"] == row["document_id"]), None)
            derived_row = deepcopy(row)
            if raw is None and native_recovery and native_recovery.get("body_matches_frozen"):
                from bct.precursor_official_source import verify
                raw = gzip.decompress((ROOT / "native-recovery" / (native_recovery["new_raw_sha256"]+".html.gz")).read_bytes())
                check = verify(raw, row["url"], native_recovery["final_url"], now(), 200, "text/html")
                doc.update(frozen_raw_sha256=doc.get("raw_sha256"), raw_sha256=native_recovery["new_raw_sha256"],
                           checks=check["checks"], native_recovery_scope="NEW_NATIVE_EXACT_FROZEN_BODY_MATCH_NOT_OLD_HTML_RESTORATION")
                doc.update(original_acquired_at=doc.get("acquired_at"), acquired_at=now(),
                           acquired_at_source="LOCAL_NATIVE_VERIFICATION_TIME_NOT_HISTORICAL_CAPTURE")
                # Keep the frozen text's PARTIAL/provenance verdict; only the
                # separately reviewed API input gains native identity proof.
                derived_row.update(raw_sha256=doc["raw_sha256"], final_url=native_recovery["final_url"])
            # This is derived, native-header-reviewed publication metadata. The
            # original document/provenance is preserved in the source ledger.
            doc["original_published_at"] = doc.get("published_at")
            doc["published_at"] = row["published_at"]
            doc["publication_precision"] = row["publication_proof"].get("precision", doc.get("publication_precision", "DAY"))
            doc["publication_metadata_origin"] = "FROZEN_NATIVE_HEADER_PROOF_SIDECAR"
            identity = next((x for x in [*captures, *access]
                             if x.get("url") == row["url"] and x.get("raw_sha256", x.get("sha256")) == doc.get("raw_sha256")), {})
            original_identity_verified = doc.get("checks", {}).get("original_identity") is True
            record = {**derived_row, "final_url": derived_row.get("final_url") or identity.get("final_url") or (row["url"] if original_identity_verified else "UNVERIFIED")}
            review = review_native(doc, raw, record)
            if native_recovery and not native_recovery.get("body_matches_frozen"):
                review["reasons"].append("REFETCHED_BODY_DIFFERS_FROZEN_VERSION_NOT_REPLACED")
            entry = {"document_id": doc["document_id"], "split": split, "split_index": row["split_index"],
                     "body_sha256": row["body_sha256"], "body_status": row["body_status"],
                     "review": review, "doc": doc}
            try:
                selected = selected_input(doc, config, review, {})
                _, _, payload = HTTPAdapter({}).request("groq", selected, config["max_output_tokens"])
                reserve = len(encode(payload).encode()) + config["max_output_tokens"]
                entry.update(status="ELIGIBLE", source=selected, reserved_tokens=reserve,
                             within_fixed_run_budget=reserve <= config["max_reserved_tokens_per_run"],
                             input_sha256=sha(selected))
                if reserve > config["max_reserved_tokens_per_run"]:
                    entry.update(status="WAIT_API_INPUT_RESERVATION_EXCEEDS_FIXED_BUDGET")
            except Exception as error:
                # Original diagnostic reasons are safe codes, not source text.
                entry.update(status="BLOCKED" if review["status"] == "BLOCKED" else "HELD_CONTEXT",
                             reason=str(error) if isinstance(error, ValueError) else type(error).__name__)
            rows.append(entry)
    result = {"version": INPUT_VERSION, "source_freeze_sha256": manifest["freeze_sha256"],
              "split": split, "documents": rows, "counts": dict(Counter(x["status"] for x in rows)),
              "inputs_sha256": sha([{k: x.get(k) for k in ("document_id", "body_sha256", "input_sha256", "status")} for x in rows])}
    write(ROOT / (split+"-inputs.json"), result)
    # The reviewer receives originals + fixed rules + exact read scope only;
    # implementation, predictions, expected labels and API responses are absent.
    packet = {"version": "bct-event-review-packet-1", "split": split,
              "review_policy": "docs/v4/EVENT_REVIEW_POLICY.md", "source_freeze_sha256": manifest["freeze_sha256"],
              "documents": [{"document_id": x["document_id"], "body_sha256": x["body_sha256"],
                             "origin_url": x["doc"]["origin_url"], "published_at": x["doc"]["published_at"],
                             "body_path": next(r["body_path"] for r in manifest["documents"] if r["document_id"] == x["document_id"]),
                             "body_status": x["body_status"], "transfer_status": x["status"],
                             "windows": x.get("source", {}).get("windows", [])} for x in rows]}
    write(ROOT / "review-packets" / (split+".json"), packet)
    return {"split": split, "counts": result["counts"], "inputs_sha256": result["inputs_sha256"]}


def run_one(split, document_id):
    inputs = json.loads((ROOT / (split+"-inputs.json")).read_text())
    row = next(x for x in inputs["documents"] if x["document_id"] == document_id)
    if row["status"] != "ELIGIBLE":
        return {"document_id": document_id, "status": "NOT_RUN", "reason": row["status"]}
    if split == "evaluation":
        freeze = json.loads((ROOT / "evaluation-freeze.json").read_text())
        verify_freeze(freeze)
        if (freeze["evaluation_inputs_sha256"] != inputs["inputs_sha256"]
                or hashlib.sha256((ROOT / "evaluation-inputs.json").read_bytes()).hexdigest() != freeze["evaluation_inputs_file_sha256"]):
            raise ValueError("EVALUATION_INPUT_CHANGED_AFTER_FREEZE")
    config = json.loads(Path("var/v4/groq-stage2/trial-config.json").read_text())
    ledger = Ledger(ROOT / "api-ledger")
    try:
        with ledger.worker():
            ledger.capture(row["doc"])
            with ledger.db:
                ledger.event("API_SAFE_INPUT_REVIEW", row["review"])
            router = Router(ledger, config)
            result = router.read(row["doc"])
            write(ROOT / "outputs" / split / (document_id+".json"), result)
            return {"document_id": document_id, "status": result["status"], "calls": router.calls,
                    "cached": result.get("cached", False), "reason": result.get("reason"),
                    "failures": result.get("failures"),
                    "validated_items": len(result.get("result", {}).get("items", [])),
                    "source_status": result.get("result", {}).get("source_status")}
    finally:
        ledger.close()


def freeze():
    files = ["pyproject.toml", "scripts/v4/repair_trial.py", "scripts/v4/requirements.lock",
             "docs/v4/EVENT_REVIEW_POLICY.md", "src/bct/v4/free_ai.py", "src/bct/v4/public_input.py",
             "src/bct/v4/semantics.py", "src/bct/v4/research_adapter.py", "src/bct/v4/event_evaluation.py",
             "src/bct/v4/adapters.py", "src/bct/v4/store.py", "src/bct/v4/pipeline.py",
             "src/bct/precursor_evidence_graph.py", "src/bct/precursor_temporal.py",
             "src/bct/precursor_scope_reader.py", "src/bct/precursor_collection.py"]
    data = {"at": now(), "models": {"groq": MODELS["groq"], "cpu": "fastino/gliner2-base-v1",
                                   "cpu_revision": "f9634218e53580c56edf0de97ca1a7d3f1c2354e"},
            "system_sha256": sha(SYSTEM), "quote_schema_sha256": sha(QUOTE_SCHEMA),
            "file_sha256": {f: hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files},
            "trial_config_sha256": hashlib.sha256(Path("var/v4/groq-stage2/trial-config.json").read_bytes()).hexdigest(),
            "evaluation_inputs_sha256": json.loads((ROOT / "evaluation-inputs.json").read_text())["inputs_sha256"],
            "evaluation_inputs_file_sha256": hashlib.sha256((ROOT / "evaluation-inputs.json").read_bytes()).hexdigest(),
            "evaluation_review_packet_sha256": hashlib.sha256((ROOT / "review-packets/evaluation.json").read_bytes()).hexdigest(),
            "source_freeze_sha256": json.loads(MANIFEST.read_text())["freeze_sha256"],
            "policy": "No tuning after holdout results. Partial input accuracy only; no human validation or early-performance claim."}
    path = ROOT / "evaluation-freeze.json"
    if path.exists():
        raise ValueError("EVALUATION_FREEZE_ALREADY_EXISTS")
    write(path, data)
    return data


def verify_freeze(data):
    for f, digest in data["file_sha256"].items():
        if hashlib.sha256(Path(f).read_bytes()).hexdigest() != digest:
            raise ValueError("CODE_OR_POLICY_CHANGED_AFTER_EVALUATION_FREEZE:"+f)
    if hashlib.sha256(Path("var/v4/groq-stage2/trial-config.json").read_bytes()).hexdigest() != data["trial_config_sha256"]:
        raise ValueError("TRIAL_CONFIG_CHANGED_AFTER_FREEZE")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["prepare", "run-one", "freeze"])
    p.add_argument("--split", choices=["development", "evaluation"], default="development")
    p.add_argument("--document-id")
    a = p.parse_args()
    out = prepare(a.split) if a.command == "prepare" else freeze() if a.command == "freeze" else run_one(a.split, a.document_id)
    print(json.dumps(out, ensure_ascii=False))
