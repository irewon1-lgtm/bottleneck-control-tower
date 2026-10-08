"""Process only a successful RSS delta; do not query or load canonical corpus."""
import json
import os
from pathlib import Path

from bct import precursor_collection as collection


def run(manifest, root, *, search_endpoint=None, live_store=None):
    completed=collection.read(Path(__file__).resolve().parents[2]/'config/precursor-completed-exclusions.json')
    ids=set(completed['document_ids']);urls=set(completed['urls'])
    docs=[d for d in manifest.get('documents',[]) if d['document_id'] not in ids and d['url'] not in urls];summaries=[]
    for start in range(0,max(1,len(docs)),100):
        batch={**manifest,'documents':docs[start:start+100],'batch_number':start//100+1}
        summaries.append(collection.cycle(root,batch,search_endpoint=search_endpoint,live_store=live_store))
    return summaries


if __name__=='__main__':
    manifest=collection.read(os.environ['PRECURSOR_MANIFEST'])
    root=Path(os.environ['PRECURSOR_STATE'])
    summaries=run(manifest,root,search_endpoint=os.environ.get('PRECURSOR_SEARCH_ENDPOINT') or collection.DEFAULT_SEARCH_ENDPOINT,
                  live_store=os.environ.get('BCT_EXISTING_LIVE_STORE') or None)
    output=Path(os.environ['PRECURSOR_SUMMARY'])
    public={'format':collection.FORMAT,'cache_run_id':os.environ.get('GITHUB_RUN_ID'),
            'completed_at':collection.acquisition.now(),'engine_hashes':collection.hashes(),
            'new_verified_documents':summaries[-1]['new_verified_documents'],
            'scope_complete_events':summaries[-1]['scope_complete_events'],
            'independent_pair_count':len(summaries[-1]['independent_demand_supply_pairs']),
            'common_window_pair_count':len(summaries[-1]['common_future_window_pairs']),
            'synthesized_targets':summaries[-1]['synthesized_targets'],
            'early_preflight':summaries[-1]['early_preflight'],
            'live_execution_state':summaries[-1]['live_execution']['state'],
            'early_frozen':summaries[-1]['live_execution']['frozen'],'baseline_reprocessed':0}
    public.update({k:summaries[-1].get(k,'LEGACY_RECEIPT_NO_REPROCESSING' if k=='scope_reader_version' else 0) for k in ('scope_reader_version','backfill_qa_documents',
                  'additional_bodies_acquired','valid_additional_primary_documents')})
    output.write_text(json.dumps(public,indent=2)+'\n')
    print(json.dumps(public))
