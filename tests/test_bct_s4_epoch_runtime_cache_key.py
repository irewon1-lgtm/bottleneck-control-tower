"""Prevent escaped GitHub Actions cache keys from blocking epoch CPU reads."""
from pathlib import Path
import re

def test_epoch_cache_key_expands_actual_runner_env_not_literals():
    flow=(Path(__file__).resolve().parents[1]/".github/workflows/bct-s4-epoch-cpu-manual.yml").read_text()
    exact='echo "key=v4-cpu-runtime-${RUNNER_OS}-${RUNNER_ARCH}-${PYTHON_VERSION}-${LOCK_SHA}" >> "$GITHUB_OUTPUT"'
    assert flow.count(exact)==1
    assert r'\${RUNNER_OS}' not in flow
    assert r'\${RUNNER_ARCH}' not in flow
    assert r'\${PYTHON_VERSION}' not in flow
    assert r'\${LOCK_SHA}' not in flow
    assert "fail-on-cache-miss: true" in flow
    assert "path: |\n            .v4-cpu-env\n            .v4-cpu-runtime" in flow

def test_pinned_manual_cpu_keeps_old_archive_and_zero_live_promotions():
    flow=(Path(__file__).resolve().parents[1]/".github/workflows/bct-s4-epoch-cpu-manual.yml").read_text()
    assert "aca2ccf56032c7841188997e857828142dadcb0a" in flow
    assert "refs/heads/codex/bct-v4-cpu-research-epoch-20261116" in flow
    assert "old_private_ref_writes':0" in flow
    assert "LIVE_registration" in flow
    assert "acquisition_run == '43645932280'" in flow
