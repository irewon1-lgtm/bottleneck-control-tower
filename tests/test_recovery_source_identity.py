"""A receipt-only HEAD change cannot cause another identical source ERROR."""
import subprocess

from bct import recovery_restore as restore


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL, text=True).strip()


def repository(root, monkeypatch):
    root.mkdir(); git(root, 'init'); git(root, 'config', 'user.email', 'fixture@example.org')
    git(root, 'config', 'user.name', 'Synthetic source identity fixture')
    monkeypatch.setattr(restore, 'SOURCE_ACCESS_PATHS', ('source.py',))
    (root/'source.py').write_text('source_adapter = 1\n')
    git(root, 'add', 'source.py'); git(root, 'commit', '-m', 'source bytes')
    return git(root, 'rev-parse', 'HEAD')


def test_changed_receipt_commit_reuses_actual_prior_source_code_identity(tmp_path, monkeypatch):
    root = tmp_path/'repo'; old = repository(root, monkeypatch)
    (root/'receipt.json').write_text('{"new_actual_gate_receipt":true}\n')
    git(root, 'add', 'receipt.json'); git(root, 'commit', '-m', 'receipt only')
    assert old != git(root, 'rev-parse', 'HEAD')
    result = restore.source_retry_identity({'code_sha': old}, root)
    assert result['comparison'] == 'SAME' and not result['retry_errors']


def test_changed_source_adapter_authorizes_existing_bounded_error_retry(tmp_path, monkeypatch):
    root = tmp_path/'repo'; old = repository(root, monkeypatch)
    (root/'source.py').write_text('source_adapter = 2\n')
    result = restore.source_retry_identity({'code_sha': old}, root)
    assert result['comparison'] == 'CHANGED' and result['retry_errors']


def test_saved_stable_fingerprint_needs_no_old_commit_fetch(tmp_path, monkeypatch):
    root = tmp_path/'repo'; repository(root, monkeypatch)
    prior = restore.source_access_fingerprint(root)
    result = restore.source_retry_identity({'code_sha': 'f'*40, 'source_access_code_sha256': prior}, root)
    assert result['comparison'] == 'SAME' and result['method'] == 'checkpoint_fingerprint'


def test_missing_prior_code_is_unknown_never_a_retry_permission(tmp_path, monkeypatch):
    root = tmp_path/'repo'; repository(root, monkeypatch)
    result = restore.source_retry_identity({'code_sha': 'f'*40}, root)
    assert result['comparison'] == 'UNKNOWN' and not result['retry_errors']
