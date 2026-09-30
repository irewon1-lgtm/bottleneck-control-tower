import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from bct.config import load_settings
from bct.db import migrate
from .collector import RSSCollector, RSSTransport


def load_feeds(path: Path) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("feeds"), dict) or not data["feeds"]:
        raise ValueError("feeds must be a nonempty mapping")
    feeds = data["feeds"]
    if any(not isinstance(name, str) or not name.strip() or not isinstance(url, str)
           or urlsplit(url).scheme != "https" or not urlsplit(url).hostname
           for name, url in feeds.items()):
        raise ValueError("feed names and HTTPS URLs are required")
    return feeds


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bct-rss")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--feeds", type=Path, default=Path("rss_feeds.yaml"))
    parser.add_argument("--run-key", default=datetime.now(timezone.utc).isoformat())
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 10:
        parser.error("limit must be 1..10")
    feeds = load_feeds(args.feeds)
    settings = load_settings(args.config)
    migrate(settings)
    collector = RSSCollector(settings, RSSTransport())
    results = []
    for name, url in feeds.items():
        result = collector.run(url, args.run_key, limit=args.limit)
        results.append({"feed": name, **result.__dict__})
    print(json.dumps(results, ensure_ascii=False))
    return 0 if any(result["status"] == "succeeded" for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
