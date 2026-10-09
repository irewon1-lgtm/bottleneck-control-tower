"""Check immutable baseline identities, rather than trusting unchanged counts."""
import hashlib
import json

from .future_review import queue_items
from .future_worker import _runs


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify(candidates, tracking, baseline):
    results=candidates.get('results', {})
    if not set(baseline['document_ids']) <= set(results):
        raise ValueError('preserved candidate identity missing')
    for document_id, hashes in baseline['version_hashes'].items():
        if not set(hashes) <= set(results[document_id].get('versions', {})):
            raise ValueError('preserved source/body version missing')
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
