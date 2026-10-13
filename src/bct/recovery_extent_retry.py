"""One exact stopped grammar-failure retry after verified native correction."""
import hashlib
from .future_body import read_cached_body
from .recovery_preservation import digest


def extent_retry_policy(requester, config, runs, cache):
    version=config['version']
    def matches(item, previous):
        return (previous.get('state')=='ERROR' and previous.get('reason')=='HTTPError'
                and previous.get('run_id')==config['worker_id']
                and item.get('document_id')==previous.get('document_id')==version['document_id']
                and item.get('body_sha256')==previous.get('body_sha256')==version['body_sha256']
                and item.get('resume_at')==previous.get('read_start')==version['read_start']
                and digest(previous)==config['prior_error_sha256'])
    needed=any(matches({'document_id':r.get('document_id'),'body_sha256':r.get('body_sha256'),
                        'resume_at':r.get('read_start')},r) for r in runs)
    if not needed:return lambda item,previous:False
    for proof,conclusion in ((config['original'],'failure'),(config['native_correction'],'success')):
        run=requester('GET','/actions/runs/'+str(proof['run_id']))
        artifact=requester('GET','/actions/artifacts/'+str(proof['artifact_id']))
        if (run['status']!='completed' or run['conclusion']!=conclusion
                or run['head_sha']!=proof['code_sha']
                or artifact['workflow_run']['id']!=proof['run_id']
                or artifact.get('expired') is True
                or artifact.get('digest')!='sha256:'+proof['artifact_sha256']):
            raise ValueError('stopped extent failure and actual native correction proof required')
    def retry(item,previous):
        if not matches(item,previous):return False
        body=read_cached_body(cache,version['body_sha256'])
        return (hashlib.sha256(body.encode()).hexdigest()==version['body_sha256']
                and len(body)==version['expected_read_end']
                and version['expected_read_end']-version['read_start']==1)
    return retry
