"""Small, reproducible RSS headline/description signal index. No article bodies."""
import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from sqlalchemy import select

from .config import Settings, load_settings
from .db import session_factory
from .models import RadarItem


PATTERNS = {
    "SHORTAGE": r"\b(?:shortages?|shortfalls?|tight[ -]+(?:(?:global|domestic)[ -]+)?suppl(?:y|ies))\b",
    "LEAD_TIME": r"\b(?:lead[ -]+times?|delivery[ -]+times?)\b",
    "CAPACITY_CONSTRAINT": r"\b(?:capacity[ -]+constrain(?:t|ts|ed)|constrain(?:ed|ts?)[ -]+capacity|bottlenecks?)\b",
    "UNABLE_TO_MEET_DEMAND": r"\b(?:unable[ -]+to[ -]+meet[ -]+demand|cannot[ -]+meet[ -]+demand|can't[ -]+meet[ -]+demand|demand[ -]+exceeds[ -]+supply)\b",
    "BACKLOG_INCREASE": r"\b(?:backlog(?:s)?[ -]+(?:increase[ds]?|grows?|growth|rises?|surges?)|(?:growing|rising|increasing|record)[ -]+backlog(?:s)?)\b",
    "PRODUCTION_DELAY": r"\b(?:(?:production|delivery)[ -]+delays?|delay(?:ed|s)?[ -]+(?:production|delivery))\b",
    "QUALIFICATION_DELAY": r"\b(?:(?:qualification|certification)[ -]+delays?|delay(?:ed|s)?[ -]+(?:qualification|certification))\b",
    "CAPACITY_EXPANSION": r"\b(?:capacity[ -]+expansion|expand(?:ed|ing|s)?[ -]+capacity|ramp(?:ed|ing|s)?[ -]+(?:up[ -]+)?production|new[ -]+(?:production[ -]+)?(?:line|plant|steel[ -]+mill|(?:[0-9]+mm[ -]+)?(?:semiconductor[ -]+)?fab)|plans?[ -]+for[ -]+(?:\$?[0-9]+[ -]+(?:billion[ -]+)?[A-Za-z-]+[ -]+){0,3}steel[ -]+mill|grand[ -]+opening[ -]+of[ -]+(?:its[ -]+)?first[ -]+[0-9]+mm[ -]+fab|(?:increase[ds]?|increasing)[ -]+production|double[sd]?[ -]+(?:[A-Za-z][A-Za-z0-9-]*[ -]+){0,2}(?:production|capacity)|new[ -]+suppliers?)\b",
}
COMPILED = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in PATTERNS.items()}
BOUNDARY = {"the", "a", "an", "of", "for", "in", "on", "at", "with", "and", "or", "to", "as", "by", "from", "after", "amid", "over"}
NOISE = {"new", "recent", "global", "industry", "long", "short", "worsening", "rising", "high", "higher", "record", "major", "severe", "ongoing", "persistent"}
WORD = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
ALIASES = {"AMRAAMS": "AMRAAM", "AIM-120": "AMRAAM"}


def _canonical_term(term: str | None) -> str | None:
    if term is None:
        return None
    return ALIASES.get(term.upper(), term)


def _term(sentence: str, match: re.Match, signal: str) -> str | None:
    phrase = match.group()
    # This narrow expansion pattern names its product between the action and production.
    product = re.search(r"\bdouble[sd]?\s+([A-Za-z][A-Za-z0-9-]{2,})\s+production\b", phrase, re.I)
    if product and product.group(1).isupper():
        return _canonical_term(product.group(1).upper())
    after = sentence[match.end():]
    of_term = re.match(r"\s+(?:of|for)\s+(?:the\s+)?([A-Za-z][A-Za-z0-9-]*)", after, re.I)
    if of_term and of_term.group(1).lower() not in NOISE | BOUNDARY:
        return _canonical_term(of_term.group(1) if of_term.group(1).isupper() else of_term.group(1).lower())
    before = sentence[:match.start()]
    words = WORD.findall(before)
    if not words:
        return None
    last = words[-1]
    if last.lower() in NOISE | BOUNDARY:
        return None
    # A nearby word is a term hint, not a validated product/entity classification.
    return _canonical_term(last if last.isupper() else last.lower())


