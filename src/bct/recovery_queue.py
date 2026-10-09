"""One operational state per version, with historical reading kept separately.

A terminal reading of PARTIAL material is a preserved reading result; it is
not a newly verified FULL completion. Failed attempts are append-only history.
"""
from collections import Counter
from hashlib import sha256
from pathlib import Path

from .future_review import _records, document_complete, queue_items
from .future_worker import _runs

STATES=('PENDING','PROCESSING','COMPLETED','SOURCE_WAIT','EVIDENCE_WAIT','FAILED','RETRY_SCHEDULED')


def key(item):
    return item['document_id'],item.get('body_sha256') or item.get('old_body_sha256') or item.get('source_version')


def corrected_version(observation,body_hash):
    while isinstance(observation,dict):
        if (observation.get('body_sha256')==body_hash and observation.get('reclassification_rule') in
                ('ARTICLE_CONTROL_ONLY_V1','ARTICLE_TERMINAL_ELLIPSIS_V1','AUTHOR_METADATA_ONLY_V1',
                 'VIDEO_SUMMARY_WITHOUT_TRANSCRIPT_V1','MEMBERSHIP_ACCESS_LIMIT_V1')):
            return observation
        observation=observation.get('prior_source_observation')
    return None


def project(candidates,tracking,versions,observations,cache):
    records={key(x):x for x in _records(candidates)}
    failures={key(v):v for v in versions}
    if len(failures)!=len(versions):raise ValueError('duplicate recovery version identity')
    queues=queue_items(candidates,tracking)
    included=set(failures)
    for lane in queues.values():included.update(key(x) for x in lane)
    active={key(r) for r in _runs(tracking).values() if isinstance(r,dict)
            and r.get('state')=='RUNNING' and r.get('document_id')}
    rows=[]
    for identity in sorted(included,key=lambda x:(x[0],str(x[1]))):
        item=records.get(identity);prior=failures.get(identity)
        if item is None:
            if not prior:raise ValueError('queue version disappeared')
            item={'document_id':prior['document_id'],'body_sha256':prior.get('old_body_sha256'),
                  'source_version':prior.get('source_version'),'body_status':'UNAVAILABLE','url':prior['url']}
        observation=observations.get(item.get('url'),{})
        body_hash=item.get('body_sha256');exact=False
        if (body_hash and observation.get('body_status')=='FULL'
                and observation.get('body_sha256')==body_hash):
            if len(body_hash)!=64 or any(c not in '0123456789abcdef' for c in body_hash):
                raise ValueError('invalid queue source body digest')
            body=(Path(cache)/(body_hash+'.txt')).read_text()
            if sha256(body.encode()).hexdigest()!=body_hash or len(body)!=item.get('body_chars'):
                raise ValueError('queue recovered body hash/extent mismatch')
            exact=True
        read_result=bool(body_hash and document_complete(tracking,item))
        stored_status=item.get('body_status','UNAVAILABLE')
        corrected=corrected_version(observation,body_hash) is not None
        full=stored_status=='FULL' and not corrected or exact
        if read_result and full:state='COMPLETED'
        elif identity in active:state='PROCESSING'
        elif prior and prior['old_failure']=='REQUIRED_EVIDENCE_MISSING':state='EVIDENCE_WAIT'
        elif corrected:state='SOURCE_WAIT'
        elif exact:state='PENDING'
        elif observation.get('resume_after') is not None:state='RETRY_SCHEDULED'
        elif observation.get('status') in ('SOURCE_BLOCKED','BLOCKED','UNAVAILABLE','ERROR'):state='FAILED'
        elif stored_status in ('PARTIAL','UNAVAILABLE') or prior:state='SOURCE_WAIT'
        else:state='PENDING'
        matching=[r for r in tracking.get('reviews',{}).values() if isinstance(r,dict)
                  and r.get('document_id')==item['document_id'] and r.get('body_sha256')==body_hash]
        evidence_wait=bool(prior and prior['old_failure']=='REQUIRED_EVIDENCE_MISSING') or any(
            r.get('candidate_state')=='DATA_WAIT' for r in matching)
        rows.append({'document_id':item['document_id'],'source_version':item.get('source_version'),
            'body_sha256':body_hash,'state':state,'stored_body_status':stored_status,
            'exact_full_source_recovered':exact,'historical_read_result_preserved':read_result,
            'source_completeness_corrected':corrected,
            'evidence_state':'EVIDENCE_WAIT' if evidence_wait else 'NOT_EVALUATED',
            'old_failure':prior['old_failure'] if prior else None,
            'failure_history_retained':bool(prior),'observed_status':observation.get('status'),
            'observed_body_sha256':observation.get('body_sha256'),
            'resume_after':observation.get('resume_after')})
    counts=Counter(r['state'] for r in rows)
    if sum(counts.values())!=len(rows) or set(counts)-set(STATES):
        raise ValueError('operational queue state partition mismatch')
    legacy=[x for x in records.values() if document_complete(tracking,x)]
    corrected_reads=[x for x in legacy if x.get('body_status')=='FULL'
                     and corrected_version(observations.get(x.get('url'),{}),x.get('body_sha256'))]
    return {'format':'bct-recovery-queue-v1','version_rows':rows,
            'counts':{s:counts[s] for s in STATES},'total_queue_versions':len(rows),
            'preserved_failure_versions':len(versions),'legacy_read_results':len(legacy),
            'legacy_partial_read_results':sum(x.get('body_status')=='PARTIAL' for x in legacy),
            'source_corrected_read_results':len(corrected_reads),
            'non_full_read_results':sum(x.get('body_status')!='FULL' for x in legacy)+len(corrected_reads),
            'historical_completed_failed_overlap':sum(key(x) in failures for x in legacy),
            'candidate_evidence_wait':sum(r['evidence_state']=='EVIDENCE_WAIT' for r in rows),
            'completion_failure_state_overlap':0,'prediction_performance':'UNVERIFIED'}
