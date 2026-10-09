import hashlib
import pytest
from bct.recovery_evidence import source_document,assess,FIELDS


def document(body, proof=None):
    return source_document('doc',{'url':'https://example.test/doc',
        'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'body_status':'FULL',
        'attempted_at':'2026-10-09T00:00:00+00:00','source_proof':proof or {}},body)


def test_literal_demand_does_not_invent_qualified_supply_or_target():
    result=assess(document('A customer placed orders for power transformers.'))
    assert result['state']=='EVIDENCE_WAIT'
    assert {'QUALIFIED_SUPPLY','READY_TIMING','INDEPENDENT_EVIDENCE','TARGET'}<=set(result['missing_fields'])
    assert result['completed_review_created'] is False and result['forecast_promotion_created'] is False


def test_missing_and_corrupt_source_are_not_assessed_as_full():
    assert assess(None)['missing_fields']==list(FIELDS)
    with pytest.raises(ValueError,match='hash mismatch'):
        source_document('doc',{'body_sha256':'f'*64},'Real source.')
