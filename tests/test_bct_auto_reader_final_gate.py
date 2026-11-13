"""Regression for verified CPU passes with earlier quarantined failure rows."""
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.github' / 'scripts'))
from bct_auto_reader import assess_current_cpu_batch


def previous_failure_with_five_successes():
    # Schema and held ERROR=1 match the saved 2026-11-13 operating run,
    # not an invented successful historical reading.
    results = [{'state': 'SUCCESS', 'document_id': f'current-{i}',
                'body_sha256': f'sha-{i}'} for i in range(5)]
    return {
        'state': 'FINISHED', 'attempted': 5, 'completed_delta': 5,
        'counts': {'SUCCESS': 5}, 'results': results,
        'model_calls': 5, 'actual_returned_native_calls': 5,
        'summary_saved': True, 'duplicate_auto_reviews': 0,
        'source_records_unchanged': True,
        'historical_judgment_holds': 0, 'historical_judgment_state': 'PASS',
        'held_prior_version_states': {'ERROR': 1},
        'release_proof': {'status': 'PASS'},
        'paid_fallback_calls': 0,
    }


def test_held_previous_error_does_not_fail_five_real_saved_cpu_reads():
    report = previous_failure_with_five_successes()
    before = deepcopy(report)
    checks = assess_current_cpu_batch(report)
    assert all(checks.values()), checks
    # The held error must not be removed, rewritten, or promoted to success.
    assert report == before
    assert report['held_prior_version_states'] == {'ERROR': 1}


@pytest.mark.parametrize('held', [{}, {'ERROR': 1, 'BLOCKED': 2}])
def test_only_known_quarantined_prior_failure_counts_are_nonfatal(held):
    report = previous_failure_with_five_successes()
    report['held_prior_version_states'] = held
    assert all(assess_current_cpu_batch(report).values())


@pytest.mark.parametrize('held', [
    {'RUNNING': 1}, {'UNRECOGNIZED': 1}, {'ERROR': -1},
    {'ERROR': '1'}, {'ERROR': True}, None,
])
def test_running_unknown_or_malformed_prior_holds_fail_closed(held):
    report = previous_failure_with_five_successes()
    report['held_prior_version_states'] = held
    checks = assess_current_cpu_batch(report)
    assert checks['prior_failures_still_held'] is False


@pytest.mark.parametrize('field,value', [
    ('summary_saved', False),
    ('source_records_unchanged', False),
    ('historical_judgment_holds', 1),
    ('historical_judgment_state', 'PARTIAL_UNVERIFIED_HISTORY'),
    ('duplicate_auto_reviews', 1),
    ('completed_delta', 4),
    ('actual_returned_native_calls', 4),
    ('model_calls', 4),
    ('paid_fallback_calls', 1),
    ('counts', {'SUCCESS': 4, 'ERROR': 1}),
    ('state', 'BLOCKED'),
])
def test_actual_current_batch_integrity_failures_are_not_masked(field, value):
    report = previous_failure_with_five_successes()
    report[field] = value
    assert not all(assess_current_cpu_batch(report).values()), field


def test_missing_release_proof_and_repeated_success_identifiers_fail():
    report = previous_failure_with_five_successes()
    report['release_proof'] = {'status': 'FAIL'}
    assert not all(assess_current_cpu_batch(report).values())
    report = previous_failure_with_five_successes()
    report['results'][1] = report['results'][0].copy()
    assert not all(assess_current_cpu_batch(report).values())
