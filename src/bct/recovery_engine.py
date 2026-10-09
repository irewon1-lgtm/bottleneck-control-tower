"""Evidence-gated, resumable CLEAN verification; never retry unchanged errors.

The caller supplies real stage executors and targeted repairs. Missing stages
or unavailable credentials are BLOCKED, not manufactured PASS. No attempt cap
or permanent server is needed. A runner deadline saves a restart checkpoint.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time
import uuid

STAGES = tuple(range(8)) + ('FULL',)


def checkpoint(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def run(stages, *, fingerprint, output, repair=None, deadline=None):
    """Every changed-condition retry begins at 0; require three fresh cycles.

    Stage results need status, actual_execution=True, execution_id, evidence
    and criteria_met=True. Executors must actually run their contracted scope.
    A repair callback returns only after performing a targeted change; its
    assertion cannot override the independent fingerprint change check.
    """
    path = Path(output)
    state = json.loads(path.read_text()) if path.exists() else {'attempts': [], 'clean_streak': 0}
    current = fingerprint()
    if (state.get('status') in ('FAIL', 'BLOCKED') and state.get('fingerprint') == current
            and state.get('reason') != 'RUNNER_DEADLINE'):
        return state
    if state.get('fingerprint') != current:
        state['clean_streak'] = 0
    state.update(status='RUNNING', fingerprint=current, resume_stage=0)
    while True:
        if deadline is not None and time.monotonic() >= deadline:
            state.update(status='BLOCKED', reason='RUNNER_DEADLINE', resume_stage=0,
                         resume_condition='Fresh runner; reverify from Stage 0')
            checkpoint(path, state);return state
        attempt = {'id': uuid.uuid4().hex, 'started_at': datetime.now(timezone.utc).isoformat(),
                   'fingerprint': fingerprint(), 'stages': []}
        state['attempts'].append(attempt)
        failed = None
        for stage in STAGES:
            if stage not in stages:
                failed = {'stage': stage, 'status': 'BLOCKED', 'reason': 'STAGE_EXECUTOR_MISSING'}
            else:
                try:
                    result = stages[stage](attempt['id'])
                except Exception as exc:
                    result = {'status': 'FAIL', 'reason': type(exc).__name__}
                failed = {**result, 'stage': stage}
                receipts = [r for a in state['attempts'] for r in a['stages']]
                reused = any(r.get('execution_id') == result.get('execution_id') for r in receipts)
                if result.get('status') == 'PASS' and (result.get('actual_execution') is not True
                        or result.get('criteria_met') is not True or not result.get('evidence')
                        or not result.get('execution_id') or reused):
                    failed.update(status='FAIL', reason='INVALID_OR_REUSED_EXECUTION_RECEIPT')
            attempt['stages'].append(failed)
            state.update(last_stage=stage, last_result=failed)
            checkpoint(path, state)
            if failed['status'] != 'PASS':
                break
            failed = None
        if failed:
            state['clean_streak'] = 0
            original = fingerprint()
            if repair is not None:
                repair(failed)
            changed = fingerprint()
            if changed == original:
                state.update(status='BLOCKED' if failed['status'] == 'BLOCKED' else 'FAIL',
                             reason=failed.get('reason'), resume_stage=0,
                             resume_condition=failed.get('resume_condition') or
                             'Code, settings or verified external condition must change before restart')
                checkpoint(path, state);return state
            state['fingerprint'] = changed
            checkpoint(path, state)
            continue
        if fingerprint() != attempt['fingerprint']:
            state.update(clean_streak=0, fingerprint=fingerprint())
            checkpoint(path, state)
            continue
        state['clean_streak'] += 1
        if state['clean_streak'] == 3:
            state.update(status='PASS', resume_stage=None,
                         prediction_performance='UNVERIFIED')
            checkpoint(path, state);return state
        checkpoint(path, state)
