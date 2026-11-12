"""Read-only public verification of latest new-article original-source intake.

The existing PUBLIC data index is durable even when a manual acquisition run
is ineligible for the pinned Pages automatic-receipt consumer. Verify the exact
source run and public artifact; do not mutate its immutable producer receipt,
the data branch, the forecast ranking or any private source document.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import tempfile

from bct.v4.public_data import validate_acquisition
from v4_public_news_export import _cmd

REPOSITORY = "irewon1-lgtm/bottleneck-control-tower"
FORMAT = "bct-public-verified-source-status-1"


def verify_receipt(index, run, snapshot_raw, artifact_manifest, *, data_commit, rss_run_id):
    if (not isinstance(index, dict)
            or index.get("format") != "bct-new-precursor-collection-v1"):
        raise ValueError("SOURCE_STATUS_INDEX_FORMAT")
    rid = index.get("cache_run_id")
    attempt = index.get("cache_run_attempt")
    if (not isinstance(rid, str) or not re.fullmatch(r"[1-9]\d{4,15}", rid)
            or type(attempt) is not int or attempt < 1):
        raise ValueError("SOURCE_STATUS_INDEX_RUN")
    if not re.fullmatch(r"[a-f0-9]{40}", str(data_commit)):
        raise ValueError("SOURCE_STATUS_PUBLIC_DATA_COMMIT")
    if (not isinstance(run, dict)
            or run.get("id") != int(rid) or run.get("run_attempt") != attempt
            or run.get("path") != ".github/workflows/precursor-acquisition.yml"
            or run.get("name") != "New precursor evidence acquisition"
            or run.get("status") != "completed" or run.get("conclusion") != "success"
            or run.get("head_branch") != "main"
            or run.get("event") not in ("workflow_dispatch", "workflow_run")
            or run.get("head_repository", {}).get("full_name") != REPOSITORY):
        raise ValueError("SOURCE_STATUS_INVALID_PRODUCER")
    if not isinstance(snapshot_raw, bytes) or len(snapshot_raw) > 128_000 or not snapshot_raw:
        raise ValueError("SOURCE_STATUS_SNAPSHOT_SIZE")
    if not isinstance(artifact_manifest, dict) or artifact_manifest != {
        "format": "bct-public-acquisition-manifest-1",
        "file": "snapshot.json",
        "bytes": len(snapshot_raw),
        "sha256": hashlib.sha256(snapshot_raw).hexdigest(),
    }:
        raise ValueError("SOURCE_STATUS_ARTIFACT_HASH_MISMATCH")
    receipt = validate_acquisition(json.loads(snapshot_raw))
    if (receipt["run_id"] != int(rid) or receipt["run_attempt"] != attempt
            or receipt["head_sha"] != run.get("head_sha")
            or receipt["completed_at"] != index.get("completed_at")
            or receipt["scope_reader_version"] != index.get("scope_reader_version")
            or receipt["source_integrity_state"] != index.get("source_integrity_state")
            or receipt["unverified_source_holds"] != index.get("unverified_source_holds")
            or receipt["counts"]["new_seed_attempts"] != index.get("new_seed_attempts")
            or receipt["counts"]["new_verified_documents"] != index.get("new_verified_documents")
            or receipt["counts"]["new_seed_statuses"] != index.get("new_seed_statuses")
            or receipt["counts"]["additional_bodies_acquired"] != index.get("additional_bodies_acquired")
            or receipt["counts"]["valid_additional_primary_documents"] != index.get("valid_additional_primary_documents")):
        raise ValueError("SOURCE_STATUS_INDEX_ARTIFACT_MISMATCH")
    if type(rss_run_id) is not int or rss_run_id <= 0:
        raise ValueError("SOURCE_STATUS_RSS_RUN_ID")
    counts = receipt["counts"]
    statuses = counts["new_seed_statuses"] or {}
    if sum(statuses.values()) != counts["new_seed_attempts"]:
        raise ValueError("SOURCE_STATUS_OUTCOME_SUM")
    captured = statuses.get("CAPTURED", 0)
    if captured != counts["new_verified_documents"]:
        raise ValueError("SOURCE_STATUS_CAPTURE_COUNT")
    processed = counts["new_seed_attempts"]
    held = processed - captured
    # Pending queue items from previous RSS runs may also be processed here;
    # new_URLs is the current manifest size, not the number of attempted queue items.
    if (held < 0 or receipt["RSS_run_id"] > rss_run_id):
        raise ValueError("SOURCE_STATUS_TIME_ORDER")
    return {
        "format": FORMAT,
        "status": "VERIFIED_PUBLIC_SOURCE_INTAKE",
        "data_commit": data_commit,
        "source_run_id": receipt["run_id"],
        "source_run_attempt": receipt["run_attempt"],
        "source_event": run["event"],
        "rss_run_id": receipt["RSS_run_id"],
        "matches_current_rss": receipt["RSS_run_id"] == rss_run_id,
        "completed_at": receipt["completed_at"],
        "source_integrity_state": receipt["source_integrity_state"],
        "source_holds": receipt["unverified_source_holds"],
        "seed_attempts": processed,
        "captured": captured,
        "held": held,
        "statuses": statuses,
        "additional_bodies_acquired": counts["additional_bodies_acquired"],
        "valid_additional_primary_documents": counts["valid_additional_primary_documents"],
        "classification": "CAPTURED_SOURCE_DOCUMENTS_NOT_VERIFIED_BOTTLENECKS",
        "source_artifact_sha256": hashlib.sha256(snapshot_raw).hexdigest(),
    }


def from_data_snapshot(repo, data_commit, rss_run_id):
    """Read the SAME canonical data commit already verified for RSS by exporter."""
    repo = Path(repo).resolve()
    try:
        raw_index = _cmd(["git", "show", data_commit + ":precursor-index.json"], cwd=repo)
    except Exception as error:
        # Older public data trees may legitimately predate the pipeline.
        raise ValueError("SOURCE_STATUS_INDEX_UNAVAILABLE") from error
    if len(raw_index) > 65_536:
        raise ValueError("SOURCE_STATUS_INDEX_SIZE")
    index = json.loads(raw_index)
    rid = str(index.get("cache_run_id", ""))
    attempt = index.get("cache_run_attempt")
    if not re.fullmatch(r"[1-9]\d{4,15}", rid) or type(attempt) is not int or attempt <= 0:
        raise ValueError("SOURCE_STATUS_BAD_RUN_REF")
    run = json.loads(_cmd(["gh", "api", f"repos/{REPOSITORY}/actions/runs/{rid}"], cwd=repo,
                          timeout=30))
    with tempfile.TemporaryDirectory(prefix="bct-source-intake-readonly-") as scratch:
        _cmd(["gh", "run", "download", rid, "--repo", REPOSITORY,
              "--name", f"bct-public-acquisition-{attempt}", "--dir", scratch],
              cwd=repo, timeout=110)
        names = {p.name for p in Path(scratch).rglob("*") if p.is_file()}
        if names != {"snapshot.json", "manifest.json"}:
            raise ValueError("SOURCE_STATUS_ARTIFACT_FILE_SET")
        snapshots = list(Path(scratch).rglob("snapshot.json"))
        manifests = list(Path(scratch).rglob("manifest.json"))
        if len(snapshots) != 1 or len(manifests) != 1:
            raise ValueError("SOURCE_STATUS_ARTIFACT_AMBIGUOUS")
        if manifests[0].stat().st_size > 4096:
            raise ValueError("SOURCE_STATUS_MANIFEST_SIZE")
        return verify_receipt(index, run, snapshots[0].read_bytes(),
                              json.loads(manifests[0].read_text(encoding="utf-8")),
                              data_commit=data_commit, rss_run_id=rss_run_id)
