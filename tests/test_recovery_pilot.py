from copy import deepcopy
import pytest
from bct.recovery_pilot import resume_batches


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
