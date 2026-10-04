import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from bct.config import load_settings
from bct.db import migrate
from .collector import GDELTTransport, QUERIES, RadarCollector


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bct-radar")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--run-key", default=datetime.now(timezone.utc).isoformat())
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--query", choices=QUERIES, action="append",
                        help="one discovery query; repeat to select several (default: all five)")
    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    migrate(settings)
    collector = RadarCollector(settings, GDELTTransport())
    results = []
    for query in args.query or QUERIES:
        result = collector.run(args.run_key, limit=args.limit, query=query)
        results.append({"query": query, **result.__dict__})
    print(json.dumps(results, ensure_ascii=False))
    return 0 if any(result["status"] == "succeeded" for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
