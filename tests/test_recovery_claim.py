"""Claim reconciliation contract; fixtures are not operating/native proof."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from bct.future_store import LocalJSONTransport
from bct.future_worker import run_worker, _runs
from bct.future_review import queue_items, document_complete
from bct.recovery_claim import reconcile_returned
from tests.test_future_worker import sources


def prepared(tmp_path):
    _, c, t, cache = sources(tmp_path)
    item = queue_items(json.loads(c.read_text()), {})['quick'][0]
    body = (cache/(item['body_sha256']+'.txt')).read_text()
    payload = {'document_id': item['document_id'], 'body_sha256': item['body_sha256'],
               'body_status': 'FULL', 'body': body, 'read_start': 0, 'expected_read_end': len(body)}
    setup = {'provider': 'local-cpu', 'weights_verified': True, 'build_verified': True,
        'api_cost_usd': 0, 'license': 'Apache-2.0', 'files': {'fixture': 'sha'},
        'alias': 'fixture-native', 'context_tokens': 2048, 'max_output_tokens': 500,
        'model': 'fixture-model', 'revision': 'fixture-revision', 'llama_cpp_sha': 'fixture-build'}
    response = {'review': {'disposition': 'DATA_INSUFFICIENT', 'reason': 'Fixture only.', 'read_end': len(body)},
        'usage': {'input_tokens': 50, 'output_tokens': 12}, 'provider': 'local-cpu',
        'model': setup['model'], 'model_revision': setup['revision'], 'api_cost_usd': 0,
        'inference_receipt': {'llama_cpp_sha': setup['llama_cpp_sha']}}
    native = {'document_id': payload['document_id'], 'body_sha256': payload['body_sha256'],
        'expected_read_end': len(body), 'prompt_tokens': 50, 'timings': {'predicted_n': 12},
        'tokens_evaluated': 50, 'truncated': False, 'stop_type': 'eos',
        'model': setup['alias'], 'content': json.dumps(response['review'])}
    def interrupt(_): raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        run_worker(LocalJSONTransport(), str(c), str(t), reader=interrupt, cache_dir=cache,
            limit=1, review_mode='API_REVIEW', input_rate=0, output_rate=0)
    claim = next(r for r in _runs(json.loads(t.read_text())).values()
                 if r.get('state') == 'RUNNING' and r.get('document_id') == payload['document_id'])
    proof = {'owner': claim['run_id'], 'stopped': True, 'observed_process_exit_code': 130,
             'execution_id': 'fixture-observer', 'observed_at': datetime.now(timezone.utc).isoformat()}
    return c, t, cache, payload, response, native, setup, proof


def reconcile(values, **updates):
    c, t, _, payload, response, native, setup, proof = values
    args = dict(payload=payload, response=response, native_receipt=native,
                setup_receipt=setup, stopped_owner=lambda _: proof)
    args.update(updates)
    return reconcile_returned(LocalJSONTransport(), str(c), str(t), **args)


def test_stopped_owner_result_saved_once_and_previous_claim_preserved(tmp_path):
    values = prepared(tmp_path)
    c, t, cache, payload, *_ = values
    result = reconcile(values)
    saved = json.loads(t.read_text())
    assert len(saved['reviews']) == 1
    event = saved['runs'][result['reconciliation_id']]
    assert event['previous_claim']['state'] == 'RUNNING'
    assert document_complete(saved, queue_items(json.loads(c.read_text()), saved)['completed'][0])
    def forbidden(_): pytest.fail('reconciled version must not be read again')
    replay = run_worker(LocalJSONTransport(), str(c), str(t), reader=forbidden,
        cache_dir=cache, limit=1, retry_failed=True, review_mode='API_REVIEW', input_rate=0, output_rate=0)
    assert replay['attempted'] == replay['model_calls'] == 0
    assert len(json.loads(t.read_text())['reviews']) == 1


@pytest.mark.parametrize('change', [
    {'stopped': False}, {'owner': 'other'}, {'observed_process_exit_code': None}, {'execution_id': ''}])
def test_no_time_based_or_unverified_unlock(tmp_path, change):
    values = prepared(tmp_path)
    before = values[1].read_bytes()
    proof = {**values[-1], **change}
    with pytest.raises(ValueError): reconcile(values, stopped_owner=lambda _: proof)
    assert values[1].read_bytes() == before


@pytest.mark.parametrize('field,value', [('truncated', True), ('model', 'other'), ('tokens_evaluated', 49)])
def test_invalid_native_identity_or_truncation_keeps_claim(tmp_path, field, value):
    values = prepared(tmp_path)
    before = values[1].read_bytes()
    native = {**values[5], field: value}
    with pytest.raises(ValueError): reconcile(values, native_receipt=native)
    assert values[1].read_bytes() == before


def test_incomplete_not_reconciled_as_full(tmp_path):
    values = prepared(tmp_path)
    response = deepcopy(values[4]); native = deepcopy(values[5])
    response['review'].update(disposition='INCOMPLETE', read_end=10)
    native['content'] = json.dumps(response['review'])
    before = values[1].read_bytes()
    with pytest.raises(ValueError): reconcile(values, response=response, native_receipt=native)
    assert values[1].read_bytes() == before
