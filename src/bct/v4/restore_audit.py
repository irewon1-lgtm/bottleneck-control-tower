"""Read-only latest-checkpoint restart and immediately prior-history proof.

Uses the existing authenticated archive reader and typed restore. It cannot
publish, initialize a replacement state, or fall back to an older Git state.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

from . import release_archive as archive
from .store import file_sha


def audit_checkpoint(monthly, checkpoint, current_database, work):
    checkpoint, current_database, work = map(Path, (checkpoint, current_database, work))
    if work.exists():
        raise ValueError('RESTORE_AUDIT_REFUSE_OVERWRITE')
    cursor = monthly.head()
    proof = json.loads((checkpoint / 'checkpoint.json').read_text())
    if (cursor is None or cursor['sqlite_sha256'] != proof['sqlite_sha256']
            or file_sha(current_database) != cursor['sqlite_sha256']):
        raise ValueError('RESTORE_AUDIT_CURRENT_HEAD_MISMATCH')
    store = monthly.store(cursor['tag'])
    manifest, manifest_hash = archive.load_commit(store, cursor['generation'], monthly.password)
    if manifest_hash != cursor['manifest_sha256'] or manifest['proof'] != proof:
        raise ValueError('RESTORE_AUDIT_CURRENT_MANIFEST_MISMATCH')
    before_assets = sorted((x['id'], x['name'], x['size']) for x in store.assets())
    work.mkdir(parents=True, exist_ok=False)
    # A fresh Python interpreter reopens the actual downloaded checkpoint. The
    # child needs no network or account credentials, including inherited ones.
    removed = {'BCT_V4_PRIVATE_STATE_TOKEN', 'BCT_V4_STATE_PASSPHRASE', 'GH_TOKEN', 'GITHUB_TOKEN'}
    environment = {k: v for k, v in os.environ.items() if k not in removed}
    code = (
        'import json,os,sys;from bct.v4.quantitative_private import restore;'
        'result=restore(sys.argv[1],sys.argv[2]);'
        'print(json.dumps({"proof":result,"pid":os.getpid(),'
        '"private_credentials_present":any(os.environ.get(k) for k in '
        '["BCT_V4_PRIVATE_STATE_TOKEN","BCT_V4_STATE_PASSPHRASE","GH_TOKEN","GITHUB_TOKEN"])}))'
    )
    child = subprocess.run([sys.executable, '-c', code, str(checkpoint), str(work / 'new-process')],
                           capture_output=True, text=True, env=environment, timeout=120)
    if child.returncode:
        raise ValueError('RESTORE_AUDIT_NEW_PROCESS_FAILED')
    restarted = json.loads(child.stdout)
    if (restarted['pid'] == os.getpid() or restarted['private_credentials_present']
            or restarted['proof']['sqlite_sha256'] != cursor['sqlite_sha256']
            or restarted['proof']['tables'] != 8):
        raise ValueError('RESTORE_AUDIT_NEW_PROCESS_PROOF_MISMATCH')
    previous = {'status': 'NOT_APPLICABLE_INITIAL_GENERATION'}
    if cursor['generation'] > 0:
        generation = cursor['generation'] - 1
        prior, prior_hash = archive.load_commit(store, generation, monthly.password)
        if prior_hash != manifest['previous_manifest_sha256']:
            raise ValueError('RESTORE_AUDIT_PREVIOUS_MANIFEST_MISMATCH')
        restored = archive.restore(store, generation, monthly.password, work / 'previous-checkpoint',
                                   expected_sqlite_sha256=prior['proof']['sqlite_sha256'])
        archive.materialize_verified(work / 'previous-checkpoint', work / 'previous.sqlite3')
        archive.require_append_only(work / 'previous.sqlite3', work / 'new-process/v4.sqlite3')
        previous = {'status': 'PASS', 'generation': generation, 'manifest_sha256': prior_hash,
                    'restored': restored, 'existing_history_preserved': True,
                    'previous_event_rows': prior['proof']['tables']['events']['rows'],
                    'current_event_rows': proof['tables']['events']['rows']}
    after_assets = sorted((x['id'], x['name'], x['size']) for x in store.assets())
    if monthly.head() != cursor or after_assets != before_assets:
        raise ValueError('RESTORE_AUDIT_REMOTE_STATE_CHANGED_DURING_READ')
    if file_sha(current_database) != cursor['sqlite_sha256']:
        raise ValueError('RESTORE_AUDIT_ORIGINAL_LOCAL_DATABASE_CHANGED')
    return {'status': 'PASS_READ_ONLY_NEW_PROCESS_AND_PREVIOUS_HISTORY', 'storage': cursor,
            'new_process_restore': restarted['proof'], 'child_pid': restarted['pid'],
            'child_private_credentials_removed': True, 'previous_generation': previous,
            'ciphertext_and_plaintext_hashes': [{k: item[k] for k in
                ('name', 'id', 'bytes', 'ciphertext_sha256', 'plaintext_sha256')}
                for item in [manifest['base'], *manifest['patches']]],
            'remote_asset_inventory_unchanged': True, 'remote_head_unchanged': True,
            'remote_writes': 0, 'source_HTTP_requests': 0, 'AI_calls': 0, 'CPU_windows': 0,
            'source_originals_restored': False, 'fallback_to_legacy_git': False}
