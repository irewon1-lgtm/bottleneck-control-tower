"""Gate 7 reads fresh main Actions, immutable sidecars and the real Pages DOM.

The caller must supply actual candidate and deployment run IDs. This verifier
does not promote code, resume a workflow, dispatch a deployment, or invent a
FULL receipt when those operations have not happened.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from bct.future_github import GitHubTransport, _raw
from bct.recovery_operations import verify_ui, verify_workflow
from bct.recovery_preservation import verify
from bct.recovery_queue import project


def execute(root, candidate_run, pages_run):
    checkpoint = root/'checkpoint.json'
    report = json.loads(checkpoint.read_text())
    proof = {'status': 'FAIL', 'actual_execution': True,
             'execution_id': uuid.uuid4().hex, 'run_id': os.environ['GITHUB_RUN_ID'],
             'started_at': datetime.now(timezone.utc).isoformat()}
    try:
        if any(report.get('gate'+str(i)) != 'PASS' for i in range(7)):
            raise RuntimeError('actual Gates 0 through 6 required before operating publication')
        if not candidate_run or not pages_run:
            raise RuntimeError('fresh actual automatic candidate and Pages run IDs required')
        transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'],
            'future-bottleneck-data', os.environ['GITHUB_TOKEN'])
        request = transport.requester
        main = request('GET', '/git/ref/heads/main')['object']['sha']
        app, _ = transport._root('docs/app.js', main)
        if app != Path('docs/app.js').read_bytes():
            raise RuntimeError('main Pages code differs from code validated in this recovery cycle')
        for key, run_id, job, steps, automatic in (
            ('candidate_execution', candidate_run, 'candidates', [
                'Run full regression suite',
                'Read existing canonical database and prior candidate sidecar',
                'Screen article bodies without any AI API',
                'Publish candidate sidecar only'], True),
            ('pages_execution', pages_run, 'publish', [
                'Read canonical data branch and generate UI-only snapshot',
                'Publish static UI'], False)):
            run = request('GET', '/actions/runs/'+str(run_id))
            jobs = request('GET', '/actions/runs/'+str(run_id)+'/jobs')['jobs']
            proof[key] = verify_workflow(run, jobs, head_sha=main,
                required_job=job, required_steps=steps, not_before=report['started_at'],
                automatic=automatic)
        head = transport.head()
        candidates = transport.read_at('future-candidates.json', head)
        tracking = transport.read_at('future-tracking.json', head)
        for baseline in (json.loads(Path('config/bct-recovery-preservation.json').read_text()),
                         json.loads((root/'recovery-preservation-seal.json').read_text())):
            verify(candidates.document, tracking.document, baseline)
        versions = json.loads((root/'source-recovery-versions.json').read_text())
        observations = {x['url']: x for x in map(json.loads,
            (root/'source-recovery-attempts.jsonl').read_text().splitlines())}
        queue = project(candidates.document, tracking.document, versions, observations,
                        root/'private-source-cache')
        stored = candidates.document['summary']['recovery_queue']
        if (stored['counts'] != queue['counts']
                or str(stored['generation_run_id']) != str(candidate_run)):
            raise ValueError('latest automatic candidate run did not save the actual operating queue')
        expected = {
            'url': 'https://irewon1-lgtm.github.io/bottleneck-control-tower/',
            'app_sha256': hashlib.sha256(app).hexdigest(),
            'source_document_sha256': hashlib.sha256(_raw(candidates.document)).hexdigest(),
            'generation_run_id': str(candidate_run), 'counts': queue['counts']}
        (root/'operating-pages-expected.json').write_text(json.dumps(expected, indent=2)+'\n')
        subprocess.run(['node', '.github/scripts/bct_pages_probe.cjs',
            str(root/'operating-pages-expected.json'), str(root/'operating-pages-receipt.json')], check=True)
        ui = json.loads((root/'operating-pages-receipt.json').read_text())
        proof['ui'] = verify_ui(ui, queue, app_sha256=expected['app_sha256'],
            source_sha256=expected['source_document_sha256'], generation_run_id=candidate_run)
        if transport.head() != head or request('GET', '/git/ref/heads/main')['object']['sha'] != main:
            raise RuntimeError('operating generation changed during publication verification; restart Stage 0')
        proof.update(status='PASS', main_sha=main, sidecar_sha=head,
            queue_counts=queue['counts'], failed_versions_preserved=len(versions))
        report.update(stage=7, status='PASS', gate7='PASS', next_stage='FULL',
            full_clean_status='BLOCKED', full_clean_reason='FULL_EXECUTOR_AND_THREE_INDEPENDENT_EXECUTIONS_REQUIRED')
        return 0
    except Exception as exc:
        proof.update(error_type=type(exc).__name__)
        if type(exc) in (ValueError, RuntimeError):
            proof['failure_code'] = str(exc)
        report.update(stage=7, status='FAIL', gate7='FAIL', full_clean_status='BLOCKED',
            resume_condition='Complete the recorded real publication/verification requirement; restart from Stage 0')
        return 1
    finally:
        proof['finished_at'] = datetime.now(timezone.utc).isoformat()
        (root/'operating-publication-verification.json').write_text(json.dumps(proof, indent=2)+'\n')
        checkpoint.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({k: proof.get(k) for k in ('status', 'main_sha', 'sidecar_sha', 'error_type')}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate-run', type=int, required=True)
    parser.add_argument('--pages-run', type=int, required=True)
    args = parser.parse_args()
    return execute(Path(os.environ['RUNNER_TEMP'])/'bct-recovery', args.candidate_run, args.pages_run)


if __name__ == '__main__':
    raise SystemExit(main())
