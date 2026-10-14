"""Frozen real-source preparation and isolated acquisition safety checks."""
import gzip
import importlib.util
import json
from pathlib import Path
import shutil
from urllib.error import URLError

import pytest

from bct.v4.cross_industry import collect
from bct.v4.dashboard import ResearchReader
from bct.v4.store import Ledger, sha

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/v4/post-ui"


def load_tool():
    spec = importlib.util.spec_from_file_location("post_ui_tool", ROOT / "tools/v4_post_ui.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def latest(tmp_path_factory):
    root = tmp_path_factory.mktemp("new-research-checkout")
    for f in ["docs/v4/PROGRESS.json", "docs/v4/cross-industry/analysis.json", "docs/v4/post-ui/VERIFICATION.json", "docs/v4/post-ui/research-snapshot.sqlite3.gz"]:
        target = root / f
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, target)
    return ResearchReader(root)


def test_initial_scope_is_exhausted_without_relabeling_new_URLs():
    scope = json.loads((REPORT / "initial-scope.json").read_text())
    outcomes = json.loads((REPORT / "initial-outcomes.json").read_text())
    assert {r["id"] for r in scope["URLs"]} == {r["id"] for r in outcomes["initial"]}
    assert len(outcomes["initial"]) == 295
    assert sum(r["outcome"] == "BODY_CAPTURED" for r in outcomes["initial"]) == 195
    assert sum(r["outcome"] == "ACCESS_UNAVAILABLE" for r in outcomes["initial"]) == 100
    assert not any(r["outcome"] == "UNATTEMPTED" for r in outcomes["initial"])
    assert len(outcomes["additional"]) == 3
    assert sum(r["status"] == "METADATA_ONLY_UNATTEMPTED_BODY" for r in outcomes["additional"]) == 2
    assert not {r["url"] for r in outcomes["initial"]} & {r["url"] for r in outcomes["additional"]}


def test_clean_checkout_restores_latest_research_not_old_549_rows(latest):
    x = latest.dashboard()
    assert latest.snapshot is True
    assert x["counts"]["body_nonempty"] == 235  # Existing40 + newly usable195.
    assert x["counts"]["pending"] == 2  # New official metadata only, not old295.
    assert x["counts"]["evidence"] == 511
    assert x["counts"]["discovery"] == 277
    assert x["counts"]["reviewed"] == 23
    assert x["counts"]["future_candidates"] == {"S1": 0, "S2": 0, "S3": 0}
    assert not any(r["product"].casefold() in ("lock", "padlock") for r in x["records"])
    with latest.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM events WHERE kind='POST_UI_PRODUCT_REVIEW'").fetchone()[0] == 81
        assert db.execute("SELECT COUNT(*) FROM events WHERE kind='POST_UI_EVENT_REVIEW'").fetchone()[0] == 14
        assert db.execute("SELECT COUNT(*) FROM events WHERE kind='CROSS_COMMON_EVIDENCE'").fetchone()[0] == 549  # Originals preserved.


def test_all_review_positions_and_values_match_real_saved_sources(latest):
    with latest.connection() as db:
        docs = {i: json.loads(p) for i, p in db.execute("SELECT id,payload FROM documents")}
    for r in json.loads((REPORT / "product-reviews.json").read_text())["products"]:
        assert r["reason_ko"]
        for ref in r["references"]:
            d = docs[ref["document_id"]]
            assert sha(d["body"].encode()) == ref["body_sha256"]
            a, b = ref["reference"]["start"], ref["reference"]["end"]
            assert d["body"][a:b] == ref["surface"]
    for r in json.loads((REPORT / "event-reviews.json").read_text())["events"]:
        assert r["no_new_S_promotions"] is True
        for ref in r["references"]:
            d = docs[ref["document_id"]]
            assert d["body"][ref["start"]:ref["end"]] == ref["quote"]


def test_saved_official_JSON_rows_not_replaced_with_product_quantities(latest):
    with latest.connection() as db:
        rows = [json.loads(t) for t, in db.execute("SELECT payload FROM events WHERE kind='POST_UI_OFFICIAL_ROW'")]
        assert len(rows) == 6
        for r in rows:
            assert r["physical_quantity"] == "UNKNOWN"
            d = json.loads(db.execute("SELECT payload FROM documents WHERE id=?", (r["document_id"],)).fetchone()[0])
            raw = db.execute("SELECT data FROM blobs WHERE id=?", (d["raw_sha256"],)).fetchone()[0]
            assert sha(raw) == d["raw_sha256"]
            idx = int(r["source_row"]["json_pointer"].split("/")[-1])
            assert isinstance(json.loads(raw)["results"][idx], dict)
            if d["origin_publisher"] == "USAspending":
                assert d["published_at"] is None  # Modification isn't publication.


