"""Publish derived queues against both authoritative roots in one generation.

Source collection may legitimately add versions while a projection is being
prepared. Owned patches are merged against the latest immutable commit; a
concurrent ref change is surfaced to the caller, never overwritten or retried
without rebuilding the projection. No review or forecast is manufactured.
"""
from copy import deepcopy
import hashlib
import json

from .future_github import _raw
from .future_store import apply_owned_patch
from .recovery_preservation import verify
from .recovery_queue import project

PATHS = ('future-candidates.json', 'future-tracking.json')


def publish_projection(transport, changes, *, versions, observations, cache,
                       preservation, retained, run_id):
    if not run_id or not changes:
        raise ValueError('actual execution identity and derived changes required')
    head = transport.head()
    snapshots = {p: transport.read_at(p, head) for p in PATHS}
    candidates = deepcopy(snapshots[PATHS[0]].document)
    tracking = snapshots[PATHS[1]].document
    verify(candidates, tracking, preservation)
    verify(candidates, tracking, retained)
    for change in changes:
        if change.get('owner') not in ('bundle', 'collection'):
            raise ValueError('queue publisher cannot create review/forecast decisions')
        candidates = apply_owned_patch(candidates, owner=change['owner'],
            patch=change['patch'], operation_id=change['operation_id'],
            prepared_document=change.get('prepared_document'))
    queue = project(candidates, tracking, versions, observations, cache)
    if queue['completion_failure_state_overlap'] or queue['preserved_failure_versions'] != len(versions):
        raise ValueError('operating queue lost historical failure identities')
    candidates.setdefault('summary', {})['recovery_queue'] = {
        k: v for k, v in queue.items() if k != 'version_rows'}
    candidates['summary']['recovery_queue']['generation_run_id'] = str(run_id)
    verify(candidates, tracking, preservation)
    verify(candidates, tracking, retained)
    # Tracking's expected SHA is a dependency even when tracking is unchanged.
    # A stale reading base cannot publish a freshly computed COMPLETED count.
    roots = transport.write_many({PATHS[0]: candidates, PATHS[1]: tracking},
                                 {p: s.sha for p, s in snapshots.items()})
    published = transport.last_commit or head
    confirmed = {p: transport.read_at(p, published) for p in PATHS}
    if confirmed[PATHS[0]].document != candidates or confirmed[PATHS[1]].document != tracking:
        raise ValueError('published projection differs at immutable commit')
    return {
        'status': 'PASS', 'actual_execution': True, 'run_id': str(run_id),
        'parent_commit': head, 'published_commit': published, 'root_shas': roots,
        'document_sha256': {p: hashlib.sha256(_raw(s.document)).hexdigest()
                            for p, s in confirmed.items()},
        'queue_counts': queue['counts'], 'queue_total': queue['total_queue_versions'],
        'failed_versions_preserved': queue['preserved_failure_versions'],
        'review_records_unchanged': confirmed[PATHS[1]].document == tracking,
        'projection_sha256': hashlib.sha256(json.dumps(queue, sort_keys=True,
            ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
        'prediction_performance': 'UNVERIFIED',
    }, queue
