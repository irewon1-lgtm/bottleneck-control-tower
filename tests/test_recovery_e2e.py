from hashlib import sha256
import pytest
from bct.recovery_e2e import trace_source,verify_display_generation,confirmed_full_observation


def item(body):
    return {'document_id':'source','body_sha256':sha256(body.encode()).hexdigest(),
            'body_chars':len(body),'body_status':'FULL','url':'https://example.test/official'}


def test_real_text_trace_keeps_incomplete_scope_and_forecast_unverified():
    body='Demand for high-voltage transformers increased. Qualified supply and timing remain unknown.'
    result=trace_source(item(body),body,{'targets':[]})
    assert result['actual_parser_execution'] is True
    assert result['production_decisions_written']==0 and result['prediction_performance']=='UNVERIFIED'
    assert all(v['stage']!='S3' for v in result['verdicts'])
    assert result['facts'] and all(f['missing_scope'] for f in result['facts'])


def test_partial_or_changed_source_cannot_be_actual_full_e2e():
    body='Actual source.';record=item(body);record['body_status']='PARTIAL'
    with pytest.raises(ValueError,match='completeness'):trace_source(record,body,{'targets':[]})
    record['body_status']='FULL'
    with pytest.raises(ValueError,match='binding'):trace_source(record,body+' changed',{'targets':[]})


def test_old_full_label_cannot_override_a_current_partial_same_hash_observation():
    record=item('Same preserved bytes, with newly observed missing attachments.')
    observed={'body_sha256':record['body_sha256'],'body_status':'PARTIAL'}
    assert not confirmed_full_observation(record,observed)
    observed['body_status']='FULL'
    assert confirmed_full_observation(record,observed)
    observed['body_sha256']='a'*64
    assert not confirmed_full_observation(record,observed)


def test_display_hash_binding_preserves_all_operational_queue_counts():
    c={'results':{'source':{'body_sha256':'a'*64}},'summary':{'recovery_queue':{
        'counts':{'PENDING':7,'COMPLETED':2,'FAILED':3},'legacy_partial_read_results':1}}}
    report=verify_display_generation('future-candidates.json',c,'b'*64)
    assert report['source_document_sha256']=='b'*64 and report['status']=='PASS'
