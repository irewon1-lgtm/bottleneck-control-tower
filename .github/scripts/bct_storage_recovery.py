"""Gate 0 then Gate 1 on a real runner; no source/review/forecast promotions."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import traceback
from datetime import datetime, timezone

from bct.future_github import GitHubTransport, GitHubRequestError, _raw
from bct.future_review import queue_summary
from bct.future_store import store_patch
from bct.future_worker import _runs, _run_patch
from bct.recovery_preservation import verify as verify_preservation


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    root = Path(os.environ['RUNNER_TEMP']) / 'bct-recovery'
    root.mkdir(exist_ok=True)
    report = {'version': 1, 'status': 'BLOCKED', 'stage': 0,
              'run_id': os.environ['GITHUB_RUN_ID'],
              'code_sha': os.environ['GITHUB_SHA'], 'started_at': datetime.now(timezone.utc).isoformat(),
              'prediction_performance': 'UNVERIFIED', 'live_early': 0}
    try:
        refs = {}
        for branch in ('main', 'data', 'future-bottleneck-data'):
            line = command('git', 'ls-remote', 'origin', 'refs/heads/' + branch)
            if not line:
                raise RuntimeError('required branch missing: ' + branch)
            refs[branch] = line.split()[0]
            subprocess.run(['git', 'fetch', '--no-tags', 'origin', refs[branch]], check=True)
        report['baseline_heads'] = refs
        database = root / 'canonical.sqlite3'
        database.write_bytes(subprocess.check_output(['git', 'show', refs['data'] + ':canonical.sqlite3']))
        con = sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True)
        if con.execute('pragma integrity_check').fetchall() != [('ok',)]:
            raise RuntimeError('canonical database integrity failure')
        con.close()
        report['database_sha256'] = hashlib.sha256(database.read_bytes()).hexdigest()
        transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'], 'future-bottleneck-data', os.environ['GITHUB_TOKEN'])
        original = transport.read('future-candidates.json')
        tracking = transport.read('future-tracking.json')
        preservation_baseline=json.loads(Path('config/bct-recovery-preservation.json').read_text())
        report['identity_preservation']=verify_preservation(original.document,tracking.document,preservation_baseline)
        before = queue_summary(original.document, tracking.document)
        # The immutable repair baseline includes these records, regardless of
        # subsequent legitimate inflow/recovery. Never initialize over them.
        if before['completed_documents'] < 184 or before['preserved_versions'] < 4023:
            raise RuntimeError('baseline records missing')
        failures = [r for r in _runs(tracking.document).values()
                    if isinstance(r, dict) and r.get('type') == 'queue_resolution' and r.get('state') == 'FAIL']
        identities = {(r['document_id'], r.get('body_sha256') or r.get('source_version')) for r in failures}
        if len(identities) < 3696:
            raise RuntimeError('failure history missing')
        (root / 'baseline-candidates.json').write_bytes(_raw(original.document))
        (root / 'baseline-tracking.json').write_bytes(_raw(tracking.document))
        report.update(stage=1, gate0='PASS', baseline_queue=before,
                      tracked_failed_versions=len(identities))
        # A separate branch tests real token permissions and both sidecar paths.
        probe_branch = 'ops/bct-storage-probe-' + os.environ['GITHUB_RUN_ID']
        transport.requester('POST', '/git/refs', {'ref': 'refs/heads/' + probe_branch, 'sha': refs['future-bottleneck-data']})
        probe = GitHubTransport(os.environ['GITHUB_REPOSITORY'], probe_branch, os.environ['GITHUB_TOKEN'])
        candidate_test = store_patch(probe, 'future-candidates.json', owner='collection',
            patch={'summary': {'storage_probe_run': report['run_id']}}, operation_id='probe-' + report['run_id'])
        if candidate_test.status != 'APPLIED':
            raise RuntimeError('candidate probe pending: ' + str(candidate_test.reason))
        probe_tracking = probe.read('future-tracking.json').document
        review_test = store_patch(probe, 'future-tracking.json', owner='review',
            patch=_run_patch({'runs': {'storage-probe-' + report['run_id']: {'type': 'storage_probe', 'state': 'PASS',
                     'actual_execution': True, 'run_id': report['run_id']}}}, probe_tracking),
            prepared_document=probe_tracking, operation_id='probe-review-' + report['run_id'])
        if review_test.status != 'APPLIED':
            raise RuntimeError('tracking probe pending: ' + str(review_test.reason))
        if probe.read('future-candidates.json').document['summary']['storage_probe_run'] != report['run_id']:
            raise RuntimeError('probe readback failed')
        report['probe_branch'] = probe_branch
        report['probe_commit'] = probe.head()
        # Re-read production after the probe; use the latest preserving patch.
        original = transport.read('future-candidates.json')
        tracking = transport.read('future-tracking.json')
        candidates_path, tracking_path = root / 'future-candidates.json', root / 'future-tracking.json'
        candidates_path.write_bytes(_raw(original.document));tracking_path.write_bytes(_raw(tracking.document))
        subprocess.run(['python', '.github/scripts/future_queue_snapshot.py', '--candidates', str(candidates_path),
                        '--tracking', str(tracking_path), '--output-dir', str(root)], check=True,
                       stdout=(root / 'queue-projection.log').open('w'))
        final = json.loads(candidates_path.read_text())
        # The local script composes owned bundle/queue patches. Publish their
        # combined final state once, so no intermediate projection is visible.
        if set(final['results']) != set(original.document['results']):
            raise RuntimeError('candidate set changed during storage repair')
        if final['results'] != original.document['results']:
            raise RuntimeError('source records changed during storage repair')
        transport.write('future-candidates.json', final, original.sha)
        confirmed = transport.read('future-candidates.json')
        if confirmed.document != final:
            raise RuntimeError('production generation readback differs')
        if transport.read('future-tracking.json').document != tracking.document:
            raise RuntimeError('tracking changed during storage repair')
        after = queue_summary(confirmed.document, tracking.document)
        for key in ('completed_documents', 'failed_versions', 'failure_reasons', 'preserved_versions'):
            if before[key] != after[key]:
                raise RuntimeError('storage repair changed queue baseline: ' + key)
        report.update(status='PASS', gate1='PASS', publication_commit=transport.last_commit,
                      candidate_blob_sha=confirmed.sha, after_queue=after,
                      candidate_sha256=hashlib.sha256(_raw(final)).hexdigest(),
                      prior_403_cause='UNCLASSIFIED_OLD_RESPONSE_NOT_RETAINED',
                      classification_tests='PRIMARY/SECONDARY_RATE_LIMIT, ACCESS_DENIED, absent header covered',
                      next_stage=2, resume_condition='Gate 2 requires real source acquisition; candidate schedule remains paused')
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc),
                      resume_condition='Fix or change the recorded blocker; rerun from Gate 0, never unchanged retries')
        if isinstance(exc, GitHubRequestError):
            report['github_response'] = exc.details
        # Local trace identifies code lines and excludes request headers/body.
        (root / 'failure-trace.log').write_text(traceback.format_exc())
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        (root / 'checkpoint.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({k: report.get(k) for k in ('status', 'stage', 'gate0', 'gate1', 'error', 'publication_commit')}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
