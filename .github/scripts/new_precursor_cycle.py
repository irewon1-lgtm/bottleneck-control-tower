"""Process only a successful RSS delta; do not query or load canonical corpus."""
import json
import hashlib
import importlib.util
import re
from collections import Counter
import os
from pathlib import Path

from bct import precursor_collection as collection


def run(manifest, root, *, search_endpoint=None, live_store=None,source_handoff=None):
    completed=collection.read(Path(__file__).resolve().parents[2]/'config/precursor-completed-exclusions.json')
    ids=set(completed['document_ids']);urls=set(completed['urls'])
    docs=[d for d in manifest.get('documents',[]) if d['document_id'] not in ids and d['url'] not in urls];summaries=[]
    if not docs and manifest.get('qa_copy_only') is not True:
        # A no-new RSS window must not reparse thousands of preserved articles.
        # This is a true no-op, not a successful scan of previous sources.
        return [{'new_verified_documents':0,'scope_complete_events':0,
                 'independent_demand_supply_pairs':[],
                 'common_future_window_pairs':[],'synthesized_targets':0,
                 'early_preflight':0,'live_execution':{'state':'NO_NEW_DOCUMENTS','frozen':0},
                 'source_integrity_state':'NOT_SCANNED_NO_NEW_DOCUMENTS',
                 'unverified_source_holds':0,'new_seed_attempts':0,'new_seed_statuses':{},
                 'additional_bodies_acquired':0,'valid_additional_primary_documents':0}]
    for start in range(0,max(1,len(docs)),100):
        batch={**manifest,'documents':docs[start:start+100],'batch_number':start//100+1}
        options={'search_endpoint':search_endpoint,'live_store':live_store}
        if source_handoff is not None:options['source_handoff']=source_handoff
        reused=(Path(root)/'cycles'/(collection.forecast_discovery.digest(batch)+'.json')).exists()
        summary=collection.cycle(root,batch,**options)
        if reused:
            summary={**summary,'cycle_receipt_reused':True,'new_seed_statuses':{}}
            for key in ('new_verified_documents','new_seed_attempts','additional_bodies_acquired',
                        'valid_additional_primary_documents'):summary[key]=0
        summaries.append(summary)
    return summaries


def count_sum(summaries, key):
    values=[row.get(key) for row in summaries]
    if any(value is None for value in values):return None
    if any(type(value) is not int or not 0<=value<=1_000_000 for value in values):
        raise ValueError('PUBLIC_ACQUISITION_INVALID_COUNTER')
    return sum(values)


def public_summary(summaries, *, cache_run_id, completed_at,cache_run_attempt=1):
    if not summaries:raise ValueError('PUBLIC_ACQUISITION_SUMMARY_REQUIRED')
    public={'format':collection.FORMAT,'cache_run_id':cache_run_id,'cache_run_attempt':cache_run_attempt,
            'completed_at':completed_at,'engine_hashes':collection.hashes(),
            'new_verified_documents':count_sum(summaries,'new_verified_documents'),
            'scope_complete_events':summaries[-1]['scope_complete_events'],
            'independent_pair_count':len(summaries[-1]['independent_demand_supply_pairs']),
            'common_window_pair_count':len(summaries[-1]['common_future_window_pairs']),
            'synthesized_targets':summaries[-1]['synthesized_targets'],
            'early_preflight':summaries[-1]['early_preflight'],
            'live_execution_state':summaries[-1]['live_execution']['state'],
            'early_frozen':summaries[-1]['live_execution']['frozen'],'baseline_reprocessed':0}
    public.update({k:summaries[-1].get(k,'LEGACY_RECEIPT_NO_REPROCESSING' if k=='scope_reader_version' else 0) for k in ('scope_reader_version','backfill_qa_documents',
                  'additional_bodies_acquired','valid_additional_primary_documents')})
    public['source_integrity_state']=summaries[-1].get('source_integrity_state','UNVERIFIED')
    public['unverified_source_holds']=summaries[-1].get('unverified_source_holds',0)
    public['evidence_graph']=summaries[-1].get('evidence_graph',{})
    public['graph_early_preflight']=summaries[-1].get('graph_early_preflight',0)
    public['graph_early_frozen']=summaries[-1].get('graph_live_execution',{}).get('frozen',0)
    public['unique_early_preflight']=summaries[-1].get('unique_early_preflight',summaries[-1]['early_preflight'])
    public['gap_verified_early_preflight']=summaries[-1].get('gap_verified_early_preflight',0)
    public['unverified_legacy_preflight']=summaries[-1].get('unverified_legacy_preflight',0)
    public['new_seed_attempts']=count_sum(summaries,'new_seed_attempts')
    statuses=Counter()
    for row in summaries:
        values=row.get('new_seed_statuses')
        if values is None:
            public['new_seed_statuses']=None;break
        if not isinstance(values,dict):raise ValueError('PUBLIC_ACQUISITION_INVALID_STATUSES')
        for key,value in values.items():
            if (key not in {'CAPTURED','PROVENANCE_BLOCKED','DUPLICATE_BODY_EXCLUDED',
                    'EXISTING_CORPUS_EXCLUDED','BEFORE_NEW_COLLECTION_CUTOVER',
                    'TIMEOUT','CONNECT_BLOCKED','NETWORK_FAILED'}
                    and not re.fullmatch(r'HTTP_[1-5][0-9]{2}',key)):
                raise ValueError('PUBLIC_ACQUISITION_STATUS_NOT_FIXED_CODE')
            if type(value)is not int or not 0<=value<=1_000_000:
                raise ValueError('PUBLIC_ACQUISITION_INVALID_COUNTER')
            statuses[key]+=value
    else:public['new_seed_statuses']=dict(statuses)
    for key in ('additional_bodies_acquired','valid_additional_primary_documents'):
        public[key]=count_sum(summaries,key)
    return public


def public_receipt(public, manifest, *, run_id, head_sha, rss_run_id, manifest_sha256, started_at,run_attempt=1,rss_run_attempt=1):
    if (type(run_id)is not int or run_id<=0 or type(rss_run_id)is not int or rss_run_id<=0
            or type(run_attempt)is not int or run_attempt<=0 or type(rss_run_attempt)is not int or rss_run_attempt<=0
            or not re.fullmatch('[0-9a-f]{40}',head_sha)
            or not re.fullmatch('[0-9a-f]{64}',manifest_sha256)):
        raise ValueError('PUBLIC_ACQUISITION_RUN_BINDING')
    counts={key:public.get(key) for key in ('new_seed_attempts','new_seed_statuses',
        'new_verified_documents','additional_bodies_acquired','valid_additional_primary_documents')}
    counts.update(new_URLs=len(manifest['documents']),body_HTTP_requests=None,body_pending=None)
    return collection.stamp_export({'format':'bct-public-acquisition-1',
        'repository':'irewon1-lgtm/bottleneck-control-tower','run_id':run_id,
        'head_sha':head_sha,'run_attempt':run_attempt,'RSS_run_id':rss_run_id,'RSS_run_attempt':rss_run_attempt,'RSS_manifest_sha256':manifest_sha256,
        'collection_started_at':manifest['collection_started_at'],
        'acquisition_started_at':started_at,'completed_at':public['completed_at'],
        'scope_reader_version':public.get('scope_reader_version'),
        'counts':counts,'units':{'new_seed_attempts':'SEED_CAPTURE_OUTCOMES_NOT_HTTP_REQUESTS',
            'new_verified_documents':'NEW_SOURCE_VERIFIED_DOCUMENTS',
            'new_seed_statuses':'SEED_CAPTURE_OUTCOMES_BY_FIXED_CODE'},
        'source_integrity_state':public.get('source_integrity_state'),
        'unverified_source_holds':public.get('unverified_source_holds')})


if __name__=='__main__':
    manifest_path=Path(os.environ['PRECURSOR_MANIFEST'])
    manifest_bytes=manifest_path.read_bytes();manifest=json.loads(manifest_bytes)
    root=Path(os.environ['PRECURSOR_STATE']);started_at=collection.acquisition.now()
    before={path.name for path in (root/'documents').glob('*.json')}
    selected_sources={}
    graph_output=os.environ.get('PRECURSOR_GRAPH_SOURCES')
    def handoff(graph,roots):
        helper_path=Path(__file__).with_name('acquisition_sources.py')
        spec=importlib.util.spec_from_file_location('acquisition_source_handoff',helper_path)
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        versions=helper.graph_source_versions(graph,roots)
        for row in versions:
            key=(row['document_id'],row['body_sha256'],row['raw_sha256'])
            if key in selected_sources:
                row['root_document_ids']=sorted(set(row['root_document_ids'])|set(selected_sources[key]['root_document_ids']))
            selected_sources[key]=row
        return versions
    summaries=run(manifest,root,search_endpoint=os.environ.get('PRECURSOR_SEARCH_ENDPOINT') or collection.DEFAULT_SEARCH_ENDPOINT,
                  live_store=os.environ.get('BCT_EXISTING_LIVE_STORE') or None,
                  source_handoff=handoff if graph_output else None)
    # Replayed cycle receipts retain their original dependency versions even
    # though the frozen cycle does not execute its graph a second time.
    for summary in summaries:
        for row in summary.get('cpu_graph_source_versions',[]):
            key=(row['document_id'],row['body_sha256'],row['raw_sha256'])
            if key in selected_sources:row={**row,'root_document_ids':sorted(set(row['root_document_ids'])|set(selected_sources[key]['root_document_ids']))}
            selected_sources[key]=row
    public=public_summary(summaries,cache_run_id=os.environ.get('GITHUB_RUN_ID'),completed_at=collection.acquisition.now(),
        cache_run_attempt=int(os.environ.get('GITHUB_RUN_ATTEMPT','1')))
    output=Path(os.environ['PRECURSOR_SUMMARY']);output.write_text(json.dumps(public,indent=2)+'\n')
    selection=os.environ.get('PRECURSOR_NEW_DOCUMENT_FILES')
    if selection:Path(selection).write_text(json.dumps(sorted(path.name for path in (root/'documents').glob('*.json') if path.name not in before))+'\n')
    if graph_output:Path(graph_output).write_text(json.dumps({'sources':list(selected_sources.values()),
        'complete':not manifest.get('documents') or all('cpu_graph_source_versions'in summary for summary in summaries)},sort_keys=True)+'\n')
    public_dir=os.environ.get('PRECURSOR_PUBLIC_RECEIPT')
    if public_dir:
        validator_path=Path(__file__).with_name('public_acquisition.py')
        spec=importlib.util.spec_from_file_location('public_acquisition_validation',validator_path)
        validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
        receipt=public_receipt(public,manifest,run_id=int(os.environ['GITHUB_RUN_ID']),
            head_sha=os.environ['GITHUB_SHA'],rss_run_id=int(os.environ['RSS_RUN_ID']),
            run_attempt=int(os.environ['GITHUB_RUN_ATTEMPT']),rss_run_attempt=int(os.environ['RSS_RUN_ATTEMPT']),
            manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),started_at=started_at)
        validator.validate_receipt(receipt)
        directory=Path(public_dir);directory.mkdir(parents=True,exist_ok=False)
        raw=(json.dumps(receipt,sort_keys=True)+'\n').encode();(directory/'snapshot.json').write_bytes(raw)
        (directory/'manifest.json').write_text(json.dumps({'format':'bct-public-acquisition-manifest-1',
            'file':'snapshot.json','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},sort_keys=True)+'\n')
    print(json.dumps(public))
