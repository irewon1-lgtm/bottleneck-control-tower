"""SYNTHETIC falsification/storage tests, never a real EARLY evaluation."""
from copy import deepcopy
import hashlib
import json
import sqlite3

import pytest

from bct.objective_lock import stamp_export
from bct.v4 import adapters
from bct.v4.pipeline import analyze, replay, cycle
from bct.v4.store import Ledger
from test_precursor_evidence_graph import pair, ASOF


def snapshot():
    doc = pair()[0]
    doc["body_status"] = "FULL"
    return doc


def test_library_comparison_does_not_upgrade_inaccessible_body():
    raw = b'<article><p>Qualified production capacity expands in 2028.</p><p>Subscribe to continue reading.</p></article>'
    result = adapters.html_views(raw)
    assert result["baseline"]["body_status"] == "PARTIAL"
    assert "BCT existing parser retained" in result["selection"]


def test_feed_is_lead_not_verified_publication():
    feed = b'<rss version="2.0"><channel><title>Official</title><item><title>Order</title><link>https://energy.gov/articles/order</link><pubDate>Tue, 13 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>'
    entry = adapters.rss_leads(feed)[0]
    assert entry["feed_published_raw"] == "Tue, 13 Oct 2026 12:00:00 GMT"
    assert entry["publication_verified"] is False
    with pytest.raises(ValueError, match="MALFORMED"):
        adapters.rss_leads(b"<rss><channel>")


def test_date_precision_no_invented_day():
    assert adapters.exact_date("March 1, 2028") == "2028-03-01"
    assert adapters.exact_date("2028") is None
    assert adapters.exact_date("March 2028") is None


def test_actual_pypdf_library_numeric_and_broken_pdf():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject
    from io import BytesIO
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 50 700 Td (Production: 100 units in 2028) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    stream = BytesIO()
    writer.write(stream)
    result = adapters.pdf_text(stream.getvalue())
    assert "100 units" in result["body"] and result["pages"][0]["page"] == 1
    assert result["status"] == "PARTIAL"
    with pytest.raises(Exception):
        adapters.pdf_text(b"not a PDF")


def test_ai_span_validation_is_not_inference_or_semantic_validation():
    doc = snapshot()
    start = doc["body"].index("tungsten")
    output = {"entities": {"product": [{"text": "tungsten", "start": start, "end": start + 8, "confidence": .99}]}}
    spans = adapters.validate_spans(doc, output)
    assert spans[0]["semantic_status"] == "UNKNOWN"
    output["entities"]["product"][0]["text"] = "invented"
    with pytest.raises(ValueError, match="SPAN_SOURCE"):
        adapters.validate_spans(doc, output)


def test_missing_model_blocks_without_paid_fallback(tmp_path):
    with pytest.raises(ValueError, match="MODEL_NOT_PREPARED"):
        adapters.CPUExtractor(tmp_path).extract(snapshot())


def test_ledger_atomicity_dedup_reopen_and_immutable_first(tmp_path):
    ledger = Ledger(tmp_path)
    doc = snapshot()
    assert ledger.capture(doc)
    assert not ledger.capture(doc)
    assert ledger.status()["documents"] == 1
    before = ledger.db.execute("SELECT COUNT(*) FROM blobs").fetchone()[0]
    raw = b"original raw"
    collided = {**doc, "raw_sha256": hashlib.sha256(raw).hexdigest(), "body": "changed"}
    collided["body_sha256"] = hashlib.sha256(collided["body"].encode()).hexdigest()
    with pytest.raises(ValueError, match="COLLISION"):
        ledger.capture(collided, raw)
    assert ledger.db.execute("SELECT COUNT(*) FROM blobs").fetchone()[0] == before
    candidate = {"target_id": "target", "candidate_first_detected_at": "2026-10-01T00:00:00+00:00"}
    first = stamp_export({"candidates": [candidate], "mode": "SYNTHETIC"})
    ledger.save_run("first", deepcopy(first), "SYNTHETIC")
    second = stamp_export({"candidates": [{**candidate, "candidate_first_detected_at": "2026-10-02T00:00:00+00:00"}]})
    assert ledger.save_run("second", second, "SYNTHETIC")["candidates"][0]["candidate_first_detected_at"] == candidate["candidate_first_detected_at"]
    ledger.save_run("third", stamp_export({"candidates": []}), "SYNTHETIC")
    assert ledger.history("SYNTHETIC")[0]["first"] == candidate
    assert ledger.history("SYNTHETIC")[0]["latest"] is None
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        ledger.db.execute("DELETE FROM documents")
    ledger.close()
    reopened = Ledger(tmp_path)
    assert reopened.latest_documents()[0]["body"] == doc["body"]
    assert reopened.status()["shadow_7_days"] == "BLOCKED"
    reopened.close()


