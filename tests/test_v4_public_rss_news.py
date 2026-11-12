"""Source-bound public RSS: no synthetic titles, unsafe URLs, or forecast promotion."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v4_public_news_export", ROOT / "tools/v4_public_news_export.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(tmp_path):
    db = tmp_path / "rss.sqlite3"
    with sqlite3.connect(db) as con:
        con.execute("""CREATE TABLE radar_items
           (id TEXT, source TEXT, title TEXT, url TEXT, published_at TEXT,
            collected_at TEXT, snippet TEXT, source_type TEXT, status TEXT)""")
        con.executemany("INSERT INTO radar_items VALUES(?,?,?,?,?,?,?,?,?)", [
            ("oldid0001", "www.example.com", "Previously collected article",
             "https://www.example.com/old", "2026-11-09T07:00:00+00:00",
             "2026-11-09T09:00:00+00:00", None, "NEWS", "active"),
            ("newid0002", "www.example.com", "Actual new article",
             "https://www.example.com/new", "2026-11-12T04:00:00+00:00",
             "2026-11-12T09:00:00+00:00", "Original factual summary", "NEWS", "active"),
        ])
    state = {"sha256": hashlib.sha256(db.read_bytes()).hexdigest(),
             "radar_items": 2, "previous_radar_items": 1, "run_id": "43191046464"}
    summary = {"registered": 2, "initial_articles": 1, "final_articles": 2,
               "new_articles": 1, "successful_feeds": 1, "failed_feeds": 1,
               "completed_at_utc": "2026-11-12T09:26:47.647793+00:00",
               "feeds": [
                   {"feed": "Good", "status": "succeeded", "attempts": 1, "saved": 1, "duplicates": 0, "error": None},
                   {"feed": "Bad", "status": "failed", "attempts": 2, "saved": 0, "duplicates": 0,
                    "error": "HTTPError: HTTP Error 404: Not Found"}
               ]}
    delta = {"format": "bct-new-rss-delta-v1", "run_id": 43191046464,
             "preexisting_document_ids": ["oldid0001"],
             "documents": [{"document_id": "newid0002", "url": "https://www.example.com/new"}]}
    return db, state, summary, delta


def test_public_rss_real_sources_and_nonpromotion(tmp_path):
    db, state, summary, delta = fixture(tmp_path)
    data = m.extract(db, state, summary, delta, data_commit="a" * 40)
    assert data["visible_article_count"] == 2
    assert data["new_article_count"] == 1
    assert data["articles"][0]["id"] == "newid0002"
    assert data["articles"][0]["is_new"]
    assert not data["articles"][1]["is_new"]
    assert data["failed_feeds"] == [{"feed": "Bad", "type": "HTTP 오류",
                                     "http_status": 404, "reason": "요청 거절 또는 응답 오류",
                                     "attempts": 2}]
    assert data["classification"] == "RSS_TITLE_METADATA_NOT_VERIFIED_BOTTLENECK"
    assert all("stage" not in row and "target" not in row for row in data["articles"])
    assert all("body" not in row for row in data["articles"])


def test_invalid_or_mismatched_run_fails_closed(tmp_path):
    db, state, summary, delta = fixture(tmp_path)
    summary["new_articles"] = 2
    with pytest.raises(ValueError, match="COUNT_MISMATCH"):
        m.extract(db, state, summary, delta, data_commit="a" * 40)
    summary["new_articles"] = 1
    delta["run_id"] = 90000
    with pytest.raises(ValueError, match="RUN_MISMATCH"):
        m.extract(db, state, summary, delta, data_commit="a" * 40)
    delta["run_id"] = 43191046464
    state["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA_MISMATCH"):
        m.extract(db, state, summary, delta, data_commit="a" * 40)


def test_nonpublic_and_secret_urls_not_exported():
    for link in ("file:///etc/passwd", "http://localhost/hello", "http://127.0.0.1/item",
                 "http://192.168.1.10/item", "https://site.example/article?token=supersecret",
                 "https://user:pass@site.example/article", "javascript:alert(1)"):
        assert m._safe_link(link) is None
    assert m._safe_link("https://example.org/article?id=123") == "https://example.org/article?id=123"


def test_every_article_is_rendered_with_original_date_and_source(tmp_path):
    db, state, summary, delta = fixture(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO radar_items VALUES(?,?,?,?,?,?,?,?,?)",
            ("newid0003", "www.example.com", "Unknown publication date",
             "https://www.example.com/third", None,
             "2026-11-12T11:00:00+00:00", None, "NEWS", "active"))
    state["sha256"] = hashlib.sha256(db.read_bytes()).hexdigest()
    state["radar_items"] = 3
    summary["final_articles"] = 3
    summary["new_articles"] = 2
    delta["documents"].append({"document_id": "newid0003", "url": "https://www.example.com/third"})
    data = m.extract(db, state, summary, delta, data_commit="a"*40)
    assert data["visible_article_count"] == 3
    assert data["articles"][0]["published_at"] is None
    assert data["new_article_count"] == 2
    assert data["latest_published_at"] == datetime(2026,11,12,4,tzinfo=timezone.utc).isoformat()



def test_future_pub_date_not_misreported_as_latest(tmp_path):
    db, state, summary, delta = fixture(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute("UPDATE radar_items SET published_at=? WHERE id='newid0002'",
                    ("2027-10-25T04:00:00+00:00",))
    state["sha256"] = hashlib.sha256(db.read_bytes()).hexdigest()
    data = m.extract(db, state, summary, delta, data_commit="a" * 40)
    assert data["future_date_holds"] == 1
    assert data["articles"][0]["published_at"] is None
    assert data["articles"][0]["publication_date_status"] == "FUTURE_DATE_HOLD"
    assert data["latest_published_at"] == "2026-11-09T07:00:00+00:00"


def test_new_articles_nav_is_unverified_and_paginated():
    html = (ROOT / "src/bct/v4/dashboard_web/index.html").read_text()
    js = (ROOT / "src/bct/v4/dashboard_web/app.js").read_text()
    assert 'data-nav="news"' in html
    for code in ('function news()', 'function rssNewsTeaser()', 'function renderNewsResults()',
                 'request("./api/rss-news.json")', "const pageSize=24",
                 '"최근 수집순"', '"최근 발행순"', '"이번 수집에서 새로 추가된 기사만 보기"',
                 '"제목·요약 수집 / 병목 미검증"'):
        assert code in js
    assert "boardEvidenceFor(sector)" in js
    assert 'data.sector_rankings' in js
