#!/usr/bin/env python3
"""Read-only, digest-verified transfer of AES256-GPG CPU state between Actions jobs.

No raw documents, models, credentials or SQLite bytes are transferred. Published
private state is still authenticated and CAS-verified by the existing pinned CPU
writer. Never relax the default read-only cache mode of workflow_run events.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

REPOSITORY = "irewon1-lgtm/bottleneck-control-tower"
WORKFLOW = ".github/workflows/v4-cpu-private-research.yml"
MAX_ZIP_BYTES = 8 * 1024 * 1024
MAX_CIPHER_BYTES = 6 * 1024 * 1024
ARTIFACT_PREFIX = {"latest-bridge": "bct-sealed-cpu-bridge", "recover-result": "bct-sealed-cpu-result"}


def api(path: str, *, binary: bool = False):
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise ValueError("SEALED_HANDOFF_REPOSITORY")
    if not os.environ.get("GH_TOKEN"):
        raise ValueError("SEALED_HANDOFF_ACTIONS_READ_TOKEN")
    response = subprocess.run(
        ["gh", "api", "repos/" + REPOSITORY + "/" + path],
        capture_output=True, timeout=40, check=False
    )
    if response.returncode:
        raise ValueError("SEALED_HANDOFF_ACTIONS_API")
    if binary:
        if len(response.stdout) > MAX_ZIP_BYTES:
            raise ValueError("SEALED_HANDOFF_ARCHIVE_SIZE")
        return response.stdout
    return json.loads(response.stdout)


def approved_run(run: dict, *, require_success: bool) -> None:
    if (run.get("path") != WORKFLOW
            or run.get("head_branch") != "main"
            or run.get("head_repository", {}).get("full_name") != REPOSITORY
            or run.get("event") not in ("workflow_run", "workflow_dispatch")
            or run.get("status") != "completed"
            or (require_success and run.get("conclusion") != "success")
            or not re.fullmatch(r"[a-f0-9]{40}", run.get("head_sha") or "")):
        raise ValueError("SEALED_HANDOFF_UNTRUSTED_PRODUCER")


def approved_job(run: dict, name: str) -> None:
    jobs = api(f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs?per_page=100")["jobs"]
    matched = [job for job in jobs if job.get("name") == name]
    if len(matched) != 1 or matched[0].get("conclusion") != "success":
        raise ValueError("SEALED_HANDOFF_PRODUCER_JOB_NOT_SUCCESSFUL")


def artifact(run: dict, prefix: str) -> dict | None:
    name = f"{prefix}-{run['run_attempt']}"
    matches = [row for row in api(f"actions/runs/{run['id']}/artifacts?per_page=100")["artifacts"]
               if row.get("name") == name]
    if len(matches) > 1:
        raise ValueError("SEALED_HANDOFF_DUPLICATE_ARTIFACT")
    if not matches:
        return None
    item = matches[0]
    digest = item.get("digest") or ""
    if (item.get("expired") is not False
            or not isinstance(item.get("size_in_bytes"), int)
            or not 0 < item["size_in_bytes"] <= MAX_ZIP_BYTES
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest)):
        raise ValueError("SEALED_HANDOFF_UNVERIFIED_ARTIFACT")
    if item.get("workflow_run") and item["workflow_run"].get("id") != run["id"]:
        raise ValueError("SEALED_HANDOFF_ARTIFACT_PRODUCER_MISMATCH")
    return item


def extract_verified_cipher(item: dict, payload: bytes) -> bytes:
    if (len(payload) != item["size_in_bytes"]
            or hashlib.sha256(payload).hexdigest() != item["digest"].split(":", 1)[1]):
        raise ValueError("SEALED_HANDOFF_DOWNLOAD_DIGEST")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if (len(entries) != 1 or entries[0].filename != "state.gpg"
                    or entries[0].is_dir()
                    or (entries[0].external_attr >> 16) & 0o170000 == 0o120000
                    or not 32 <= entries[0].file_size <= MAX_CIPHER_BYTES):
                raise ValueError("SEALED_HANDOFF_ONLY_ENCRYPTED_PACKET")
            cipher = archive.read(entries[0])
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise ValueError("SEALED_HANDOFF_MALFORMED_ARCHIVE") from exc
    return cipher


def store_cipher(destination: Path, cipher: bytes):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as tmp:
        tmp.write(cipher)
        tmp.flush()
        os.fchmod(tmp.fileno(), 0o600)
        tmp_path = Path(tmp.name)
    try:
        tmp_path.replace(destination)
    finally:
        tmp_path.unlink(missing_ok=True)


def get_latest_bridge() -> tuple[dict, dict] | None:
    """Search bounded artifact metadata pages, never an unbounded run-by-run scan."""
    current = int(os.environ.get("GITHUB_RUN_ID") or "0")
    prefix = ARTIFACT_PREFIX["latest-bridge"]
    for page in range(1, 9):
        entries = api(f"actions/artifacts?per_page=100&page={page}")["artifacts"]
        # Repository artifacts are returned newest first; verify the producer
        # only for an exact sealed-bridge candidate, not every unrelated run.
        for entry in entries:
            match = re.fullmatch(re.escape(prefix) + r"-([1-9][0-9]*)", entry.get("name") or "")
            if not match:
                continue
            reference = entry.get("workflow_run") or {}
            producer_id = reference.get("id")
            if type(producer_id) is not int or producer_id >= current:
                continue
            run = api(f"actions/runs/{producer_id}")
            approved_run(run, require_success=True)
            if run.get("run_attempt") != int(match[1]):
                raise ValueError("SEALED_HANDOFF_ARTIFACT_ATTEMPT")
            item = artifact(run, prefix)
            if item is None or item["id"] != entry.get("id"):
                raise ValueError("SEALED_HANDOFF_ARTIFACT_IDENTITY")
            approved_job(run, "publish")
            return run, item
        if len(entries) < 100:
            break
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=tuple(ARTIFACT_PREFIX))
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--allow-existing-bootstrap", action="store_true")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    if args.mode == "latest-bridge":
        found = get_latest_bridge()
        if found is None:
            if (not args.allow_existing_bootstrap or not args.destination.is_file()
                    or not 32 <= args.destination.stat().st_size <= MAX_CIPHER_BYTES):
                raise ValueError("SEALED_HANDOFF_NO_ACKNOWLEDGED_BRIDGE")
            print(json.dumps({"handoff": "existing_legacy_cache_bootstrap", "status": "PENDING_AUTHENTICATION"}))
            return
        run, item = found
    else:
        if (not args.run_id or not args.attempt or args.attempt < 1
                or args.run_id >= int(os.environ.get("GITHUB_RUN_ID") or "0")):
            raise ValueError("SEALED_HANDOFF_RECOVERY_ID")
        # A failed writer can be rerun without rerunning the successful
        # research producer. GitHub then increments the run's latest attempt,
        # while its authenticated sealed artifact remains bound to attempt 1.
        # Fetch the explicitly selected historical attempt, never relabel a
        # previous artifact as belonging to the latest attempt.
        run = api(f"actions/runs/{args.run_id}/attempts/{args.attempt}")
        if run.get("id") != args.run_id or run.get("run_attempt") != args.attempt:
            raise ValueError("SEALED_HANDOFF_RECOVERY_ATTEMPT")
        approved_run(run, require_success=False)
        approved_job(run, "research")
        item = artifact(run, ARTIFACT_PREFIX["recover-result"])
        if item is None:
            raise ValueError("SEALED_HANDOFF_RECOVERY_NOT_SAVED")
    cipher = extract_verified_cipher(item, api(f"actions/artifacts/{item['id']}/zip", binary=True))
    store_cipher(args.destination, cipher)
    print(json.dumps({"handoff": args.mode, "status": "PENDING_GPG_AUTHENTICATION",
                      "producer_run": run["id"], "attempt": run["run_attempt"],
                      "cipher_sha256": hashlib.sha256(cipher).hexdigest(), "cipher_bytes": len(cipher)}))


if __name__ == "__main__":
    main()
