"""Live provider probes only when credentials, free accounts and saved originals exist.

No dummy success, new collection, CPU installation, paid tier or model search.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from bct.v4.free_ai import KEYS, MODELS, Router, api_status, checked_config
from bct.v4.store import Ledger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("var/v4/runtime"))
    parser.add_argument("--config", type=Path, default=Path("config/v4-free-ai.json"))
    parser.add_argument("--output", type=Path, default=Path("var/v4/evidence/api-live.json"))
    args = parser.parse_args()
    config = checked_config(json.loads(args.config.read_text()))
    results = {"at": datetime.now(timezone.utc).isoformat(), "kind": "LIVE_CONNECTIVITY",
               "providers": {}, "calls": 0, "reported_tokens": 0, "api_cost": 0,
               "local_cpu_comparison": "BLOCKED_UNTIL_SAME_ORIGINAL_AND_LIVE_API_OUTPUT_EXIST",
               "semantic_accuracy": "UNKNOWN", "forecast_performance": "BLOCKED"}
    ledger = Ledger(args.root) if (args.root / "v4.sqlite3").is_file() else None
    try:
        if ledger:
            with ledger.worker():
                docs = ledger.latest_documents()
                router = Router(ledger, config)
                for provider in MODELS:
                    reason = "EXPLICIT_OPT_IN_REQUIRED" if not config["enabled"] else router.available(provider)
                    if reason or not docs:
                        results["providers"][provider] = {"status": "BLOCKED", "reason": reason or "SAVED_V4_ORIGINAL_MISSING", "model": MODELS[provider]}
                    else:
                        value = router.read(docs[0], probe_provider=provider)
                        results["providers"][provider] = {"status": value["status"], "model": MODELS[provider],
                            "cached": value.get("cached", False), "failures": value.get("failures", []),
                            "response_saved": value["status"] == "PASS", "input_key": value.get("input_key")}
                results["calls"] = router.calls
                responses = [x for x in router.events("API_RESPONSE") if x["run_id"] == router.run_id]
                results["reported_tokens"] = sum(x["usage"].get("total_tokens") or 0 for x in responses)
                results["usage_missing"] = any(x["usage"].get("total_tokens") is None for x in responses)
                results["ledger_status"] = api_status(ledger)
        else:
            for provider in MODELS:
                results["providers"][provider] = {"status": "BLOCKED", "model": MODELS[provider],
                    "reasons": (["KEY_MISSING"] if not os.getenv(KEYS[provider]) else [])
                        + ["FREE_ACCOUNT_AND_LIMITS_UNVERIFIED", "SAVED_V4_ORIGINAL_MISSING"]}
    finally:
        if ledger:
            ledger.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"providers": results["providers"], "calls": results["calls"],
                      "reported_tokens": results["reported_tokens"], "api_cost": results["api_cost"]}, ensure_ascii=False))
    return 0 if all(x["status"] == "PASS" for x in results["providers"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
