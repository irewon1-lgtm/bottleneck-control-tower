from hashlib import sha256
import json
import pytest
from bct.future_local_reader import LocalCPUQuickReader


def payload():
    body='A customer placed an order. Qualified capacity and readiness are unknown.'
    return {'body':body,'body_sha256':sha256(body.encode()).hexdigest(),
            'body_status':'FULL','read_start':0,'expected_read_end':len(body)}


def receipt():
    return {'provider':'local-cpu','weights_verified':True,'build_verified':True,
            'api_cost_usd':0,'license':'Apache-2.0','files':{'weight':'a'*64},
            'alias':'local','model':'Qwen','revision':'revision','llama_cpp_sha':'build',
            'context_tokens':100,'max_output_tokens':10}


def inference(value,**overrides):
    return {'truncated':False,'stop_type':'eos','tokens_evaluated':3,'model':'local',
            'timings':{'predicted_n':9},'content':json.dumps({'disposition':'DATA_INSUFFICIENT',
            'reason':'Supply capacity and readiness are absent.','read_end':value['expected_read_end']}),**overrides}


def test_real_usage_and_unknown_evidence_remain_distinct_from_forecast():
    value=payload();calls=[]
    def request(path,data):
        calls.append((path,data))
        return {'tokens':[1,2,3]} if path=='/tokenize' else inference(value)
    result=LocalCPUQuickReader(receipt(),requester=request)(value)
    assert result['review']['disposition']=='DATA_INSUFFICIENT'
    assert result['usage']=={'input_tokens':3,'output_tokens':9}
    assert calls[1][1]['cache_prompt'] is False and calls[1][1]['prompt']==[1,2,3]
    schema=calls[1][1]['json_schema'];complete,incomplete=schema['oneOf']
    assert 'properties' not in schema
    assert all(branch['properties']['reason']['maxLength']==500 for branch in schema['oneOf'])
    assert complete['properties']['read_end']['const']==value['expected_read_end']
    assert 'INCOMPLETE' not in complete['properties']['disposition']['enum']
    assert incomplete['properties']['disposition']['const']=='INCOMPLETE'
    assert incomplete['properties']['read_end']['maximum']==value['expected_read_end']
    assert 'stage' not in result['review'] and result['api_cost_usd']==0


@pytest.mark.parametrize('override',[{'truncated':True},{'stop_type':'limit'},
    {'tokens_evaluated':2},{'model':'other'},{'timings':{'predicted_n':None}}])
def test_incomplete_or_wrong_model_receipt_never_makes_a_review(override):
    value=payload()
    def request(path,data):return {'tokens':[1,2,3]} if path=='/tokenize' else inference(value,**override)
    with pytest.raises(ValueError):LocalCPUQuickReader(receipt(),requester=request)(value)


def test_missing_weight_proof_and_source_hash_fail_before_inference():
    def no_request(*args):pytest.fail('must not call inference')
    r=receipt();r['weights_verified']=False
    with pytest.raises(RuntimeError):LocalCPUQuickReader(r,requester=no_request)(payload())
    value=payload();value['body']='changed'
    with pytest.raises(ValueError,match='source hash'):LocalCPUQuickReader(receipt(),requester=no_request)(value)


def test_context_limit_never_silently_drops_source_text():
    calls=[]
    def request(path,data):calls.append(path);return {'tokens':list(range(95))}
    with pytest.raises(ValueError,match='context budget'):
        LocalCPUQuickReader(receipt(),requester=request)(payload())
    assert calls==['/tokenize']


def test_failed_validation_still_retains_actual_returned_execution_receipt():
    value=payload();receipts=[]
    def request(path,data):
        return {'tokens':[1,2,3]} if path=='/tokenize' else inference(value,truncated=True)
    reader=LocalCPUQuickReader(receipt(),requester=request,receipt_observer=receipts.append)
    with pytest.raises(ValueError):reader(value)
    assert len(receipts)==1 and receipts[0]['truncated'] is True
    assert receipts[0]['body_sha256']==value['body_sha256']
    assert receipts[0]['tokens_evaluated']==3 and len(receipts[0]['response_sha256'])==64


def test_model_ignoring_reason_bound_still_fails_without_trimming_output():
    value=payload()
    result=inference(value,content=json.dumps({'disposition':'CHANGE','reason':'x'*501,
                                             'read_end':value['expected_read_end']}))
    def request(path,data):return {'tokens':[1,2,3]} if path=='/tokenize' else result
    with pytest.raises(ValueError,match='reason'):
        LocalCPUQuickReader(receipt(),requester=request)(value)


def test_model_reporting_a_shorter_terminal_extent_is_still_rejected_without_rewriting():
    value=payload();observed=[]
    raw={'disposition':'DATA_INSUFFICIENT','reason':'Demand timing is unknown.','read_end':10}
    def request(path,data):
        return {'tokens':[1,2,3]} if path=='/tokenize' else inference(value,content=json.dumps(raw))
    with pytest.raises(ValueError,match='unfinished reading'):
        LocalCPUQuickReader(receipt(),requester=request,receipt_observer=observed.append)(value)
    assert json.loads(observed[0]['content'])==raw


def test_native_adapter_never_turns_an_unfinished_read_into_completion():
    value=payload()
    raw={'disposition':'INCOMPLETE','reason':'Reading stopped before the end.','read_end':10}
    def request(path,data):
        return {'tokens':[1,2,3]} if path=='/tokenize' else inference(value,content=json.dumps(raw))
    result=LocalCPUQuickReader(receipt(),requester=request)(value)
    assert result['review']==raw
