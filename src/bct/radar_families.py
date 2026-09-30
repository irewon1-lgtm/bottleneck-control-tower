"""Contextual, reproducible candidate families from the existing RSS reviews."""
import argparse
import json
import os
import re
import tempfile
from pathlib import Path

from sqlalchemy import select

from .config import Settings, load_settings
from .db import session_factory
from .models import RadarItem
from .radar_pressure_relief import RELIEF, build as build_pressure_relief
from .radar_watch import current as current_core_review

# Keep this one observed supply-chain relationship narrow. It is not a general
# industry taxonomy: a co-mention without the refining context stays separate.
FUEL_TERMS = {
    "diesel": re.compile(r"\bdiesel\b", re.I),
    "distillate fuel oil": re.compile(r"\bdistillate fuel oil\b", re.I),
    "jet fuel": re.compile(r"\bjet fuels?\b", re.I),
    "marine fuel": re.compile(r"\bmarine fuels?\b", re.I),
    "petrochemical feedstock": re.compile(r"\bpetrochemical feedstocks?\b", re.I),
}
REFINING = re.compile(r"\b(?:refin(?:e|ed|ery|eries|ing)|petroleum)\b", re.I)


def _family_rows(reviews: list[dict], entries: dict[str, dict], texts: dict[str, str]) -> list[dict]:
    candidates = {term for item in reviews for term in item["candidate_terms"]}
    linked: set[str] = set()
    for item in reviews:
        id_ = item["radar_item_id"]
        body = texts[id_]
        present = {term for term, pattern in FUEL_TERMS.items()
                   if term in candidates and pattern.search(body)}
        if REFINING.search(body) and len(present) >= 2 and present & set(item["candidate_terms"]):
            linked.update(present)

    grouped: dict[str, dict] = {}
    for item in reviews:
        id_ = item["radar_item_id"]
        body = texts[id_]
        date = entries[id_]["published_at"] or entries[id_]["collected_at"]
        signals = set(item["signals"])
        for term in set(item["candidate_terms"]):
            # Standalone mentions outside this supply-chain context stay standalone.
            contextual = (term in linked and REFINING.search(body) and
                          FUEL_TERMS[term].search(body))
            name = "refined petroleum products" if contextual else term
            data = grouped.setdefault(name, {"members": set(), "pressure": set(),
                                             "relief": set(), "articles": set(),
                                             "sources": set(), "signals": set(), "latest": None})
            data["members"].add(term)
            data["articles"].add(id_)
            data["sources"].add(item["source"])
            data["signals"].update(signals)
            if signals - RELIEF:
                data["pressure"].add(id_)
            if signals & RELIEF:
                data["relief"].add(id_)
            if date and (data["latest"] is None or date > data["latest"]):
                data["latest"] = date
    return [{"family": name, "members": sorted(data["members"]),
             "pressure_articles": len(data["pressure"]),
             "relief_articles": len(data["relief"]),
             "article_count": len(data["articles"]),
             "source_count": len(data["sources"]),
             "signal_type_count": len(data["signals"]),
             "latest_at": data["latest"],
             "promote": bool(data["pressure"] and len(data["articles"]) >= 2
                             and len(data["sources"]) >= 2)}
            for name, data in sorted(grouped.items())]


def build(settings: Settings, feeds_path: Path) -> dict:
    summary = build_pressure_relief(settings, feeds_path)
    reviews = json.loads((settings.derived_dir / "rss_term_review.json").read_text())
    signals = json.loads((settings.derived_dir / "rss_signals.json").read_text())
    entries = {entry["radar_item_id"]: entry for entry in signals["entries"]}
    ids = [item["radar_item_id"] for item in reviews["reviews"]]
    with session_factory(settings)() as db:
        rows = db.scalars(select(RadarItem).where(RadarItem.id.in_(ids))).all() if ids else []
        texts = {row.id: row.title + "\n" + (row.snippet or "") for row in rows}
    families = _family_rows(reviews["reviews"], entries, texts)
    with session_factory(settings)() as db:
        for family in families:
            manual = current_core_review(db, family["family"])
            if manual is not None:
                family.update({"new_promote": False,
                               "core_status": manual["status"],
                               "confirmed_scope": manual["confirmed_scope"],
                               "unresolved_scope": manual["unresolved_scope"],
                               "re_review_required": manual["re_review_required"],
                               "re_review_triggers": sorted({change["trigger"]
                                                             for change in manual["pending_changes"]})})
    output = {"version": 1, "scope": "RSS title and snippet; family requires observed refining context",
              "processed_articles": summary["processed_articles"],
              "signal_articles": summary["signal_articles"], "families": families}
    dest = settings.derived_dir / "rss_candidate_families.json"
    payload = (json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if not dest.exists() or dest.read_bytes() != payload:
        fd, name = tempfile.mkstemp(prefix="rss-families-", suffix=".tmp", dir=settings.derived_dir)
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
