"""Append CPU read pointers beside the frozen classic REVIEW queue.

These source-free receipts are advisory read evidence. They never complete the
separate semantic review, alter its frozen policy, or load a source original.
"""
import argparse
import json
from pathlib import Path

from bct import review_leads as review
from bct.review_shadow import safe_root, snapshot
from .public_research import validate_snapshot

FORMAT = 'bct-classic-review-cpu-read-1'
SOURCE_FIELDS = ('document_id', 'body_sha256', 'raw_sha256', 'source_version')
READ_FIELDS = ('read_state', 'review_state', 'reason_code', 'missing_fields',
               'source_verification', 'window_counts', 'model', 'revision')
HASH_FIELDS = ('analysis_sha256', 'window_binding_sha256', 'derived_reuse_binding_sha256')


def queue_binding(root, source):
    """Only a complete exact version matches; queue absence may be a race."""
    candidates = []
    exact = []
    for path in sorted((root / 'queue').glob('*.json')):
        queue = review.sealed_read(path)
        if queue.get('document_id') != source['document_id']:
            continue
        candidates.append(queue['record_sha256'])
        doc = queue.get('source_document', {})
        if (queue.get('body_sha256') == source['body_sha256']
                and doc.get('document_id') == source['document_id']
                and doc.get('body_sha256') == source['body_sha256']
                and doc.get('raw_sha256') == source['raw_sha256']
                and doc.get('version') == source['source_version'] == source['body_sha256']):
            exact.append(queue['record_sha256'])
    status = ('QUEUE_AMBIGUOUS' if len(exact) > 1 else 'EXACT_QUEUE_VERSION' if exact
              else 'QUEUE_VERSION_PENDING' if candidates else 'QUEUE_UNMATCHED')
    return {'status': status, 'queue_record_sha256': exact[0] if len(exact) == 1 else None}


def append_snapshot(public, root):
    """Consume a validated ACK projection; callers verify its public transport."""
    validate_snapshot(public)
    root = safe_root(root)
    if not (root / 'shadow-activation.json').is_file():
        raise ValueError('SHADOW_NOT_INITIALIZED')
    # Validate every row before the first append, including conflicting aliases.
    rows = {}
    for trace in public['trace']:
        key = tuple(trace[field] for field in SOURCE_FIELDS)
        if key in rows and rows[key] != trace:
            raise ValueError('REVIEW_CPU_TRACE_AMBIGUOUS')
        if trace['read_state'] == 'READ_COMPLETE':
            counts = trace['window_counts']
            if (counts['total'] is None or counts['total'] < 1 or counts['success'] != counts['total']
                    or counts['failed'] != 0 or counts['unread'] != 0):
                raise ValueError('REVIEW_CPU_COMPLETE_WINDOW_COUNTS')
        rows[key] = trace
    created = duplicate = 0
    with review.locked(root):
        safe_root(root)
        activation = review.sealed_read(root / 'shadow-activation.json')
        before = snapshot(root)
        for trace in rows.values():
            source = {field: trace[field] for field in SOURCE_FIELDS}
            read = {field: trace[field] for field in READ_FIELDS}
            read['missing_fields'] = sorted(set(read['missing_fields']))
            for field in HASH_FIELDS:
                if field in trace:
                    read[field] = trace[field]
            binding = queue_binding(root, source)
            # Snapshot/run/ACK clocks are provenance, never duplicate identity.
            semantic = {'format': FORMAT, 'source': source, 'read': read,
                        'queue_binding': binding, 'execution_sha': public['generation']['execution_sha']}
            identity = review.digest(semantic)
            path = root / 'cpu-read-receipts' / (identity + '.json')
            if path.exists():
                prior = review.sealed_read(path)
                if prior.get('semantic_sha256') != identity or prior.get('semantic') != semantic:
                    raise ValueError('REVIEW_CPU_RECEIPT_COLLISION')
                duplicate += 1
                continue
            review.write_first(path, {
                'review_rules_version': activation['review_rules_version'],
                'format': FORMAT, 'semantic_sha256': identity, 'semantic': semantic,
                'source': source, 'read': read, 'queue_binding': binding,
                'generation': public['generation'], 'snapshot_sha256': public['snapshot_sha256'],
                # This is the snapshot's last batch, not an attribution of all
                # retained historical source rows to that particular CPU run.
                'snapshot_last_read_batch': public['last_read_batch'],
                'shadow_activation_sha256': activation['record_sha256'],
                'helper_sha256': review.digest(Path(__file__).read_bytes()),
                'semantic_review': {'status': 'PENDING', 'completed_by_CPU': False},
                'EARLY_success': False, 'LIVE_writes': 0,
            })
            created += 1
        if any(not (root / name).is_file() or review.digest((root / name).read_bytes()) != digest
               for name, digest in before.items()):
            raise ValueError('REVIEW_CPU_PRIOR_RECORD_CHANGED')
    return {'created': created, 'duplicate': duplicate, 'exported_traces': len(rows),
            'trace_truncated': public['analysis']['trace_truncated'], 'semantic_status': 'PENDING'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(append_snapshot(json.loads(args.snapshot.read_text()), args.state)))


if __name__ == '__main__':
    main()
