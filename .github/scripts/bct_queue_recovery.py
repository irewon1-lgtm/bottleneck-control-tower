"""Gate 5: import actual CPU readings, preserve history, publish one generation."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from bct.future_github import GitHubTransport
from bct.future_review import _records, document_complete, review_patch, validate_review, queue_summary, READER_VERSION
from bct.future_store import apply_owned_patch
from bct.recovery_preservation import verify,seal
from bct.recovery_queue import project,corrected_version
from bct.recovery_pilot import resume_batches
from bct.recovery_versions import append_observed_versions
from bct.future_worker import _runs, LOCK_ID


def identity(*parts):
    return hashlib.sha256(json.dumps(parts,separators=(',',':')).encode()).hexdigest()


def merge_review_patch(document,patch,run_id):
    return apply_owned_patch(document,owner='review',patch=patch,
        operation_id='recovery-review-'+identity(run_id,patch),prepared_document=document)


def completeness_review(item,observation,run_id,fallback_time):
    digest=item['body_sha256'];document_id=item['document_id']
    return {'review_id':'recovered-completeness-'+identity(document_id,digest,observation['reclassification_rule']),
        'document_id':document_id,'body_sha256':digest,'reader_version':READER_VERSION,
        'kind':'access','access_status':'BLOCKED','observed_body_sha256':digest,
        'reviewed_at':observation.get('classification_corrected_at',fallback_time),
        'reason':'Source completeness corrected; preserved excerpt cannot establish FULL coverage. Prior observation, source hash and decisions retained.',
        'source_completeness_status':observation['body_status'],
        'reclassification_rule':observation['reclassification_rule'],
        'source_recovery_run_id':run_id}


def execute():
    root=Path(os.environ['RUNNER_TEMP'])/'bct-recovery'
    checkpoint=root/'checkpoint.json';report=json.loads(checkpoint.read_text())
    if any(report.get('gate'+str(i))!='PASS' for i in range(5)):
        raise RuntimeError('prior recovery gates required')
    atomic_probe=report.get('atomic_recovery_probe',{})
    if atomic_probe.get('status')!='PASS' or atomic_probe.get('actual_remote_execution') is not True:
        raise RuntimeError('actual remote interruption and competing-writer proof required')
    pilot=json.loads((root/'local-reader-probe.json').read_text())
    qualification=pilot.get('qualification_pilot') if pilot.get('mode')=='DRAIN' else pilot
    if (not qualification or qualification.get('probe_status')!='PASS' or qualification.get('actual_model_calls')!=61
            or [b.get('limit') for b in qualification['batches']]!=[1,10,50]
            or any(b.get('status')!='PASS' or b.get('actual_model_calls')!=b['limit']
                   or len(b['results'])!=b['limit'] for b in qualification['batches'])):
        raise RuntimeError('real 1/10/50 reading pilot not completed')
    limits=tuple(pilot.get('batch_limits',[1,10,50]))
    if (pilot.get('probe_status')!='PASS' or pilot.get('actual_model_calls')!=sum(limits)
            or [b.get('limit') for b in pilot['batches']]!=list(limits)
            or any(b.get('status')!='PASS' or b.get('actual_model_calls')!=b['limit']
                   or len(b['results'])!=b['limit'] for b in pilot['batches'])
            or pilot.get('mode')=='DRAIN' and (len(limits)>1 or any(not 1<=n<=50 for n in limits))):
        raise RuntimeError('actual current bounded reading batch incomplete')
    versions=json.loads((root/'source-recovery-versions.json').read_text())
    observations={x['url']:x for x in map(json.loads,(root/'source-recovery-attempts.jsonl').read_text().splitlines())}
    baseline=json.loads(Path('config/bct-recovery-preservation.json').read_text())
    transport=GitHubTransport(os.environ['GITHUB_REPOSITORY'],'future-bottleneck-data',os.environ['GITHUB_TOKEN'])
    c=transport.read('future-candidates.json');t=transport.read('future-tracking.json')
    if _runs(t.document).get(LOCK_ID,{}).get('state')=='RUNNING':
        raise RuntimeError('active worker claim blocks recovery publication')
    verify(c.document,t.document,baseline)
    candidate_document,added_versions=append_observed_versions(c.document,versions,observations,root/'private-source-cache')
    records={(x['document_id'],x.get('body_sha256')):x for x in _records(candidate_document)}
    for evidence,expected_limits in ((qualification,(1,10,50)),(pilot,limits)):
        payloads=[]
        for batch in evidence['batches']:
            for result in batch['results']:
                item=records[(result['document_id'],result['body_sha256'])]
                body=(root/'private-source-cache'/(result['body_sha256']+'.txt')).read_text()
                payloads.append({'document_id':result['document_id'],'body_sha256':result['body_sha256'],
                    'body':body,'body_status':item['body_status'],'read_start':0,'expected_read_end':len(body)})
                if evidence is qualification and evidence is not pilot and not document_complete(t.document,item):
                    raise ValueError('qualified pilot production completion disappeared')
        verified_batches=resume_batches(evidence,payloads,json.loads(Path('config/bct-local-reader.json').read_text()),limits=expected_limits)
        if len(verified_batches)!=len(expected_limits) or any(b['status']!='PASS' for b in verified_batches):
            raise ValueError('actual reading checkpoint validation failed')
    tracking=deepcopy(t.document);readings_added=0;accesses_added=0
    patch: dict[str, Any]={'reviews':{},'progress':{}}
    try:
        # Authenticate source bytes again before reopening any old failed task.
        initial=project(candidate_document,tracking,versions,observations,root/'private-source-cache')
        for row in initial['version_rows']:
            if row.get('source_completeness_corrected'):
                document_id=row['document_id'];digest=row['body_sha256']
                observation=corrected_version(observations[records[(document_id,digest)]['url']],digest)
                if observation is None:raise ValueError('corrected source observation missing')
                review=completeness_review(records[(document_id,digest)],observation,report['run_id'],pilot['finished_at'])
                rid=review['review_id']
                if rid in tracking.get('reviews',{}):continue
                view={**candidate_document,'results':{document_id:candidate_document['results'][document_id]}}
                normalized=validate_review(view,tracking,review)
                patch['reviews'][rid]=normalized;tracking.setdefault('reviews',{})[rid]=normalized;accesses_added+=1
                continue
            if not row['exact_full_source_recovered'] or row['state']=='COMPLETED':continue
            document_id=row['document_id'];digest=row['body_sha256'];observation=observations[records[(document_id,digest)]['url']]
            rid='recovered-access-'+identity(document_id,digest,observation['attempted_at'])
            if rid in tracking.get('reviews',{}):continue
            review={'review_id':rid,'document_id':document_id,'body_sha256':digest,
                    'reader_version':READER_VERSION,'kind':'access','access_status':'AVAILABLE',
                    'observed_body_sha256':digest,'reviewed_at':observation['attempted_at'],
                    'reason':'Actual hosted-runner FULL reaccess; private cache SHA256 and extent verified; prior failed attempt retained.',
                    'source_recovery_run_id':report['run_id']}
            # Exact document view retains the original immutable versions and
            # lets existing review validation avoid scanning all 128MB per row.
            view={**candidate_document,'results':{document_id:candidate_document['results'][document_id]}}
            normalized=validate_review(view,tracking,review)
            patch['reviews'][rid]=normalized;tracking.setdefault('reviews',{})[rid]=normalized;accesses_added+=1
        seen=set()
        for batch in pilot['batches']:
            for result in batch['results']:
                key=result['document_id'],result['body_sha256']
                if key in seen:raise ValueError('duplicate actual pilot reading')
                seen.add(key);item=records.get(key)
                if item is None or item['body_status']!='FULL':raise ValueError('pilot source version unavailable or not FULL')
                observation=observations.get(item.get('url'),{})
                if (observation.get('body_status')!='FULL' or observation.get('body_sha256')!=key[1]
                        or corrected_version(observation,key[1])):
                    raise ValueError('pilot source completeness corrected or actual FULL access missing')
                body=(root/'private-source-cache'/(key[1]+'.txt')).read_text()
                if hashlib.sha256(body.encode()).hexdigest()!=key[1] or len(body)!=result['expected_read_end'] or len(body)!=item['body_chars']:
                    raise ValueError('pilot reading binding changed')
                usage=result.get('usage',{});inference=result.get('inference_receipt',{})
                if (result.get('provider')!='local-cpu' or result.get('api_cost_usd')!=0
                        or usage.get('input_tokens',0)<=0 or usage.get('output_tokens',0)<=0
                        or inference.get('tokens_evaluated')!=usage['input_tokens']
                        or inference.get('truncated') is not False or inference.get('stop_type') not in ('eos','word')):
                    raise ValueError('pilot model execution receipt invalid')
                if document_complete(tracking,item):continue  # Same-version resume never rereads.
                rid='recovered-quick-'+identity(*key,READER_VERSION,result['model_revision'])
                submitted={**result['review'],'review_id':rid,'document_id':key[0],
                    'body_sha256':key[1],'source_version':item.get('source_version'),
                    'reader_version':READER_VERSION,'kind':'quick','read_start':result['read_start'],
                    'reviewed_at':pilot['finished_at'],'worker_provider':'local-cpu',
                    'worker_model':result['model'],'model_revision':result['model_revision'],
                    'actual_input_tokens':usage['input_tokens'],'actual_output_tokens':usage['output_tokens'],
                    'recovery_run_id':report['run_id']}
                view={**candidate_document,'results':{key[0]:candidate_document['results'][key[0]]}}
                changes=review_patch(view,tracking,submitted)
                for field in ('reviews','progress'):
                    patch[field].update(changes.get(field,{}));tracking.setdefault(field,{}).update(changes.get(field,{}))
                readings_added+=1
        patch['updated_at']=pilot['finished_at']
        merged=merge_review_patch(t.document,patch,report['run_id'])
        verify(candidate_document,merged,baseline)
        projection=project(candidate_document,merged,versions,observations,root/'private-source-cache')
        if projection['preserved_failure_versions']!=3696 or projection['completion_failure_state_overlap']!=0:
            raise ValueError('queue recovery preservation/partition failure')
        candidates=deepcopy(candidate_document)
        candidates.setdefault('summary',{})['review_queue']=queue_summary(candidate_document,merged)
        candidates.setdefault('summary',{})['recovery_queue']={k:v for k,v in projection.items() if k!='version_rows'}
        candidates['summary']['recovery_queue']['generation_run_id']=report['run_id']
        # Both authoritative roots and both display projections publish together.
        transport.write_many({'future-candidates.json':candidates,'future-tracking.json':merged},
            {'future-candidates.json':c.sha,'future-tracking.json':t.sha})
        # Verify the immutable generation just returned by the ref update;
        # a mutable-ref GET can briefly lag after a successful publication.
        confirmed_c=transport.read_at('future-candidates.json',transport.last_commit)
        confirmed_t=transport.read_at('future-tracking.json',transport.last_commit)
        if confirmed_c.document!=candidates or confirmed_t.document!=merged:
            raise ValueError('queue/reading generation readback differs')
        verify(confirmed_c.document,confirmed_t.document,baseline)
        retained=seal(confirmed_c.document,confirmed_t.document)
        (root/'recovery-preservation-seal.json').write_text(json.dumps(retained,ensure_ascii=False,indent=2)+'\n')
        if confirmed_c.document['results']!=candidate_document['results']:
            raise ValueError('queue recovery changed source decisions/scores')
        for field in ('targets','prediction_ledger'):
            if confirmed_t.document.get(field)!=t.document.get(field):
                raise ValueError('quick reading changed confirmed target/forecast')
        (root/'queue-recovery-versions.json').write_text(json.dumps(projection,ensure_ascii=False,indent=2)+'\n')
        # Restart/idempotency validation is real: reread stored immutable IDs.
        if any(confirmed_t.document.get('reviews',{}).get(rid)!=review for rid,review in patch['reviews'].items()):
            raise ValueError('resume review identity mismatch')
        if any(not document_complete(confirmed_t.document,records[(r['document_id'],r['body_sha256'])])
               for b in pilot['batches'] for r in b['results']):
            raise ValueError('stored actual reading coverage incomplete')
        published_commit=transport.last_commit
        replay_roots=transport.write_many({'future-candidates.json':candidates,'future-tracking.json':merged},
            {'future-candidates.json':confirmed_c.sha,'future-tracking.json':confirmed_t.sha})
        if (replay_roots!={'future-candidates.json':confirmed_c.sha,'future-tracking.json':confirmed_t.sha}
                or transport.last_commit!=published_commit):
            raise ValueError('same generation restart produced another commit')
        report.update(stage=5,status='PASS',gate5='PASS',next_stage=6,
            queue_recovery_commit=transport.last_commit,queue_state_counts=projection['counts'],
            actual_reader_results_added=readings_added,source_access_records_added=accesses_added,
            source_versions_appended=len(added_versions),source_previous_judgments_preserved=True,
            reader_completions_added=projection['legacy_read_results']-len(baseline['completed_versions']),
            original_184_completions_preserved=True,
            legacy_read_results=projection['legacy_read_results'],legacy_partial_read_results=projection['legacy_partial_read_results'],
            old_failure_versions_preserved=3696,source_decisions_scores_preserved=True,
            production_restart_same_generation='PASS',actual_remote_interruption_concurrency='PASS',
            confirmed_targets_predictions_preserved=True,completion_failure_state_overlap=0,
            full_clean_status='BLOCKED',full_clean_reason='STAGES_6_TO_FULL_NOT_CONNECTED',
            resume_condition='Real E2E and regression Stage 6, then publication Stage 7 required')
    except Exception as exc:
        report.update(stage=5,status='FAIL',gate5='FAIL',error_type=type(exc).__name__,
                      resume_condition='Fix actual queue/save/identity failure and restart Stage 0')
        raise
    finally:
        report['queue_recovery_finished_at']=datetime.now(timezone.utc).isoformat()
        checkpoint.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:report.get(k) for k in ('stage','status','gate5','actual_reader_results_added','source_access_records_added','queue_recovery_commit')}))
    return 0


def main():
    try:
        return execute()
    except Exception as exc:
        checkpoint=Path(os.environ['RUNNER_TEMP'])/'bct-recovery/checkpoint.json'
        report=json.loads(checkpoint.read_text())
        report.update(stage=5,status='FAIL',gate5='FAIL',error_type=type(exc).__name__,
                      full_clean_status='BLOCKED',resume_condition='Fix recorded queue gate failure and restart Stage 0')
        if type(exc) in (ValueError,RuntimeError):report['queue_failure_code']=str(exc)
        checkpoint.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:report.get(k) for k in ('stage','status','gate5','error_type','queue_failure_code')}))
        return 1


if __name__=='__main__':raise SystemExit(main())