def extract(title: str, snippet: str | None) -> list[dict]:
    found = set()
    for value in (title, snippet or ""):
        for sentence in re.split(r"[.!?;\n]+", value):
            for signal, pattern in COMPILED.items():
                for match in pattern.finditer(sentence):
                    found.add((signal, _term(sentence, match, signal)))
    return [{"signal": signal, "candidate_term": term} for signal, term in
            sorted(found, key=lambda pair: (pair[0], pair[1] or ""))]


def _rss_hosts(feeds_path: Path) -> set[str]:
    config = yaml.safe_load(feeds_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(config.get("feeds"), dict):
        raise ValueError("feeds must be a mapping")
    hosts = set()
    for url in config["feeds"].values():
        if not isinstance(url, str) or urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
            raise ValueError("invalid RSS feed URL")
        hosts.add(urlsplit(url).hostname.lower())
    return hosts


def _candidate_summary(entries: list[dict]) -> list[dict]:
    grouped = {}
    for entry in entries:
        for signal in entry["signals"]:
            term = _canonical_term(signal["candidate_term"])
            if not term:
                continue
            data = grouped.setdefault(term, {"candidate_term": term, "article_ids": set(),
                                             "signals": set(), "sources": set(), "latest_at": None})
            data["article_ids"].add(entry["radar_item_id"])
            data["signals"].add(signal["signal"])
            data["sources"].add(entry["source"])
            date = entry["published_at"] or entry["collected_at"]
            if date and (data["latest_at"] is None or date > data["latest_at"]):
                data["latest_at"] = date
    return [{"candidate_term": term, "article_count": len(data["article_ids"]),
             "signals": sorted(data["signals"]), "source_count": len(data["sources"]),
             "latest_at": data["latest_at"],
             "status": "WATCH" if len(data["article_ids"]) >= 2 else "OBSERVE"}
            for term, data in sorted(grouped.items())]


def build(settings: Settings, feeds_path: Path) -> dict:
    hosts = _rss_hosts(feeds_path)
    with session_factory(settings)() as db:
        items = db.scalars(select(RadarItem).where(RadarItem.source.in_(hosts),
                     RadarItem.status == "active").order_by(RadarItem.id)).all()
        entries = [{"radar_item_id": item.id, "source": item.source,
                    "published_at": item.published_at, "collected_at": item.collected_at,
                    "source_updated_at": item.updated_at, "signals": extract(item.title, item.snippet)}
                   for item in items]
    records = sum(len(entry["signals"]) for entry in entries)
    candidates = _candidate_summary(entries)
    output = {"version": 2, "scope": "configured RSS feeds, active radar_items, title and snippet only",
              "entries": entries, "candidates": candidates}
    payload = (json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    dest = settings.derived_dir / "rss_signals.json"
    settings.mkdirs()
    old = json.loads(dest.read_text(encoding="utf-8")) if dest.exists() else {"entries": []}
    old_keys = {(e["radar_item_id"], s["signal"], s["candidate_term"])
                for e in old["entries"] for s in e["signals"]}
    keys = {(e["radar_item_id"], s["signal"], s["candidate_term"])
            for e in entries for s in e["signals"]}
    if not dest.exists() or dest.read_bytes() != payload:
        fd, name = tempfile.mkstemp(prefix="rss-signals-", suffix=".tmp", dir=settings.derived_dir)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, dest)
        finally:
            Path(name).unlink(missing_ok=True)
    counts = {name: sum(any(s["signal"] == name for s in e["signals"]) for e in entries)
              for name in PATTERNS}
    return {"processed": len(entries), "matched_articles": sum(bool(e["signals"]) for e in entries),
            "signal_records": records, "existing_duplicates": len(keys & old_keys),
            "new_signals": len(keys - old_keys), "removed_signals": len(old_keys - keys),
            "signal_article_counts": counts, "candidates": candidates,
            "sha256": hashlib.sha256(payload).hexdigest(), "path": str(dest)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--feeds", type=Path, default=Path("rss_feeds.yaml"))
    args = parser.parse_args(argv)
    print(json.dumps(build(load_settings(args.config), args.feeds), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
