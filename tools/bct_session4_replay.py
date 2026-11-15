#!/usr/bin/env python3
"""Replay two exact previously saved GitHub artifacts, with zero API/model calls.

Input: existing source delta ZIP + existing public source-separated research ZIP.
Output: private, source-free SQLite HOLD ledger, JSON projection and receipt.
This is a research SHADOW recheck; it does not reclassify earlier CPU windows
or modify any LIVE / production reference or Git branch.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from bct import session4_evidence_chain as evidence


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _load(archive, path):
    return json.loads(archive.read(path))


def replay(source_zip, research_zip, output):
    output = Path(output)
    if output.exists() and list(output.iterdir()):
        raise ValueError("SESSION4_OUTPUT_MUST_START_EMPTY")
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_zip) as sources, zipfile.ZipFile(research_zip) as research:
        manifest = _load(sources, "manifest.json")
        rm = _load(research, "manifest.json")
        snapshot_raw = research.read("snapshot.json")
        snapshot = json.loads(snapshot_raw)
        if manifest["format"] != "bct-cpu-source-delta-1" or manifest["status"] != "READY":
            raise ValueError("SESSION4_SOURCE_DELTA_NOT_READY")
        if (not manifest["graph_context_complete"]
                or manifest["unavailable_graph_sources"]
                or manifest["malformed_metadata_files"]):
            raise ValueError("SESSION4_INCOMPLETE_GRAPH_SOURCE_DELTA")
        expected_files = manifest["files"]
        if set(sources.namelist()) != set(expected_files) | {"manifest.json"}:
            raise ValueError("SESSION4_UNLISTED_OR_MISSING_ARCHIVE_MEMBER")
        for path, expected in expected_files.items():
            raw = sources.read(path)
            if len(raw) != expected["bytes"] or _digest(raw) != expected["sha256"]:
                raise ValueError("SESSION4_SOURCE_ARCHIVE_FILE_HASH_MISMATCH")
        if _digest(sources.read("cpu-manifest.json")) != manifest["cpu_manifest_sha256"]:
            raise ValueError("SESSION4_CPU_MANIFEST_HASH_MISMATCH")
        if rm["format"] != "bct-public-research-artifact-1" or snapshot["format"] != "bct-public-research-1":
            raise ValueError("SESSION4_RESEARCH_PUBLIC_SNAPSHOT_FORMAT")
        if _digest(snapshot_raw) != rm["file_sha256"]:
            raise ValueError("SESSION4_PUBLIC_SNAPSHOT_FILE_HASH_MISMATCH")
        content = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
        digest = _digest(evidence.canonical(content).encode())
        if digest != snapshot["snapshot_sha256"] or digest != rm["snapshot_sha256"]:
            raise ValueError("SESSION4_PUBLIC_SNAPSHOT_CANONICAL_HASH_MISMATCH")
        gen = snapshot["generation"]
        if (rm["generation"] != gen
                or gen["acquisition_run_id"] != manifest["acquisition_run_id"]
                or gen["RSS_run_id"] != manifest["rss_run_id"]
                or gen["execution_sha"] != "6e788d18cf85fdb834b451bb35585a8b58925301"
                or gen["producer_run_id"] != rm["transport_run_id"]):
            raise ValueError("SESSION4_SOURCE_CPU_GENERATION_NOT_SAME_LINEAGE")
        traces = {value["document_id"]: value for value in snapshot["trace"]}
        if len(traces) != len(snapshot["trace"]):
            raise ValueError("SESSION4_DUPLICATE_PUBLIC_TRACE")
        rows = []
        seen = set()
        for item in manifest["documents"]:
            doc_id = item["document_id"]
            if doc_id in seen:
                raise ValueError("SESSION4_DUPLICATE_DELTA_DOCUMENT")
            seen.add(doc_id)
            document_bytes = sources.read(item["document_member"])
            source = json.loads(document_bytes)
            if (_digest(document_bytes) != item["metadata_sha256"]
                    or item["document_member"] != "documents/" + item["body_sha256"] + ".json"):
                raise ValueError("SESSION4_DOC_METADATA_MISMATCH")
            if (source["document_id"] != doc_id
                    or source["body_sha256"] != item["body_sha256"]
                    or source["raw_sha256"] != item["raw_sha256"]
                    or source["origin_url"] != item["origin_url"]):
                raise ValueError("SESSION4_DOC_VERSION_BINDING_MISMATCH")
            if _digest(sources.read(item["native_member"])) != item["raw_sha256"]:
                raise ValueError("SESSION4_NATIVE_SOURCE_HASH_MISMATCH")
            trace = traces.get(doc_id)
            if trace is None:
                # Truncated public output cannot prove this source was read.
                raise ValueError("SESSION4_MISSING_EXACT_DOCUMENT_CPU_TRACE")
            rows.append(evidence.build(source, trace))
        if not rows:
            raise ValueError("SESSION4_NO_REAL_SOURCES")
    ledger = output / "session4.sqlite3"
    reloaded = evidence.persist(ledger, rows)
    if reloaded != rows:
        # readback sorted by immutable case_id; ignore input ordering only.
        if {x["case_id"]: x for x in reloaded} != {x["case_id"]: x for x in rows}:
            raise ValueError("SESSION4_RESTORED_HOLD_RECORD_MISMATCH")
    projection = evidence.dashboard(reloaded)
    if projection["held_sources"] != len(rows) or projection["candidate_count"] != 0:
        raise ValueError("SESSION4_PROJECTION_NOT_CONSERVATIVE")
    receipt = {
        "format": "bct-session4-verified-source-hold-proof-v1",
        "status": "PASS_BACKFILL_HOLD_ONLY",
        "input_acquisition_run": manifest["acquisition_run_id"],
        "cpu_producer_run": gen["producer_run_id"],
        "cpu_producer_sha": gen["execution_sha"],
        "source_verified_documents": len(rows),
        "distinct_document_ids": len(seen),
        "cpu_unread_documents": sum(x["cpu"]["blocker"] == "CPU_WINDOW_UNREAD" for x in rows),
        "pending_cpu_windows_in_exact_documents": sum(
            x["cpu"].get("window_counts", {}).get("unread", 0) for x in rows),
        "source_bound_events": sum(len(x["events"]) for x in rows),
        "source_bound_field_gaps": sum(len(e["missing_fields"]) for x in rows for e in x["events"]),
        "quantity_facts_located": sum(len(e["quantity_path"]) for x in rows for e in x["events"]),
        "timing_facts_located": sum(len(e["timing_path"]) for x in rows for e in x["events"]),
        "independent_qualified_pairs": sum(x["independent_pairs"] for x in rows),
        "automatic_promotions": 0,
        "latest_study_S_stage": "UNVERIFIED",
        "not_live_discovery": True,
        "prediction_performance": "UNVERIFIED",
        "raw_sources_persisted": False,
        "source_zip_sha256": _digest(Path(source_zip).read_bytes()),
        "public_research_zip_sha256": _digest(Path(research_zip).read_bytes()),
        "source_manifest_sha256": _digest(evidence.canonical(manifest).encode()),
        "public_snapshot_sha256": digest,
        "ledger_sha256": _digest(ledger.read_bytes()),
        "dashboard_sha256": _digest(evidence.canonical(projection).encode()),
        "first_replayed_document_id": rows[0]["source"]["document_id"],
    }
    (output / "dashboard.json").write_text(evidence.canonical(projection) + "\n")
    (output / "receipt.json").write_text(evidence.canonical(receipt) + "\n")
    return receipt


def verify(output):
    output = Path(output)
    receipt = json.loads((output / "receipt.json").read_text())
    projection = json.loads((output / "dashboard.json").read_text())
    ledger = output / "session4.sqlite3"
    rows = evidence.readback(ledger)
    if (_digest(ledger.read_bytes()) != receipt["ledger_sha256"]
            or _digest(evidence.canonical(projection).encode()) != receipt["dashboard_sha256"]
            or evidence.dashboard(rows) != projection
            or len(rows) != receipt["source_verified_documents"]
            or receipt["automatic_promotions"] != 0
            or receipt["status"] != "PASS_BACKFILL_HOLD_ONLY"):
        raise ValueError("SESSION4_FRESH_PROCESS_RESTORE_MISMATCH")
    if any(x["decision"] != "HOLD" or x["auto_promoted"] is not False
           for x in rows):
        raise ValueError("SESSION4_UNAUTHORIZED_DISCOVERY_PROMOTION")
    return {
        "status": "PASS_NEW_PROCESS_LEDGER_READBACK",
        "cases": len(rows),
        "source_id": rows[0]["source"]["document_id"],
        "source_body_sha": rows[0]["source"]["body_sha256"],
        "cpu_unread_sources": projection["cpu_unread_sources"],
        "candidate_count": projection["candidate_count"],
        "new_model_calls": 0,
        "production_writes": 0,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("replay", "verify"))
    p.add_argument("--source-zip", type=Path)
    p.add_argument("--research-zip", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.action == "replay":
        if not a.source_zip or not a.research_zip:
            p.error("replay requires both pinned ZIP paths")
        result = replay(a.source_zip, a.research_zip, a.out)
    else:
        result = verify(a.out)
    print(evidence.canonical(result))


if __name__ == "__main__":
    main()
