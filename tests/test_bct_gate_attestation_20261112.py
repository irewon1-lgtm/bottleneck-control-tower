"""Safe main-only Gate renewal requires actual Gate proof before any receipt update."""
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / ".github/workflows/bct-gate-renewal-20261112.yml"
TEXT = PATH.read_text(encoding="utf-8")


def test_current_main_gate_dispatch_covers_strict_guarded_roots_without_changing_pipeline():
    for protected_root in (
        "src/**",
        "tests/**",
        ".github/scripts/**",
        ".github/workflows/**",
        "config/**",
        "docs/**",
    ):
        assert f"- '{protected_root}'" in TEXT
    assert "- '!config/bct-operating-release.json'" in TEXT
    assert "branches: [main]" in TEXT
    assert '"full_pipeline":false' in TEXT
    assert '"preserve_resume_only":false' in TEXT
    assert "bct-recovery.yml/dispatches" in TEXT
    assert "actions: write" in TEXT
    assert "Gate dispatch accepted. This is not a Gate PASS." in TEXT


def test_gate_receipt_requires_actual_completed_main_gate_and_exact_hashes():
    for required in (
        "run.get('conclusion') != 'success'",
        "run.get('event') != 'workflow_dispatch'",
        "(run.get('head_repository') or {}).get('full_name') != repo",
        "run.get('path') != '.github/workflows/bct-recovery.yml'",
        "run.get('head_sha') != current['commit']['sha']",
        "bct-recovery-checkpoint-",
        "GATE_CHECKPOINT_ARTIFACT_NOT_UNIQUE",
        "verify_release(api, receipt, pathlib.Path('.'))",
        "GATE_RELEASE_GUARD_REJECTED",
        "GATE_ATOMIC_DUAL_RECEIPT_API_REJECTED",
    ):
        assert required in TEXT


def test_strict_receipt_cas_and_recovery_only_after_proof():
    assert "config/bct-operating-release.json" in TEXT
    assert "prepare_receipts(API(),run_id,run['head_sha']" in TEXT
    assert "'.github/bct-recovery-request.json':target/'bct-recovery-request.json'" in TEXT
    assert "'/git/trees'" in TEXT
    assert "'/git/commits'" in TEXT
    assert "'/git/refs/heads/main'" in TEXT
    assert "'force':False" in TEXT
    assert "GATE_RELEASE_RECEIPT_COMMITTED" in TEXT
    assert TEXT.index("verify_release(api, receipt") < TEXT.index("prepare_receipts(API(),run_id")
    assert TEXT.index("prepare_receipts(API(),run_id") < TEXT.index("'/git/refs/heads/main'")
    assert TEXT.index("'/git/refs/heads/main'") < TEXT.index("Trigger existing source-free private ACK recovery")
    assert '"purpose":"recover-public"' in TEXT
    assert "v4-cpu-private-research.yml/dispatches" in TEXT
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" not in TEXT
    assert "publish-private-source" not in TEXT

def test_new_code_gate_dispatch_and_operational_resume_are_proof_bound():
    assert "GATE_DUAL_RECEIPT_GENERATION_MISMATCH" in TEXT
    assert "GATE_ATOMIC_BOTH_FILES_READBACK_MISMATCH" in TEXT
    assert "BCT_FAIR_QUEUE_MODE" not in TEXT
    assert "future-bottleneck.yml/dispatches" in TEXT
    assert TEXT.index("GATE_RELEASE_RECEIPT_COMMITTED") < TEXT.index(
        "Resume existing CPU candidate cycle after BOTH Gate receipts")


def test_completed_gate_is_authenticated_inside_job_even_if_event_fields_are_missing():
    assert "if: ${{ github.event_name == 'workflow_run' }}" in TEXT
    assert 'GATE_NON_ATTESTABLE_EVENT_NO_WRITE' in TEXT
    assert "output.write('published=false\\n')" in TEXT
    assert "output.write('published=true\\n')" in TEXT
    assert TEXT.count("if: ${{ steps.attest.outputs.published == 'true' }}") == 2
    assert TEXT.index('GATE_NON_ATTESTABLE_EVENT_NO_WRITE') < TEXT.index('verify_release(api, receipt')
    assert TEXT.index('GATE_RELEASE_RECEIPT_COMMITTED') < TEXT.index("output.write('published=true")
