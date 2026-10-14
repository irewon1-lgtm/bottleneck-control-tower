"""Resume only untouched round2 inputs; keep all previous outputs/scores intact.

Run --probe once, inspect its actual generation, then --continue explicitly.
No HTTP authentication GET, key changes, automatic retries or model changes.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from bct.v4.auth_recovery import AuthRecoveryRouter
from bct.v4.free_ai import QUOTE_SCHEMA, SYSTEM, VERSION, source_input
from bct.v4.store import Ledger, now, sha
from v4_scoped_evaluation import verify_freeze

CORPUS = Path("docs/v4/stage4-corpus/round2")
OUTPUT = CORPUS / "auth-resume"
LEDGER = Path("var/v4/sequential/api-ledger")


def read(path):
    return json.loads(path.read_text())


def write_once(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def run(probe):
    freeze = verify_freeze(CORPUS)
    config = read(CORPUS / "request-config.json")
    rows = [r for r in read(CORPUS / "inputs.json")["documents"] if r["status"] == "ELIGIBLE"]
    receipt = OUTPUT / "probe.json"
    if probe and receipt.exists():
        raise ValueError("RECOVERY_PROBE_ALREADY_RECORDED")
    if not probe and not read(receipt)["response"]:
        raise ValueError("SUCCESSFUL_FRESH_GENERATION_REQUIRED")
    processed = []
    for row in rows:
        verify_freeze(CORPUS)
        ledger = Ledger(LEDGER)
        try:
            with ledger.worker():
                router = AuthRecoveryRouter(ledger, config)
                if router.request_contract != freeze["request_contract"]:
                    raise ValueError("FROZEN_REQUEST_CHANGED")
                # Source scope is identical to CPU and the original gold packet.
                reviewed = {**row["doc"], "api_safe_input_review": row["review"]}
                source = source_input(reviewed, config, router.env)
                if source != row["source"]:
                    raise ValueError("FROZEN_SOURCE_CHANGED")
                key = sha([VERSION, SYSTEM, QUOTE_SCHEMA, source, row["body_sha256"]])
                if any(a["provider"] == "groq" and a["input_key"] == key
                       for a in router.events("API_ATTEMPT")):
                    continue  # Includes the earlier401, regardless of receipt status.
                attempts = router.events("API_ATTEMPT")
                if attempts:
                    delay = 65 - (datetime.now(timezone.utc) - datetime.fromisoformat(attempts[-1]["at"])).total_seconds()
                    if delay > 0:
                        print(json.dumps({"waiting_seconds": round(delay, 1), "reason": "UNCHANGED_FREE_BUDGET_SPACING"}), flush=True)
                        while delay > 0:
                            time.sleep(min(10, delay))
                            delay = 65 - (datetime.now(timezone.utc) - datetime.fromisoformat(attempts[-1]["at"])).total_seconds()
                ledger.capture(row["doc"])
                with ledger.db:
                    ledger.event("API_SAFE_INPUT_REVIEW", row["review"])
                previous_seq = ledger.db.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0]
                result = router.read_unattempted(row["doc"],
                    auth_evidence=read(OUTPUT / "auth-evidence.json") if probe else None)
                events = [{"seq": seq, "kind": kind, **json.loads(payload)}
                          for seq, kind, payload in ledger.db.execute(
                              "SELECT seq,kind,payload FROM events WHERE seq>? ORDER BY seq", (previous_seq,))]
                def latest(kind):
                    return next((e for e in reversed(events) if e["kind"] == kind), None)
                item = {"document_id": row["document_id"], "at": now(), "status": result["status"],
                    "calls": router.calls, "cached": result.get("cached", False), "input_key": key,
                    "attempt": latest("API_ATTEMPT"), "response": latest("API_RECEIVED"),
                    "validation": latest("API_VALIDATION"), "error": latest("API_ERROR"),
                    "reading": result, "provider_state_after": router.state("groq"),
                    "evidence_kind": "FRESH_GENERATION_PROBE" if probe else "SEQUENTIAL_UNATTEMPTED_EVALUATION"}
                write_once(OUTPUT / "documents" / (row["document_id"] + ".json"), item)
                if probe:
                    write_once(receipt, item)
                processed.append(item)
                print(json.dumps({"document_id": item["document_id"], "status": item["status"],
                    "calls": item["calls"], "generation_received": bool(item["response"]),
                    "reported_usage": (item["response"] or {}).get("usage"),
                    "failures": result.get("failures", []), "blocked": bool((router.state("groq") or {}).get("blocked"))}), flush=True)
                if probe or not item["response"] or (router.state("groq") or {}).get("blocked"):
                    break
        finally:
            ledger.close()
    print(json.dumps({"new_documents_this_command": len(processed), "no_existing_input_retried": True}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--continue", dest="continue_batch", action="store_true")
    args = parser.parse_args()
    run(args.probe)
