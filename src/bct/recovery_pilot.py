"""Resume actual reading receipts without counting cached work as new calls."""
from copy import deepcopy
from typing import Any

from .future_reader import validate_output


def resume_batches(previous,items,config):
    if not previous:return []
    if not any(b.get('results') for b in previous.get('batches',[])):return []
    setup=previous.get('model_setup_receipt',{})
    for field in ('model','revision','files','llama_cpp_sha','alias','context_tokens','max_output_tokens'):
        if setup.get(field)!=config[field]:raise ValueError('prior reading model configuration changed')
    if setup.get('weights_verified') is not True or setup.get('build_verified') is not True:
        raise ValueError('prior reading model proof unavailable')
    positions={ (p['document_id'],p['body_sha256']):i for i,p in enumerate(items) }
    seen=set();offset=0
    batches: list[dict[str, Any]]=[]
    prior_batches=previous.get('batches',[])
    if len(prior_batches)>3:raise ValueError('invalid prior reading batch count')
    for index,batch in enumerate(prior_batches):
        count=(1,10,50)[index];results=batch.get('results',[])
        calls=batch.get('actual_model_calls')
        if batch.get('limit')!=count or type(calls) is not int or calls<len(results) or len(results)>count:
            raise ValueError('invalid prior reading batch extent')
        if index and batches[-1]['status']!='PASS':raise ValueError('prior pilot stage skipped')
        for position,result in enumerate(results):
            key=result['document_id'],result['body_sha256']
            if key in seen or positions.get(key)!=offset+position:raise ValueError('prior reading source order/binding changed')
            seen.add(key);payload=items[offset+position]
            if result.get('expected_read_end')!=payload['expected_read_end'] or result.get('read_start')!=0:
                raise ValueError('prior reading source range changed')
            validate_output(result['review'],payload)
            if result['review']['disposition']=='INCOMPLETE':raise ValueError('prior reading incomplete')
            usage=result.get('usage',{});inference=result.get('inference_receipt',{})
            if (result.get('provider')!='local-cpu' or result.get('model_revision')!=config['revision']
                    or inference.get('llama_cpp_sha')!=config['llama_cpp_sha']
                    or any(type(usage.get(k)) is not int or usage[k]<=0 for k in ('input_tokens','output_tokens'))
                    or inference.get('tokens_evaluated')!=usage['input_tokens']
                    or inference.get('truncated') is not False or inference.get('stop_type') not in ('eos','word')):
                raise ValueError('prior reading inference proof invalid')
        restored=deepcopy(batch);restored['preserved_from_run_id']=previous['run_id']
        restored['prior_actual_model_calls']=calls
        restored['actual_model_calls']=len(results)
        restored['status']='PASS' if len(results)==count else 'RUNNING'
        batches.append(restored);offset+=count
    return batches
