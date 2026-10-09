"""Derive queues and a fixed bundle; never perform semantic review."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from bct.future_review import _records, document_complete, ensure_bundle, full_queue_entries, queue_items, queue_summary
from bct.future_quality import observation_status
from bct.future_store import patch_json
from bct.future_hypothesis import CRITERIA_VERSION, POLICY, operation_report, performance_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--tracking', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    clock = datetime.now(timezone.utc).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates = json.loads(args.candidates.read_text())
    retained_before = set(candidates.get('results', {}))
    tracking = json.loads(args.tracking.read_text())
    bundle_patch = ensure_bundle(candidates, tracking, now=clock)
    # A projection can return to a previously seen state. Its content-derived
    # generation ID then repeats, but this is a new transition/time, not an
    # edit to the immutable prior history entry.
    for hypothesis_id, changes in bundle_patch.get('hypotheses', {}).items():
        prior = {entry['id']: entry for entry in
                 candidates.get('hypotheses', {}).get(hypothesis_id, {}).get('history', [])
                 if 'id' in entry}
        for entry in changes.get('history', []):
            identity = entry.get('id', '')
            if identity.startswith('generation-') and identity in prior and prior[identity] != entry:
                entry['id'] = 'generation-' + str(uuid.uuid4())
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
        for name in ('quick', 'material', 'deep', 'data_wait', 'failed') for item in queues[name]
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
    sample.update(failed_total=summary['failed_versions'],
                  retries=sample['retry_attempts'], material_wait=sample['material_pending'],
                  pending_total=len(pending_versions),
                  oldest_wait_seconds=(sample['oldest_wait_hours'] or 0) * 3600)
    sample.update(criteria_version=CRITERIA_VERSION, fixed_policy=POLICY,
                  hypotheses_total=len(candidates.get('hypotheses', {})),
                  automatic_s3_total=sum(h.get('current', {}).get('stage') == 'S3' for h in candidates.get('hypotheses', {}).values()),
                  candidates_auto_discarded=len(retained_before - set(candidates['results'])),
                  review_execution='REQUEST_DRIVEN_NOT_AUTOMATIC')
    bundles = list(bundle_patch.get('bundles', {}).values())
    reviews = [r for r in tracking.get('reviews', {}).values() if r.get('kind') in ('quick', 'deep')]
    times = [r.get('review_seconds') for r in reviews]
    time_measured = all(isinstance(t, (int, float)) and not isinstance(t, bool) and t >= 0 for t in times)
    reservations = [b.get('selection_reservations_verified') for b in bundles]
    sample.update(collection_budget_verified=candidates.get('summary', {}).get('collection_budget_verified'),
                  candidate_retention_verified=(retained_before <= set(candidates['results'])
                      if candidates.get('summary', {}).get('candidate_retention_verified') is True
                      else candidates.get('summary', {}).get('candidate_retention_verified')),
                  source_wide_scan=candidates.get('summary', {}).get('source_wide_scan'),
                  review_bundle_budget_verified=all(len(b.get('documents', [])) <= POLICY['review_documents']
                      and sum(r['end'] - r['start'] for r in b.get('documents', [])) <= POLICY['review_characters'] for b in bundles),
                  selection_reservations_verified=(False if any(value is False for value in reservations)
                      else True if all(value is True for value in reservations) else None),
                  review_documents_total=len({r['document_id'] for r in reviews}),
                  review_seconds_total=sum(times) if time_measured else None)
    observation = observation_status(samples + [sample], now=clock)
    prd_observation = operation_report(samples + [sample], now=clock)
    patch = {'summary': {'review_queue': summary, 'operation_observation': observation,
                        'prd_operation_observation': prd_observation,
                        'forecast_performance': performance_report(candidates.get('hypotheses', {}), now=clock)}, 'operation_samples': [sample]}
    op = 'queue-' + str(uuid.uuid4())
    saved = patch_json(args.candidates, owner='collection', patch=patch, operation_id=op,
                       prepared_document=candidates)
    if saved.status not in ('APPLIED', 'ALREADY_APPLIED'):
        raise RuntimeError('Queue snapshot pending: ' + str(saved.reason))
    (args.output_dir / 'queue-change.json').write_text(json.dumps({'owner': 'collection', 'operation_id': op, 'patch': patch, 'prepared_document': candidates}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