def test_backup_restored_ledger_and_restart_interruption(tmp_path):
    ledger = Ledger(tmp_path / "runtime")
    ledger.capture(snapshot())
    with ledger.db:
        ledger.event("RUN_STARTED", {"run_id": "interrupted"})
    assert ledger.recover() == 1
    assert ledger.recover() == 0
    backup = tmp_path / "restored" / "v4.sqlite3"
    ledger.backup(backup)
    with pytest.raises(ValueError, match="EXISTS"):
        ledger.backup(backup)
    ledger.close()
    restored = Ledger(backup.parent)
    assert restored.status()["integrity"] == "ok"
    assert restored.latest_documents()[0]["body_sha256"] == snapshot()["body_sha256"]
    restored.close()


def test_unowned_operating_database_refused_without_changes(tmp_path):
    path = tmp_path / "v4.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE operating(id PRIMARY KEY)")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="UNOWNED"):
        Ledger(tmp_path)
    assert path.read_bytes() == before


def test_validated_graph_reused_unknown_totals_not_S3():
    result = analyze(pair(), mode="SYNTHETIC", as_of=ASOF)
    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate["total_qualified_supply"] == "UNKNOWN" and candidate["s_stage"] == "UNKNOWN"
    assert candidate["early_success_verified"] is False
    assert result["graph"]["edges"] and result["graph"]["reference_checks"] > 0
    assert result["early_success_cases"] == 0


@pytest.mark.parametrize("mutation", ["spec", "publisher", "date", "future", "quantity", "plan", "relief"])
def test_bad_promotion_is_blocked(mutation):
    buyer, maker = pair()
    if mutation == "spec":
        maker["body"] = maker["body"].replace("military-grade", "non-Chinese")
        maker["body_sha256"] = hashlib.sha256(maker["body"].encode()).hexdigest()
    elif mutation == "publisher":
        maker["origin_publisher"] = buyer["origin_publisher"]
    elif mutation == "date":
        buyer["published_at"] = None
    elif mutation == "future":
        maker["available_at"] = "2027-01-01T00:00:00+00:00"
    elif mutation == "quantity":
        buyer["body"] += "\nRevenue $100 million is not unit orders."
        buyer["body_sha256"] = hashlib.sha256(buyer["body"].encode()).hexdigest()
        # An unrelated financial amount cannot turn unknown market supply into a numeric gap.
        result = analyze([buyer, maker], mode="SYNTHETIC", as_of=ASOF)
        assert all(c["total_qualified_supply"] == "UNKNOWN" for c in result["candidates"])
        return
    elif mutation == "plan":
        buyer["body"] = buyer["body"].replace("signed firm new orders", "forecasts hypothetical orders")
        buyer["body_sha256"] = hashlib.sha256(buyer["body"].encode()).hexdigest()
    elif mutation == "relief":
        from test_precursor_source_pipeline import doc
        relief = doc("Sufficient qualified supply for military-grade tungsten for military drones in United States under contract K-242 covers all contracted demand in 2027.", "Alternate", url="https://alternate.example/press-release/capacity")
        result = analyze([buyer, maker, relief], mode="SYNTHETIC", as_of=ASOF)
        assert not result["candidates"]
        return
    assert not analyze([buyer, maker], mode="SYNTHETIC", as_of=ASOF)["candidates"]


def test_duplicate_document_ids_rejected_before_graph():
    doc = snapshot()
    with pytest.raises(ValueError, match="DUPLICATE_DOCUMENT_ID"):
        analyze([doc, deepcopy(doc)], mode="SYNTHETIC", as_of=ASOF)


def test_replay_never_live_and_cannot_create_real_shadow_days(tmp_path):
    batch = stamp_export({"documents": list(pair())})
    assert replay(tmp_path, batch, ASOF, mode="SYNTHETIC")["candidates"]
    with pytest.raises(ValueError, match="cannot be LIVE"):
        replay(tmp_path, batch, ASOF, mode="LIVE")
    ledger = Ledger(tmp_path)
    assert ledger.status()["observed_live_days"] == []
    ledger.close()


def test_source_failures_saved_no_retry_and_no_live_success_days(tmp_path):
    class Denied:
        calls = []
        def document(self, url):
            self.calls.append(url)
            raise ValueError("CONNECT_BLOCKED")
    client = Denied()
    result = cycle(tmp_path, {"urls": ["https://eia.gov/test"], "document_limit": 1}, client=client)
    assert client.calls == ["https://eia.gov/test"]
    assert result["integration_status"] == "BLOCKED" and len(result["failures"]) == 1
    ledger = Ledger(tmp_path)
    assert ledger.status()["observed_live_days"] == []
    assert ledger.db.execute("SELECT COUNT(*) FROM events WHERE kind='FAILURE'").fetchone()[0] == 1
    ledger.close()
