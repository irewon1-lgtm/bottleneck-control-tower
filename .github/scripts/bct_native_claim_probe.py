"""Interrupt a real CPU worker after its response, then reconcile its claim.

Only an isolated, newly created test branch is mutated. The selected exact
FULL source remains a normal fresh pilot input and its returned reading is
passed back for normal production Gate 5 publication, never called twice.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from bct.future_github import GitHubTransport, _raw
from bct.future_local_reader import LocalCPUQuickReader
from bct.future_review import document_complete, queue_summary
from bct.future_worker import run_worker, _runs
from bct.recovery_claim import reconcile_returned
from bct.recovery_queue import project


def append_private(path, value):
    with path.open('a') as f:
        f.write(json.dumps(value, ensure_ascii=False)+'\n'); f.flush(); os.fsync(f.fileno())


def child(directory):
    data = json.loads((directory/'input.json').read_text())
    transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'], data['branch'], os.environ['GITHUB_TOKEN'])
    def observe(value):
        append_private(directory/'native-execution.jsonl', value)
    class InterruptAfterResponse(LocalCPUQuickReader):
        def __call__(self, payload):
            response = super().__call__(payload)
            with (directory/'response.json').open('w') as f:
                f.write(json.dumps(response, ensure_ascii=False)+'\n'); f.flush(); os.fsync(f.fileno())
            raise KeyboardInterrupt('controlled interruption after returned native result')
    reader = InterruptAfterResponse(data['setup'], receipt_observer=observe)
    try:
        run_worker(transport, 'future-candidates.json', 'future-tracking.json',
            reader=reader, cache_dir=Path(data['cache']), limit=1, max_input_chars=12000,
            review_mode='API_REVIEW', input_rate=0, output_rate=0)
    except KeyboardInterrupt:
        return 130
    return 1


def execute(root, payload, record, setup_receipt, observe_returned):
    run_id = os.environ['GITHUB_RUN_ID']
    directory = root/'private-native-claim'/run_id; directory.mkdir(parents=True, exist_ok=False)
    branch = 'ops/bct-native-claim-probe-' + run_id + '-' + uuid.uuid4().hex[:8]
    production = GitHubTransport(os.environ['GITHUB_REPOSITORY'], 'future-bottleneck-data', os.environ['GITHUB_TOKEN'])
    production_before = production.head()
    selected = deepcopy(record)
    # An isolated projection includes only this actual source version. It
    # neither edits production nor introduces a synthetic candidate flag.
    selected.pop('versions', None)
    selected.update(body_sha256=payload['body_sha256'], current_body_sha256=payload['body_sha256'])
    candidates = {'results': {payload['document_id']: selected}}
    if (selected.get('body_status') != 'FULL'
            or not (selected.get('candidate') or selected.get('tracked_matches'))
            or document_complete({}, selected)):
        raise ValueError('actual eligible unread FULL worker input required')
    initial = {'future-candidates.json': candidates, 'future-tracking.json': {}}
    entries = [{'path': path, 'mode': '100644', 'type': 'blob', 'content': _raw(value).decode()}
               for path, value in initial.items()]
    tree = production.requester('POST', '/git/trees', {'tree': entries})
    commit = production.requester('POST', '/git/commits', {
        'message': 'Isolated exact-source native claim recovery verification',
        'tree': tree['sha'], 'parents': []})
    production.requester('POST', '/git/refs', {'ref': 'refs/heads/'+branch, 'sha': commit['sha']})
    remote = GitHubTransport(os.environ['GITHUB_REPOSITORY'], branch, os.environ['GITHUB_TOKEN'])
    for path, value in initial.items():
        if remote.read_at(path, commit['sha']).document != value:
            raise ValueError('native claim test initial SHA readback differs')
    (directory/'input.json').write_text(json.dumps({'branch': branch,
        'cache': str(root/'private-source-cache'), 'setup': setup_receipt}, indent=2)+'\n')
    log = root/'native-claim-child.log'
    started = datetime.now(timezone.utc).isoformat()
    with log.open('w') as stream:
        process = subprocess.Popen([sys.executable, __file__, '--child', str(directory)],
            stdout=stream, stderr=subprocess.STDOUT)
        timed_out = False
        try:
            exit_code = process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
            exit_code = process.returncode
    native_path = directory/'native-execution.jsonl'
    native = [json.loads(s) for s in native_path.read_text().splitlines()] if native_path.exists() else []
    for value in native: observe_returned(value)
    if timed_out:
        raise RuntimeError('native worker controlled interruption deadline')
    if exit_code != 130 or process.poll() != 130:
        raise RuntimeError('native child did not stop at verified controlled interruption')
    response = json.loads((directory/'response.json').read_text())
    if len(native) != 1:
        raise ValueError('native interrupted worker returned unexpected inference count')
    stopped_tracking = remote.read('future-tracking.json').document
    running = [r for r in _runs(stopped_tracking).values()
               if r.get('state') == 'RUNNING' and r.get('document_id') == payload['document_id']]
    if len(running) != 1 or stopped_tracking.get('reviews'):
        raise ValueError('uncertain native version claim or zero-completion state lost')
    initial_queue = project(candidates, stopped_tracking, [], {}, root/'private-source-cache')
    if initial_queue['counts']['PROCESSING'] != 1 or initial_queue['counts']['COMPLETED'] != 0:
        raise ValueError('uncertain native claim is not displayed as PROCESSING')
    forbidden_calls = 0
    def forbidden(_):
        nonlocal forbidden_calls
        forbidden_calls += 1
        raise RuntimeError('uncertain or completed version reached a duplicate reader call')
    resumed = run_worker(remote, 'future-candidates.json', 'future-tracking.json',
        reader=forbidden, cache_dir=root/'private-source-cache', limit=1, retry_failed=True,
        review_mode='API_REVIEW', input_rate=0, output_rate=0)
    if resumed['attempted'] or resumed['model_calls'] or forbidden_calls:
        raise ValueError('uncertain claim allowed automatic duplicate reading')
    owner = running[0]['run_id']
    observed_stop = {'owner': owner, 'stopped': process.poll() == 130,
        'observed_process_exit_code': process.returncode, 'observed_pid': process.pid,
        'execution_id': run_id+':native-claim-child:'+str(process.pid),
        'observed_at': datetime.now(timezone.utc).isoformat()}
    reconciled = reconcile_returned(remote, 'future-candidates.json', 'future-tracking.json',
        payload=payload, response=response, native_receipt=native[0], setup_receipt=setup_receipt,
        stopped_owner=lambda selected_owner: observed_stop if selected_owner == owner else {})
    again = run_worker(remote, 'future-candidates.json', 'future-tracking.json',
        reader=forbidden, cache_dir=root/'private-source-cache', limit=1, retry_failed=True,
        review_mode='API_REVIEW', input_rate=0, output_rate=0)
    if again['attempted'] or again['model_calls'] or forbidden_calls:
        raise ValueError('reconciled completed version allowed a duplicate reader call')
    final_head = remote.head()
    final_candidates = remote.read_at('future-candidates.json', final_head).document
    final_tracking = remote.read_at('future-tracking.json', final_head).document
    final_queue = project(final_candidates, final_tracking, [], {}, root/'private-source-cache')
    if (final_candidates['results'] != candidates['results']
            or len(final_tracking['reviews']) != 1
            or queue_summary(final_candidates, final_tracking)['completed_documents'] != 1
            or final_queue['counts']['PROCESSING'] != 0 or final_queue['counts']['COMPLETED'] != 1
            or production.head() != production_before):
        raise ValueError('native claim reconciliation or untouched production proof failed')
    proof = {'run_id': run_id, 'code_sha': os.environ['GITHUB_SHA'], 'status': 'PASS',
        'actual_remote_execution': True, 'actual_native_inference': True,
        'uncertain_claim_preserved': True, 'stopped_owner_and_result_reconciled': True,
        'duplicate_model_calls': forbidden_calls, 'actual_model_calls': 1,
        'source_body_sha256': payload['body_sha256'], 'source_document_id': payload['document_id'],
        'probe_branch': branch, 'probe_commit': final_head, 'production_unchanged_at': production_before,
        'initial_processing_count': 1, 'final_completed_count': 1,
        'reconciliation': reconciled, 'stopped_owner': observed_stop,
        'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
        'response_sha256': hashlib.sha256((directory/'response.json').read_bytes()).hexdigest(),
        'private_file_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(directory.iterdir())},
        'api_cost_usd': 0, 'prediction_performance': 'UNVERIFIED'}
    (root/'native-claim-recovery.json').write_text(json.dumps(proof, indent=2)+'\n')
    history_path = root/'native-claim-history.json'
    history = json.loads(history_path.read_text()) if history_path.exists() else []
    if any(value['run_id'] == run_id for value in history):
        raise ValueError('native claim proof already exists for this execution')
    history.append(proof)
    history_path.write_text(json.dumps(history, indent=2)+'\n')
    return response, native[0]


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--child':
        raise SystemExit('claim probe must be called by the real-source pilot')
    raise SystemExit(child(Path(sys.argv[2])))
