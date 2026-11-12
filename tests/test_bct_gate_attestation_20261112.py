"""Safe main-only Gate renewal requires actual Gate proof before any receipt update."""
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / ".github/workflows/bct-gate-renewal-20261112.yml"
TEXT = PATH.read_text(encoding="utf-8")


def test_one_time_gate_dispatch_does_not_change_operating_pipeline():
    assert "paths: ['.github/workflows/bct-gate-renewal-20261112.yml']" in TEXT
    assert "branches: [main]" in TEXT
    assert '"full_pipeline":false' in TEXT
    assert '"preserve_resume_only":false' in TEXT
    assert "bct-recovery.yml/dispatches" in TEXT
    assert "actions: write" in TEXT
    assert "Gate dispatch accepted. This is not a Gate PASS." in TEXT


def test_gate_receipt_requires_actual_completed_main_gate_and_exact_hashes():
    for required in (
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'workflow_dispatch'",
        "github.event.workflow_run.head_repository.full_name == github.repository",
        "run.get('path') != '.github/workflows/bct-recovery.yml'",
        "run.get('head_sha') != current['commit']['sha']",
        "bct-recovery-checkpoint-",
        "GATE_CHECKPOINT_ARTIFACT_NOT_UNIQUE",
        "verify_release(api, receipt, pathlib.Path('.'))",
        "GATE_RELEASE_GUARD_REJECTED",
        "GATE_RECEIPT_COMMIT_DENIED_OR_CONFLICT",
    ):
        assert required in TEXT


def test_strict_receipt_cas_and_recovery_only_after_proof():
    assert "config/bct-operating-release.json" in TEXT
    assert "old_file['sha']" in TEXT
    assert "GATE_RELEASE_RECEIPT_COMMITTED" in TEXT
    assert TEXT.index("verify_release(api, receipt") < TEXT.index("gh','api','--method','PUT'")
    assert TEXT.index("gh','api','--method','PUT'") < TEXT.index("Trigger existing source-free private ACK recovery")
    assert '"purpose":"recover-public"' in TEXT
    assert "v4-cpu-private-research.yml/dispatches" in TEXT
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" not in TEXT
    assert "publish-private-source" not in TEXT
