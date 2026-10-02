"""Derive queues and a fixed bundle; never perform semantic review."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from bct.future_review import _records, document_complete, ensure_bundle, full_queue_entries, queue_items, queue_summary
from bct.future_quality import observation_status
from bct.future_store import patch_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--tracking', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    clock = datetime.now(timezone.utc).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates = json.loads(args.candidates.read_text())
    tracking = json.loads(args.tracking.read_text())
    bundle_patch = ensure_bundle(candidates, tracking, now=clock)
    op = 'bundle-' + str(uuid.uuid4())
    result = patch_json(args.candidates, owner='bundle', patch=bundle_patch, operation_id=op,
                        prepared_document=candidates)
    if result.status not in ('APPLIED', 'ALREADY_APPLIED'):
        raise RuntimeError('Bundle save pending: ' + str(result.reason))
    (args.output_dir / 'bundle-change.json').write_text(json.dumps({'owner': 'bundle', 'operation_id': op, 'patch': bundle_patch, 'prepared_document': candidates}, ensure_ascii=False, indent=2) + '\n')
    candidates = result.document
    summary = queue_summary(candidates, tracking, now=clock)
    queues = queue_items(candidates, tracking, now=clock)
    pending_versions = {
        (item['document_id'], item.get('body_sha256') or item.get('source_version'))
        for name in ('quick', 'material', 'deep', 'data_wait') for item in queues[name]
    }
    entries = full_queue_entries(candidates, tracking, now=clock)
    review_version_keys = {
        (entry['document_id'], entry.get('body_sha256') or entry.get('source_version') or '')
        for entry in entries
    }
    review_version_refs = [list(ref) for ref in sorted(review_version_keys)]
    (args.output_dir / 'review-queue.json').write_text(json.dumps({'computed_at': clock, 'entries': entries}, ensure_ascii=False, indent=2) + '\n')
    samples = list(candidates.get('operation_samples', []))
    previous = samples[-1] if samples else {}
    collection_completed_at = candidates.get('summary', {}).get('checked_at')
    new_collection = collection_completed_at != previous.get('collection_completed_at')
    new_documents = candidates.get('summary', {}).get('new_documents_this_run', 0) if samples and new_collection else 0
    prior_review_versions = {
        tuple(ref) for sample in samples for ref in sample.get('review_version_refs', [])
    }
    has_version_baseline = any('review_version_refs' in sample for sample in samples)
    inflow = len(review_version_keys - prior_review_versions) if has_version_baseline else 0
    completed_total = sum(document_complete(tracking, item) for item in _records(candidates))
    sample = {'id': 'sample-' + str(uuid.uuid4()), 'observed_at': clock,
              'recorded_at': clock, 'actual_execution': True,
              'actual_elapsed_time': True, 'documents_total': len(candidates['results']),
              'new_documents': new_documents, 'inflow_total': previous.get('inflow_total', 0) + inflow,
              'review_version_refs': review_version_refs,
              'completed_total': completed_total,
              'completed_documents': summary['completed_documents'],
              'quick_pending': summary['quick_pending'], 'material_pending': summary['material_pending'],
              'deep_pending': summary['deep_pending'], 'candidate_data_wait': summary['candidate_data_wait'],
              'oldest_wait_hours': summary['oldest_wait_hours'],
              'retry_attempts': sum(v.get('automatic_attempts', 0) + len(v.get('explicit_checks', {}))
                                    for r in candidates['results'].values()
                                    for v in r.get('acquisition', {}).get('versions', {}).values()),
              'user_wait': summary['quick_pending'] + summary['deep_pending'],
              'system_wait': candidates.get('summary', {}).get('pending_due', 0),
              'source_wait': summary['material_pending'],
              'collection_completed_at': collection_completed_at}
    sample.update(retries=sample['retry_attempts'], material_wait=sample['material_pending'],
                  pending_total=len(pending_versions),
                  oldest_wait_seconds=(sample['oldest_wait_hours'] or 0) * 3600)
    observation = observation_status(samples + [sample], now=clock)
    patch = {'summary': {'review_queue': summary, 'operation_observation': observation}, 'operation_samples': [sample]}
    op = 'queue-' + str(uuid.uuid4())
    saved = patch_json(args.candidates, owner='collection', patch=patch, operation_id=op,
                       prepared_document=candidates)
    if saved.status not in ('APPLIED', 'ALREADY_APPLIED'):
        raise RuntimeError('Queue snapshot pending: ' + str(saved.reason))
    (args.output_dir / 'queue-change.json').write_text(json.dumps({'owner': 'collection', 'operation_id': op, 'patch': patch, 'prepared_document': candidates}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
