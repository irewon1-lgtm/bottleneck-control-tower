"""Bind the CLEAN engine to real commands and one distinct GitHub runner cycle.

Restore/installation and the fixed 230-source corpus are workflow prerequisites.
Publication requires actual fresh run IDs. Missing operating claim evidence or
publication is BLOCKED; neither a fixture nor an old successful CI can replace it.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from bct.future_github import GitHubTransport
from bct.recovery_engine import run
from bct.recovery_preservation import verify


def load_current(path, run_id):
    value = json.loads(path.read_text())
    if str(value.get('run_id')) != str(run_id):
        raise ValueError('prior execution receipt cannot satisfy this runner stage')
    return value


def main():
    root = Path(os.environ['RUNNER_TEMP'])/'bct-recovery'
    root.mkdir(exist_ok=True)
    run_id = os.environ['GITHUB_RUN_ID']
    transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'],
        'future-bottleneck-data', os.environ['GITHUB_TOKEN'])
    observed_main = transport.requester('GET', '/git/ref/heads/main')['object']['sha']
    files = sorted({*Path('src').rglob('*.py'), *Path('tests').rglob('*.py'),
                    *Path('tests').rglob('*.js'), *Path('.github/scripts').glob('*.py'),
                    *Path('.github/scripts').glob('*.cjs'), *Path('.github/workflows').glob('*.yml'),
                    *Path('config').glob('*.json'), *Path('docs').glob('*.js')})
    request = json.loads(Path('.github/bct-recovery-request.json').read_text())
    fingerprint = hashlib.sha256(json.dumps({
        'code_files': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
        'observed_main': observed_main,
        # Resume artifact IDs/hashes are new checkpoints, not changed code.
        'reader_batch_limit': request.get('reader_batch_limit', 50)}, sort_keys=True).encode()).hexdigest()
    external_runs = {}
    for name in ('BCT_CANDIDATE_RUN_ID', 'BCT_PAGES_RUN_ID'):
        selected = os.environ.get(name)
        if selected:
            value = transport.requester('GET', '/actions/runs/'+str(int(selected)))
            external_runs[name] = {key: value.get(key) for key in
                ('id', 'head_sha', 'event', 'status', 'conclusion', 'created_at')}
    condition = hashlib.sha256(json.dumps(external_runs, sort_keys=True).encode()).hexdigest()
    def receipt(stage, status, paths, reason=None):
        return {'status': status, 'actual_execution': True, 'criteria_met': status == 'PASS',
            'execution_id': run_id+'-'+str(stage)+'-'+uuid.uuid4().hex,
            'evidence': [{'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                         for path in paths if path.exists()],
            'reason': reason, 'observed_at': datetime.now(timezone.utc).isoformat()}
    def command(name):
        log = root/('operating-command-'+name+'.log')
        with log.open('w') as stream:
            code = subprocess.run([sys.executable, '.github/scripts/'+name+'.py'],
                stdout=stream, stderr=subprocess.STDOUT, check=False).returncode
        return code, log
    def standard(stage, name):
        def execute(attempt):
            code, log = command(name)
            path = root/'checkpoint.json'
            value = load_current(path, run_id)
            good = value.get('gate'+str(stage)) == 'PASS'
            # Storage's combined command may pass preservation Gate 0 and then
            # fail Gate 1. Keep those distinct results instead of losing Gate 0.
            status = 'PASS' if good and (code == 0 or stage == 0) else 'FAIL'
            return receipt(stage, status, [path, log], value.get('error') or value.get('resume_condition'))
        return execute
    def storage_readback(attempt):
        value = load_current(root/'checkpoint.json', run_id)
        if value.get('gate1') != 'PASS':
            return receipt(1, 'FAIL', [root/'checkpoint.json'], value.get('error'))
        head = value['publication_commit']
        candidates = transport.read_at('future-candidates.json', head)
        tracking = transport.read_at('future-tracking.json', head)
        verify(candidates.document, tracking.document,
               json.loads(Path('config/bct-recovery-preservation.json').read_text()))
        proof = {'run_id': run_id, 'commit': head, 'actual_remote_readback': True,
                 'root_shas': [candidates.sha, tracking.sha]}
        path = root/'operating-storage-readback.json'
        path.write_text(json.dumps(proof, indent=2)+'\n')
        return receipt(1, 'PASS', [path])
    def reading(attempt):
        code, log = command('bct_local_reader_probe')
        pilot_path = root/'local-reader-probe.json'
        pilot = load_current(pilot_path, run_id)
        if code or pilot.get('probe_status') != 'PASS':
            status = 'BLOCKED' if pilot.get('reason') == 'RUNNER_DEADLINE' else 'FAIL'
            return receipt(5, status, [pilot_path, log], pilot.get('reason'))
        return standard(5, 'bct_queue_recovery')(attempt)
    def publication(attempt):
        candidate = os.environ.get('BCT_CANDIDATE_RUN_ID')
        pages = os.environ.get('BCT_PAGES_RUN_ID')
        if not candidate or not pages:
            return {'status': 'BLOCKED', 'reason': 'ACTUAL_MAIN_PUBLICATION_AND_FRESH_ACTIONS_REQUIRED',
                'resume_condition': 'Promote only after this cycle Gates 0–6 pass, then obtain fresh automatic candidate/Pages run IDs'}
        from importlib.util import module_from_spec, spec_from_file_location
        spec = spec_from_file_location('publication_executor', '.github/scripts/bct_verify_publication.py')
        if spec is None or spec.loader is None:
            raise RuntimeError('operating publication executor unavailable')
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        code = module.execute(root, int(candidate), int(pages))
        proof = load_current(root/'operating-publication-verification.json', run_id)
        return receipt(7, 'PASS' if code == 0 and proof['status'] == 'PASS' else 'FAIL',
                       [root/'operating-publication-verification.json'], proof.get('failure_code'))
    def full(attempt):
        value = load_current(root/'checkpoint.json', run_id)
        if any(value.get('gate'+str(i)) != 'PASS' for i in range(8)):
            return {'status': 'BLOCKED', 'reason': 'REQUIRED_OPERATING_GATE_NOT_PASS'}
        claims = root/'native-claim-recovery.json'
        if not claims.exists():
            return {'status': 'BLOCKED', 'reason': 'ACTUAL_NATIVE_WORKER_CLAIM_INTERRUPTION_RECONCILIATION_REQUIRED'}
        claim = load_current(claims, run_id)
        if (claim.get('status') != 'PASS' or claim.get('actual_remote_execution') is not True
                or claim.get('actual_native_inference') is not True
                or claim.get('uncertain_claim_preserved') is not True
                or claim.get('stopped_owner_and_result_reconciled') is not True
                or claim.get('duplicate_model_calls') != 0):
            return {'status': 'BLOCKED', 'reason': 'OPERATING_NATIVE_CLAIM_PROOF_INVALID'}
        head = transport.head()
        c = transport.read_at('future-candidates.json', head)
        t = transport.read_at('future-tracking.json', head)
        verify(c.document, t.document, json.loads((root/'recovery-preservation-seal.json').read_text()))
        published = load_current(root/'operating-publication-verification.json', run_id)
        if published.get('sidecar_sha') != head:
            return {'status': 'FAIL', 'reason': 'GENERATION_CHANGED_AFTER_OPERATING_GATE_7'}
        return receipt('FULL', 'PASS', [claims, root/'checkpoint.json',
            root/'e2e-recovery.json', root/'operating-publication-verification.json'])
    stages = {0: standard(0, 'bct_storage_recovery'), 1: storage_readback,
        2: standard(2, 'bct_source_audit'), 3: standard(3, 'bct_full_source_recovery'),
        4: standard(4, 'bct_evidence_recovery'), 5: reading,
        6: standard(6, 'bct_e2e_recovery'), 7: publication, 'FULL': full}
    state = run(stages, fingerprint=lambda: fingerprint,
        output=root/'operating-engine-checkpoint.json', deadline=time.monotonic()+50*60,
        condition=lambda: condition,
        single_cycle=True, execution_identity=run_id+':'+os.environ.get('GITHUB_RUN_ATTEMPT', '1'))
    checkpoint = root/'checkpoint.json'
    report = json.loads(checkpoint.read_text()) if checkpoint.exists() else {'run_id': run_id}
    report.update(full_clean_status=state['status'], clean_streak=state['clean_streak'],
                  operating_engine_reason=state.get('reason'), prediction_performance='UNVERIFIED')
    checkpoint.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: state.get(k) for k in ('status', 'clean_streak', 'last_stage', 'reason')}))
    return 0 if state['status'] == 'PASS' or state.get('reason') == 'INDEPENDENT_NEXT_RUN_REQUIRED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
