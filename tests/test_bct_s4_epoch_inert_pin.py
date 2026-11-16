"""Only dedicated original-source manual CPU epoch may use reviewed inert-run fix."""
from pathlib import Path

def test_dedicated_epoch_cpu_exact_reviewed_sha_and_original_scope():
    repo=Path(__file__).resolve().parents[1]
    w=(repo/".github/workflows/bct-s4-epoch-cpu-manual.yml").read_text()
    reviewed="f3fb861c8dab87670983660a8a5eaa40a3962dab"
    assert w.count(reviewed)==2
    assert "1cfcd3d7aefcfc068944a47ee924822216961f60" not in w
    assert "acquisition_run == '43645932280'" in w
    assert "verified-exact-manual-v1" in w
    assert "refs/heads/codex/bct-v4-cpu-research-epoch-20261116" in w
    assert "fail-on-cache-miss: true" in w
    assert "BCT_V4_PRIVATE_STATE_TOKEN" in w
    assert "REVIEW_LEAD" not in w

def test_scheduled_workflow_is_unchanged_by_epoch_pin():
    repo=Path(__file__).resolve().parents[1]
    w=(repo/".github/workflows/v4-cpu-private-research.yml").read_text()
    assert "f3fb861c8dab87670983660a8a5eaa40a3962dab" not in w
