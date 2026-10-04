import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from bct.config import load_settings
from bct.db import migrate
from .collector import SECCollector, SECTransport


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bct-sec")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--cik", required=True, help="CIK, e.g. 320193")
    parser.add_argument("--user-agent", default=os.environ.get("BCT_SEC_USER_AGENT"),
                        help="Identifying SEC User-Agent with operator contact")
    parser.add_argument("--run-key", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    parser.add_argument("--max-per-form", type=int, default=1)
    args = parser.parse_args(argv)
    if not args.user_agent:
        parser.error("set --user-agent or BCT_SEC_USER_AGENT with your actual contact")
    settings = load_settings(args.config)
    migrate(settings)
    result = SECCollector(settings, SECTransport(args.user_agent)).run(
        args.cik, args.run_key, max_per_form=args.max_per_form)
    print(json.dumps(result.__dict__, ensure_ascii=False))
    return 0 if result.status == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
