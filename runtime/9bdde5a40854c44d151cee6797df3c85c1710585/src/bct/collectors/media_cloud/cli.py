import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from bct.config import load_settings
from bct.db import migrate
from .collector import MediaCloudCollector, MediaCloudTransport, QUERIES


def load_project_env(path: Path) -> None:
    """Load the one supported local secret without overriding an existing environment variable."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if key.strip() == "MEDIACLOUD_API_KEY" and separator:
            if value.strip():
                os.environ.setdefault("MEDIACLOUD_API_KEY", value.strip())
            return


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bct-media-cloud")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--run-key", default=datetime.now(timezone.utc).isoformat())
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--query", action="append", choices=QUERIES,
                        help="select query; repeat for several (default: all three)")
    args = parser.parse_args(argv)
    load_project_env(Path(__file__).resolve().parents[4] / ".env")
    settings = load_settings(args.config)
    migrate(settings)
    transport = MediaCloudTransport()
    collector = MediaCloudCollector(settings, transport)
    results = []
    for index, query in enumerate(args.query or QUERIES):
        if index and transport.api_key:
            time.sleep(31)  # The public API documents some endpoints at two requests/minute.
        result = collector.run(query, args.run_key, limit=args.limit)
        results.append({"query": query, **result.__dict__})
    print(json.dumps(results, ensure_ascii=False))
    return 0 if any(result["status"] == "succeeded" for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
