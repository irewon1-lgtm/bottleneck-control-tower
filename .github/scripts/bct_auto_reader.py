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
from bct.future_worker import run_worker, _runs
from bct.recovery_auto_reader import eligible
from bct.recovery_preservation import verify, quarantine_changed_version_judgments, digest
from bct.recovery_restore import copy_preserved_caches
from bct.recovery_extent_retry import extent_retry_policy
from bct_release_guard import verify_release
from bct_local_reader_probe import setup



def assess_current_cpu_batch(report, *, expected_reads=5):
    """Evaluate THIS batch; keep previously blocked versions quarantined.

    run_worker records historical ERROR/BLOCKED holds without selecting or
    changing them. Their mere presence is not a failure of current successful
    CPU reads. RUNNING or unknown hold states still fail closed.
    """
    held = report.get('held_prior_version_states')
    safe_historical_holds = (isinstance(held, dict) and all(
        state in ('ERROR', 'BLOCKED') and type(number) is int and number >= 0
        for state, number in held.items()))
    results = report.get('results')
    unique_current_successes = (
        isinstance(results, list) and len(results) == expected_reads
        and all(isinstance(row, dict) and row.get('state') == 'SUCCESS'
                and row.get('document_id') and row.get('body_sha256')
                for row in results)
        and len({(row['document_id'], row['body_sha256']) for row in results})
            == expected_reads)
    return {
        'finished': report.get('state') == 'FINISHED',
        'current_batch_completed': (report.get('attempted') == expected_reads
            and report.get('completed_delta') == expected_reads
            and report.get('counts') == {'SUCCESS': expected_reads}
            and unique_current_successes),
        'native_cpu_receipts': (report.get('model_calls') == expected_reads
            and report.get('actual_returned_native_calls') == expected_reads),
        'summary_saved': report.get('summary_saved') is True,
        'no_duplicate_auto_reviews': report.get('duplicate_auto_reviews') == 0,
        'source_records_unchanged': report.get('source_records_unchanged') is True,
        'historical_judgments_intact': (report.get('historical_judgment_holds') == 0
            and report.get('historical_judgment_state') == 'PASS'),
        'prior_failures_still_held': safe_historical_holds,
        'released_code_proof': (isinstance(report.get('release_proof'), dict)
            and report['release_proof'].get('status') == 'PASS'),
        'cost_zero': report.get('paid_fallback_calls') == 0,
    }


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
    verify(c.document, t.document, baseline)
    # The retained seal can be older than later intake. Report every changed
    # historic judgment, but do not delete or silently approve any version.
    # The unchanged identities, old reviews and completion records remain
    # strictly pinned by verify() before running the native reader.
    retained_guard, historic_holds = quarantine_changed_version_judgments(
        c.document, t.document, retained)
    held_versions={(r['document_id'],r['body_sha256']) for r in historic_holds}
    original_held_digests={(r['document_id'],r['body_sha256']):r['observed_record_sha256']
                           for r in historic_holds}
    if historic_holds:
        (root/'historical-version-holds.json').write_text(
            json.dumps({'state':'PARTIAL_UNVERIFIED_HISTORY','records':historic_holds},
                       ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'integrity_state':'PARTIAL_UNVERIFIED_HISTORY',
                          'quarantined_versions':len(historic_holds)}),flush=True)
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
            # The standard CPU runner needed 140–156s for successful bodies;
            # the longer exact FULL sources exceeded the former 180s deadline.
            # Keep input/output/context unchanged; grant a bounded 600s read.
            reader = LocalCPUQuickReader(setup_receipt, timeout=600, receipt_observer=observe)
            retries = json.loads(Path('config/bct-cpu-timeout-recovery.json').read_text())
            retry_keys = {(r['document_id'], r['body_sha256']) for r in retries['versions']}
            needed = any(r.get('state') == 'ERROR' and r.get('reason') == 'TimeoutError'
                and r.get('run_id') == retries['worker_id']
                and (r.get('document_id'), r.get('body_sha256')) in retry_keys
                for r in _runs(t.document).values())
            if needed:
                old_run = transport.requester('GET', '/actions/runs/' + str(retries['run_id']))
                old_artifact = transport.requester('GET', '/actions/artifacts/' + str(retries['artifact_id']))
                if (old_run['status'] != 'completed' or old_run['head_sha'] != retries['code_sha']
                        or old_artifact['workflow_run']['id'] != retries['run_id']
                        or old_artifact.get('digest') != 'sha256:' + retries['artifact_sha256']):
                    raise ValueError('stopped timeout owner and archived failure proof required')
            else:
                retry_keys = set()  # Resolved history is not a future artifact dependency.
            def retry_timeout(item, previous):
                return (previous.get('state') == 'ERROR' and previous.get('reason') == 'TimeoutError'
                        and previous.get('run_id') == retries['worker_id']
                        and (item['document_id'], item['body_sha256']) in retry_keys)
            extent_retry=extent_retry_policy(transport.requester,
                json.loads(Path('config/bct-native-extent-recovery.json').read_text()),
                _runs(t.document).values(),cache)
            def retry_confirmed(item,previous):
                return retry_timeout(item,previous) or extent_retry(item,previous)
            budget_held = set()
            def ready(item):
                # Do not let an altered historical judgment be read or promoted.
                # Old sealed judgments remain available for a separate
                # content-addressed, trusted-generation repair.
                if (item['document_id'],item.get('body_sha256')) in held_versions:
                    return False
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
                source_eligible=ready, retry_failed=retry_confirmed,
                review_mode='API_REVIEW', input_rate=0, output_rate=0)
        after_head = transport.last_commit or transport.head()
        after_c = transport.read_at('future-candidates.json', after_head)
        after_t = transport.read_at('future-tracking.json', after_head)
        verify(after_c.document, after_t.document, baseline)
        verify(after_c.document, after_t.document, retained_guard)
        for (document_id, body_sha256), old_digest in original_held_digests.items():
            current=after_c.document.get('results',{}).get(document_id,{}).get(
                'versions',{}).get(body_sha256)
            if digest(current)!=old_digest:
                raise ValueError('quarantined historical judgment changed during automatic reading')
        report.update(run_id=os.environ['GITHUB_RUN_ID'], release_proof=release_proof,
            actual_returned_native_calls=len(returned), paid_fallback_calls=0,
            source_eligibility='EXACT_FULL_PROVENANCE_OR_VERIFIED_RECOVERED_SOURCE',
            input_budget_held_versions=[{'document_id': d, 'body_sha256': h} for d, h in sorted(budget_held)],
            prediction_performance='UNVERIFIED',
            historical_judgment_holds=len(historic_holds),
            historical_judgment_state='PARTIAL_UNVERIFIED_HISTORY' if historic_holds else 'PASS',
            full_clean_status='BLOCKED_HISTORICAL_DRIFT' if historic_holds else 'ELIGIBLE_FOR_VERIFICATION')
        (root/'automatic-reader-report.json').write_text(json.dumps(report, indent=2)+'\n')
        checks = assess_current_cpu_batch(report)
        passed = all(checks.values())
        # Report individual release reasons. Historical ERROR/BLOCKED holds stay
        # visible but do not falsely invalidate five verified current successes.
        print(json.dumps({
            'run_id': report.get('run_id'), 'state': report.get('state'),
            'counts': report.get('counts'),
            'model_calls': report.get('model_calls'),
            'actual_returned_native_calls': report.get('actual_returned_native_calls'),
            'completed_delta': report.get('completed_delta'),
            'held_prior_version_states': report.get('held_prior_version_states'),
            'cpu_batch_gate': 'PASS' if passed else 'FAIL', 'checks': checks,
            'paid_fallback_calls': report.get('paid_fallback_calls'),
        }, sort_keys=True), flush=True)
        return 0 if passed else 1
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == '__main__': raise SystemExit(main())
