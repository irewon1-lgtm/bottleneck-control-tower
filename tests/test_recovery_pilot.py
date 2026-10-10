from copy import deepcopy

import pytest

from bct.recovery_pilot import prior_results_applied, resume_batches


def fixture():
    config={'model':'Qwen','revision':'rev','files':{'weight':'hash'},'llama_cpp_sha':'build',
            'alias':'local','context_tokens':100,'max_output_tokens':10}
    items=[{'document_id':str(i),'body_sha256':str(i),'read_start':0,'expected_read_end':10} for i in range(61)]
    def result(i):
        return {**items[i],'review':{'disposition':'DATA_INSUFFICIENT','reason':'Timing absent.','read_end':10},
            'provider':'local-cpu','model_revision':'rev','usage':{'input_tokens':10,'output_tokens':5},
            'inference_receipt':{'llama_cpp_sha':'build','tokens_evaluated':10,'truncated':False,'stop_type':'eos'}}
    previous={'run_id':'real-run','model_setup_receipt':{**config,'weights_verified':True,'build_verified':True},
        'batches':[{'limit':1,'status':'PASS','actual_model_calls':1,'results':[result(0)]},
                   {'limit':10,'status':'RUNNING','actual_model_calls':2,'results':[result(1),result(2)]}]}
    return previous,items,config


def test_partial_pilot_resumes_exact_progress_without_changing_old_receipts():
    p,items,c=fixture();original=deepcopy(p);batches=resume_batches(p,items,c)
    assert [len(b['results']) for b in batches]==[1,2]
    assert batches[1]['status']=='RUNNING' and batches[0]['status']=='PASS'
    assert batches[1]['preserved_from_run_id']=='real-run' and p==original


@pytest.mark.parametrize('mutation',['model','source','range','tokens','partial'])
def test_changed_or_incomplete_prior_work_is_not_silently_reused(mutation):
    p,items,c=fixture();r=p['batches'][1]['results'][0]
    if mutation=='model':p['model_setup_receipt']['revision']='changed'
    elif mutation=='source':r['body_sha256']='changed'
    elif mutation=='range':r['expected_read_end']=9
    elif mutation=='tokens':r['usage']['input_tokens']=None
    else:r['review'].update(disposition='INCOMPLETE',read_end=5)
    with pytest.raises(ValueError):resume_batches(p,items,c)


def test_bounded_production_resume_preserves_actual_calls_without_fake_qualification():
    p,items,c=fixture();batch=p['batches'][0];batch['limit']=5;p['batches']=[batch]
    b=resume_batches(p,items,c,limits=(5,))
    assert b[0]['status']=='RUNNING' and b[0]['actual_model_calls']==1
    with pytest.raises(ValueError):resume_batches(p,items,c)


def test_prior_results_use_exact_storage_proof_when_newer_checkpoint_failed_early():
    p,items,_=fixture();p['batches']=p['batches'][:1]
    records={(item['document_id'],item['body_sha256']):item for item in items}
    assert prior_results_applied(p,records,{},lambda record:record is items[0]) is True
    assert prior_results_applied(p,records,{},lambda record:False) is False


def test_corrected_prior_result_is_held_without_replay_and_empty_is_not_applied():
    p,items,_=fixture();p['batches']=p['batches'][:1]
    key=items[0]['document_id'],items[0]['body_sha256']
    records={key:items[0]}
    assert prior_results_applied(p,records,{key:{'status':'PARTIAL'}},lambda record:False) is True
    assert prior_results_applied({'batches':[]},records,{},lambda record:True) is False


def test_duplicate_prior_receipt_cannot_be_used_as_storage_proof():
    p,items,_=fixture();p['batches'][0]['results']*=2;p['batches']=p['batches'][:1]
    records={(items[0]['document_id'],items[0]['body_sha256']):items[0]}
    with pytest.raises(ValueError,match='duplicate prior reading receipt'):
        prior_results_applied(p,records,{},lambda record:True)
