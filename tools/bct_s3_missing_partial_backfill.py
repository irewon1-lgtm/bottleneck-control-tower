"""BCT S3 independent missing-sidecar and PARTIAL-body original-source recovery.

A scheduled main-only bounded real batch. Exact canonical active RSS IDs, immutable
sidecar head, per-host caps, operation-specific CAS patch, and fresh
remote readback prove each attempted source without promoting shortages.
No raw article text or extracted bodies are published.
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
from bct.future_bottleneck import run
from bct.future_github import GitHubTransport
from bct.future_store import store_patch
from tools.bct_original_proof_backfill import (
    accepted_url, already_reproof_attempted, host, qualified_fact
)

REPO = "irewon1-lgtm/bottleneck-control-tower"
BRANCH = "refs/heads/main"
LIMIT = 24
LANE_LIMIT = 12
PER_HOST = 3


def cmd(*args, timeout=180):
    p = subprocess.run(args, check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=timeout)
    return p.stdout


def status(record):
    digest = record.get("current_body_sha256") or record.get("body_sha256")
    version = (record.get("versions") or {}).get(digest, {}) if digest else {}
    return version.get("body_status") or record.get("body_status") or "UNKNOWN"


def selection(canonical, sidecar, *, limit=LIMIT, lane_limit=LANE_LIMIT,
              per_host=PER_HOST):
    if type(limit) is not int or not 1 <= limit <= 24:
        raise ValueError("S3_BATCH_OVER_LIMIT")
    if type(lane_limit) is not int or not 1 <= lane_limit <= limit:
        raise ValueError("S3_LANE_LIMIT_INVALID")
    if type(per_host) is not int or not 1 <= per_host <= 4:
        raise ValueError("S3_PUBLISHER_CAP_INVALID")
    records = sidecar.get("results", {})
    missing = []
    partial = []
    holds = Counter()
    for docid, source in canonical.items():
        current = records.get(docid)
        url = source["url"]
        if not accepted_url(url):
            holds["url_invalid_or_nonpublic"] += 1
            continue
        h = host(url)
        # Missing article metadata is not a previously examined article.
        if current is None:
            missing.append((str(source.get("collected_at") or ""), docid, h))
            continue
        body_status = status(current)
        holds["body_" + str(body_status)] += 1
        if body_status != "PARTIAL":
            continue
        if already_reproof_attempted(current):
            holds["partial_explicit_attempt_hold"] += 1
            continue
        partial.append((not qualified_fact(current),
                        str(source.get("collected_at") or ""), docid, h))
    missing.sort()
    partial.sort()
    selected = []
    used = Counter()
    chosen_lane = Counter()
    for lane, candidates, cap in (
            ("missing", missing, lane_limit),
            ("partial", partial, lane_limit)):
        for record in candidates:
            docid, h = record[-2:]
            if used[h] >= per_host or chosen_lane[lane] >= cap:
                continue
            selected.append((docid, lane, h))
            used[h] += 1
            chosen_lane[lane] += 1
    # If either lane has fewer eligible articles, fill its unused capacity
    # from the other lane without lifting per-publisher limits.
    if len(selected) < limit:
        for lane, candidates in (("missing", missing), ("partial", partial)):
            for record in candidates:
                docid, h = record[-2:]
                if len(selected) >= limit:
                    break
                if used[h] >= per_host or any(docid == z[0] for z in selected):
                    continue
                selected.append((docid, lane, h))
                chosen_lane[lane] += 1
                used[h] += 1
    assert len(selected) <= limit
    if len({item[0] for item in selected}) != len(selected):
        raise ValueError("S3_DUPLICATE_ARTICLE")
    return selected, {
        "missing_eligible": len(missing),
        "partial_eligible": len(partial),
        "publisher_counts": dict(used),
        "lane_counts": dict(chosen_lane),
        "full_sidecar_body_counts": dict(holds)
    }


def self_test():
    def rec(i, h):
        return {"id": str(i), "url": f"https://{h}/article/{i}",
                "collected_at": f"2026-11-13T00:{i%60:02d}:00Z"}
    data = {str(i): rec(i, f"source{i%8}.example.org") for i in range(40)}
    sidecar = {"results": {str(i): {
        **data[str(i)], "body_status": "PARTIAL",
        "body_sha256": "a" * 64,
        "scope_facts": []
    } for i in range(20)}}
    chosen, info = selection(data, sidecar)
    assert len(chosen) == 24 and len(set(z[0] for z in chosen)) == 24
    assert info["lane_counts"]["missing"] == 12
    assert info["lane_counts"]["partial"] == 12
    assert max(info["publisher_counts"].values()) <= 3
    x = sidecar["results"]["0"]
    x["source_version"] = "fp0"
    x["acquisition"] = {"versions": {"fp0": {"explicit_checks": {
        "bct-scheduled-original-proof-test": {"trigger": "SCHEDULED"}}}}}
    chosen2, info2 = selection(data, sidecar)
    assert "0" not in [z[0] for z in chosen2]
    assert info2["full_sidecar_body_counts"]["partial_explicit_attempt_hold"] == 1
    for bad in (0, 25, True):
        try:
            selection(data, sidecar, limit=bad)
        except ValueError:
            pass
        else:
            raise AssertionError("S3_BOUND_NOT_ENFORCED")
    print("BCT_S3_MISSING_PARTIAL_SELECTOR_SELFTEST_PASS=1", flush=True)


def stage():
    if (os.environ.get("GITHUB_REPOSITORY") != REPO or
            os.environ.get("GITHUB_REF") != BRANCH or
            os.environ.get("GITHUB_EVENT_NAME") not in ("schedule", "workflow_dispatch")):
        raise ValueError("S3_MAIN_SCHEDULED_OR_MANUAL_ONLY")
    actual_main = cmd("git", "ls-remote", "origin", "refs/heads/main").decode().split()[0]
    # A receipt-only release advance is allowed: the enclosing workflow has
    # already checked the strict current-code release guard.
    if not re.fullmatch(r"[0-9a-f]{40}", actual_main):
        raise ValueError("S3_CURRENT_MAIN_SHA_MISSING")
    root = Path(os.environ["RUNNER_TEMP"]) / "bct-s3-missing-partial"
    root.mkdir(parents=True, exist_ok=True)
    receipt = root / "receipt.json"
    report = {"format": "bct-s3-missing-partial-real-cas-v1",
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "INPUT_AUDIT_NOT_SAVED",
              "session3_complete": False,
              "private_source_bodies_published": False,
              "data_branch_writes": 0,
              "research_rank_promotions": 0,
              "requested_batch_cap": LIMIT,
              "per_host_cap": PER_HOST,
              "main_reviewed_sha": os.environ.get("GITHUB_SHA"),
              "current_main_sha": actual_main}
    def save():
        receipt.write_text(json.dumps(report, ensure_ascii=False,
                                      sort_keys=True, indent=2) + "\n")
    save()
    transport = GitHubTransport(REPO, "future-bottleneck-data",
                                os.environ["GITHUB_TOKEN"])
    original_sha = transport.head()
    candidates = transport.read_at("future-candidates.json", original_sha).document
    tracking = transport.read_at("future-tracking.json", original_sha).document
    data_sha = cmd("git", "ls-remote", "origin", "refs/heads/data").decode().split()[0]
    if not re.fullmatch(r"[0-9a-f]{40}", data_sha):
        raise ValueError("S3_RSS_BRANCH_SHA_NOT_VERIFIED")
    cmd("git", "fetch", "--no-tags", "--depth=1", "origin", data_sha, timeout=160)
    state = json.loads(cmd("git", "show", data_sha + ":state.json"))
    db_path = root / "canonical.sqlite3"
    db_path.write_bytes(cmd("git", "show", data_sha + ":canonical.sqlite3", timeout=160))
    if hashlib.sha256(db_path.read_bytes()).hexdigest() != state["sha256"]:
        raise ValueError("S3_CANONICAL_DB_HASH_MISMATCH")
    with sqlite3.connect(f"file:{db_path.resolve()}?mode=ro&immutable=1", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("S3_CANONICAL_SQLITE_INVALID")
        db.row_factory = sqlite3.Row
        sources = {row["id"]: dict(row) for row in db.execute(
            "SELECT id,url,collected_at FROM radar_items WHERE status='active'")}
    if len(sources) != state["radar_items"]:
        raise ValueError("S3_CANONICAL_ACTIVE_IDS_MISMATCH")
    current_ids = set(candidates["results"])
    if current_ids - set(sources):
        raise ValueError("S3_SIDECAR_HAS_NONCANONICAL_ID")
    if len(current_ids) < 10500:
        raise ValueError("S3_SIDECAR_REGRESSION")
    selected, categories = selection(sources, candidates)
    source_groups = Counter(status(c) for c in candidates["results"].values())
    report.update({
        "rss": len(sources), "sidecar_before": len(current_ids),
        "missing_before": len(set(sources) - current_ids),
        "source_status_before": dict(source_groups),
        "selection": categories,
        "source_before_sha": original_sha,
        "canonical_data_sha": data_sha,
        "selected": len(selected),
        "selected_article_ids_sha256": hashlib.sha256(
            "|".join(sorted(z[0] for z in selected)).encode()).hexdigest(),
        "status": "SELECTION_RECONCILED_NOT_PROCESSED"})
    save()
    print("BCT_S3_RECONCILIATION_INPUT=" + json.dumps(report, sort_keys=True), flush=True)
    if not selected:
        report["status"] = "NO_ELIGIBLE_MISSING_OR_PARTIAL"
        save()
        return
    c = root / "future-candidates.json"
    t = root / "future-tracking.json"
    c.write_text(json.dumps(candidates, ensure_ascii=False))
    t.write_text(json.dumps(tracking, ensure_ascii=False))
    patch = root / "patch.json"
    requested = {z[0] for z in selected}
    outcome = run(db_path, c, limit=len(requested), workers=4,
                  tracking_path=t, cache_dir=root/"private-source-body",
                  document_ids=requested, trigger="SCHEDULED",
                  trigger_id="bct-scheduled-original-proof-s3-triage-"+os.environ["GITHUB_RUN_ID"],
                  patch_output=patch)
    changed = json.loads(patch.read_text())
    modified = changed["patch"]["results"]
    if set(modified) != requested or outcome["summary"]["processed_this_run"] != len(requested):
        raise ValueError("S3_ACTUAL_PROCESSOR_OR_PATCH_IDS_MISMATCH")
    after_classification = Counter()
    for docid,item in modified.items():
        proof = verified_source_metadata(item, item.get("current_body_sha256") or item.get("body_sha256"))
        after_classification["body_"+str(status(item))] += 1
        if proof.get("provenance_verified") is True and proof.get("publication_verified") is True:
            after_classification["proof_origin_and_publication"] += 1
        else:
            after_classification["proof_hold"] += 1
    report.update(status="SOURCES_PROCESSED_AWAITING_CAS",
                  requested_source_reads=len(requested),
                  processed_source_reads=outcome["summary"]["processed_this_run"],
                  processor_outcomes=dict(after_classification))
    save()
    committed = store_patch(
        transport, "future-candidates.json", owner=changed["owner"],
        patch=changed["patch"], operation_id=changed["operation_id"],
        prepared_document=changed["prepared_document"])
    if committed.status not in ("APPLIED", "ALREADY_APPLIED"):
        report.update(status="CAS_SAVE_FAILED", reason=committed.reason)
        save()
        raise ValueError("S3_REMOTE_SAVE_NOT_CONFIRMED")
    remote_sha = transport.last_commit or transport.head()
    remote = transport.read_at("future-candidates.json", remote_sha).document
    if not current_ids <= set(remote["results"]):
        raise ValueError("S3_LOST_OLD_SIDECAR_IDS")
    for docid in requested:
        if docid not in remote["results"]:
            raise ValueError("S3_SELECTED_DOC_NOT_READ_BACK")
    persisted_outcomes = Counter()
    for docid,lane,host_name in selected:
        item = remote["results"][docid]
        digest = item.get("current_body_sha256") or item.get("body_sha256")
        proof = verified_source_metadata(item, digest) if digest else {}
        persisted_outcomes["body_"+str(status(item))] += 1
        persisted_outcomes["lane_"+lane] += 1
        if proof.get("provenance_verified") is True and proof.get("publication_verified") is True:
            persisted_outcomes["publisher_and_date_verified"] += 1
        else:
            persisted_outcomes["publisher_or_date_unverified"] += 1
    report.update(status="PASS_REAL_SOURCE_BATCH_CAS_SAVED_AND_RETRIEVED",
                  source_after_sha=remote_sha,
                  sidecar_after=len(remote["results"]),
                  new_linked_ids_read_back=sum(z[1] == "missing" and z[0] in remote["results"] for z in selected),
                  missing_after=len(set(sources)-set(remote["results"])),
                  persisted_outcomes=dict(persisted_outcomes),
                  ended_at_utc=datetime.now(timezone.utc).isoformat())
    save()
    print("BCT_S3_RECONCILIATION_PERSISTED=" + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    if os.environ.get("BCT_S3_SELF_TEST_ONLY") == "1":
        self_test()
    else:
        stage()
