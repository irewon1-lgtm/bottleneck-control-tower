"""Regression: a GITHUB_TOKEN-dispatched Gate must finalize its own proven receipt.

The finalizer is requested only after upload and still requires completed
Gate 0-6, matching current code, artifact digest and source-archive hashes.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
GATE=(ROOT/".github/workflows/bct-recovery.yml").read_text(encoding="utf-8")
ATTEST=(ROOT/".github/workflows/bct-gate-renewal-20261112.yml").read_text(encoding="utf-8")


def test_gate_job_dispatches_finalizer_only_after_successful_artifact_upload():
    storage=GATE.split("  storage:",1)[1]
    assert "      actions: write" in storage
    assert "      contents: write" in storage
    assert "name: bct-recovery-checkpoint-${{ github.run_id }}" in storage
    assert "Dispatch strict actual Gate attestation after successful checkpoint upload" in storage
    assert storage.index("name: bct-recovery-checkpoint-") < storage.index(
        "Dispatch strict actual Gate attestation after successful checkpoint upload")
    assert "success() && github.event_name == 'workflow_dispatch'" in storage
    assert "github.ref == 'refs/heads/main'" in storage
    assert "steps.request.outputs.full_pipeline != 'true'" in storage
    assert "actions/workflows/bct-gate-renewal-20261112.yml/dispatches" in storage
    assert "'gate_run_id':os.environ['GITHUB_RUN_ID']" in storage
    assert "no Gate PASS asserted" in storage


def test_explicit_finalizer_requires_same_completed_real_gate_and_archive_hash():
    assert "  workflow_dispatch:" in ATTEST
    assert "      gate_run_id:" in ATTEST
    assert "        required: true" in ATTEST
    assert "github.event.workflow_run.id || inputs.gate_run_id" in ATTEST
    assert "github.event.workflow_run.head_sha || github.sha" in ATTEST
    assert "os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'" in ATTEST
    assert "GATE_NOT_COMPLETED_AFTER_FINALIZER_WAIT" in ATTEST
    assert "run.get('status') != 'completed'" in ATTEST
    assert "run.get('conclusion') != 'success'" in ATTEST
    assert "run.get('event') != 'workflow_dispatch'" in ATTEST
    assert "run.get('head_sha') != current['commit']['sha']" in ATTEST
    for binding in (
        "bct-recovery-checkpoint-",
        "GATE_ARTIFACT_HASH_OR_PRODUCER",
        "verify_release(api, receipt, pathlib.Path('.'))",
        "prepare_receipts(API(),run_id,run['head_sha']",
        "GATE_ATOMIC_DUAL_RECEIPT_API_REJECTED",
        "'force':False",
        "GATE_ATOMIC_BOTH_FILES_READBACK_MISMATCH",
    ):
        assert binding in ATTEST
    assert ATTEST.index("verify_release(api, receipt") < ATTEST.index("prepare_receipts(API(),run_id")
    assert ATTEST.index("prepare_receipts(API(),run_id") < ATTEST.index("'/git/refs/heads/main'")


def test_no_approval_from_dispatch_or_unverified_candidate():
    dispatch=GATE.split("Dispatch strict actual Gate attestation after successful checkpoint upload",1)[1]
    assert "no Gate PASS asserted" in dispatch
    assert "BCT_S3_SOURCE_PROOF_PROMOTED" not in dispatch
    assert "publish-private-source" not in ATTEST
    assert ATTEST.index("GATE_RELEASE_RECEIPT_COMMITTED") < ATTEST.index(
        "Resume existing CPU candidate cycle after BOTH Gate receipts")
