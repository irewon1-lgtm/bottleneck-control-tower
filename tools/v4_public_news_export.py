"""Publish *only public RSS article metadata*, never the canonical SQLite DB.

Runs in the already approved GitHub Pages build after the V4 dashboard gate.
The data branch is the existing public RSS writer's state; no collection or
model inference occurs here. Verifies the exact RSS run's saved artifacts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
from urllib.parse import parse_qsl, urlsplit

FORMAT = "bct-public-rss-news-1"
SENSITIVE_QUERY = {"key", "api_key", "apikey", "token", "access_token", "auth", "secret", "password", "signature", "sig"}
NEEDED = {"id", "source", "title", "url", "published_at", "collected_at", "snippet", "source_type", "status"}


def _iso(value):
    if not isinstance(value, str) or len(value) > 45:
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if t.tzinfo is None:
            return None
        return t.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def _safe_link(value):
    if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 for c in value):
        return None
    try:
        u = urlsplit(value.strip())
        host = u.hostname or ""
        if u.scheme.lower() not in ("https", "http") or not host or u.username or u.password:
            return None
        if host in ("localhost",) or host.endswith((".local", ".internal", ".localhost")):
            return None
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return None
        except ValueError:
            if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,248}[a-z0-9]", host.lower()):
                return None
            if "." not in host:
                return None
        if any(k.casefold() in SENSITIVE_QUERY for k, _ in parse_qsl(u.query, keep_blank_values=True)):
            return None
        return value.strip()
    except ValueError:
        return None


def _text(value, limit):
    if not isinstance(value, str):
        return ""
    return "".join(" " if ord(c) < 32 else c for c in value).strip()[:limit]


def _hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _positive_int(value):
    return type(value) is int and value >= 0


def extract(db_path, state, summary, delta, *, data_commit):
    """Verify authoritative RSS state against run receipts and create safe data."""
    if not isinstance(state, dict) or not re.fullmatch("[0-9a-f]{64}", str(state.get("sha256", ""))):
        raise ValueError("RSS_STATE_INVALID")
    if _hash_file(db_path) != state["sha256"]:
        raise ValueError("RSS_DB_SHA_MISMATCH")
    run_id = str(state.get("run_id", ""))
    if not re.fullmatch(r"[1-9][0-9]{4,15}", run_id):
        raise ValueError("RSS_RUN_ID_INVALID")
    if not isinstance(summary, dict) or not isinstance(delta, dict):
        raise ValueError("RSS_RUN_RECEIPTS_MISSING")
    if str(delta.get("run_id")) != run_id or delta.get("format") != "bct-new-rss-delta-v1":
        raise ValueError("RSS_DELTA_RUN_MISMATCH")
    for key in ("initial_articles", "final_articles", "new_articles", "successful_feeds", "failed_feeds", "registered"):
        if not _positive_int(summary.get(key)):
            raise ValueError("RSS_SUMMARY_COUNT_INVALID_" + key)
    if (summary["final_articles"] != state.get("radar_items")
            or summary["initial_articles"] != state.get("previous_radar_items")
            or summary["new_articles"] != summary["final_articles"] - summary["initial_articles"]):
        raise ValueError("RSS_SUMMARY_STATE_COUNT_MISMATCH")
    feeds = summary.get("feeds")
    if (not isinstance(feeds, list) or len(feeds) != summary["registered"]
            or summary["successful_feeds"] + summary["failed_feeds"] != len(feeds)):
        raise ValueError("RSS_FEEDS_MISMATCH")
    prior = delta.get("preexisting_document_ids")
    newly = delta.get("documents")
    if (not isinstance(prior, list) or not isinstance(newly, list)
            or len(prior) != summary["initial_articles"] or len(newly) != summary["new_articles"]):
        raise ValueError("RSS_DELTA_SET_INVALID")
    old_ids = set(prior)
    new_ids = {r["document_id"] for r in newly if isinstance(r, dict) and isinstance(r.get("document_id"), str)}
    if (len(old_ids) != len(prior) or len(new_ids) != len(newly) or old_ids.intersection(new_ids)):
        raise ValueError("RSS_DELTA_DUPLICATE")
    collected_rows = []
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("RSS_DB_CORRUPT")
        fields = {row[1] for row in db.execute("PRAGMA table_info(radar_items)")}
        if not NEEDED.issubset(fields):
            raise ValueError("RSS_TABLE_SCHEMA_MISSING")
        saved_count = db.execute("SELECT count(*) FROM radar_items").fetchone()[0]
        if saved_count != state["radar_items"]:
            raise ValueError("RSS_DB_ROW_COUNT_MISMATCH")
        seen = set()
        for rec in db.execute("SELECT id,source,title,url,published_at,collected_at,snippet,source_type,status FROM radar_items"):
            id_, source, title, url, published, collected, snippet, source_type, status = rec
            if id_ in seen:
                raise ValueError("RSS_DUPLICATE_ID")
            seen.add(id_)
            if source_type != "NEWS" or status != "active":
                continue  # Soft-deleted items and non-news are not public articles.
            if not isinstance(id_, str) or not 8 <= len(id_) <= 64:
                raise ValueError("RSS_ITEM_ID_INVALID")
            if not title or not _iso(collected):
                raise ValueError("RSS_ITEM_METADATA_INVALID")
            safe_url = _safe_link(url)
            collected_rows.append({
                "id": id_, "source": _text(source, 120),
                "title": _text(title, 350),
                "url": safe_url,
                "published_at": _iso(published),
                "collected_at": _iso(collected),
                "snippet": _text(snippet, 300) if snippet else None,
                "is_new": id_ in new_ids,
                "link_available": safe_url is not None,
            })
        if set(new_ids) - seen:
            raise ValueError("RSS_DELTA_NEW_ID_NOT_IN_DATABASE")
    # The last-run delta is preserved independently from article publication dates.
    actual_new = sum(row["is_new"] for row in collected_rows)
    if actual_new != len(new_ids):
        raise ValueError("RSS_DELTA_NEW_ACTIVE_MISMATCH")
    collected_rows.sort(key=lambda r: (r["collected_at"], r["published_at"] or "", r["id"]), reverse=True)
    by_published = sorted((r["published_at"] for r in collected_rows if r["published_at"]), reverse=True)
    failures = []
    for item in feeds:
        if not isinstance(item, dict) or item.get("status") not in ("succeeded", "failed"):
            raise ValueError("RSS_FEED_STATUS_INVALID")
        if item["status"] == "succeeded":
            continue
        message = _text(item.get("error"), 160)
        http = re.search(r"(?:HTTP\s*(?:Error\s*)?)([1-5][0-9]{2})", message, re.IGNORECASE)
        failures.append({
            "feed": _text(item.get("feed"), 140),
            "type": "HTTP 오류" if "HTTP" in message else "네트워크/주소 오류" if "URL" in message else "기타 수집 오류",
            "http_status": int(http.group(1)) if http else None,
            "reason": "요청 거절 또는 응답 오류" if "HTTP" in message else "접속/주소 확인 필요",
            "attempts": item.get("attempts") if _positive_int(item.get("attempts")) else None,
        })
    if len(failures) != summary["failed_feeds"]:
        raise ValueError("RSS_FEED_FAILURE_MISMATCH")
    completed = _iso(summary.get("completed_at_utc"))
    if completed is None:
        raise ValueError("RSS_COMPLETED_TIME_MISSING")
    if not re.fullmatch("[0-9a-f]{40}", data_commit):
        raise ValueError("RSS_DATA_REF_INVALID")
    return {
        "format": FORMAT, "status": "VERIFIED_PUBLIC_RSS_METADATA",
        "data_ref": data_commit, "source_db_sha256": state["sha256"],
        "source_run_id": int(run_id), "collected_completed_at": completed,
        "total_db_records": state["radar_items"], "visible_article_count": len(collected_rows),
        "new_article_count": actual_new,
        "latest_published_at": by_published[0] if by_published else None,
        "feed_total": summary["registered"], "feed_success": summary["successful_feeds"],
        "feed_failed": len(failures), "failed_feeds": failures,
        "classification": "RSS_TITLE_METADATA_NOT_VERIFIED_BOTTLENECK",
        "articles": collected_rows,
    }


def _cmd(argv, *, cwd, timeout=180, output=None):
    if output is None:
        return subprocess.run(argv, cwd=cwd, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout).stdout
    with open(output, "wb") as stream:
        subprocess.run(argv, cwd=cwd, check=True, stdout=stream,
                       stderr=subprocess.PIPE, timeout=timeout)
    return None


def build_from_public_branch(repo):
    """Read pinned existing public data ref. No token, DB or raw body is published."""
    repo = Path(repo).resolve()
    with tempfile.TemporaryDirectory(prefix="bct-public-rss-") as scratch:
        scratch = Path(scratch)
        _cmd(["git", "fetch", "--no-tags", "--depth=1", "origin", "refs/heads/data"],
             cwd=repo, timeout=210)
        data_commit = _cmd(["git", "rev-parse", "FETCH_HEAD"], cwd=repo).decode().strip()
        state = json.loads(_cmd(["git", "show", "FETCH_HEAD:state.json"], cwd=repo))
        db_path = scratch / "canonical.sqlite3"
        _cmd(["git", "show", "FETCH_HEAD:canonical.sqlite3"], cwd=repo,
             timeout=180, output=db_path)
        artifact_dir = scratch / "artifact"
        artifact_dir.mkdir()
        repo_name = os.environ.get("GITHUB_REPOSITORY", "irewon1-lgtm/bottleneck-control-tower")
        if repo_name != "irewon1-lgtm/bottleneck-control-tower" or not os.environ.get("GH_TOKEN"):
            raise ValueError("RSS_REQUIRED_GITHUB_READ_ACCESS_MISSING")
        run_id = str(state.get("run_id", ""))
        if not re.fullmatch(r"[1-9][0-9]{4,15}", run_id):
            raise ValueError("RSS_STATE_RUN_ID_INVALID")
        _cmd(["gh", "run", "download", run_id, "-R", repo_name, "-p", "rss-live-result-*",
              "-D", str(artifact_dir)], cwd=repo, timeout=150)
        summaries = list(artifact_dir.rglob("rss-live-result.json"))
        manifests = list(artifact_dir.rglob("new-document-manifest.json"))
        if len(summaries) != 1 or len(manifests) != 1:
            raise ValueError("RSS_ARTIFACT_FILES_MISSING_OR_AMBIGUOUS")
        if summaries[0].stat().st_size > 2_000_000 or manifests[0].stat().st_size > 5_000_000:
            raise ValueError("RSS_ARTIFACT_SIZE_EXCEEDED")
        return extract(db_path, state, json.loads(summaries[0].read_text()),
                       json.loads(manifests[0].read_text()), data_commit=data_commit)
