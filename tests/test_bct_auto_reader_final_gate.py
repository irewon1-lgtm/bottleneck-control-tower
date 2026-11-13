"""Regression for verified CPU passes with earlier quarantined failure rows."""
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.github' / 'scripts'))
from bct_auto_reader import assess_current_cpu_batch, fresh_native_event_guard
from bct.future_review import event_groups, READER_VERSION


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


def test_native_batch_selects_fresh_distinct_event_bodies_only():
    """Five saved references may mean four real calls plus one exact reuse."""
    a, b, c = ('a' * 64, 'b' * 64, 'c' * 64)
    candidates = {'results': {
        'fresh-a': {'body_sha256': a, 'body_status': 'FULL', 'body_chars': 100},
        'same-body-different-reference': {'body_sha256': a, 'body_status': 'FULL', 'body_chars': 100},
        'already-reviewed': {'body_sha256': b, 'body_status': 'FULL', 'body_chars': 100},
        'fresh-c': {'body_sha256': c, 'body_status': 'FULL', 'body_chars': 100},
    }}
    events = event_groups(candidates)
    prior_event = next(event_id for event_id, event in events.items()
                       if any(ref['document_id'] == 'already-reviewed'
                              for ref in event['documents']))
    tracking = {'reviews': {'prior': {
        'kind': 'quick', 'reader_version': READER_VERSION,
        'worker_event_id': prior_event, 'body_sha256': b,
        'read_complete': True, 'disposition': 'CURRENT',
    }}}
    select = fresh_native_event_guard(candidates, tracking)
    assert select({'document_id': 'fresh-a', 'body_sha256': a})
    assert not select({'document_id': 'same-body-different-reference', 'body_sha256': a})
    assert not select({'document_id': 'already-reviewed', 'body_sha256': b})
    assert select({'document_id': 'fresh-c', 'body_sha256': c})
    assert not select({'document_id': 'fresh-c', 'body_sha256': c})
    assert not select({'document_id': 'missing', 'body_sha256': 'unknown'})


def test_reused_document_is_not_counted_as_a_fifth_native_inference():
    report = previous_failure_with_five_successes()
    report['results'][2]['reused'] = True
    report['model_calls'] = 4
    report['actual_returned_native_calls'] = 4
    assert assess_current_cpu_batch(report)['native_cpu_receipts'] is False
