"""S2: any change to the strict approved-code tree requests a REAL Gate.

Do not change the operating release guard or treat a Gate dispatch as proof.
"""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT / ".github/workflows/bct-gate-renewal-20261112.yml"
GUARD=ROOT / ".github/scripts/bct_release_guard.py"

def _guard():
    spec=importlib.util.spec_from_file_location("bct_strict_guard",GUARD)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_all_existing_strict_code_roots_are_watched_by_actual_gate_renewal():
    s=WORKFLOW.read_text(encoding="utf-8")
    push=s.split("  workflow_run:",1)[0]
    expected={
        "src/**","tests/**",".github/scripts/**",
        ".github/workflows/**","config/**","docs/**"
    }
    for root in expected:
        assert "      - '"+root+"'" in push,root
    guard=_guard()
    actual={
        "src/bct/future_bottleneck.py":"src/**",
        "tests/test_operating_release_guard.py":"tests/**",
        ".github/scripts/bct_release_guard.py":".github/scripts/**",
        ".github/workflows/ui-pages.yml":".github/workflows/**",
        "config/bct-operating-release-test.json":"config/**",
        "docs/app.js":"docs/**"
    }
    for path,pattern in actual.items():
        assert guard.code_path(path),path
        assert pattern in expected

def test_receipt_only_commit_cannot_trigger_recursive_gate():
    guard=_guard()
    s=WORKFLOW.read_text(encoding="utf-8")
    push=s.split("  workflow_run:",1)[0]
    assert not guard.code_path("config/bct-operating-release.json")
    assert "      - '!config/bct-operating-release.json'" in push
    assert not guard.code_path(".github/bct-recovery-request.json")

def test_gate_remains_actual_current_main_and_no_skip_bypass():
    s=WORKFLOW.read_text(encoding="utf-8")
    assert "repos/$GITHUB_REPOSITORY/actions/workflows/bct-recovery.yml/dispatches" in s
    assert "GATE_NOT_COMPLETED_FOR_CURRENT_MAIN" in s
    assert "GATE_RELEASE_GUARD_REJECTED" in s
    assert "GATE_ATOMIC_DUAL_RECEIPT_API_REJECTED" in s
    assert "published=true" in s
