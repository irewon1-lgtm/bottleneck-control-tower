"""Reconcile an uncertain exact-version claim only after its owner stopped.

The stopped-owner observer is external to the stored record. A missing or
invalid result keeps PROCESSING; neither an age nor a timeout unlocks it.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

from .future_reader import validate_output
from .future_local_reader import LocalCPUQuickReader
from .future_review import READER_VERSION, event_groups, save_review
from .future_worker import _key, _patch, _runs


def reconcile_returned(transport, candidates_path, tracking_path, *, payload,
                       response, native_receipt, setup_receipt, stopped_owner):
    c = transport.read(candidates_path).document
    t = transport.read(tracking_path).document
    work_id = 'quick-version-' + _key(payload['document_id'], payload['body_sha256'], READER_VERSION)
    current = _runs(t).get(work_id, {})
    proof = stopped_owner(current.get('run_id'))
    if (current.get('state') != 'RUNNING' or proof.get('stopped') is not True
            or proof.get('owner') != current.get('run_id')
            or proof.get('observed_process_exit_code') != 130
            or not proof.get('execution_id') or not proof.get('observed_at')):
        raise ValueError('uncertain claim owner was not independently observed stopped')
    if (current.get('document_id') != payload['document_id']
            or current.get('body_sha256') != payload['body_sha256']
            or current.get('read_start') != payload['read_start']
            or hashlib.sha256(payload['body'].encode()).hexdigest() != payload['body_sha256']
            or len(payload['body']) != payload['expected_read_end']):
        raise ValueError('uncertain claim source or range differs')
    decision = validate_output(response['review'], payload)
    # Validate the preserved native receipt independently of the worker response.
    tokens = native_receipt.get('prompt_tokens')
    output = native_receipt.get('timings', {}).get('predicted_n')
    if (LocalCPUQuickReader(setup_receipt).preflight() is not None
            or native_receipt.get('model') != setup_receipt['alias']
            or response.get('model') != setup_receipt['model']
            or response.get('model_revision') != setup_receipt['revision']
            or response.get('inference_receipt', {}).get('llama_cpp_sha') != setup_receipt['llama_cpp_sha']
            or response.get('provider') != 'local-cpu' or response.get('api_cost_usd') != 0
            or response.get('usage') != {'input_tokens': tokens, 'output_tokens': output}
            or type(tokens) is not int or tokens <= 0 or type(output) is not int or output <= 0
            or native_receipt.get('tokens_evaluated') != tokens
            or native_receipt.get('truncated') is not False
            or native_receipt.get('stop_type') not in ('eos', 'word')
            or native_receipt.get('document_id') != payload['document_id']
            or native_receipt.get('body_sha256') != payload['body_sha256']
            or native_receipt.get('expected_read_end') != payload['expected_read_end']
            or validate_output(json.loads(native_receipt['content']), payload) != decision
            or decision['disposition'] == 'INCOMPLETE'):
        raise ValueError('stopped owner native result is not a complete validated reading')
    ref = (payload['document_id'], payload['body_sha256'])
    event = next(key for key, value in event_groups(c).items()
                 if {'document_id': ref[0], 'body_sha256': ref[1]} in value['documents'])
    review_id = 'auto-quick-' + _key(*ref, READER_VERSION, payload['read_start'])
    now = datetime.now(timezone.utc).isoformat()
    result_hash = hashlib.sha256(json.dumps(response, sort_keys=True).encode()).hexdigest()
    review = {**decision, 'review_id': review_id, 'document_id': ref[0],
        'body_sha256': ref[1], 'reader_version': READER_VERSION, 'kind': 'quick',
        'read_start': payload['read_start'], 'reviewed_at': now, 'worker_event_id': event,
        'worker_provider': 'local-cpu', 'worker_model': response['model'],
        'reconciled_stopped_owner': proof['owner'], 'preserved_result_sha256': result_hash}
    saved = save_review(transport, tracking_path, c, review)
    if saved.status not in ('APPLIED', 'ALREADY_APPLIED'):
        raise RuntimeError('stopped owner review was not saved')
    latest = transport.read(tracking_path).document
    if _runs(latest).get(work_id) != current:
        raise RuntimeError('uncertain claim changed during result reconciliation')
    event_id = 'claim-reconciliation-' + _key(work_id, proof['owner'], result_hash)
    completed = {**current, 'state': 'SUCCESS', 'review_id': review_id,
                 'reconciled_at': now, 'reconciliation_id': event_id}
    # The previous RUNNING bytes remain as a linked, immutable event.
    event_record = {'type': 'stopped_owner_result_reconciliation', 'state': 'PASS',
        'previous_claim': deepcopy(current), 'stopped_owner_proof': deepcopy(proof),
        'preserved_result_sha256': result_hash, 'review_id': review_id, 'reconciled_at': now}
    confirmed = _patch(transport, tracking_path,
        {'runs': {work_id: completed, event_id: event_record}}, event_id, latest)
    if confirmed['reviews'][review_id]['preserved_result_sha256'] != result_hash:
        raise RuntimeError('stopped owner review readback differs')
    return {'work_id': work_id, 'review_id': review_id, 'reconciliation_id': event_id,
            'preserved_result_sha256': result_hash, 'previous_claim': current}
