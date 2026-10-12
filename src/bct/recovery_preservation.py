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
            versions[body_hash] = deepcopy(trusted)
    return restored, receipts
