"""Separate v2 entry point, immutable epoch and shadow-only append store."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path

from . import precursor_v2 as v2
from .objective_lock import stamp_export, require_objective
from .future_manual_review import _private_write

MODE='SHADOW'


def now():return datetime.now(timezone.utc).isoformat()


def write(path,value):
    value=stamp_export(value);value['record_sha256']=v2.digest(value)
    _private_write(Path(path),value);Path(path).chmod(0o444)
    return value


def read(path):
    value=json.loads(Path(path).read_text());require_objective(value)
    if value.get('record_sha256')!=v2.digest({k:v for k,v in value.items() if k!='record_sha256'}):raise ValueError('SHADOW_RECORD_INTEGRITY_MISMATCH')
    if value.get('mode')!=MODE:raise ValueError('NON_SHADOW_RECORD')
    return value


def engine_hashes():
    from . import objective_lock,forecast_discovery,future_manual_review,future_store,shadow_input_v2
    modules=(v2,objective_lock,forecast_discovery,future_manual_review,future_store,shadow_input_v2)
    hashes={Path(m.__file__).name:v2.digest(Path(m.__file__).read_bytes()) for m in modules}
    hashes[Path(__file__).name]=v2.digest(Path(__file__).read_bytes())
    return hashes


@contextmanager
def locked(root):
    root=Path(root).resolve()
    if 'live-state' in root.parts or (root/'session.json').exists():raise ValueError('V1_LIVE_STORE_FORBIDDEN')
    root.mkdir(parents=True,exist_ok=True)
    with (root/'.shadow-lock').open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        try:yield root
        finally:fcntl.flock(stream,fcntl.LOCK_UN)


def activate(root):
    with locked(root) as root:
        path=root/'activation.json'
        if path.exists():
            saved=read(path)
            if saved['engine_hashes']!=engine_hashes():raise ValueError('V2_EPOCH_ENGINE_CHANGED_CREATE_SEPARATE_EPOCH')
            return saved
        t=now();hashes=engine_hashes()
        return write(path,{'mode':MODE,'version':v2.VERSION,'epoch_id':'v2-shadow-'+v2.digest([t,hashes])[:24],
                         'activated_at':t,'engine_hashes':hashes,'policy':'Shadow only. No v1 prospective or LIVE writes. No backdating.'})


def validate_decision(evaluation):
    require_objective(evaluation)
    if evaluation['version']!=v2.VERSION or evaluation['decision_sha256']!=v2.digest({k:v for k,v in evaluation.items() if k!='decision_sha256'}):raise ValueError('PAIR_DECISION_INTEGRITY_MISMATCH')


def freeze(root,prepared,activation):
    """Consume evaluated decisions, not a second discovery/period predicate."""
    first=0;history=0;seen=set()
    grouped={}
    for evaluation in prepared['evaluations']:
        validate_decision(evaluation)
        if evaluation['target_id'] is None:continue
        grouped.setdefault(evaluation['target_id'],[]).append(evaluation)
    for tid,variants in grouped.items():
        evaluation=next((e for e in variants if e['early_eligible']),variants[0])
        tid=evaluation['target_id']
        path=Path(root)/'candidates'/(tid+'.json')
        if not evaluation['early_eligible'] and not path.exists():continue
        if tid in seen:continue
        seen.add(tid)
        if evaluation['early_eligible'] and evaluation['state']!='EARLY_FORECAST_CANDIDATE':raise ValueError('INCONSISTENT_PAIR_DECISION')
        payload={'mode':MODE,'version':v2.VERSION,'epoch_id':activation['epoch_id'],
                 'target_id':tid,'first_shadow_detected_at':prepared['as_of'],'decision':evaluation,
                 'live_performance':False,'engine_hashes':activation['engine_hashes']}
        if not path.exists():write(path,payload);first+=1
        else:
            saved=read(path)
            if saved['epoch_id']!=activation['epoch_id']:raise ValueError('CANDIDATE_EPOCH_MISMATCH')
        h=Path(root)/'history'/(tid+'-'+evaluation['decision_sha256']+'.json')
        if not h.exists():write(h,{'mode':MODE,'epoch_id':activation['epoch_id'],'decision':evaluation});history+=1
    return {'first_shadow_frozen':first,'history_appended':history,'live_early':0}


def run(root,documents):
    activation=activate(root)
    with locked(root) as root:
        # Same document/body snapshot is replay-idempotent within an epoch.
        input_sha=v2.digest(documents);receipt=root/'runs'/(input_sha+'.json')
        if receipt.exists():return read(receipt)
        before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*.json')}
        previous_first={r['target_id']:r['first_shadow_detected_at'] for r in (read(p) for p in (root/'candidates').glob('*.json'))}
        t=now();prepared=v2.synthesize(documents,as_of=t,previous_first=previous_first);stats=v2.counters(prepared)
        frozen=freeze(root,prepared,activation)
        result=write(receipt,{'mode':MODE,'version':v2.VERSION,'epoch_id':activation['epoch_id'],
                            'engine_hashes':activation['engine_hashes'],'input_sha256':input_sha,
                            'evaluated_at':t,'prepared':prepared,'counts':stats,'freeze':frozen,'live_performance':False})
        if any((root/p).read_bytes()!=b for p,b in before.items()):raise RuntimeError('EXISTING_SHADOW_RECORD_CHANGED')
        return result


def compare(root,*,input_path,gold_path,seal_path):
    """Frozen preserved input, v1 replay and v2 shadow; no LIVE operations."""
    seal=json.loads(Path(seal_path).read_text())
    for path in (input_path,gold_path):
        if seal[Path(path).name]!=v2.digest(Path(path).read_bytes()):raise ValueError('PREOUTPUT_INPUT_GOLD_SEAL_CHANGED')
    inputs=json.loads(Path(input_path).read_text());gold=json.loads(Path(gold_path).read_text())
    if not gold.get('frozen_before_v2_outputs'):raise ValueError('GOLD_NOT_FROZEN')
    docs=inputs['documents'];result=run(root,docs);as_of=result['evaluated_at']
    from . import precursor_discovery as v1
    # Identical original documents; no enriched scope/labels supplied to either.
    old,old_prepared=v1.discover(stamp_export({'documents':docs,'signals':[]}),mode='BACKFILL',now=as_of)
    prepared=result['prepared'];events=prepared['events'];docmap={d['document_id']:d for d in docs};case_results=[]
    evaluations={(e['demand_event_id'],e['supply_event_id']):e for e in prepared['evaluations']}
    for case in gold['cases']:
        for key in ('demand','supply'):
            ep=case[key];d=docmap[ep['document_id']];a,b=ep['locator']['start'],ep['locator']['end']
            if ep['body_sha256']!=d['body_sha256'] or ep['source_quote']!=d['body'][a:b]:raise ValueError('GOLD_SOURCE_LOCATOR_MISMATCH')
        def matches(ep,role):return [e for e in events if e['document_id']==ep['document_id'] and e['role']==role and e['reference']['locator']['start']<=ep['locator']['start'] and e['reference']['locator']['end']>=ep['locator']['end']]
        ds,ss=matches(case['demand'],'DEMAND'),matches(case['supply'],'SUPPLY')
        found=[evaluations[(d['event_id'],s['event_id'])] for d in ds for s in ss if (d['event_id'],s['event_id']) in evaluations]
        linked=any(e['relation']['state']=='VERIFIED' for e in found);early=any(e['early_eligible'] for e in found)
        case_results.append({'id':case['id'],'link_gold':case['link_gold'],'early_gold':case['early_gold'],
                             'link_predicted':linked,'early_predicted':early,'hard_negative':case['hard_negative'],
                             'stage':'PAIR_EVALUATED' if found else 'EVENT_NOT_EXTRACTED',
                             'states':[e['state'] for e in found],'reasons':sorted({r for e in found for r in e['reasons']})})
    certain=[c for c in case_results if c['link_gold'] is not None]
    tp=sum(c['link_gold'] and c['link_predicted'] for c in certain);fp=sum(not c['link_gold'] and c['link_predicted'] for c in certain);fn=sum(c['link_gold'] and not c['link_predicted'] for c in certain)
    report={'mode':MODE,'input_sha256':v2.digest(docs),'gold_sha256':v2.digest(Path(gold_path).read_bytes()),
            'v2_counts':result['counts'],'v1_counts':{'documents_valid':len(old_prepared['documents']),
            'events':len(old_prepared['retained_precursor_events']),'targets':len(old_prepared['synthesized_targets']),
            'early':len(old['candidates']),'rejections':len(old['rejected_inputs'])},
            'gold_cases':case_results,'link_metrics':{'tp':tp,'fp':fp,'fn':fn,'recall':tp/(tp+fn) if tp+fn else None,
            'precision':tp/(tp+fp) if tp+fp else None,'positive_gold_count':tp+fn,'independent_second_reader':gold.get('independent_second_reader',False),
            'recall_one_sided_95_lower':lower_bound(tp,tp+fn),'precision_one_sided_95_lower':lower_bound(tp,tp+fp)},
            'hard_negative_early_false_promotions':sum(c['hard_negative'] and c['early_predicted'] for c in case_results),
            'traceability':{'checked_references':0,'failures':0},'live_writes':0}
    etp=sum(c['early_gold'] and c['early_predicted'] for c in case_results)
    efp=sum(not c['early_gold'] and c['early_predicted'] for c in case_results)
    efn=sum(c['early_gold'] and not c['early_predicted'] for c in case_results)
    report['early_metrics']={'tp':etp,'fp':efp,'fn':efn,'precision':etp/(etp+efp) if etp+efp else None,'recall':etp/(etp+efn) if etp+efn else None}
    lm=report['link_metrics']
    sufficient=(gold.get('independent_second_reader') is True and gold.get('independent_sampling_units') is True and lm['positive_gold_count']>0
                and lm['recall_one_sided_95_lower'] is not None and lm['recall_one_sided_95_lower']>=.8
                and lm['precision_one_sided_95_lower'] is not None and lm['precision_one_sided_95_lower']>=.95
                and any(c['hard_negative'] for c in case_results) and not report['hard_negative_early_false_promotions'])
    lm['performance_status']='DIAGNOSTIC_PASS_NOT_HOLDOUT' if sufficient else 'UNVERIFIED: independent labels or statistical sample insufficient; no performance PASS'
    report['gold_pair_funnel']={'denominator':len(case_results),'extracted_pair':sum(c['stage']=='PAIR_EVALUATED' for c in case_results),
                              'linked':sum(c['link_predicted'] for c in case_results),'early':sum(c['early_predicted'] for c in case_results),
                              'uncertain_labels':sum(c['link_gold'] is None for c in case_results)}
    refs=[]
    for e in events:
        refs.append(e['reference']);refs+=e['context_references'];refs+=[f['reference'] for f in e['fields'].values()];refs+=[f['reference'] for f in e['facts'].values()]
        if e['period']:refs.append(e['period']['reference'])
    for e in prepared['evaluations']:refs+=e['evidence'];validate_decision(e)
    for ref in refs:v2.verify_reference(ref,docmap)
    report['traceability']['checked_references']=len(refs)
    path=Path(root)/'comparisons'/(v2.digest(report)+'.json')
    if not path.exists():write(path,report)
    return report


def lower_bound(successes,total):
    """Exact binomial one-sided 95% lower bound; clusters need grouped labels."""
    if not total:return None
    if not successes:return 0.0
    lo,hi=0.0,1.0
    for _ in range(60):
        p=(lo+hi)/2
        tail=sum(math.comb(total,k)*p**k*(1-p)**(total-k) for k in range(successes,total+1))
        if tail<.05:lo=p
        else:hi=p
    return (lo+hi)/2


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--store',type=Path,required=True)
    p.add_argument('--source-snapshot',type=Path,action='append',default=[])
    p.add_argument('--provenance-index',type=Path,action='append',default=[])
    p.add_argument('--gold',type=Path);p.add_argument('--seal',type=Path);a=p.parse_args()
    if bool(a.gold)!=bool(a.seal):p.error('--gold and --seal must be used together')
    if a.gold and (a.source_snapshot or a.provenance_index):p.error('Sealed comparison input cannot be supplemented; freeze a separate expanded input first.')
    if a.gold:result=compare(a.store,input_path=a.input,gold_path=a.gold,seal_path=a.seal)
    else:
        from .shadow_input_v2 import load_documents
        docs,loader=load_documents(a.input,source_snapshots=a.source_snapshot,provenance_indexes=a.provenance_index)
        result={**run(a.store,docs),'loader':loader}
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
