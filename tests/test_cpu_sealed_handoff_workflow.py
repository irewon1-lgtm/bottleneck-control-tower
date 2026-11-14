"""Regression coverage for ciphertext-only BCT CPU workflow_run handoffs."""
from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import zipfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/v4_cpu_sealed_handoff.py"
WORKFLOW = ROOT / ".github/workflows/v4-cpu-private-research.yml"


def load_helper():
    spec = importlib.util.spec_from_file_location("v4_sealed_handoff", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def jobs():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]


def step(job, name):
    return next(x for x in jobs()[job]["steps"] if x.get("name") == name)


def test_workflow_run_does_not_try_to_write_default_branch_cache():
    content = WORKFLOW.read_text()
    assert "cache-mode: write" not in content
    assert "actions/cache/save@v4" not in content
    assert content.count("Check out current reviewed ciphertext-transfer helper") == 2
    assert "sha256" in SCRIPT.read_text()
    assert "STATE_PASSPHRASE" not in SCRIPT.read_text()
    assert "BCT_V4_PRIVATE_STATE_TOKEN" not in SCRIPT.read_text()
    research = jobs()["research"]["steps"]
    assert any("latest-bridge --destination var/v4/cpu-private/bridge/state.gpg" in
               s.get("run", "") for s in research)
    bridge_cache = next(s for s in research if s.get("with", {}).get("restore-keys") == "v4-cpu-private-bridge-")
    assert bridge_cache["with"]["fail-on-cache-miss"] is False


def test_result_and_bridge_artifacts_are_cipher_only_and_attempt_bound():
    marker = "$" + "{{ github.run_attempt }}"
    result = step("research", "Upload only AES256-GPG sealed CPU result; fail on missing packet")
    result_w = result["with"]
    assert result["uses"] == "actions/upload-artifact@v4"
    assert result_w["path"] == "var/v4/cpu-private/result/state.gpg"
    assert result_w["name"] == "bct-sealed-cpu-result-" + marker
    assert result_w["if-no-files-found"] == "error"
    assert 0 < result_w["retention-days"] <= 7
    receive = step("publish", "Download only the sealed CPU result produced in this same run")
    assert receive["uses"] == "actions/download-artifact@v4"
    assert receive["with"]["name"] == result_w["name"]
    assert receive["with"]["path"] == "var/v4/cpu-private/result"
    bridge = step("publish", "Upload only acknowledged AES256-GPG bridge for the next scheduled CPU run")
    assert bridge["with"]["path"] == "var/v4/cpu-private/bridge/state.gpg"
    assert bridge["with"]["name"] == "bct-sealed-cpu-bridge-" + marker
    assert bridge["with"]["if-no-files-found"] == "error"
    steps = jobs()["publish"]["steps"]
    assert steps.index(bridge) > steps.index(step("publish", "Seal acknowledged private state for next read-only CPU job"))
    assert steps.index(bridge) > steps.index(step("publish", "New-process remote research restore and dedup validation; no CPU load"))


def test_existing_cache_recover_result_path_remains_separate():
    recover = step("publish", "Verify exact failed CPU result producer and cache identity")
    assert "recover-sealed-result" not in recover["if"]
    cipher = step("publish", "Recover a prior failed sealed CPU result without rerunning the model")
    assert "recover-sealed-result" in cipher["if"]
    assert "recover-result --run-id" in cipher["run"]
    assert "tools/v4_cpu_private.py unseal" in cipher["run"]
    assert "recover-sealed-result" in jobs()["publish"]["if"]


def test_refuse_untrusted_runs_even_if_artifact_exists():
    mod = load_helper()
    run = {"path": mod.WORKFLOW, "head_branch": "main",
           "head_repository": {"full_name": mod.REPOSITORY},
           "event": "workflow_run", "status": "completed", "conclusion": "success",
           "head_sha": "a" * 40}
    mod.approved_run(run, require_success=True)
    for key, value in [("head_branch", "evil"), ("event", "pull_request"),
                       ("status", "in_progress"), ("head_sha", "not-sha"),
                       ("path", "another-workflow")]:
        changed = {**run, key: value}
        with pytest.raises(ValueError, match="UNTRUSTED"):
            mod.approved_run(changed, require_success=True)
    with pytest.raises(ValueError, match="UNTRUSTED"):
        mod.approved_run({**run, "head_repository": {"full_name": "fork/repo"}}, require_success=True)


def zip_packet(name="state.gpg", payload=b"GPG-encrypted-test-packet", extra=False):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(name, payload)
        if extra:
            archive.writestr("checkpoint.sqlite3", b"plaintext-not-allowed")
    return out.getvalue()


def metadata(payload):
    return {"size_in_bytes": len(payload), "digest": "sha256:" + hashlib.sha256(payload).hexdigest()}


def test_only_digest_checked_single_cipher_is_accepted():
    mod = load_helper()
    good = zip_packet(payload=b"A" * 48)
    assert mod.extract_verified_cipher(metadata(good), good) == b"A" * 48
    with pytest.raises(ValueError, match="DIGEST"):
        mod.extract_verified_cipher(metadata(good), good + b"0")
    bad = zip_packet(extra=True)
    with pytest.raises(ValueError, match="ONLY_ENCRYPTED"):
        mod.extract_verified_cipher(metadata(bad), bad)
    traversal = zip_packet(name="../state.gpg")
    with pytest.raises(ValueError, match="ONLY_ENCRYPTED"):
        mod.extract_verified_cipher(metadata(traversal), traversal)
    tiny = zip_packet(payload=b"x")
    with pytest.raises(ValueError, match="ONLY_ENCRYPTED"):
        mod.extract_verified_cipher(metadata(tiny), tiny)


