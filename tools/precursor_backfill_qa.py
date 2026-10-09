"""Version-bound real-cache QA. No collection or LIVE/session/ledger writes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from bct import precursor_collection as c, precursor_discovery as pd
from bct import precursor_scope_reader as scope
from bct import precursor_evidence_graph as graph_reader
from bct.objective_lock import stamp_export


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def snapshot(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


def metrics(documents, as_of):
    events=[e for d in documents for e in d.get('retained_collection_events',[])]
    b=stamp_export({'documents':documents,'signals':[],'mode':'BACKFILL'})
    result,prepared=pd.discover(b,mode='BACKFILL',now=as_of)
    stats=c.counters(result,prepared)
    unknown=Counter(k for e in events for k in e.get('missing_scope',[]))
    timing_unknown=Counter(r for e in events for r in e.get('temporal_facts',{}).get('unknown_reasons',[]))
    return {'verified_documents':len(documents),'events':len(events),
            **{k:sum(k in e['scope'] for e in events) for k in pd.SCOPE},
            'complete_target_events':sum(not e.get('missing_scope',list(pd.SCOPE)) for e in events),
            'independent_pairs':len(stats['independent_demand_supply_pairs']),
            'comparable_period_pairs':len(stats['common_future_window_pairs'])+len(stats['explicit_future_timing_pairs']),
            'synthesized_targets':stats['synthesized_targets'],'backfill_early_candidates':len(result['candidates']),
            'new_live_early_candidates':0,
            'known_bad_product_events':sum(e['scope'].get('product',{}).get('value','').casefold()=='the id' for e in events),
            'taxonomy_region_events':sum(bool(e['scope'].get('region') and d['body'][max(0,e['scope']['region']['locator']['start']-8):e['scope']['region']['locator']['start']].strip().upper().endswith('REGION:')) for d in documents for e in d.get('retained_collection_events',[])),
            'scope_unknowns':dict(unknown),'temporal_unknowns':dict(timing_unknown),
            'period_references':sum(len(e.get('temporal_facts',{}).get('periods',[])) for e in events),
            'physical_quantity_references':sum(len(e.get('temporal_facts',{}).get('quantities',[])) for e in events),
            'rejected_inputs':len(result['rejected_inputs']),
            'rejection_reasons':dict(Counter(r['reason'] for r in result['rejected_inputs']))},prepared


def validate(documents):
    refs=0
    for d in documents:
        scope.validate_references(d,d['retained_collection_events'])
        for e in d['retained_collection_events']:
            pd._validate(d,e)
            facts=e.get('temporal_facts',{})
            for fact in facts.get('periods',[])+facts.get('quantities',[])+facts.get('relief',[]):
                ref=fact['reference'];loc=ref['locator']
                assert ref['body_sha256']==d['body_sha256'] and ref['document_id']==d['document_id']
                assert d['body'][loc['start']:loc['end']]==ref['source_quote'];refs+=1
    return refs


def run(root,as_of):
    root=Path(root);before_hashes=snapshot(root)
    original=[c.read(p) for p in sorted((root/'documents').glob('*.json')) if c.read(p).get('provenance')=='PASS']
    if len(original)>230:raise ValueError('baseline cache limit is 230; select a fixed snapshot')
    new=c.stored_documents(root)
    before,unused=metrics(original,as_of);after,prepared=metrics(new,as_of)
    repeat=[]
    for d in original:
        raw=(root/'raw'/(d['raw_sha256']+'.html')).read_bytes()
        meta=d.get('sec_filing_metadata')
        meta_raw=(root/'raw'/(meta['raw_sha256']+'.json')).read_bytes() if meta else None
        snapshot_document=c.verified_stored_snapshot(d,raw,metadata_record=meta,metadata_raw=meta_raw)
        repeat.append(c.structure(snapshot_document,raw))
    deterministic=digest(new)==digest(repeat)
    references=validate(new)
    graph=graph_reader.analyze(new,mode='BACKFILL',now=as_of)
    requests=[c.read(p) for p in sorted((root/'requests').glob('*.json'))]
    searches={'baseline_requests':len(requests),'baseline_url_attempts':sum(len(r.get('captures',[])) for r in requests),
              'baseline_bodies_acquired':sum(x.get('status')=='CAPTURED' for r in requests for x in r.get('captures',[])),
              'baseline_valid_primary_evidence':'UNKNOWN_NOT_RECORDED_BY_OLD_COLLECTOR',
              'access_failure_statuses':dict(Counter(x.get('status') for r in requests for x in r.get('captures',[])))}
    preserved=before_hashes==snapshot(root)
    assert preserved and deterministic
    return stamp_export({'mode':'BACKFILL_QA','as_of':as_of,'scope_reader_version':scope.VERSION,
            'before':before,'after':after,'search_baseline':searches,
            'graph_qa':{'version':graph_reader.VERSION,'source_reference_checks':graph['reference_checks'],
                        'cross_document_edges':sum(e['references'][0]['document_id']!=e['references'][1]['document_id'] for e in graph['edges']),
                        'complete_target_events':graph['complete_target_events'],'independent_pairs':graph['independent_pairs'],
                        'comparable_period_pairs':graph['comparable_period_pairs'],'backfill_early_candidates':len(graph['protected_result']['candidates'])},
            'preservation':{'cache_files_unchanged':preserved,'cache_file_count':len(before_hashes),
                            'deterministic_replay':deterministic,'source_reference_checks':'PASS','new_temporal_references_checked':references,
                            'source_input_sha256':digest([{'document_id':d['document_id'],'body_sha256':d['body_sha256'],'raw_sha256':d['raw_sha256']} for d in original]),
                            'engine_hashes':c.hashes(),'live_write_count':0,
                            'same_version_documents':sum(d['body_sha256']==old['body_sha256'] for d,old in zip(new,original)),
                            'corrected_source_versions':[{'document_id':d['document_id'],**d['source_version_correction']}
                                                         for d in new if d.get('source_version_correction')]},
            'examples':[{'document_id':d['document_id'],'origin_url':d['origin_url'],'body_sha256':d['body_sha256'],
                         'event_id':e['event_id'],'scope':e['scope'],'missing_scope':e['missing_scope']}
                        for d in new for e in d['retained_collection_events'] if e['scope']][:18],
            'limitations':['Backfill candidates are not LIVE detection successes.',
                           'Unsupported literal date expressions remain outside protected-engine windows.',
                           'Absence of fully evidenced eligibility/customer/pool scope cannot be repaired by inference.']})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--as-of',default='2026-10-08T14:11:35+00:00');p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();value=run(args.cache,args.as_of);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:value[k] for k in ('mode','before','after','preservation')},ensure_ascii=False))
