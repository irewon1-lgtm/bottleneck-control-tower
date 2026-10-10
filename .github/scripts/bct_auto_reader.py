"""Bounded real CPU reading for automatically collected main candidates.

An actual released qualification is required. Older reading receipts are
prerequisites, not fresh calls or new completions. No paid endpoint is used.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.request import urlopen

from bct.future_github import GitHubTransport
from bct.future_body import read_cached_body
from bct.future_local_reader import LocalCPUQuickReader
from bct.future_worker import run_worker
from bct.recovery_auto_reader import eligible
from bct.recovery_preservation import verify
from bct.recovery_restore import copy_preserved_caches
from bct_release_guard import verify_release
from bct_local_reader_probe import setup


def main():
    if os.environ.get('GITHUB_REF') != 'refs/heads/main' or os.environ.get('BCT_PUBLIC_REPOSITORY') != 'true':
        raise ValueError('released main on a standard public repository runner required')
    temporary = Path(os.environ['RUNNER_TEMP'])
    root = temporary/'automatic-local-reader'; root.mkdir(exist_ok=True)
    preserved = temporary/'operating-recovery-state'
    transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'], 'future-bottleneck-data', os.environ['GITHUB_TOKEN'])
    release = json.loads(Path('config/bct-operating-release.json').read_text())
    release_proof = verify_release(transport.requester, release, Path('.'))
    pilot = json.loads((preserved/'local-reader-probe.json').read_text())
    qualification = pilot.get('qualification_pilot') if pilot.get('mode') == 'DRAIN' else pilot
    if (not qualification or qualification.get('probe_status') != 'PASS'
            or qualification.get('actual_model_calls') != 61
            or [b.get('limit') for b in qualification.get('batches', [])] != [1, 10, 50]
            or any(b.get('status') != 'PASS' or len(b.get('results', [])) != b['limit']
                   for b in qualification['batches'])):
        raise ValueError('released actual cost-zero 1/10/50 qualification required')
    copy_preserved_caches(preserved, root)
    cache = root/'private-source-cache'
    # New collector cache files are accepted by content SHA, never filename alone.
    for path in sorted((temporary/'private-future-body-cache').glob('*.txt')):
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != path.stem:
            raise ValueError('new automatic source cache hash mismatch')
        destination = cache/path.name
        if destination.exists() and destination.read_bytes() != path.read_bytes():
            raise ValueError('new and preserved automatic source cache conflict')
        if not destination.exists(): shutil.copy2(path, destination)
    observations = {x['url']: x for x in map(json.loads,
        (preserved/'source-recovery-attempts.jsonl').read_text().splitlines())}
    baseline = json.loads(Path('config/bct-recovery-preservation.json').read_text())
    retained = json.loads((preserved/'recovery-preservation-seal.json').read_text())
    head = transport.head()
    c = transport.read_at('future-candidates.json', head)
    t = transport.read_at('future-tracking.json', head)
    verify(c.document, t.document, baseline); verify(c.document, t.document, retained)
    config = json.loads(Path('config/bct-local-reader.json').read_text())
    process = None
    returned = []
    def observe(value):
        value.update(run_id=os.environ['GITHUB_RUN_ID'])
        returned.append(value)
        with (root/'private-auto-native-execution.jsonl').open('a') as journal:
            journal.write(json.dumps(value, ensure_ascii=False)+'\n'); journal.flush(); os.fsync(journal.fileno())
    try:
        binary, weight, setup_receipt = setup(root, config)
        with (root/'automatic-reader-server.log').open('w') as server_log:
            process = subprocess.Popen([str(binary), '-m', str(weight), '--alias', config['alias'],
                '--host', '127.0.0.1', '--port', '8080', '-c', str(config['context_tokens']),
                '-t', '4', '-tb', '4', '-np', '1', '--no-context-shift', '--log-disable'],
                stdout=server_log, stderr=subprocess.STDOUT)
            deadline = time.monotonic()+120
            while True:
                if process.poll() is not None: raise RuntimeError('automatic local reader exited')
                try:
                    with urlopen('http://127.0.0.1:8080/health', timeout=2) as response:
                        if response.status == 200: break
                except OSError:
                    if time.monotonic() >= deadline: raise TimeoutError('automatic local reader startup deadline')
                    time.sleep(1)
            reader = LocalCPUQuickReader(setup_receipt, receipt_observer=observe)
            budget_held = set()
            def ready(item):
                if not eligible(item, observations, cache): return False
                body = read_cached_body(cache, item['body_sha256'])
                payload = {'document_id': item['document_id'], 'title': item.get('title'),
                    'body_sha256': item['body_sha256'], 'body_status': 'FULL',
                    'read_start': item['resume_at'], 'expected_read_end': len(body), 'body': body}
                if reader.input_characters(payload) > 12000:
                    budget_held.add((item['document_id'], item['body_sha256']))
                    return False  # Keep the full source pending, never truncate.
                return True
            report = run_worker(transport, 'future-candidates.json', 'future-tracking.json',
                reader=reader, cache_dir=cache, limit=5, max_input_chars=12000,
                source_eligible=ready,
                review_mode='API_REVIEW', input_rate=0, output_rate=0)
        after_head = transport.last_commit or transport.head()
        after_c = transport.read_at('future-candidates.json', after_head)
        after_t = transport.read_at('future-tracking.json', after_head)
        verify(after_c.document, after_t.document, baseline); verify(after_c.document, after_t.document, retained)
        report.update(run_id=os.environ['GITHUB_RUN_ID'], release_proof=release_proof,
            actual_returned_native_calls=len(returned), paid_fallback_calls=0,
            source_eligibility='EXACT_FULL_PROVENANCE_OR_VERIFIED_RECOVERED_SOURCE',
            input_budget_held_versions=[{'document_id': d, 'body_sha256': h} for d, h in sorted(budget_held)],
            prediction_performance='UNVERIFIED')
        (root/'automatic-reader-report.json').write_text(json.dumps(report, indent=2)+'\n')
        passed = (report.get('state') == 'FINISHED' and report.get('summary_saved') is True
            and not report.get('counts', {}).get('ERROR') and not report.get('counts', {}).get('BLOCKED')
            and report.get('duplicate_auto_reviews') == 0
            and not report.get('held_prior_version_states'))
        print(json.dumps({k: report.get(k) for k in ('run_id', 'state', 'counts', 'model_calls',
            'actual_returned_native_calls', 'completed_delta', 'paid_fallback_calls')}))
        return 0 if passed else 1
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == '__main__': raise SystemExit(main())
