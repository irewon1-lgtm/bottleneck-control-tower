"""Check immutable baseline identities, rather than trusting unchanged counts."""
from copy import deepcopy
import hashlib
import json

from .future_review import queue_items
from .future_worker import _runs


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def seal(candidates,tracking):
    """Extend the immutable baseline to every result recovered so far."""
    targets=tracking.get('targets',[])
    targets=targets if isinstance(targets,dict) else {r.get('id') or r.get('target'):r for r in targets}
    runs=_runs(tracking)
    return {'document_ids':sorted(candidates.get('results',{})),
        'version_hashes':{key:sorted(r.get('versions',{})) for key,r in candidates.get('results',{}).items()},
        'version_record_hashes':{key:{h:digest(v) for h,v in r.get('versions',{}).items()}
                                for key,r in candidates.get('results',{}).items()},
        'review_hashes':{key:digest(v) for key,v in tracking.get('reviews',{}).items()},
        'failed_run_hashes':{key:digest(v) for key,v in runs.items()
            if v.get('type')=='queue_resolution' and v.get('state')=='FAIL'},
        'completed_versions':sorted([r['document_id'],r['body_sha256']]
            for r in queue_items(candidates,tracking)['completed']),
        'target_hashes':{key:digest(v) for key,v in targets.items()}}


def verify(candidates, tracking, baseline):
    results=candidates.get('results', {})
    if not set(baseline['document_ids']) <= set(results):
        raise ValueError('preserved candidate identity missing')
    for document_id, hashes in baseline['version_hashes'].items():
        if not set(hashes) <= set(results[document_id].get('versions', {})):
            raise ValueError('preserved source/body version missing')
    for document_id, hashes in baseline.get('version_record_hashes',{}).items():
        for body_hash,expected in hashes.items():
            if digest(results[document_id].get('versions',{}).get(body_hash))!=expected:
                raise ValueError('preserved source version judgment changed')
    for review_id, expected in baseline['review_hashes'].items():
        if digest(tracking.get('reviews', {}).get(review_id)) != expected:
            raise ValueError('preserved review changed or missing')
    runs=_runs(tracking)
    for run_id, expected in baseline['failed_run_hashes'].items():
        if digest(runs.get(run_id)) != expected:
            raise ValueError('preserved failure history changed or missing')
    completed={(r['document_id'],r['body_sha256']) for r in queue_items(candidates,tracking)['completed']}
    if not {tuple(x) for x in baseline['completed_versions']} <= completed:
        raise ValueError('preserved read completion missing')
    targets=tracking.get('targets', [])
    targets=targets if isinstance(targets,dict) else {r.get('id') or r.get('target'):r for r in targets}
    for target_id, expected in baseline.get('target_hashes', {}).items():
        if digest(targets.get(target_id)) != expected:
            raise ValueError('preserved confirmed target changed or missing')
    return {'status':'PASS','preserved_candidates':len(baseline['document_ids']),
            'preserved_completed_versions':len(baseline['completed_versions']),
            'preserved_failure_versions':len(baseline['failed_run_hashes']),
            'preserved_reviews':len(baseline['review_hashes'])}


def restore_version_records(candidates, baseline, trusted_candidates):
    """Restore only sealed version judgments from their trusted generation."""
    restored = deepcopy(candidates)
    receipts = []
    current_results = restored.get('results', {})
    trusted_results = trusted_candidates.get('results', {})
    for document_id, hashes in baseline.get('version_record_hashes', {}).items():
        if document_id not in current_results:
            raise ValueError('preserved candidate identity missing')
        versions = current_results[document_id].setdefault('versions', {})
        trusted_versions = trusted_results.get(document_id, {}).get('versions', {})
        for body_hash, expected in hashes.items():
            current = versions.get(body_hash)
            if digest(current) == expected:
                continue
            trusted = trusted_versions.get(body_hash)
            if digest(trusted) != expected:
                raise ValueError('trusted generation does not contain sealed source version judgment')
            receipts.append({'document_id': document_id, 'body_sha256': body_hash,
                             'before_sha256': digest(current) if current is not None else None,
                             'restored_sha256': expected})
            # Preserve the exact drifted record as HOLD evidence before
            # restoring the independently sealed original judgment.
            record = current_results[document_id]
            record.setdefault('version_judgment_holds', {})[digest(current)] = {
                'state': 'HOLD', 'body_sha256': body_hash,
                'observed_record': deepcopy(current), 'original_record_sha256': expected,
                'reason': 'SEALED_VERSION_RECORD_DRIFT', 'promoted_to_completion': False,
            }
            if isinstance(current, dict) and current.get('access_checked_at'):
                checked = current['access_checked_at']
                record.setdefault('version_access', {}).setdefault(body_hash, {}).setdefault(checked, {
                    'reaccess_status': current.get('reaccess_status'),
                    'access_checked_at': checked,
                    'observed_body_sha256': record.get('current_body_sha256'),
                })
            versions[body_hash] = deepcopy(trusted)
    return restored, receipts


def quarantine_changed_version_judgments(candidates, tracking, baseline):
    """Hold untrusted historical changes without discarding immutability gates.

    A prior sealed version has changed when its whole-record digest differs.
    The exact identity, original expected digest and observed digest are
    recorded. ONLY that version's historic judgment-digest assertion is
    isolated; the original version identity, all old reviews, old failures,
    completed reading receipts and confirmed targets still have to verify.

    This does not restore or approve the changed judgment. Automatic readers
    must exclude all held versions and verify they have not changed again.
    """
    guarded=deepcopy(baseline)
    hashes=guarded.get('version_record_hashes', {})
    held=[]
    for document_id, versions in hashes.items():
        observed=candidates.get('results',{}).get(document_id,{}).get('versions',{})
        for body_sha256, expected in list(versions.items()):
            current=digest(observed.get(body_sha256))
            if current != expected:
                held.append({'document_id':document_id,'body_sha256':body_sha256,
                             'expected_record_sha256':expected,
                             'observed_record_sha256':current,
                             'status':'UNVERIFIED_PREEXISTING_JUDGMENT_DRIFT',
                             'promoted_to_completion':False})
                del versions[body_sha256]
    # Unmodified requirements still pass. Crucially, a missing version or
    # altered previously completed review MUST still fail closed.
    verify(candidates,tracking,guarded)
    return guarded, held
