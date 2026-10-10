"""Resume actual reading receipts without counting cached work as new calls."""
from copy import deepcopy
from typing import Any

from .future_reader import validate_output


def prior_results_applied(previous, records, corrections, is_complete):
    """Prove that a restored pilot's usable results already reached storage.

    A later run can fail before Gate 5 and therefore replace the checkpoint
    carrying ``gate5=PASS`` while still preserving the earlier reader report.
    The authoritative proof in that case is the exact document/body version
    and its complete immutable review in the current tracking generation.
    Corrected-source results are quarantined separately and do not need to be
    replayed.  Empty reports are never treated as applied.
    """
    results=[result for batch in previous.get('batches',[])
             for result in batch.get('results',[])]
    if not results:return False
    keys=[(result['document_id'],result['body_sha256']) for result in results]
    if len(set(keys))!=len(keys):raise ValueError('duplicate prior reading receipt')
    usable=[key for key in keys if key not in corrections]
    return all(key in records and is_complete(records[key]) for key in usable)


def quarantine_corrected_readings(previous, corrections):
    """Keep corrected-source receipts as history, never import as completions.

    A changed source inventory must still pass normal order/hash validation.
    Only explicit, hash-bound completeness corrections can withhold receipts.
    Qualification history is immutable and cannot be silently requalified.
    """
    restored=deepcopy(previous);held=[]
    for batch in restored.get('batches',[]):
        kept=[]
        for result in batch.get('results',[]):
            key=result['document_id'],result['body_sha256']
            correction=corrections.get(key)
            if correction is None:
                kept.append(result);continue
            correction_rules = (
                'ARTICLE_CONTROL_ONLY_V1', 'ARTICLE_TERMINAL_ELLIPSIS_V1',
                'AUTHOR_METADATA_ONLY_V1', 'VIDEO_SUMMARY_WITHOUT_TRANSCRIPT_V1',
                'MEMBERSHIP_ACCESS_LIMIT_V1')
            qualification_gate = (previous.get('mode') == 'QUALIFICATION'
                                  and correction.get('reclassification_rule') in correction_rules)
            if (previous.get('mode')!='DRAIN' and not qualification_gate or correction.get('body_sha256')!=key[1]
                    or correction.get('reclassification_rule') not in correction_rules):
                raise ValueError('prior reading quarantine requires exact source correction')
            held.append({'result':deepcopy(result),'source_correction':deepcopy(correction),
                         'preserved_from_run_id':previous['run_id'],
                         'reason':'SOURCE_COMPLETENESS_CORRECTED'})
        batch['results']=kept
    return restored,held


def resume_batches(previous,items,config,*,limits=(1,10,50)):
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
    if any(type(n) is not int or not 1<=n<=50 for n in limits):raise ValueError('invalid reading batch limit')
    if len(prior_batches)>len(limits):raise ValueError('invalid prior reading batch count')
    for index,batch in enumerate(prior_batches):
        count=limits[index];results=batch.get('results',[])
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
