"""Recover one explicitly authorized sealed result, without repeating inference.

This is a bounded repair of run43060982183's failed writer. It is not a generic
cache importer. Original producer identities and parent-CAS are never rewritten.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from . import cpu_operations as op, cpu_resume as resume, private_state as private

RUN = 43060982183
ATTEMPT = 1
WORKFLOW_SHA = '41b1f74931f86f9c6d9f243be741efa0bfe68a04'
EXECUTION_SHA = '58817b1fed0791e2a4ac591b1e684cab8e7f3b61'
PARENT = '662060fbc29eacce875bd6fff7910cdb5fd72745'
CACHE_ID = 10365971981
CACHE_BYTES = 1064174
CACHE_KEY = f'v4-cpu-private-result-{RUN}-{ATTEMPT}'
PATH = '.github/workflows/v4-cpu-private-research.yml'
JOBS = {'research': (130663160270, 'success'),
        'runtime-verify': (130663163145, 'skipped'), 'publish': (130663731583, 'failure')}


def verify(run_id, attempt, *, read=None):
    """Authenticate the exact stopped producer and current immutable cache entry."""
    if type(run_id) is not int or type(attempt) is not int or (run_id, attempt) != (RUN, ATTEMPT):
        raise ValueError('EXACT_AUTHORIZED_RESULT_RECOVERY_REQUIRED')
    deadline = time.monotonic() + 45
    if read is None:
        def read(path):
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise ValueError('RESULT_METADATA_DEADLINE')
            result = subprocess.run(['gh', 'api', path], capture_output=True,
                                    timeout=min(8, remaining))
            if result.returncode or len(result.stdout) > 2 * 1024**2:
                raise ValueError('RESULT_METADATA_UNAVAILABLE')
            try: return json.loads(result.stdout)
            except ValueError: raise ValueError('RESULT_METADATA_INVALID') from None
    prefix = 'repos/' + private.PUBLIC_REPO
    path = prefix + '/actions/runs/' + str(RUN)
    def identity(value):
        if (type(value.get('id')) is not int or type(value.get('run_attempt')) is not int
                or value.get('id') != RUN or value.get('run_attempt') != ATTEMPT
                or value.get('event') != 'workflow_dispatch' or value.get('head_branch') != 'main'
                or value.get('head_sha') != WORKFLOW_SHA or value.get('path') != PATH
                or value.get('head_repository', {}).get('full_name') != private.PUBLIC_REPO
                or value.get('status') != 'completed' or value.get('conclusion') != 'failure'):
            raise ValueError('RESULT_PRODUCER_IDENTITY_OR_ATTEMPT')
        return {k: value[k] for k in ('id', 'run_attempt', 'event', 'head_branch', 'head_sha', 'path', 'status', 'conclusion')}
    initial = identity(read(path))
    if identity(read(path + '/attempts/' + str(ATTEMPT))) != initial:
        raise ValueError('RESULT_PRODUCER_ATTEMPT_CHANGED')
    jobs = read(path + '/attempts/' + str(ATTEMPT) + '/jobs?per_page=100')
    entries = jobs.get('jobs', [])
    if jobs.get('total_count') != len(JOBS) or len(entries) != len(JOBS):
        raise ValueError('RESULT_PRODUCER_JOBS_INCOMPLETE')
    seen = set()
    for row in entries:
        name = row.get('name')
        if (name not in JOBS or name in seen or row.get('run_id') != RUN
                or row.get('status') != 'completed' or (row.get('id'), row.get('conclusion')) != JOBS[name]):
            raise ValueError('RESULT_PRODUCER_JOBS_DIFFER')
        seen.add(name)
    caches = read(prefix + '/actions/caches?key=' + CACHE_KEY + '&ref=refs%2Fheads%2Fmain')
    entries = caches.get('actions_caches', [])
    if caches.get('total_count') != 1 or len(entries) != 1:
        raise ValueError('RESULT_EXACT_CACHE_UNAVAILABLE')
    entry = entries[0]
    if (entry.get('id'), entry.get('key'), entry.get('ref'), entry.get('size_in_bytes')) != (
            CACHE_ID, CACHE_KEY, 'refs/heads/main', CACHE_BYTES):
        raise ValueError('RESULT_CACHE_IDENTITY_OR_SIZE')
    if identity(read(path)) != initial: raise ValueError('RESULT_PRODUCER_CHANGED_AFTER_CHECK')
    return {'status': 'PASS_EXACT_FAILED_RESEARCH_RESULT_METADATA', 'original_run_id': RUN,
            'original_attempt': ATTEMPT, 'original_workflow_sha': WORKFLOW_SHA,
            'original_execution_sha': EXECUTION_SHA, 'original_expected_parent': PARENT,
            'cache_id': CACHE_ID, 'cache_key': CACHE_KEY, 'cache_bytes': CACHE_BYTES,
            'model_loads': 0, 'new_CPU_windows': 0}


def authenticate(run_id, attempt, packet, destination, passphrase, *, read=None):
    """Retain authenticated original readings; publish still requires unchanged CAS."""
    proof = verify(run_id, attempt, read=read)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink(): raise ValueError('RESULT_RECOVERY_DESTINATION_EXISTS')
    with tempfile.TemporaryDirectory(prefix='bct-failed-result-') as temporary:
        root = Path(temporary); staged = root/'checkpoint'
        private.unseal(packet, staged, passphrase)
        parent = json.loads((staged/'parent.json').read_text())
        if parent != {'expected_parent': PARENT, 'producer_run_id': str(RUN),
                      'producer_attempt': str(ATTEMPT), 'producer_job': 'research'}:
            raise ValueError('RESULT_ENCRYPTED_PRODUCER_OR_PARENT_MISMATCH')
        restored = op.restore(staged, root/'restored')
        ledger = resume.Ledger(root/'restored')
        try:
            safe = resume.audit(ledger)
            observations = resume.rows(ledger.db, 'CPU_OPERATION_OBSERVATION')
            observation = observations[-1] if observations else {}
            expected = {'consumer_run_id': RUN, 'consumer_attempt': ATTEMPT,
                        'execution_mode': 'MANUAL_ACTUAL_INPUT', 'scheduled': False,
                        'new_CPU_windows': 24, 'successful_new_CPU_windows': 24,
                        'actually_read_new_characters': 4114, 'new_analysis_results': 6,
                        'analysis_runtime_failures': 0, 'complete_analyzed_new_CPU_documents': 0,
                        'seven_day_start': None}
            if any(k not in observation or type(observation[k]) is not type(v) or observation[k] != v
                   for k, v in expected.items()):
                raise ValueError('RESULT_SAVED_OBSERVATION_MISMATCH')
            original = {'run_id': RUN, 'run_attempt': ATTEMPT,
                        'execution_sha': EXECUTION_SHA, 'workflow_sha': WORKFLOW_SHA}
            windows = [row for row in resume.rows(ledger.db, 'CPU_RESUME_WINDOW')
                       if row.get('inference_producer', {}).get('run_id') == RUN]
            if len(windows) != 24 or any(row.get('inference_producer') != original for row in windows):
                raise ValueError('RESULT_SAVED_WINDOW_PRODUCER_MISMATCH')
        finally: ledger.close()
        destination.mkdir(parents=True, exist_ok=False)
        for name in ('checkpoint.json', 'checkpoint.sqlite3.gz', 'parent.json'):
            shutil.copy2(staged/name, destination/name)
    return {**proof, 'status': 'PASS_AUTHENTICATED_SAVED_RESULT_NO_REREADING',
            'sqlite_sha256': restored['sqlite_sha256'], 'restored_tables': restored['tables'],
            'restored_original_new_CPU_windows': 24, 'restored_original_read_characters': 4114,
            'source_free_audit': safe['status'], 'private_writes': 0,
            'original_inference_producer_unchanged': True, 'expected_parent_CAS_unchanged': True}
