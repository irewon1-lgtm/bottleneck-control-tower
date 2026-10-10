"""Reject stale Actions success and stale UI generations at operating Gate 7."""
from datetime import datetime

from .recovery_queue import STATES


def verify_workflow(run, jobs, *, head_sha, required_job, required_steps,
                    not_before, automatic=False):
    if (run.get('head_sha') != head_sha or run.get('head_branch') != 'main'
            or run.get('status') != 'completed' or run.get('conclusion') != 'success'):
        raise ValueError('current main workflow success required')
    created = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
    start = datetime.fromisoformat(not_before.replace('Z', '+00:00'))
    if created < start:
        raise ValueError('cached prior workflow cannot prove this execution')
    if automatic and run.get('event') not in ('push', 'schedule', 'workflow_run', 'repository_dispatch'):
        raise ValueError('actual automatic candidate trigger required')
    selected = [job for job in jobs if job.get('name') == required_job]
    if len(selected) != 1 or selected[0].get('conclusion') != 'success':
        raise ValueError('required operating job did not succeed')
    steps = {step['name']: step for step in selected[0].get('steps', [])}
    for name in required_steps:
        if steps.get(name, {}).get('conclusion') != 'success':
            raise ValueError('required operating step missing, skipped or failed: '+name)
    return {'status': 'PASS', 'actual_execution': True, 'run_id': run['id'],
            'job_id': selected[0]['id'], 'event': run.get('event'),
            'head_sha': head_sha, 'url': run['html_url']}


def verify_ui(receipt, queue, *, app_sha256, source_sha256, generation_run_id):
    if (receipt.get('actual_browser_execution') is not True or receipt.get('status') != 'PASS'
            or not receipt.get('execution_id') or receipt.get('browser_errors')):
        raise ValueError('successful actual browser execution required')
    if receipt.get('app_sha256') != app_sha256:
        raise ValueError('deployed Pages app differs from verified main code')
    if receipt.get('source_document_sha256') != source_sha256:
        raise ValueError('UI consumed a different authoritative generation')
    if receipt.get('generation_run_id') != str(generation_run_id):
        raise ValueError('UI recovery generation differs from actual saved queue')
    if set(receipt.get('counts', {})) != set(STATES) or receipt['counts'] != queue['counts']:
        raise ValueError('displayed seven-state queue differs from saved queue')
    if sum(receipt['counts'].values()) != queue['total_queue_versions']:
        raise ValueError('displayed queue does not partition all document versions')
    return {'status': 'PASS', 'actual_execution': True,
            'execution_id': receipt['execution_id'], 'url': receipt['url'],
            'counts': receipt['counts'], 'source_document_sha256': source_sha256}
