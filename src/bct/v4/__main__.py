import argparse
import json
from pathlib import Path
import sys

from bct.objective_lock import stamp_export
from .adapters import prepare_model
from .pipeline import cycle, replay
from .store import Ledger


def main():
    parser = argparse.ArgumentParser(description="BCT V4 independent CPU shadow worker")
    parser.add_argument("--root", type=Path, default=Path("var/v4/runtime"))
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("cycle")
    run.add_argument("--config", type=Path, default=Path("config/v4-sources.json"))
    run.add_argument("--no-ai", action="store_true")
    run.add_argument("--api-config", type=Path, help="Explicit opt-in free API annotations; never operating promotion")
    api = sub.add_parser("api-read")
    api.add_argument("--config", type=Path, default=Path("config/v4-free-ai.json"))
    api.add_argument("--limit", type=int)
    api.add_argument("--probe-provider", choices=["gemini", "groq"], help="Isolated connectivity test only")
    backfill = sub.add_parser("replay")
    backfill.add_argument("--input", type=Path, required=True)
    backfill.add_argument("--as-of", required=True)
    backfill.add_argument("--synthetic", action="store_true")
    sub.add_parser("prepare-model")
    sub.add_parser("status")
    sub.add_parser("export")
    backup = sub.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    code = 0
    try:
        if args.command == "prepare-model":
            result = prepare_model(args.root)
        elif args.command == "cycle":
            result = cycle(args.root, json.loads(args.config.read_text()), use_ai=not args.no_ai,
                           api_config=json.loads(args.api_config.read_text()) if args.api_config else None)
            code = 2 if result["integration_status"] == "BLOCKED" else 0
        elif args.command == "api-read":
            from .free_ai import annotate
            result = annotate(args.root, json.loads(args.config.read_text()), limit=args.limit,
                              probe_provider=args.probe_provider)
            code = 2 if result["status"] == "BLOCKED" else 0
        elif args.command == "replay":
            result = replay(args.root, json.loads(args.input.read_text()), args.as_of,
                            mode="SYNTHETIC" if args.synthetic else "BACKFILL")
        else:
            ledger = Ledger(args.root)
            try:
                if args.command == "backup":
                    ledger.backup(args.output)
                    result = {"status": "PASS", "backup": str(args.output)}
                elif args.command == "export":
                    result = stamp_export({"status": ledger.status(), "candidates": ledger.history()})
                else:
                    result = ledger.status()
                from .free_ai import api_status
                result["api"] = api_status(ledger)
            finally:
                ledger.close()
    except Exception as exc:
        result = {"status": "BLOCKED", "reason": str(exc)[:300]}
        code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())

