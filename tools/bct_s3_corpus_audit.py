"""Read-only, exact-ID S3 whole-corpus coverage audit after real source CAS writes.

This is NOT a source authenticity PASS for inaccessible documents. It separates
verified original publisher+date, still-eligible attempts, prior holds, partial
bodies, inaccessible bodies and RSS items without any source metadata.
No article bodies, raw URLs, credentials, or private research records are saved.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

from bct.future_body import verified_source_metadata
from bct.future_github import GitHubTransport
from tools.bct_original_proof_backfill import (
    source, already_reproof_attempted, accepted_url, host
)
from tools.bct_s3_missing_partial_backfill import status

REPO = "irewon1-lgtm/bottleneck-control-tower"
FULL_SUCCESS = {
    "PASS_SOURCE_PROOFS_SAVED_AND_RETRIEVED",
    "PASS_ATTEMPTS_SAVED_NO_VERIFIED_PROOF",
    "NO_ELIGIBLE_ORIGINAL_REPROOF_DUE"
}
PARTIAL_SUCCESS = {
    "PASS_REAL_SOURCE_BATCH_CAS_SAVED_AND_RETRIEVED",
    "NO_ELIGIBLE_MISSING_OR_PARTIAL"
}


def audit_snapshot(canonical, candidates):
    """Audit every active ID exactly once; never turn an evidence hold into PASS."""
    results = candidates.get("results", {})
    if not isinstance(canonical, dict) or not isinstance(results, dict):
        raise ValueError("S3_CORPUS_SCHEMA_INVALID")
    active = set(canonical)
    linked = set(results)
    if linked - active:
        raise ValueError("S3_CORPUS_HAS_UNMATCHED_SIDECAR_ID")
    if any(not isinstance(v, dict) for v in results.values()):
        raise ValueError("S3_CORPUS_RECORD_NOT_OBJECT")
    by_status = Counter()
    decisions = Counter()
    eligible_hosts = set()
    blocked_by_status = Counter()
    for docid in active:
        original = canonical[docid]
        if not isinstance(original, dict) or not original.get("url"):
            raise ValueError("S3_CANONICAL_SOURCE_URL_NOT_PRESENT")
        rec = results.get(docid)
        if rec is None:
            decisions["rss_not_in_sidecar"] += 1
            if accepted_url(original["url"]):
                decisions["rss_missing_url_syntactically_eligible"] += 1
            else:
                decisions["rss_missing_invalid_url_hold"] += 1
            continue
        state = status(rec)
        by_status[str(state)] += 1
        if original["url"] != rec.get("url"):
            decisions["canonical_url_mismatch_needs_review"] += 1
        if state == "FULL":
            digest = rec.get("current_body_sha256") or rec.get("body_sha256")
            if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
                decisions["full_bad_or_missing_hash_hold"] += 1
                continue
            ver = (rec.get("versions") or {}).get(digest, {})
            p1 = verified_source_metadata(rec, digest)
            p2 = verified_source_metadata({**rec, **ver}, digest)
            proven = ((p1.get("provenance_verified") is True and p1.get("publication_verified") is True)
                      or (p2.get("provenance_verified") is True and p2.get("publication_verified") is True))
            if proven:
                decisions["full_publisher_and_date_verified"] += 1
            else:
                decisions["full_publisher_or_date_unverified"] += 1
                if not source(rec):
                    decisions["full_proof_state_inconsistent_hold"] += 1
                elif not accepted_url(rec.get("url")):
                    decisions["full_invalid_url_hold"] += 1
                elif already_reproof_attempted(rec):
                    decisions["full_explicit_attempt_hold"] += 1
                else:
                    decisions["full_original_reproof_eligible"] += 1
                    eligible_hosts.add(host(rec["url"]))
        elif state == "PARTIAL":
            decisions["partial_unverified_completeness"] += 1
            if not accepted_url(rec.get("url")):
                decisions["partial_invalid_url_hold"] += 1
            elif already_reproof_attempted(rec):
                decisions["partial_explicit_attempt_hold"] += 1
            else:
                decisions["partial_original_recovery_eligible"] += 1
                eligible_hosts.add(host(rec["url"]))
        elif state == "UNAVAILABLE":
            decisions["unavailable_no_full_content_hold"] += 1
            attempts = rec.get("attempts")
            if type(attempts) is int and attempts >= 3:
                blocked_by_status["auto_attempt_limit_at_least_3"] += 1
            elif type(attempts) is int and 0 <= attempts < 3:
                blocked_by_status["auto_attempts_below_3"] += 1
            else:
                blocked_by_status["auto_attempts_unknown"] += 1
            if already_reproof_attempted(rec):
                blocked_by_status["explicit_source_attempt_recorded"] += 1
            if not accepted_url(rec.get("url")):
                blocked_by_status["invalid_or_nonpublic_url"] += 1
        elif state == "BODY_OK":
            decisions["legacy_body_ok_completeness_unverified"] += 1
        else:
            decisions["unknown_body_status_hold"] += 1
    if sum(by_status.values()) != len(results):
        raise ValueError("S3_SOURCE_COVERAGE_ACCOUNTING_MISMATCH")
    if decisions["rss_not_in_sidecar"] + len(results) != len(canonical):
        raise ValueError("S3_RSS_LINKAGE_ACCOUNTING_MISMATCH")
    if (decisions["full_publisher_and_date_verified"]
            + decisions["full_publisher_or_date_unverified"]
            + decisions["full_bad_or_missing_hash_hold"] != by_status["FULL"]):
        raise ValueError("S3_FULL_PROOF_ACCOUNTING_MISMATCH")
    return {
        "rss_active": len(active),
        "sidecar_linked": len(results),
        "rss_unlinked": len(active - linked),
        "body_status_counts": dict(by_status),
        "proof_and_eligibility_counts": dict(decisions),
        "unavailable_attempt_and_hold_counts": dict(blocked_by_status),
        "eligible_publisher_count": len(eligible_hosts),
        "active_id_set_sha256": hashlib.sha256("|".join(sorted(active)).encode()).hexdigest(),
        "linked_id_set_sha256": hashlib.sha256("|".join(sorted(linked)).encode()).hexdigest(),
        "count_consistency_pass": True,
        "verified_full_originals_only": decisions["full_publisher_and_date_verified"],
        "verified_shortages_created": 0,
        "readable_full_does_not_imply_verified_original": True,
        "unavailable_does_not_imply_not_a_bottleneck": True,
        "session3_complete": False,
    }


def cmd(*args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True, timeout=180).stdout


def stage():
    if (os.environ.get("GITHUB_REPOSITORY") != REPO
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") not in ("schedule", "workflow_dispatch")):
        raise ValueError("S3_CORPUS_AUDIT_MAIN_ONLY")
    root = Path(os.environ["RUNNER_TEMP"])
    report_root = root / "bct-s3-corpus-audit"
    report_root.mkdir(parents=True, exist_ok=True)
    full_path = root / "bct-owner-reproof" / "receipt.json"
    gap_path = root / "bct-s3-missing-partial" / "receipt.json"
    if not full_path.is_file() or not gap_path.is_file():
        raise ValueError("S3_CORPUS_MISSING_SOURCE_LANE_RECEIPTS")
    full = json.loads(full_path.read_text())
    gap = json.loads(gap_path.read_text())
    if full.get("status") not in FULL_SUCCESS or gap.get("status") not in PARTIAL_SUCCESS:
        raise ValueError("S3_CORPUS_SOURCE_LANE_NOT_ACTUALLY_SAVED")
    data_sha = cmd("git", "ls-remote", "origin", "refs/heads/data").decode().split()[0]
    if (not re.fullmatch(r"[0-9a-f]{40}", data_sha)
            or any(not re.fullmatch(r"[0-9a-f]{40}", str(ref or ""))
                   for ref in (full.get("collection_sha"), gap.get("canonical_data_sha")))):
        raise ValueError("S3_CORPUS_RSS_GENERATION_NOT_ATTESTABLE")
    # Audit the LATEST canonical RSS generation even if a new RSS ingest
    # arrived during FULL or PARTIAL processing; never mark new IDs complete.
    cmd("git", "fetch", "--no-tags", "--depth=1", "origin", data_sha)
    state = json.loads(cmd("git", "show", data_sha + ":state.json"))
    db_path = report_root / "canonical.sqlite3"
    db_path.write_bytes(cmd("git", "show", data_sha + ":canonical.sqlite3"))
    if hashlib.sha256(db_path.read_bytes()).hexdigest() != state["sha256"]:
        raise ValueError("S3_CORPUS_CANONICAL_DB_SHA_MISMATCH")
    with sqlite3.connect(f"file:{db_path.resolve()}?mode=ro&immutable=1", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("S3_CORPUS_BAD_CANONICAL_DB")
        db.row_factory = sqlite3.Row
        canonical = {row["id"]: dict(row)
                     for row in db.execute("SELECT id,url FROM radar_items WHERE status='active'")}
    if len(canonical) != state["radar_items"]:
        raise ValueError("S3_CORPUS_ACTIVE_UNIQUE_IDS_MISMATCH")
    transport = GitHubTransport(REPO, "future-bottleneck-data",
                                os.environ["GITHUB_TOKEN"])
    generation_sha = transport.head()
    candidates = transport.read_at("future-candidates.json", generation_sha).document
    outcome = audit_snapshot(canonical, candidates)
    result = {
        "format": "bct-s3-corpus-coverage-and-provenance-v1",
        "status": "PASS_EXACT_FULL_CORPUS_AUDIT_NOT_S3_FINAL_PASS",
        "audited_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_rss_sha": data_sha,
        "full_lane_rss_sha": full["collection_sha"],
        "gap_lane_rss_sha": gap["canonical_data_sha"],
        "source_lanes_used_same_rss_generation": full["collection_sha"] == gap["canonical_data_sha"],
        "rss_advanced_since_any_source_lane": (
            full["collection_sha"] != data_sha or gap["canonical_data_sha"] != data_sha),
        "sidecar_generation_sha": generation_sha,
        "full_lane_status": full["status"],
        "partial_lane_status": gap["status"],
        "full_lane_source_attempts": full.get("source_downloads_attempted", 0),
        "full_lane_saved_original_proofs": full.get("source_proofs_persisted", 0),
        "gap_lane_source_attempts": gap.get("processed_source_reads", 0),
        "gap_lane_new_linked_ids": gap.get("new_linked_ids_read_back", 0),
        "no_full_article_text_in_receipt": True,
        "no_private_cpu_data_in_receipt": True,
        "no_research_rank_promotions": True,
        **outcome,
    }
    path = report_root / "receipt.json"
    path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print("BCT_S3_FULL_CORPUS_AUDIT=" + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    stage()
