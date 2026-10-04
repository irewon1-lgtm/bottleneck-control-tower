"""Bounded recovery through the existing collection pipeline, not a new reader.

The immutable request contains only IDs already in the operational database.
Bodies remain in the existing private cache and an authenticated, short-lived
Actions artifact; no third-party full text is published to a repository.
"""
import argparse
import json
import shutil
import os
import hashlib
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from bct.future_bottleneck import run


def recover(db, candidates, tracking, cache, request, output, cache_only=False):
    value = json.loads(Path(request).read_text())
    ids = value['document_ids']
    if not isinstance(ids, list) or len(ids) != len(set(ids)) or len(ids) > 1523:
        raise ValueError('invalid frozen operational document selection')
    if cache_only:
        from bct.future_body import read_cached_body
        current = json.loads(Path(candidates).read_text())
        ids = [i for i in ids if read_cached_body(cache,
            current['results'][i].get('current_body_sha256') or current['results'][i].get('body_sha256')) is not None]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'future-candidates.json'
    shutil.copy2(candidates, target)
    for index in range(0, len(ids), 300):
        state = run(db, target, limit=300, workers=6, cache_dir=cache,
                    tracking_path=tracking, document_ids=ids[index:index + 300],
                    trigger='FILTER_CHANGED' if cache_only else 'SCHEDULED', trigger_id=value['operation_id'],
                    patch_output=output / f'collection-change-{index // 300}.json')
        print(json.dumps({'batch': index // 300, 'processed': state['summary']['processed_this_run']}))
    return target


def publish_and_audit(target, cache, output, request):
    from bct.future_github import GitHubTransport
    from bct.future_store import store_patch
    from bct.future_body import read_cached_body
    transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'], 'future-bottleneck-data', os.environ['GITHUB_TOKEN'])
    saved = []
    for path in sorted(Path(output).glob('collection-change-*.json')):
        change = json.loads(path.read_text())
        # Persist current observations through the existing preserving CAS writer.
        result = store_patch(transport, 'future-candidates.json', owner='collection',
            patch=change['patch'], operation_id=change['operation_id'], prepared_document=change['prepared_document'])
        if result.status not in ('APPLIED', 'ALREADY_APPLIED'):
            raise RuntimeError('collection pending: ' + str(result.reason))
        saved.append(result.status)
    state = transport.read('future-candidates.json').document
    checked, readable, misses = [], [], []
    patterns = {
        'DEMAND': r'\b(?:orders?|contracts?|reservations?|procurement|deployment)\b',
        'SUPPLY': r'\b(?:capacity|production|qualification|commissioning|lead[- ]time|yield|utilization)\b',
        'RELIEF': r'\b(?:expansion|inventory|substitute|dual[- ]source|redesign|new supplier)\b',
    }
    for document_id, record in state['results'].items():
        digest = record.get('current_body_sha256') or record.get('body_sha256')
        body = read_cached_body(cache, digest)
        if body is None:
            continue
        readable.append(document_id)
        facts = record.get('scope_facts', [])
        checked.append({'document_id': document_id, 'body_sha256': digest, 'body_chars': len(body),
                        'scope_facts': len(facts)})
        for match in re.finditer(r'[^\n]+', body):
            line = match.group()
            targets = [t['name'] for t in record.get('targets', []) if t['name'].casefold() in line.casefold()]
            if not targets:
                continue
            for role, pattern in patterns.items():
                if re.search(pattern, line, re.I) and not any(f['role'] == role and f['locator']['start'] == match.start() for f in facts):
                    misses.append({'document_id': document_id, 'body_sha256': digest, 'role': role,
                                   'targets': targets, 'locator': {'start': match.start(), 'end': match.end()},
                                   'excerpt': ' '.join(line.split()[:24])})
    report = {'operation_id': json.loads(Path(request).read_text())['operation_id'],
              'observed_at': datetime.now(timezone.utc).isoformat(),
              'published_batches': saved, 'verified_cached_documents': len(readable),
              'verified_cached_document_records': checked,
              'parser_missing_role_counts': dict(Counter(x['role'] for x in misses)),
              'parser_missing_role_examples': misses[:24],
              'selected_outcomes': [{'document_id': k, 'body_status': state['results'][k].get('body_status'),
                 'body_sha256': state['results'][k].get('body_sha256'), 'reasons': state['results'][k].get('reasons', [])}
                 for k in json.loads(Path(request).read_text())['document_ids']]}
    from bct.objective_lock import stamp_export
    from bct.forecast_discovery import discover, PUBLIC_CONFIRMATION
    from bct.early_forecast import discover as early_discover
    documents, signals, public_documents = [], [], []
    for row in checked:
        r = state['results'][row['document_id']]
        body = read_cached_body(cache, row['body_sha256'])
        if PUBLIC_CONFIRMATION.search(body):
            public_documents.append(row['document_id'])
            continue
        documents.append({'document_id': row['document_id'], 'body': body, 'body_sha256': row['body_sha256'],
            'published_at': r.get('published_at') if r.get('publication_verified') else None,
            'publication_precision': r.get('publication_precision') if r.get('publication_verified') else 'UNKNOWN',
            'public_snapshot_observed_at': r['checked_at'], 'available_at': r['checked_at'],
            'origin_id': r.get('origin_id'), 'origin_url': r.get('origin_url'),
            'origin_publisher': r.get('origin_publisher'), 'provenance_verified': r.get('provenance_verified') is True})
        for f in r.get('scope_facts', []):
            if f['role'] not in ('DEMAND', 'SUPPLY'):
                continue
            signals.append({**f, 'document_id': row['document_id'],
                'target_id': f.get('target_id', 'UNKNOWN'), 'signal_type': f.get('signal_type', 'UNKNOWN')})
    batch = stamp_export({'documents': documents, 'signals': signals, 'confirmations': []})
    early = early_discover(batch)
    # Strict discovery needs verified publication timestamps; excluded rows
    # stay explicit provenance/time failures rather than fabricated inputs.
    strict_batch = stamp_export({**batch, 'documents': [d for d in documents if d['published_at'] is not None]})
    quantitative = discover(strict_batch)
    report['discovery'] = {'mode': 'LIVE', 'early': early, 'quantitative': quantitative,
        'explicit_confirmation_excluded_documents': public_documents,
        'input_signal_count': len(signals), 'input_document_count': len(documents)}
    report = stamp_export(report)
    if early['candidates'] or quantitative['candidates']:
        raise RuntimeError('new candidates require the existing prospective freeze path before publication')
    path = 'backlog-recovery/' + os.environ['GITHUB_RUN_ID'] + '.json'
    raw = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()
    import base64
    transport._request('PUT', '/contents/' + path, {'branch': 'future-bottleneck-data',
        'message': 'Preserve actual body recovery audit (no full text)', 'content': base64.b64encode(raw).decode()})
    print(json.dumps({'published_batches': saved, 'verified_cached_documents': len(readable), 'report': path}))


def main():
    p = argparse.ArgumentParser()
    for name in ('db', 'candidates', 'tracking', 'cache', 'request', 'output'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--publish', action='store_true')
    p.add_argument('--cache-only', action='store_true')
    args = vars(p.parse_args())
    publish = args.pop('publish')
    target = recover(**args)
    if publish:
        publish_and_audit(target, args['cache'], args['output'], args['request'])


if __name__ == '__main__':
    main()
