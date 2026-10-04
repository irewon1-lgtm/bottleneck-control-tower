"""Export existing RSS results for the static, read-only Pages UI.

The canonical file is opened read-only. Existing derived passes run against a
throwaway copy, so neither this script nor a failed Pages job can alter data.
"""
import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import yaml

from bct.collectors.rss.cli import load_feeds
from bct.config import Settings
from bct.radar_families import build as build_families
from bct.radar_pressure_relief import RELIEF


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export(database, state_path, feeds_path, destination):
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if sha256(database) != state["sha256"]:
        raise ValueError("canonical snapshot hash mismatch")

    feeds = load_feeds(feeds_path)
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro&immutable=1", uri=True) as db:
        db.row_factory = sqlite3.Row
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("canonical SQLite integrity check failed")
        articles = [dict(row) for row in db.execute(
            "SELECT id, title, url, source, published_at, collected_at "
            "FROM radar_items WHERE status = 'active'")]
        total = db.execute("SELECT count(*) FROM radar_items").fetchone()[0]
        if total != state["radar_items"]:
            raise ValueError("canonical article count mismatch")
        run_id = str(state.get("run_id", ""))
        # Each feed's persisted run key is URL-SHA256:actions-RUN_ID-ATTEMPT.
        last_rss = db.execute("SELECT run_key FROM collector_runs WHERE collector='radar_rss' "
                              "ORDER BY updated_at DESC LIMIT 1").fetchone()
        suffix = last_rss[0].split(":", 1)[1] if last_rss and ":" in last_rss[0] else None
        runs = [dict(row) for row in db.execute(
            "SELECT run_key, status, attempts, last_error, updated_at "
            "FROM collector_runs WHERE collector = 'radar_rss' AND "
            "substr(run_key, instr(run_key, ':') + 1) = ? "
            "ORDER BY updated_at DESC", (suffix,))] if suffix else []
        has_ai = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                            "AND name='rss_ai_reviews'").fetchone() is not None
        ai_rows = [dict(row) for row in db.execute(
            "SELECT r.radar_item_id, r.status, r.result_json, r.created_at, "
            "i.title FROM rss_ai_reviews r JOIN radar_items i ON i.id=r.radar_item_id "
            "ORDER BY r.created_at DESC, r.id DESC")] if has_ai else []

    # Reuse the existing SIGNAL and Family implementations without touching the
    # canonical DB. Their generated files stay inside this temporary directory.
    with tempfile.TemporaryDirectory(prefix="bct-ui-") as directory:
        root = Path(directory)
        (root / "canonical").mkdir()
        shutil.copyfile(database, root / "canonical" / "canonical.sqlite3")
        summary = build_families(Settings(root), feeds_path)
        signals = json.loads((root / "derived" / "rss_signals.json").read_text(encoding="utf-8"))

    article_by_id = {row["id"]: row for row in articles}
    latest_ai = {}
    reviews = []
    for row in ai_rows:
        result = json.loads(row["result_json"]) if row["result_json"] else None
        if row["status"] == "OK" and row["radar_item_id"] not in latest_ai:
            latest_ai[row["radar_item_id"]] = result
        reviews.append({"title": row["title"], "status": row["status"],
                        "created_at": row["created_at"], "result": result})

    signal_articles = []
    for entry in signals["entries"]:
        if not entry["signals"] or entry["radar_item_id"] not in article_by_id:
            continue
        article = article_by_id[entry["radar_item_id"]]
        kinds = sorted({value["signal"] for value in entry["signals"]})
        directions = sorted({"RELIEF" if kind in RELIEF else "PRESSURE" for kind in kinds})
        annotation = latest_ai.get(article["id"]) or {}
        signal_articles.append({"title": article["title"], "url": article["url"],
                                "source": article["source"],
                                "sector": annotation.get("SCOPE_INDUSTRY")
                                if annotation.get("SCOPE_INDUSTRY") not in (None, "", "UNRESOLVED") else None,
                                "published_at": article["published_at"],
                                "collected_at": article["collected_at"],
                                "directions": directions, "signal_types": kinds,
                                "fact_status": annotation.get("FACT_STATUS")})
    signal_articles.sort(key=lambda row: row["published_at"] or row["collected_at"],
                         reverse=True)

    # Group explicit stored industry scopes only; missing classifications remain
    # one unclassified bucket. Family results currently have no sector field.
    sectors = {}
    for row in signal_articles:
        name = row["sector"] or "미분류"
        group = sectors.setdefault(name, {"sector": name, "pressure": 0,
                                         "relief": 0, "family_count": 0,
                                         "sources": set(), "latest_at": None})
        group["pressure"] += "PRESSURE" in row["directions"]
        group["relief"] += "RELIEF" in row["directions"]
        if row["source"]:
            group["sources"].add(row["source"])
        stamp = row["published_at"] or row["collected_at"]
        if stamp and (not group["latest_at"] or stamp > group["latest_at"]):
            group["latest_at"] = stamp
    if summary["families"]:
        group = sectors.setdefault("미분류", {"sector": "미분류", "pressure": 0,
                                            "relief": 0, "family_count": 0,
                                            "sources": set(), "latest_at": None})
        group["family_count"] = len(summary["families"])
    for group in sectors.values():
        group["source_count"] = len(group.pop("sources"))

    feed_hashes = {hashlib.sha256(url.encode()).hexdigest(): name
                   for name, url in feeds.items()}
    feed_status = {}
    for row in runs:
        feed_id = row["run_key"].split(":", 1)[0]
        name = feed_hashes.get(feed_id)
        if name and name not in feed_status:
            feed_status[name] = {"name": name, "status": row["status"],
                                 "attempts": row["attempts"],
                                 "last_error": row["last_error"],
                                 "updated_at": row["updated_at"]}
    feed_rows = [feed_status.get(name, {"name": name, "status": None,
                                      "attempts": None, "last_error": None,
                                      "updated_at": None}) for name in feeds]
    recent = sorted([row for row in feed_rows if row["updated_at"]],
                    key=lambda row: row["updated_at"], reverse=True)

    ai_workflow = Path('.github/workflows/rss-ai.yml')
    ai_config = yaml.load(ai_workflow.read_text(encoding='utf-8'), Loader=yaml.BaseLoader) if ai_workflow.exists() else {}
    ai_mode = 'scheduled' if (ai_config or {}).get('on', {}).get('schedule') else 'manual'
    output = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_run_id": run_id or None,
        "overview": {
            "configured_rss": len(feeds),
            "successful_feeds": sum(row["status"] == "succeeded" for row in feed_rows),
            "failed_feeds": sum(row["status"] == "failed" for row in feed_rows),
            "new_articles": total - state["previous_radar_items"]
                            if "previous_radar_items" in state else None,
            "total_articles": total,
            "signal_articles": len(signal_articles),
            "candidate_families": len(summary["families"]),
            "last_collection_at": recent[0]["updated_at"] if recent else None,
            "ai_mode": ai_mode,
        },
        "sector_rankings": list(sectors.values()),
        "sector_note": "저장된 SCOPE_INDUSTRY만 사용합니다. 섹터 정보가 없는 SIGNAL·Family는 미분류로 집계합니다. 출처 수와 최근 신호는 SIGNAL 기사 기준입니다.",
        "signal_articles": signal_articles,
        "ai_reviews": reviews,
        "families": [{"name": row["family"], "sector": None,
                      "article_count": row["article_count"],
                      "source_count": row["source_count"],
                      "status": row.get("core_status"),
                      "latest_at": row["latest_at"],
                      "members": row["members"],
                      "pressure_articles": row["pressure_articles"],
                      "relief_articles": row["relief_articles"],
                      "confirmed_scope": row.get("confirmed_scope"),
                      "unresolved_scope": row.get("unresolved_scope")}
                     for row in summary["families"]],
        "feeds": feed_rows,
        "recent_collections": recent[:12],
        "recent_errors": [row for row in recent if row["status"] == "failed"][:12],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n",
                           encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--feeds", type=Path, default=Path("rss_feeds.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export(args.database, args.state, args.feeds, args.output)
    print(json.dumps({"generated_at": result["generated_at"],
                      "articles": result["overview"]["total_articles"],
                      "signals": result["overview"]["signal_articles"],
                      "families": result["overview"]["candidate_families"]}))
