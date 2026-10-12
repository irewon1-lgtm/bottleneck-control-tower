"""Read-only proof of original native failure and incomplete review preservation."""
import json,os,hashlib
from pathlib import Path
from bct.future_github import GitHubTransport
from bct.future_worker import _runs
from bct.future_review import _version_item,document_complete
from bct.recovery_preservation import digest
def main():
    cfg=json.loads(Path('config/bct-native-extent-recovery.json').read_text())
    t=GitHubTransport(os.environ['GITHUB_REPOSITORY'],'future-bottleneck-data',os.environ['GITHUB_TOKEN'])
    request=t.requester
    def read_only(method,suffix,payload=None):
        if method!='GET':raise ValueError('mutations forbidden')
        return request(method,suffix,payload)
    t.requester=read_only
    head='e71c2f9e68ce21893d58505be96597a8389dc125'
    candidates=t.read_at('future-candidates.json',head).document
    tracking=t.read_at('future-tracking.json',head).document
    doc=cfg['version']['document_id'];body=cfg['version']['body_sha256']
    runs=_runs(tracking)
    archived=[(k,v) for k,v in runs.items() if v.get('type')=='worker_retry_history' and v.get('document_id')==doc and v.get('body_sha256')==body and digest(v['prior_state'])==cfg['prior_error_sha256']]
    assert len(archived)==1,'exact original ERROR archive required'
    old=archived[0][1]['prior_state']
    assert old['state']=='ERROR' and old['reason']=='HTTPError' and old['run_id']==cfg['worker_id']
    current=runs[archived[0][1]['work_id']]
    assert current['state']=='SUCCESS' and current['run_id']!=old['run_id']
    reviews=tracking['reviews']
    prior=reviews['auto-quick-e65cdb55a521d0d271f2eb6ff5d30683']
    assert prior['disposition']=='INCOMPLETE' and prior['read_end']==5534 and prior['body_sha256']==body
    complete=[(k,v) for k,v in reviews.items() if v.get('body_sha256')==body and v.get('document_id')==doc and v.get('read_start')==5534 and v.get('read_end')==5535 and v.get('read_complete') is True and v.get('disposition')!='INCOMPLETE']
    assert len(complete)==1,'one actual continuation completion required'
    item=_version_item(candidates,doc,body)
    assert item['body_chars']==5535 and document_complete(tracking,item)
    receipt={'status':'PASS','actual_execution':True,'pinned_sidecar_sha':head,'document_id':doc,'original_body_sha256':body,'archived_error_sha256':digest(old),'archive_id':archived[0][0],'prior_incomplete_review_id':'auto-quick-e65cdb55a521d0d271f2eb6ff5d30683','prior_incomplete_review_sha256':digest(prior),'new_real_completion_id':complete[0][0],'new_real_completion_sha256':digest(complete[0][1]),'new_disposition':complete[0][1]['disposition'],'actual_read_range':[5534,5535],'entire_version_complete':True,'production_writes':0,'prediction_performance':'UNVERIFIED'}
    p=Path(os.environ['RUNNER_TEMP'])/'native-archive-receipt.json';p.write_text(json.dumps(receipt,indent=2))
    print('NATIVE_ARCHIVE_VALIDATED_JSON='+json.dumps(receipt,separators=(',',':')))
if __name__=='__main__':main()
