"""Optional isolated post-save hook; not activated in any operational workflow.

Input is an explicit new-document delta with complete body/provenance records,
not RSS metadata. Reads only the supplied delta; no fetching or corpus scan.
Failures are recorded separately and do not fail collection/V2 execution.
"""
import json
import os
from pathlib import Path
from bct import review_intake
from bct.objective_lock import stamp_export

def run(input_path, store, output, semantic=None, prospective=False):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    try:
        bundle=json.loads(Path(input_path).read_text())
        packets=json.loads(Path(semantic).read_text()) if semantic else stamp_export({'packets':[]})
        review_intake.require_objective(packets)
        result=review_intake.process(bundle,json.loads(Path('review-leads/contract.json').read_text()),
            store,semantic_packets=packets['packets'],prospective=prospective)
    except Exception as error:
        result=stamp_export({'review_intake_status':'BLOCKED','reason':str(error),'collector_failed_by_review':False,
                            'EARLY_success_count':0,'LIVE_writes':0})
    output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    if 'records' in result:output.with_suffix('.md').write_text(review_intake.render(result))
    return result

if __name__=='__main__':
    result=run(os.environ['BCT_REVIEW_NEW_DOCUMENTS'],os.environ['BCT_REVIEW_STORE'],os.environ['BCT_REVIEW_OUTPUT'],
        os.environ.get('BCT_REVIEW_SEMANTIC'),os.environ.get('BCT_REVIEW_PROSPECTIVE')=='1')
    print(json.dumps({'review_intake_status':result.get('review_intake_status','COMPLETED'),
                      'counts':result.get('counts',{}),'LIVE_writes':0}))
