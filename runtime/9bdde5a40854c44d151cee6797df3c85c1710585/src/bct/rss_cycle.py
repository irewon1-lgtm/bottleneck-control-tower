"""One serial RSS pass, then regenerate the existing derived RADAR reviews."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .collectors.rss.cli import load_feeds
from .collectors.rss.collector import RSSCollector, RSSTransport
from .config import Settings, load_settings
from .db import migrate
from .radar_families import build as build_families


def run(settings: Settings, feeds_path: Path, run_key: str, *, limit: int = 10,
        transport=None) -> dict:
    if not 1 <= limit <= 10:
        raise ValueError("limit must be 1..10")
    feeds = load_feeds(feeds_path)
    collector = RSSCollector(settings, transport or RSSTransport())
    results = []
    for name, url in feeds.items():
        result = collector.run(url, run_key, limit=limit)
        results.append({"feed": name, **result.__dict__})
    summary = build_families(settings, feeds_path)
    return {"feeds": results, "saved": sum(row["saved"] for row in results),
            "duplicates": sum(row["duplicates"] for row in results),
            "updated": sum(row["updated"] for row in results),
            "failed_feeds": [row["feed"] for row in results if row["status"] != "succeeded"],
            "articles": summary["processed_articles"],
            "families": summary["families"]}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bct-rss-cycle")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--feeds", type=Path, default=Path("rss_feeds.yaml"))
    parser.add_argument("--run-key", default=datetime.now(timezone.utc).isoformat())
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    migrate(settings)
    result = run(settings, args.feeds, args.run_key, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if len(result["failed_feeds"]) < len(result["feeds"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
