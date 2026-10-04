"""Rebuild a read-only RSS candidate summary from existing signal and term passes."""
import argparse
import json
import os
import tempfile
from pathlib import Path

from .config import Settings, load_settings
from .radar_signals import PATTERNS, build as build_signals
from .radar_terms import build as build_terms

RELIEF = {"CAPACITY_EXPANSION"}


def _pairs(entries: list[dict]) -> set[tuple[str, str]]:
    return {(entry["radar_item_id"], signal["signal"])
            for entry in entries for signal in entry["signals"]}


def build(settings: Settings, feeds_path: Path) -> dict:
    prior_path = settings.derived_dir / "rss_signals.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8")) if prior_path.exists() else {"entries": []}
    old_pairs = _pairs(prior["entries"])
    build_signals(settings, feeds_path)
    signal_data = json.loads(prior_path.read_text(encoding="utf-8"))
    review = build_terms(settings, feeds_path)
    entries = {entry["radar_item_id"]: entry for entry in signal_data["entries"]}
    grouped: dict[str, dict] = {}
    for item in review["reviews"]:
        entry = entries[item["radar_item_id"]]
        names = set(item["candidate_terms"])
        signals = set(item["signals"])
        date = entry["published_at"] or entry["collected_at"]
        for name in names:
            record = grouped.setdefault(name, {"pressure": set(), "relief": set(),
                                               "sources": set(), "signals": set(), "latest": None})
            if signals - RELIEF:
                record["pressure"].add(item["radar_item_id"])
            if signals & RELIEF:
                record["relief"].add(item["radar_item_id"])
            record["sources"].add(item["source"])
            record["signals"].update(signals)
            if date and (record["latest"] is None or date > record["latest"]):
                record["latest"] = date
    candidates = [{"candidate_term": name, "pressure_articles": len(data["pressure"]),
                   "relief_articles": len(data["relief"]), "source_count": len(data["sources"]),
                   "signal_type_count": len(data["signals"]), "signals": sorted(data["signals"]),
                   "latest_at": data["latest"],
                   "group": ("BOTH" if data["pressure"] and data["relief"] else
                             "PRESSURE" if data["pressure"] else "RELIEF")}
                  for name, data in sorted(grouped.items())]
    current_pairs = _pairs(signal_data["entries"])
    output = {"version": 1, "scope": "configured RSS, active items, title and snippet only",
              "processed_articles": review["processed_articles"],
              "signal_articles": review["signal_articles"],
              "new_article_signals": len(current_pairs - old_pairs),
              "pressure_signals": sorted(set(PATTERNS) - RELIEF),
              "relief_signals": sorted(RELIEF), "candidates": candidates,
              "unresolved_signal_articles": sum(bool(item["unresolved_terms"])
                                                for item in review["reviews"])}
    settings.mkdirs()
    dest = settings.derived_dir / "rss_pressure_relief.json"
    payload = (json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if not dest.exists() or dest.read_bytes() != payload:
        fd, name = tempfile.mkstemp(prefix="rss-pressure-relief-", suffix=".tmp", dir=settings.derived_dir)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, dest)
        finally:
            Path(name).unlink(missing_ok=True)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--feeds", type=Path, default=Path("rss_feeds.yaml"))
    args = parser.parse_args(argv)
    print(json.dumps(build(load_settings(args.config), args.feeds), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
