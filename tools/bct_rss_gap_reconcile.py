#!/usr/bin/env python3
"""Reconcile historical RSS artifact manifests without any network or DB writes.

This audits URLs captured during a failed RSS publication against the later
canonical URL list carried in a verified successful RSS manifest. It does not
claim source coverage, full-body availability, or CPU analysis completion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

MAX_ZIP = 12 * 1024 * 1024
MAX_MANIFEST = 6 * 1024 * 1024
WANTED = {"new-document-manifest.json", "rss-live-result.json"}


def read_artifact(path: Path):
    raw = path.read_bytes()
    if not 100 <= len(raw) <= MAX_ZIP:
        raise ValueError("RSS_AUDIT_ZIP_SIZE")
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != 2 or set(names) != WANTED:
                raise ValueError("RSS_AUDIT_ARTIFACT_MEMBERS")
            for info in archive.infolist():
                if info.is_dir() or info.file_size > MAX_MANIFEST:
                    raise ValueError("RSS_AUDIT_MEMBER_SIZE")
            manifest = json.loads(archive.read("new-document-manifest.json"))
            summary = json.loads(archive.read("rss-live-result.json"))
    except zipfile.BadZipFile as exc:
        raise ValueError("RSS_AUDIT_BAD_ZIP") from exc
    if (manifest.get("format") != "bct-new-rss-delta-v1"
            or type(manifest.get("documents")) is not list
            or type(manifest.get("preexisting_urls")) is not list
            or type(manifest.get("preexisting_document_ids")) is not list
            or summary.get("new_articles") != len(manifest["documents"])):
        raise ValueError("RSS_AUDIT_MANIFEST_CONTRACT")
    if (type(summary.get("initial_articles")) is not int
            or len(manifest["preexisting_urls"]) != summary["initial_articles"]
            or len(manifest["preexisting_document_ids"]) != summary["initial_articles"]):
        raise ValueError("RSS_AUDIT_BASELINE_COUNT")
    if (not all(isinstance(row, dict) and isinstance(row.get("url"), str)
                and isinstance(row.get("document_id"), (str, int)) for row in manifest["documents"])
            or not all(isinstance(url, str) for url in manifest["preexisting_urls"])):
        raise ValueError("RSS_AUDIT_DOCUMENT_SCHEMA")
    return manifest, summary, hashlib.sha256(raw).hexdigest()


def compare(before: Path, after: Path):
    old, old_summary, old_zip_sha = read_artifact(before)
    recent, recent_summary, recent_zip_sha = read_artifact(after)
    if old["collection_started_at"] >= recent["collection_started_at"]:
        raise ValueError("RSS_AUDIT_REVERSED_ORDER")
    old_docs = old["documents"]
    old_urls = [r["url"] for r in old_docs]
    if len(set(old_urls)) != len(old_urls):
        raise ValueError("RSS_AUDIT_DUPLICATE_FAILED_URL")
    latest_urls = set(recent["preexisting_urls"])
    latest_urls.update(d["url"] for d in recent["documents"])
    latest_ids = {str(d) for d in recent["preexisting_document_ids"]}
    latest_ids.update(str(d["document_id"]) for d in recent["documents"])
    missing = sorted(u for u in old_urls if u not in latest_urls)
    present = len(old_urls) - len(missing)
    same_id = sum(str(d["document_id"]) in latest_ids for d in old_docs)
    return {
        "audit": "BCT_RSS_FAILED_PUBLISH_URL_RECONCILIATION",
        "status": "PASS_SAVED_URL_RECONCILIATION" if not missing else "PARTIAL_MISSING_URLS",
        "scope": "Failed run's newly captured URLs versus later saved RSS URLs, not all historical news",
        "before": {"zip_sha256": old_zip_sha, "collection_started_at": old["collection_started_at"],
                   "initial_articles": old_summary["initial_articles"], "new_urls": len(old_urls),
                   "saved_to_remote": "NOT_PROVEN_BY_FAILED_RUN"},
        "after": {"zip_sha256": recent_zip_sha, "collection_started_at": recent["collection_started_at"],
                  "initial_articles": recent_summary["initial_articles"],
                  "new_urls": recent_summary["new_articles"],
                  "total_saved_urls_visible": len(latest_urls)},
        "comparison": {
            "failed_run_new_urls": len(old_urls), "same_url_in_later_save": present,
            "still_missing_by_exact_url": len(missing),
            "same_original_document_id_visible": same_id,
            "missing_url_sha256": [hashlib.sha256(url.encode()).hexdigest() for url in missing],
        },
        "limits": ["Exact URL identity only; different canonical URLs may refer to the same article",
                   "URL retention does not prove original body capture, CPU analysis, or source completeness",
                   "Historical source publications never visible to an RSS feed cannot be counted here"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--failed-artifact", type=Path, required=True)
    parser.add_argument("--later-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = compare(args.failed_artifact, args.later_artifact)
    encoded = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded)
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
