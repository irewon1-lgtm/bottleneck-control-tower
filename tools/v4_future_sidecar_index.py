"""Read only the immutable Future sidecar *index*, not its private source bodies.

The counts in the manifest are screening-record inventory, never confirmed
bottleneck evidence. Legacy research-ranking rows remain source-separated.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

REPO = "irewon1-lgtm/bottleneck-control-tower"
FORMAT = "bct-future-screening-manifest-summary-v1"


def summarize(manifest, *, commit_sha, blob_sha):
    if (not isinstance(manifest, dict) or manifest.get("format") != "bct-sharded-sidecar-v1"
            or not re.fullmatch(r"[0-9a-f]{40}", str(commit_sha))
            or not re.fullmatch(r"[0-9a-f]{40}", str(blob_sha))
            or not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("document_sha256", "")))):
        raise ValueError("SIDECAR_SCREENING_MANIFEST_IDENTITY")
    counts = manifest.get("item_counts")
    if (not isinstance(counts, dict) or any(type(v) is not int or v < 0 for v in counts.values())
            or type(counts.get("results")) is not int
            or type(counts.get("hypotheses")) is not int
            or type(counts.get("events")) is not int):
        raise ValueError("SIDECAR_SCREENING_COUNTS_INVALID")
    shards = manifest.get("shards")
    if (not isinstance(shards, list) or not 1 <= len(shards) <= 150
            or type(manifest.get("total_item_count")) is not int
            or sum(counts.values()) != manifest["total_item_count"]
            or len({s.get("path") for s in shards if isinstance(s, dict)}) != len(shards)
            or any(not isinstance(s, dict) or
                   not re.fullmatch("[0-9a-f]{64}", str(s.get("sha256", ""))) or
                   not re.fullmatch("[0-9a-f]{40}", str(s.get("git_sha", ""))) or
                   type(s.get("item_count")) is not int or s["item_count"] < 1
                   for s in shards)
            or sum(s["item_count"] for s in shards) != manifest["total_item_count"]):
        raise ValueError("SIDECAR_SCREENING_SHARD_INVENTORY")
    stem = "future-candidates"
    for i, item in enumerate(shards, 1):
        expect = f"{stem}.shards/{manifest['document_sha256']}/{stem}.part-{i:03d}.json"
        if item["path"] != expect:
            raise ValueError("SIDECAR_SCREENING_PATH")
    return {
      "format": FORMAT,
      "status": "VERIFIED_INDEX_ONLY_NOT_ANALYSIS_COMPLETE",
      "sidecar_commit": commit_sha,
      "manifest_blob_sha": blob_sha,
      "sharded_document_sha256": manifest["document_sha256"],
      "registered_screening_record_slots": counts["results"],
      "unverified_hypothesis_slots": counts["hypotheses"],
      "grouped_event_slots": counts["events"],
      "shards_declared": len(shards),
      "shards_verified_in_this_read": 0,
      "qualification": "SCREENING_STORAGE_NOT_ORIGINAL_SOURCE_OR_VERIFIED_BOTTLENECK",
    }


def retrieve(repo):
    if Path(repo).resolve() != Path.cwd().resolve():
        raise ValueError("SCREENING_REPO_UNEXPECTED")
    if os.environ.get("GITHUB_REPOSITORY") != REPO or not os.environ.get("GH_TOKEN"):
        raise ValueError("SCREENING_READ_ONLY_GITHUB_CONTEXT_REQUIRED")
    def cmd(*args):
        return subprocess.run(args, check=True, capture_output=True, timeout=70).stdout
    branch_sha = cmd("git", "ls-remote", "origin", "refs/heads/future-bottleneck-data").decode().split()[0]
    if not re.fullmatch(r"[0-9a-f]{40}", branch_sha):
        raise ValueError("SCREENING_BRANCH_HEAD_INVALID")
    resp = json.loads(cmd("gh", "api", f"repos/{REPO}/contents/future-candidates.json?ref={branch_sha}"))
    if resp.get("encoding") != "base64" or type(resp.get("size")) is not int or resp["size"] > 140_000:
        raise ValueError("SCREENING_MANIFEST_SIZE_OR_ENCODING")
    raw = base64.b64decode(resp["content"], validate=False)
    if len(raw) != resp["size"]:
        raise ValueError("SCREENING_MANIFEST_BYTES")
    blob_sha = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if blob_sha != resp.get("sha"):
        raise ValueError("SCREENING_MANIFEST_GIT_SHA")
    return summarize(json.loads(raw), commit_sha=branch_sha, blob_sha=blob_sha)
