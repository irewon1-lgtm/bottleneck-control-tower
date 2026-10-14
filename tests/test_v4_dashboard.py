"""Read-only projection and source-grounded UI API, using the preserved real DB.

Mutation/absence cases are isolated test doubles. They never change the corpus.
"""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from bct.v4.dashboard import DataUnavailable, ResearchReader, make_server, public_link


REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def reader(tmp_path_factory):
    root = tmp_path_factory.mktemp("dashboard-research-only")
    (root / "docs").symlink_to(REPO / "docs", target_is_directory=True)
    return ResearchReader(root)  # Clean-checkout path restores verified backup.


@pytest.fixture
def server(reader):
    s = make_server(reader, 0)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield s, "http://127.0.0.1:" + str(s.server_port)
    s.shutdown()
    s.server_close()
    t.join(timeout=5)


def get(url):
    with urlopen(url, timeout=30) as r:
        return r, r.read()


def test_actual_sqlite_records_revision_and_counts(reader):
    x = reader.dashboard()
    assert reader.snapshot is True
    assert x["source"]["read_only"] is True
    assert x["counts"]["evidence"] == 549
    assert x["counts"]["reviewed"] == 23
    assert x["counts"]["structured"] == 211
    assert x["counts"]["discovery"] == 315
    assert len({r["id"] for r in x["records"]}) == 549  # Revisions aren't new facts.
    assert x["counts"]["future_candidates"] == {"S1": 0, "S2": 0, "S3": 0}
    assert x["counts"]["s1_signals"] == 14
    assert not any(r["is_future_candidate"] for r in x["records"])
    assert x["counts"]["pending"] == 295
    assert x["counts"]["body_status"] == {"FULL": 31, "PARTIAL": 9, "UNAVAILABLE": 6}
    assert x["coverage"]["documents"] == 110
    assert x["coverage"]["read_characters"] == 58488
    assert x["coverage"]["body_characters"] == 601012
    assert x["automation"]["collection_runs"] == 2
    assert x["automation"]["ai_mode"] == "DISABLED"
    assert x["automation"]["api_calls"] == 0
    assert len(x["automation"]["errors"]) == 12
    assert [(r["attempted"], r["received"]) for r in x["automation"]["ai_history"]] == [(14, 13), (9, 8), (6, 6)]
    assert "HTTP 400 오류 1건" in x["automation"]["ai_history"][1]["notes"]


def test_connection_and_requests_never_change_db(reader, server):
    before = hashlib.sha256(reader.path.read_bytes()).hexdigest()
    with reader.connection() as db:
        with pytest.raises(sqlite3.OperationalError):
            db.execute("INSERT INTO metadata VALUES('dashboard-test','forbidden')")
    _, base = server
    get(base + "/api/dashboard")
    get(base + "/api/export")
    assert hashlib.sha256(reader.path.read_bytes()).hexdigest() == before


def test_all_reused_reviewed_sources_exactly_rechecked(reader):
    for r in reader.dashboard()["records"]:
        if r["category"] == "reviewed":
            result = reader.evidence(r["id"])
            assert result["all_references_verified"], r["product"]
            assert result["is_future_candidate"] is False
            assert result["period"] == "예상 시기 미확인"


@pytest.mark.parametrize("bad_field,bad_value", [("quote", "없는 인용문"), ("body_sha256", "0" * 64), ("start", -1), ("origin_url", "https://example.org/wrong")])
def test_false_or_ambiguous_claim_is_never_marked_verified(reader, monkeypatch, bad_field, bad_value):
    original = reader._state
    with reader.connection() as db:
        records, _, _ = original(db)
    rid = next(k for k, r in records.items() if r["event_status"] == "ADOPTED_RESEARCH_EVENT")
    def broken(db):
        result = copy.deepcopy(original(db))
        result[0][rid]["references"][0][bad_field] = bad_value
        return result
    monkeypatch.setattr(reader, "_state", broken)
    result = reader.evidence(rid)
    assert result["all_references_verified"] is False
    assert result["references"][0]["verified"] is False
    assert result["references"][0]["context_before"] is None


def test_structured_original_rows_verified_and_semantics_still_unknown(reader):
    row = next(r for r in reader.dashboard()["records"] if r["category"] == "structured")
    result = reader.evidence(row["id"])
    assert result["all_references_verified"] is True
    assert len(result["references"]) == 2
    assert result["future_gap"] == "UNKNOWN"
    assert result["stage"] == "UNKNOWN"
    assert result["is_future_candidate"] is False


def test_missing_db_is_not_replaced_by_empty_or_fake_data(tmp_path):
    with pytest.raises(DataUnavailable):
        ResearchReader(REPO, tmp_path / "missing.sqlite3")
    assert not (tmp_path / "missing.sqlite3").exists()


def test_backup_hash_mismatch_is_rejected(tmp_path):
    reports = tmp_path / "docs/v4/cross-industry"
    reports.mkdir(parents=True)
    (reports / "research-snapshot.sqlite3.gz").write_bytes(b"not the real archive")
    (reports / "verification.json").write_text(json.dumps({"snapshot_file_sha256": "0" * 64}))
    with pytest.raises(DataUnavailable, match="해시"):
        ResearchReader(tmp_path)
    assert not (tmp_path / "var").exists()


def test_api_files_errors_export_and_no_mutation_route(server):
    _, base = server
    r, raw = get(base + "/api/dashboard")
    x = json.loads(raw)
    assert len(x["records"]) == 549
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    r, raw = get(base + "/api/export")
    assert "attachment" in r.headers["Content-Disposition"]
    assert json.loads(raw)["counts"] == x["counts"]
    for path in ["/", "/style.css", "/app.js", "/api/health"]:
        assert get(base + path)[0].status == 200
    for path in ["/api/evidence/" + "0" * 64, "/api/evidence/1%20OR%201=1", "/../docs/v4/PROGRESS.json", "/.env", "/var/v4/cross-industry/ledger/v4.sqlite3"]:
        with pytest.raises(HTTPError) as err:
            get(base + path)
        assert err.value.code == 404
    with pytest.raises(HTTPError) as err:
        urlopen(Request(base + "/api/dashboard", method="POST"), timeout=10)
    assert err.value.code == 405
    with pytest.raises(HTTPError) as err:
        urlopen(Request(base + "/api/dashboard", headers={"Host": "untrusted.example"}), timeout=10)
    assert err.value.code == 403


def test_missing_report_returns_error_never_zero_success(server, reader, monkeypatch):
    _, base = server
    def unavailable():
        raise OSError("private path must not reach HTTP response")
    monkeypatch.setattr(reader, "dashboard", unavailable)
    with pytest.raises(HTTPError) as err:
        get(base + "/api/dashboard")
    assert err.value.code == 503
    body = err.value.read().decode()
    assert "private path" not in body
    assert "읽지 못했습니다" in body


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:secret@example.org/", "https://example.org/?token=private", "file:///etc/passwd"])
def test_source_links_cannot_execute_code_or_expose_credentials(url):
    assert public_link(url) is None


def test_official_article_identifier_is_kept():
    url = "https://www.eia.gov/todayinenergy/detail.php?id=68104"
    assert public_link(url) == url
