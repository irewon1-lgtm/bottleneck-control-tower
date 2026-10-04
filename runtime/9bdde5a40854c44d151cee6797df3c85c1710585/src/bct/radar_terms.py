"""Conservative product phrase review after the existing RSS signal pass."""
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
from .radar_signals import COMPILED, _rss_hosts, extract

NOISE = {"skilled", "navigate", "device", "production", "capacity", "demand",
         "market", "company", "supply", "growth"}
LABOR = re.compile(r"\b(?:workers?|contractors?|crews?|staff|labor|labour)\b", re.I)
STOP = re.compile(r"\s+(?:if|when|which|that|while|because|as)[\s,]", re.I)
LIST = re.compile(r"\bshortages?\s+of\s+([^.;\n]+)", re.I)
PHRASES = (
    (re.compile(r"\bdistillate\s+fuel\s+oil\b", re.I), "distillate fuel oil"),
    (re.compile(r"\bsteel\s+mill\b", re.I), "steel"),
    (re.compile(r"\bsteel\b", re.I), "steel"),
    (re.compile(r"\b(?:300mm|12[- ]inch)\s+(?:semiconductor\s+)?(?:wafers?|fab)\b", re.I), "300mm semiconductor wafer"),
    (re.compile(r"\bradar[- ]satellites?\b", re.I), "radar satellite"),
    (re.compile(r"\bsolid\s+rocket\s+motors?\b", re.I), "solid rocket motor"),
    (re.compile(r"\b(?:large\s+)?(?:power\s+|distribution\s+|high[- ]voltage\s+)?transformers?\b", re.I), None),
    (re.compile(r"\b(?:HBM|DDR\d+|GDDR\d+)\s+memory\b", re.I), None),
    (re.compile(r"\b(?:gas|steam)\s+turbines?\b", re.I), None),
    (re.compile(r"\b(?:AMRAAMs?|AIM-120)\b", re.I), "AMRAAM"),
    (re.compile(r"\b(?:PlayStation\s+5\s+Pro|PS5\s+Pro)\b", re.I), "PlayStation 5 Pro"),
    (re.compile(r"\b(?:uranium|diesel)\b", re.I), None),
)


def _normalize(phrase: str) -> str:
    words = phrase.lower().split()
    if words and words[-1] in {"motors", "transformers", "turbines", "fuels", "feedstocks"}:
        words[-1] = words[-1][:-1]
    return " ".join(words)


def terms(title: str, snippet: str | None, signals: list[dict]) -> dict:
    """Only explicit product phrases; ungrounded context stays unresolved."""
    if not signals:
        return {"candidate_terms": [], "removed_noise_terms": [], "unresolved_terms": []}
    text = title + "\n" + (snippet or "")
    candidates = set()
    raw = {s["candidate_term"] for s in signals if s["candidate_term"]}
    removed = sorted(x for x in raw if x.lower() in NOISE)

    # Supply-shortage lists explicitly name their affected materials/products.
    for match in LIST.finditer(text):
        remainder = STOP.split(match.group(1), maxsplit=1)[0]
        for part in re.split(r",\s*|\s+and\s+", remainder):
            part = re.sub(r"^(?:the|a|an)\s+", "", part.strip(), flags=re.I)
            words = part.split()
            if not 1 <= len(words) <= 4 or LABOR.search(part):
                continue
            if any(word.lower() in NOISE for word in words):
                continue
            if re.fullmatch(r"[A-Za-z][A-Za-z-]*(?:\s+[A-Za-z][A-Za-z-]*){0,3}", part):
                candidates.add(_normalize(part))

    # Other phrases need to be close to a signal in the same sentence.
    for sentence in re.split(r"[.!?;\n]+", text):
        spans = [match.span() for signal in COMPILED.values()
                 for match in signal.finditer(sentence)]
        for pattern, canonical in PHRASES:
            for match in pattern.finditer(sentence):
                if any(max(start - match.end(), match.start() - end, 0) <= 45
                       for start, end in spans):
                    candidates.add(canonical or _normalize(match.group()))

    # A product anywhere in the article is insufficient for an unrelated signal.
    # Restrict the model name to generic device shortage wording in the same snippet.
    if re.search(r"\bdevice shortages?\b", snippet or "", re.I) and \
            re.search(r"\b(?:PlayStation\s+5\s+Pro|PS5\s+Pro)\b", text, re.I):
        candidates.add("PlayStation 5 Pro")
    else:
        candidates.discard("PlayStation 5 Pro")
    if not any(s["signal"] == "SHORTAGE" for s in signals):
        # A material in background context should not attach to an unrelated signal.
        candidates.difference_update({"diesel", "uranium"})
    unresolved = []
    if not candidates:
        unresolved.append({"status": "UNRESOLVED_TERM",
                           "raw_term": next(iter(sorted(raw - set(removed))), None),
                           "reason": "no specific product phrase tied to the signal"})
    return {"candidate_terms": sorted(candidates), "removed_noise_terms": removed,
            "unresolved_terms": unresolved}


def build(settings: Settings, feeds_path: Path) -> dict:
    hosts = _rss_hosts(feeds_path)
    with session_factory(settings)() as db:
        items = db.scalars(select(RadarItem).where(RadarItem.source.in_(hosts),
                           RadarItem.status == "active").order_by(RadarItem.id)).all()
        reviews = []
        for item in items:
            signals = extract(item.title, item.snippet)
            if signals:
                reviews.append({"radar_item_id": item.id, "source": item.source,
                                "source_updated_at": item.updated_at, "url": item.url,
                                "signals": sorted({s["signal"] for s in signals}),
                                **terms(item.title, item.snippet, signals)})
    output = {"version": 1, "scope": "RSS title and snippet only; signals unchanged",
              "processed_articles": len(items), "signal_articles": len(reviews), "reviews": reviews}
    settings.mkdirs()
    dest = settings.derived_dir / "rss_term_review.json"
    payload = (json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if not dest.exists() or dest.read_bytes() != payload:
        fd, name = tempfile.mkstemp(prefix="rss-terms-", suffix=".tmp", dir=settings.derived_dir)
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
    result = build(load_settings(args.config), args.feeds)
    print(json.dumps({"processed_articles": result["processed_articles"],
                      "signal_articles": result["signal_articles"],
                      "reviews": result["reviews"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
