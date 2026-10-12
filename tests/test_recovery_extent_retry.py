from copy import deepcopy
from hashlib import sha256
import pytest
from bct.recovery_extent_retry import extent_retry_policy
from bct.recovery_preservation import digest


def fixture(tmp_path):
    body='abcde';h=sha256(body.encode()).hexdigest();(tmp_path/(h+'.txt')).write_text(body)
    old={'state':'ERROR','reason':'HTTPError','run_id':'stopped-worker','document_id':'d',
         'body_sha256':h,'read_start':4}
    config={'worker_id':'stopped-worker','prior_error_sha256':digest(old),
            'version':{'document_id':'d','body_sha256':h,'read_start':4,'expected_read_end':5},
            'original':{'run_id':1,'artifact_id':11,'code_sha':'old','artifact_sha256':'a'*64},
            'native_correction':{'run_id':2,'artifact_id':22,'code_sha':'fixed','artifact_sha256':'b'*64}}
    item={'document_id':'d','body_sha256':h,'resume_at':4}
    def request(method,path):
        if '/runs/' in path:
            first=path.endswith('/1');return {'status':'completed','conclusion':'failure' if first else 'success',
                                             'head_sha':'old' if first else 'fixed'}
        first=path.endswith('/11');return {'workflow_run':{'id':1 if first else 2},
                                          'digest':'sha256:'+('a'*64 if first else 'b'*64),'expired':False}
    return config,old,item,request


def test_exact_stopped_error_and_actual_correction_enable_one_retry(tmp_path):
    c,old,item,request=fixture(tmp_path)
    retry=extent_retry_policy(request,c,[old],tmp_path)
    assert retry(item,old)
    new=deepcopy(old);new['run_id']='new-failed-worker'
    assert not retry(item,new)  # A later failure is not an automatic repeat.


@pytest.mark.parametrize('change',[{'state':'RUNNING'},{'reason':'TimeoutError'},
                                 {'read_start':3},{'body_sha256':'other'},
                                 {'run_id':'other-worker'}])
def test_other_states_and_sources_never_receive_retry_permission(tmp_path,change):
    c,old,item,_=fixture(tmp_path);old.update(change)
    def no_request(*args):pytest.fail('unrelated state must not become artifact dependency')
    assert not extent_retry_policy(no_request,c,[old],tmp_path)(item,old)


def test_unfinished_owner_or_wrong_archived_proof_blocks_retry(tmp_path):
    c,old,_,request=fixture(tmp_path)
    def unfinished(method,path):
        result=request(method,path)
        if path=='/actions/runs/1':result['status']='in_progress'
        return result
    with pytest.raises(ValueError):extent_retry_policy(unfinished,c,[old],tmp_path)
    c['native_correction']['artifact_sha256']='c'*64
    with pytest.raises(ValueError):extent_retry_policy(request,c,[old],tmp_path)


def test_changed_source_extent_or_prior_error_cannot_be_overwritten(tmp_path):
    c,old,item,request=fixture(tmp_path)
    retry=extent_retry_policy(request,c,[old],tmp_path)
    assert not retry({**item,'resume_at':3},old)
    altered={**old,'reason':'different'};assert not retry(item,altered)
    c['version']['expected_read_end']=6
    assert not extent_retry_policy(request,c,[old],tmp_path)(item,old)
