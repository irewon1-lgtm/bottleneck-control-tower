import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from bct.config import load_settings
from bct.db import migrate
from .collector import USAspendingCollector, USAspendingTransport


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bct-usaspending")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    query = parser.add_mutually_exclusive_group(required=True)
    query.add_argument("--company")
    query.add_argument("--keyword")
    parser.add_argument("--run-key", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    parser.add_argument("--limit", type=int, default=3, help="awards on first page, 1..100")
    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    migrate(settings)
    result = USAspendingCollector(settings, USAspendingTransport()).run(
        args.company or args.keyword, args.run_key,
        mode="company" if args.company is not None else "keyword", limit=args.limit)
    print(json.dumps(result.__dict__, ensure_ascii=False))
    return 0 if result.status == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
