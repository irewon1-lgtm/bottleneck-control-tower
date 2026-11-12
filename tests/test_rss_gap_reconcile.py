"""Historical RSS gap reconciliation: URL-level, source-free, no synthetic backfill."""
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gap_reconcile", ROOT / "tools/bct_rss_gap_reconcile.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def make_artifact(path, *, at, old_urls, new_urls, ids=None):
    ids = ids or list(range(1, len(old_urls) + 1))
    manifest = {
        "format": "bct-new-rss-delta-v1", "collection_started_at": at,
        "preexisting_urls": old_urls, "preexisting_document_ids": ids,
        "documents": [{"url": u, "document_id": i, "collected_at": at}
                      for i, u in enumerate(new_urls, start=100)],
    }
    summary = {"registered": 1, "initial_articles": len(old_urls),
               "new_articles": len(new_urls), "final_articles": len(old_urls) + len(new_urls)}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("new-document-manifest.json", json.dumps(manifest))
        z.writestr("rss-live-result.json", json.dumps(summary))
    return path


def test_identical_url_is_recovered_even_if_document_id_changed(tmp_path):
    earlier = make_artifact(tmp_path / "fail.zip", at="2026-11-05T23:20:06+00:00",
                            old_urls=["https://example.test/old"],
                            new_urls=["https://example.test/a", "https://example.test/b"])
    later = make_artifact(tmp_path / "saved.zip", at="2026-11-12T00:07:49+00:00",
                          old_urls=["https://example.test/old", "https://example.test/a",
                                    "https://example.test/b"], ids=[1, 200, 201],
                          new_urls=["https://example.test/c"])
    report = audit.compare(earlier, later)
    assert report["status"] == "PASS_SAVED_URL_RECONCILIATION"
    assert report["comparison"]["same_url_in_later_save"] == 2
    assert report["comparison"]["still_missing_by_exact_url"] == 0
    assert report["comparison"]["same_original_document_id_visible"] == 0
    assert not report["comparison"]["missing_url_sha256"]


def test_missing_url_is_not_fabricated_as_recovered(tmp_path):
    earlier = make_artifact(tmp_path / "fail.zip", at="2026-11-05T23:20:06+00:00",
                            old_urls=[], new_urls=["https://example.test/missing"])
    later = make_artifact(tmp_path / "saved.zip", at="2026-11-12T00:07:49+00:00",
                          old_urls=[], new_urls=["https://example.test/different"])
    report = audit.compare(earlier, later)
    assert report["status"] == "PARTIAL_MISSING_URLS"
    assert report["comparison"]["still_missing_by_exact_url"] == 1
    assert report["comparison"]["same_url_in_later_save"] == 0
    assert report["comparison"]["missing_url_sha256"]


def test_reversed_timestamps_are_rejected(tmp_path):
    later = make_artifact(tmp_path / "later.zip", at="2026-11-12T00:07:49+00:00",
                          old_urls=[], new_urls=[])
    earlier = make_artifact(tmp_path / "earlier.zip", at="2026-11-05T23:20:06+00:00",
                            old_urls=[], new_urls=[])
    with pytest.raises(ValueError, match="REVERSED_ORDER"):
        audit.compare(later, earlier)


def test_unsafe_zip_members_and_manifest_counts_block(tmp_path):
    invalid = tmp_path / "invalid.zip"
    with zipfile.ZipFile(invalid, "w") as z:
        z.writestr("../new-document-manifest.json", "{}")
        z.writestr("rss-live-result.json", "{}")
    with pytest.raises(ValueError, match="ARTIFACT_MEMBERS"):
        audit.read_artifact(invalid)
    broken = make_artifact(tmp_path / "broken.zip", at="2026-11-12T00:07:49+00:00",
                           old_urls=["one"], new_urls=["two"])
    with zipfile.ZipFile(broken, "a") as z:
        z.writestr("unexpected.raw", "must be rejected")
    with pytest.raises(ValueError, match="ARTIFACT_MEMBERS"):
        audit.read_artifact(broken)