def test_latest_bridge_prefers_successful_ack_and_checks_job(monkeypatch):
    mod = load_helper()
    monkeypatch.setenv("GITHUB_RUN_ID", "90")
    good = {"id": 80, "run_attempt": 1, "path": mod.WORKFLOW,
            "head_branch": "main", "head_repository": {"full_name": mod.REPOSITORY},
            "event": "workflow_run", "status": "completed", "conclusion": "success",
            "head_sha": "a" * 40}
    item = {"id": 1, "name": "bct-sealed-cpu-bridge-1",
            "expired": False, "size_in_bytes": 100,
            "digest": "sha256:" + "a" * 64, "workflow_run": {"id": 80}}
    def fake_api(path):
        if path == "actions/artifacts?per_page=100&page=1":
            return {"artifacts": [item]}
        if path == "actions/runs/80":
            return good
        if path == "actions/runs/80/artifacts?per_page=100":
            return {"artifacts": [item]}
        if "actions/runs/80/attempts/" in path:
            return {"jobs": [{"name": "publish", "conclusion": "success"}]}
        raise AssertionError(path)
    monkeypatch.setattr(mod, "api", fake_api)
    chosen, item = mod.get_latest_bridge()
    assert chosen["id"] == 80
    assert item["id"] == 1


def test_bootstrap_needs_actual_existing_encrypted_state(monkeypatch, tmp_path, capsys):
    mod = load_helper()
    monkeypatch.setattr(mod, "get_latest_bridge", lambda: None)
    monkeypatch.setattr(sys, "argv", ["handoff", "latest-bridge", "--destination",
                                     str(tmp_path / "state.gpg"), "--allow-existing-bootstrap"])
    with pytest.raises(ValueError, match="NO_ACKNOWLEDGED_BRIDGE"):
        mod.main()
    (tmp_path / "state.gpg").write_bytes(b"A" * 60)
    mod.main()
    assert "existing_legacy_cache_bootstrap" in capsys.readouterr().out


def test_retry_must_restore_the_original_artifact_attempt_not_latest_run(monkeypatch, tmp_path, capsys):
    """A writer retry changes latest run_attempt without changing sealed research result."""
    mod = load_helper()
    run_id = 43577616321
    old_attempt = 1
    monkeypatch.setenv("GITHUB_RUN_ID", "43599999999")
    old = {
        "id": run_id, "run_attempt": old_attempt, "path": mod.WORKFLOW,
        "head_branch": "main", "head_repository": {"full_name": mod.REPOSITORY},
        "event": "workflow_run", "status": "completed", "conclusion": "failure",
        "head_sha": "a" * 40,
    }
    sealed = b"S" * 60
    zipped = zip_packet(payload=sealed)
    item = {
        "id": 501, "name": "bct-sealed-cpu-result-1", "expired": False,
        "size_in_bytes": len(zipped),
        "digest": "sha256:" + hashlib.sha256(zipped).hexdigest(),
        "workflow_run": {"id": run_id},
    }
    requested = []
    def fake_api(path, *, binary=False):
        requested.append((path, binary))
        if path == f"actions/runs/{run_id}/attempts/1":
            return old
        if path == f"actions/runs/{run_id}/attempts/1/jobs?per_page=100":
            return {"jobs": [{"name": "research", "conclusion": "success"}]}
        if path == f"actions/runs/{run_id}/artifacts?per_page=100":
            return {"artifacts": [item]}
        if path == "actions/artifacts/501/zip" and binary:
            return zipped
        raise AssertionError(path)
    monkeypatch.setattr(mod, "api", fake_api)
    dest = tmp_path / "state.gpg"
    monkeypatch.setattr(sys, "argv", [
        "sealed-handoff", "recover-result", "--run-id", str(run_id),
        "--attempt", "1", "--destination", str(dest),
    ])
    mod.main()
    assert dest.read_bytes() == sealed
    assert (f"actions/runs/{run_id}/attempts/1", False) in requested
    assert (f"actions/runs/{run_id}", False) not in requested
    assert "PENDING_GPG_AUTHENTICATION" in capsys.readouterr().out


def test_wrong_historical_attempt_cannot_inherit_another_attempts_artifact(monkeypatch, tmp_path):
    mod = load_helper()
    monkeypatch.setenv("GITHUB_RUN_ID", "43599999999")
    old = {"id": 43577616321, "run_attempt": 1}
    monkeypatch.setattr(mod, "api", lambda path, **kw: old)
    monkeypatch.setattr(sys, "argv", [
        "sealed-handoff", "recover-result", "--run-id", "43577616321",
        "--attempt", "2", "--destination", str(tmp_path / "state.gpg"),
    ])
    with pytest.raises(ValueError, match="SEALED_HANDOFF_RECOVERY_ATTEMPT"):
        mod.main()
