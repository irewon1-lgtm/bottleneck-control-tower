"""New epoch workflow is manual-only and secrets do not reach CPU reader."""
from pathlib import Path
import yaml

p=Path(__file__).resolve().parents[1]/".github/workflows/bct-s4-epoch-cpu-manual.yml"
sha="399c63008380dc2d2646ea60956259dda53b2534"
old_ref="refs/heads/codex/bct-v4-cpu-research-state"
new_ref="refs/heads/codex/bct-v4-cpu-research-epoch-20261116"

def test_manual_source_stated_only_and_unmodified_scheduled_pipeline():
    s=p.read_text()
    w=yaml.safe_load(s)
    assert "workflow_dispatch:" in s and "workflow_run:" not in s and "schedule:" not in s
    assert w["permissions"]=={"contents":"read","actions":"read"}
    assert w["env"]["CPU_CODE_SHA"]==w["env"]["EXPECTED_CPU_CODE_SHA"]==sha
    assert w["env"]["ORIGINAL_ACQUISITION"]=="43645932280"
    assert set(w["jobs"])=={"bridge","research","publish"}
    assert old_ref not in s


def test_private_repo_secret_never_in_cpu_reading_job():
    s=yaml.safe_load(p.read_text())
    reading=s["jobs"]["research"]
    assert "BCT_V4_PRIVATE_STATE_TOKEN" not in str(reading)
    assert "GITHUB_TOKEN" not in str(reading)
    assert reading["needs"]=="bridge"
    assert s["jobs"]["publish"]["needs"]=="research"
    assert "BCT_V4_PRIVATE_STATE_TOKEN" in str(s["jobs"]["bridge"])
    assert "BCT_V4_PRIVATE_STATE_TOKEN" in str(s["jobs"]["publish"])
    assert "BCT_V4_S4_EPOCH_MODE" in str(reading)
    assert "verified-exact-manual-v1" in str(reading)
    assert "bct-s4-epoch-bridge" in str(reading)
    assert "bct-s4-epoch-cpu-result" in str(s["jobs"]["publish"])


def test_no_source_publication_or_automatic_candidate_promotion():
    s=p.read_text()
    assert "--manual-acquisition-run" in s
    assert "BCT_V4_S4_EPOCH_BRIDGE_PROOF" in s
    assert "LIVE_registration" in s
    assert "new_validated_windows" in s
    assert "S3" not in s
    assert "contents: write" not in s
    assert new_ref in s
    assert "actions/upload-artifact@v4" in s
