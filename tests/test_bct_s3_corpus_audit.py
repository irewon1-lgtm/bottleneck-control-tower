"""Immutable, whole-RSS S3 audit distinguishes metadata presence from proof."""
from pathlib import Path
import pytest
from tools import bct_s3_corpus_audit as mod


def rec(i, body="FULL", *, proof=False, attempted=False, attempts=None):
    url = f"https://publisher.example.com/article/{i}"
    d = {"id": str(i), "url": url,
         "body_status": body, "body_sha256": "a" * 64,
         "current_body_sha256": "a" * 64, "source_version": f"v{i}",
         "versions": {"a" * 64: {"body_status": body}}}
    if proof:
        d.update(origin_id="publisher", origin_url=url,
                 origin_publisher="Publisher",
                 provenance_verified=True,
                 provenance_evidence={"body_sha256": "a" * 64,
                     "verified_source_url": url, "source_identity": "original"},
                 published_at="2026-11-14", publication_precision="DATE",
                 publication_verified=True,
                 publication_evidence={"body_sha256": "a" * 64,
                                       "source_quote": "November 14 2026"})
    if attempted:
        d["acquisition"] = {"versions": {f"v{i}": {
            "explicit_checks": {"bct-scheduled-original-proof-123": {"trigger": "SCHEDULED"}}}}}
    if attempts is not None:
        d["attempts"] = attempts
    return d


def test_every_rss_id_is_reconciled_and_full_proof_is_body_hash_bound():
    canonical = {str(i): {"url": f"https://publisher.example.com/article/{i}"}
                 for i in range(6)}
    sidecar = {"results": {
        "0": rec(0, proof=True),
        "1": rec(1),
        "2": rec(2, attempted=True),
        "3": rec(3, body="PARTIAL"),
        "4": rec(4, body="UNAVAILABLE", attempts=3),
    }}
    v = mod.audit_snapshot(canonical, sidecar)
    assert v["rss_active"] == 6
    assert v["sidecar_linked"] == 5
    assert v["rss_unlinked"] == 1
    assert v["body_status_counts"] == {"FULL": 3, "PARTIAL": 1, "UNAVAILABLE": 1}
    p = v["proof_and_eligibility_counts"]
    assert p["full_publisher_and_date_verified"] == 1
    assert p["full_publisher_or_date_unverified"] == 2
    assert p["full_original_reproof_eligible"] == 1
    assert p["full_explicit_attempt_hold"] == 1
    assert p["partial_original_recovery_eligible"] == 1
    assert p["rss_not_in_sidecar"] == 1
    assert v["unavailable_attempt_and_hold_counts"]["auto_attempt_limit_at_least_3"] == 1
    assert v["count_consistency_pass"] is True
    assert v["session3_complete"] is False
    assert v["verified_shortages_created"] == 0


def test_unverified_and_changed_body_must_not_be_promoted_as_original():
    original = rec(1, proof=True)
    original["body_sha256"] = "b" * 64
    original["current_body_sha256"] = "b" * 64
    original["versions"] = {"b" * 64: {"body_status": "FULL"}}
    canonical = {"1": {"url": original["url"]}}
    audit = mod.audit_snapshot(canonical, {"results": {"1": original}})
    assert audit["proof_and_eligibility_counts"]["full_publisher_and_date_verified"] == 0
    assert audit["proof_and_eligibility_counts"]["full_original_reproof_eligible"] == 1


def test_noncanonical_sidecar_id_is_fatal_even_if_corpus_is_large():
    canonical = {"1": {"url": "https://example.org/1"}}
    with pytest.raises(ValueError, match="UNMATCHED_SIDECAR"):
        mod.audit_snapshot(canonical, {"results": {"2": rec(2)}})


def test_invalid_missing_and_partial_urls_are_explicit_holds():
    canonical = {"1": {"url": "http://127.0.0.1/private"},
                 "2": {"url": "https://valid.example.org/partial"}}
    partial = rec(2, body="PARTIAL")
    partial["url"] = canonical["2"]["url"]
    partial["source_version"] = "p"
    partial["acquisition"] = {"versions": {"p": {
        "history": [{"trigger_id": "bct-scheduled-original-proof-999"}]}}}
    x = mod.audit_snapshot(canonical, {"results": {"2": partial}})
    v = x["proof_and_eligibility_counts"]
    assert v["rss_missing_invalid_url_hold"] == 1
    assert v["partial_explicit_attempt_hold"] == 1
    assert "http://127.0.0.1" not in str(x)
    assert "valid.example.org" not in str(x)
    assert x["session3_complete"] is False


def test_invalid_body_hash_is_held_not_inferred_from_full_label():
    x = rec(1)
    x["current_body_sha256"] = "not-sha"
    x["body_sha256"] = "not-sha"
    result = mod.audit_snapshot({"1": {"url": x["url"]}},
                                {"results": {"1": x}})
    v = result["proof_and_eligibility_counts"]
    assert v["full_bad_or_missing_hash_hold"] == 1
    assert v["full_publisher_and_date_verified"] == 0


def test_corpus_audit_is_source_free_and_after_both_successful_writers():
    root = Path(__file__).resolve().parents[1]
    wf = (root / ".github/workflows/bct-recurring-original-reproof.yml").read_text()
    audit = (root / "tools/bct_s3_corpus_audit.py").read_text()
    assert "python tools/bct_s3_corpus_audit.py" in wf
    assert wf.index("python tools/bct_original_proof_backfill.py") < wf.index(
        "python tools/bct_s3_missing_partial_backfill.py") < wf.index(
        "python tools/bct_s3_corpus_audit.py")
    assert "S3_CORPUS_SOURCE_LANE_NOT_ACTUALLY_SAVED" in audit
    assert "transport.read_at(" in audit
    assert "private CPU" not in audit  # Never read private CPU state
    assert "PASS_EXACT_FULL_CORPUS_AUDIT_NOT_S3_FINAL_PASS" in audit