def test_source_review_annotation_reaches_existing_detail_schema(latest):
    row = next(r for r in latest.dashboard()["records"] if "FOX-XP TM" in r["product"])
    detail = latest.evidence(row["id"])
    assert "Codex AI" in detail["status"]
    assert "140만 달러" in detail["missing"][0]
    assert detail["all_references_verified"] is True
    assert detail["stage"] == "S1"  # Historical stage unchanged.
    assert detail["is_future_candidate"] is False


def test_fixed_scope_does_not_fetch_new_discovery_or_stale_success(tmp_path):
    ledger = Ledger(tmp_path)
    good, fail, outside, old = ["https://example.org/" + s for s in ("ceramic", "fail", "later", "stale")]
    with ledger.db:
        for url in [good, fail, outside]:
            ledger.event("CROSS_DISCOVERED", {"url": url, "industry_hint": "UNCLASSIFIED_OPEN_DISCOVERY"})
        ledger.event("CROSS_ARTICLE_ATTEMPT", {"url": old, "at": "2020-01-01T00:00:00+00:00"})
        ledger.event("CROSS_ARTICLE_RESULT", {"url": old, "at": "2020-01-01T00:00:00+00:00", "status": "CAPTURED", "industry_hint": "UNKNOWN"})
    ledger.close()
    class Client:
        def __init__(self): self.calls = []
        def document(self, url):
            self.calls.append(url)
            if url == fail: raise URLError("isolated fixture timeout")
            body = "Authored safety fixture; not research evidence."
            raw = body.encode()
            return {"document_id": "fixture-ceramic", "origin_url": url, "raw_sha256": sha(raw), "body": body, "body_sha256": sha(raw), "body_status": "PARTIAL", "provenance": "BLOCKED"}, raw, {}
    client = Client()
    result = collect(tmp_path, [], allowed_urls={good, fail}, refresh_existing=False, article_limit=2, client=client)
    assert sorted(client.calls) == sorted([good, fail])
    assert len(result["captured"]) == 1
    assert result["pending_unattempted"] == 0
    result2 = collect(tmp_path, [], allowed_urls={good, fail}, refresh_existing=False, article_limit=2, client=client)
    assert result2["article_attempts"] == 0
    assert len(client.calls) == 2


def test_access_gate_stores_empty_body_and_raw_without_model_call():
    mod = load_tool()
    client = mod.PublicClient()
    raw = b'<html><body class="gsd-paywall">Private article text</body></html>'
    client.fetch = lambda url: (raw, url, 200, "text/html")
    d, saved, views = client.document("https://example.org/restricted")
    assert saved == raw
    assert d["body"] == ""
    assert d["body_status"] == "UNAVAILABLE"
    assert d["access_review"] == "RESTRICTED_NO_BODY_PROCESSING"


def test_missing_review_input_stops_before_opening_writable_db(tmp_path, monkeypatch):
    mod = load_tool()
    monkeypatch.setattr(mod, "R", tmp_path)
    with pytest.raises(FileNotFoundError):
        mod.apply_reviews()
    assert not (tmp_path / "v4.sqlite3").exists()


def test_alternative_extraction_does_not_turn_subscription_preview_into_body(tmp_path, monkeypatch):
    import bct.v4.cross_industry as shared
    mod = load_tool()
    monkeypatch.setattr(mod, "V", tmp_path)
    monkeypatch.setattr(mod, "R", tmp_path / "reports")
    url = "https://example.org/subscription"
    monkeypatch.setattr(mod, "freeze", lambda: {"URLs": [{"url": url}]})
    ledger = Ledger(tmp_path / "ledger")
    raw = b"An authored subscription-gate test fixture."
    original = {"document_id": "test-only", "origin_url": url, "requested_url": url,
                "raw_sha256": sha(raw), "body": "", "body_sha256": sha(b""), "body_status": "UNAVAILABLE"}
    ledger.capture(original, raw)
    ledger.close()
    monkeypatch.setattr(shared, "alternative_body_view", lambda *args: {"body": "You've reached your limit of free weekly articles"})
    assert mod.body_views() == {"ACCESS_RESTRICTED": 1}
    ledger = Ledger(tmp_path / "ledger")
    assert ledger.db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    ledger.close()


def test_original_UI_and_frozen_evidence_files_unchanged():
    manifest = json.loads((REPORT / "initial-scope.json").read_text())
    for name, expected in manifest["protected_files"].items():
        assert sha((ROOT / name).read_bytes()) == expected, name
