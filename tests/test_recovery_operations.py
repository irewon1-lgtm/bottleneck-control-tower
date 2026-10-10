from copy import deepcopy
import pytest
from bct.recovery_operations import verify_workflow, verify_ui
from bct.recovery_queue import STATES


def execution():
    run = {'id': 1, 'head_sha': 'verified-sha', 'head_branch': 'main',
        'created_at': '2026-10-10T07:20:00Z', 'status': 'completed',
        'conclusion': 'success', 'event': 'push', 'html_url': 'https://example.test/run'}
    jobs = [{'id': 2, 'name': 'candidates', 'conclusion': 'success',
             'steps': [{'name': 'publish', 'conclusion': 'success'}]}]
    return run, jobs


@pytest.mark.parametrize('field,value', [('head_sha','old'), ('event','workflow_dispatch'),
    ('created_at','2026-10-09T00:00:00Z'), ('conclusion','failure')])
def test_prior_success_manual_trigger_and_wrong_revision_cannot_prove_auto_execution(field, value):
    run, jobs = execution()
    run[field] = value
    with pytest.raises(ValueError):
        verify_workflow(run, jobs, head_sha='verified-sha', required_job='candidates',
            required_steps=['publish'], not_before='2026-10-10T07:00:00Z', automatic=True)


def test_job_success_cannot_hide_skipped_publisher():
    run, jobs = execution()
    jobs[0]['steps'][0]['conclusion'] = 'skipped'
    with pytest.raises(ValueError, match='skipped'):
        verify_workflow(run, jobs, head_sha='verified-sha', required_job='candidates',
            required_steps=['publish'], not_before='2026-10-10T07:00:00Z', automatic=True)


def test_actual_fresh_main_automatic_execution_is_accepted():
    run, jobs = execution()
    assert verify_workflow(run, jobs, head_sha='verified-sha', required_job='candidates',
        required_steps=['publish'], not_before='2026-10-10T07:00:00Z', automatic=True)['run_id'] == 1


def ui():
    counts = dict.fromkeys(STATES, 0)
    counts.update(PENDING=10, COMPLETED=2, FAILED=5)
    queue = {'counts': counts, 'total_queue_versions': 17}
    receipt = {'actual_browser_execution': True, 'status': 'PASS', 'execution_id': 'test-only',
        'browser_errors': [], 'app_sha256': 'app', 'source_document_sha256': 'source',
        'generation_run_id': '123', 'counts': deepcopy(counts), 'url':'https://example.test/pages'}
    return receipt, queue


@pytest.mark.parametrize('field,value', [('actual_browser_execution',False), ('app_sha256','old'),
    ('source_document_sha256','old-source'), ('generation_run_id','122'), ('browser_errors',['TypeError'])])
def test_ui_success_needs_real_execution_and_matching_app_source_generation(field,value):
    receipt, queue = ui()
    receipt[field] = value
    with pytest.raises(ValueError):
        verify_ui(receipt, queue, app_sha256='app', source_sha256='source', generation_run_id='123')


def test_queue_zero_cannot_hide_unfinished_or_failed_work():
    receipt, queue = ui()
    receipt['counts']['PENDING'] = 0
    with pytest.raises(ValueError, match='seven-state'):
        verify_ui(receipt, queue, app_sha256='app', source_sha256='source', generation_run_id='123')
    receipt, queue = ui()
    assert verify_ui(receipt, queue, app_sha256='app', source_sha256='source', generation_run_id='123')['counts']['FAILED'] == 5
