"""S3 missing RSS / PARTIAL original coverage must not invent verified proofs."""
from pathlib import Path

import pytest

from tools import bct_s3_missing_partial_backfill as mod


ROOT = Path(__file__).resolve().parents[1]


def row(i, h=None):
    host = h or f"publisher{i%30}.example.org"
    return {"id": str(i), "url": f"https://{host}/report/{i}",
            "collected_at": f"2026-11-13T00:{i%60:02d}:00Z"}


def part(i, body="PARTIAL"):
    return {**row(i), "body_status": body, "body_sha256": "a" * 64,
            "scope_facts": []}


def test_missing_articles_and_partial_sources_have_separate_bounded_quotas():
    canonical = {str(i): row(i) for i in range(160)}
    sidecar = {"results": {str(i): part(i) for i in range(80)}}
    selected, audit = mod.selection(canonical, sidecar)
    assert len(selected) == 48
    assert len({d for d, _, _ in selected}) == 48
    assert audit["lane_counts"] == {"missing": 24, "partial": 24}
    assert audit["missing_eligible"] == 80
    assert audit["partial_eligible"] == 80
    assert max(audit["publisher_counts"].values()) <= 4
    assert {lane for _, lane, _ in selected} == {"missing", "partial"}


def test_explicit_attempt_hold_is_not_rerequested_without_new_version():
    canonical = {"1": row(1), "2": row(2), "3": row(3)}
    old = part(1)
    old["source_version"] = "fp1"
    old["acquisition"] = {"versions": {"fp1": {"explicit_checks": {
        "bct-scheduled-original-proof-old": {"trigger": "SCHEDULED"}}}}}
    sidecar = {"results": {"1": old, "2": part(2), "3": part(3)}}
    selected, audit = mod.selection(canonical, sidecar)
    assert "1" not in {d for d, _, _ in selected}
    assert audit["full_sidecar_body_counts"]["partial_explicit_attempt_hold"] == 1


def test_full_unavailable_body_ok_and_invalid_urls_are_not_forced():
    canonical = {str(i): row(i) for i in range(6)}
    canonical["5"]["url"] = "http://127.0.0.1/private"
    sidecar = {"results": {
        "0": part(0, "FULL"),
        "1": part(1, "UNAVAILABLE"),
        "2": part(2, "BODY_OK"),
        "3": part(3, "PARTIAL"),
        "4": part(4, "UNAVAILABLE"),
    }}
    selected, audit = mod.selection(canonical, sidecar)
    assert [d for d, _, _ in selected] == ["3"]
    assert audit["full_sidecar_body_counts"]["url_invalid_or_nonpublic"] == 1
    assert audit["full_sidecar_body_counts"]["body_UNAVAILABLE"] == 2


def test_cannot_bypass_corpus_and_host_limits():
    for limit in (0, 49, -1, True, 2.4):
        with pytest.raises(ValueError, match="S3_BATCH_OVER_LIMIT"):
            mod.selection({}, {"results": {}}, limit=limit)
    for host_cap in (0, 5, True):
        with pytest.raises(ValueError, match="S3_PUBLISHER_CAP_INVALID"):
            mod.selection({}, {"results": {}}, per_host=host_cap)


def test_preserve_verifiable_proofs_without_promoting_research_ranks():
    source = (ROOT / "tools/bct_s3_missing_partial_backfill.py").read_text()
    assert "session3_complete" in source and "False" in source
    assert '"research_rank_promotions": 0' in source
    assert 'store_patch(' in source
    assert 'transport.read_at("future-candidates.json", remote_sha)' in source
    assert 'if not current_ids <= set(remote["results"]):' in source
    assert "S3_SELECTED_DOC_NOT_READ_BACK" in source
    assert "S3_CANONICAL_DB_HASH_MISMATCH" in source
    assert "S3_SIDECAR_HAS_NONCANONICAL_ID" in source
    assert 'os.environ.get("GITHUB_REF") != BRANCH' in source
    assert '("schedule", "workflow_dispatch")' in source


def test_existing_source_proof_schedule_runs_both_lanes_after_strict_gate():
    wf = (ROOT / ".github/workflows/bct-recurring-original-reproof.yml").read_text()
    assert "group: bct-periodic-original-proof" in wf
    assert "cancel-in-progress: false" in wf
    assert "cron: '17 * * * *'" in wf
    check = wf.index("python .github/scripts/bct_release_guard.py")
    full = wf.index("python tools/bct_original_proof_backfill.py")
    partial = wf.index("python tools/bct_s3_missing_partial_backfill.py")
    assert check < full < partial
    assert "bct-s3-missing-partial/receipt.json" in wf
    assert "No S3 missing/PARTIAL receipt" in wf

def test_both_lanes_share_one_four_per_host_budget_with_prior_full_attempts():
    canonical = {str(i): row(i, "example.org") for i in range(24)}
    sidecar = {"results": {}}
    selected, audit = mod.selection(
        canonical, sidecar, prior_host_counts={"example.org": 3})
    assert len(selected) == 1
    assert audit["full_lane_publisher_counts"] == {"example.org": 3}
    assert audit["publisher_counts"] == {"example.org": 1}
    assert audit["combined_publisher_requests"] == {"example.org": 4}
    for prior in ({"example.org": 5}, {"example.org": -1},
                  {"example.org": True}, {"example.org": "3"}):
        with pytest.raises(ValueError, match="S3_INVALID_PRIOR_PUBLISHER_BUDGET"):
            mod.selection(canonical, sidecar, prior_host_counts=prior)


def test_missing_partial_stage_refuses_unproven_prior_full_lane():
    source = (ROOT / "tools/bct_s3_missing_partial_backfill.py").read_text()
    assert "S3_FULL_LANE_RECEIPT_MISSING" in source
    assert "S3_FULL_LANE_NOT_COMMITTED" in source
    assert "S3_INVALID_PRIOR_PUBLISHER_BUDGET" in source
    assert "cross_lane_publisher_budget_enforced" in source

def test_stale_partial_canonical_url_is_a_hold_not_an_old_url_recheck():
    old=part(1)
    canonical={"1":{**row(1),"url":"https://new-domain.example.org/latest"}}
    selected,audit=mod.selection(canonical,{"results":{"1":old}})
    assert selected==[]
    assert audit["full_sidecar_body_counts"]["partial_canonical_url_mismatch_hold"]==1
