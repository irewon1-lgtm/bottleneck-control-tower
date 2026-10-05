"""Acquire a bounded, explicitly selected LIVE batch with the existing pipeline.

No provenance assertions, discovery decisions, canonical writes or backlog drain.
The caller supplies only newly collected document IDs; private artifacts expire.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess

from bct.future_bottleneck import run
from bct.objective_lock import stamp_export


def preserve_source_inputs(db_path, output, result, document_ids, revision):
    """Preserve collected inputs verbatim; missing provenance stays missing."""
    output = Path(output)
    documents = []
    with sqlite3.connect(f'file:{Path(db_path).resolve()}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        for document_id in document_ids:
            row = db.execute('SELECT * FROM radar_items WHERE id=?',
                             (document_id,)).fetchone()
            if row is None:
                raise ValueError('selected source row missing')
            record = result['results'][document_id]
            digest = record.get('current_body_sha256') or record.get('body_sha256')
            body_path = None
            if digest:
                # Verify the original cache bytes, without truncating/re-extracting.
                if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                    raise ValueError('invalid snapshot body hash')
                relative = 'body-cache/' + digest + '.txt'
                path = output / relative
                if not path.is_file() or path.is_symlink():
                    raise ValueError('snapshot body cache missing')
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise ValueError('snapshot body hash mismatch')
                body_path = relative
            from bct.precursor_discovery import extract_events
            precursor_events = extract_events({'document_id': document_id, 'body': path.read_text()}) if body_path else []
            documents.append({
                'document_id': document_id,
                'upstream_row': dict(row),
                'snapshot_metadata': {k: v for k, v in record.items()
                                      if k not in ('body', 'full_text')},
                'body_path': body_path,
                'precursor_events': precursor_events,
                'precursor_policy': 'Source-addressed leads only; no inferred scope/provenance or S upgrade',
            })
    with (output / 'source-inputs.json').open('x', encoding='utf-8') as stream:
        json.dump(stamp_export({
            'format': 'bct-live-source-inputs-v1', 'data_revision': revision,
            'documents': documents,
            'provenance_policy': 'Collected inputs only; no inferred origin or publication verification',
        }), stream, ensure_ascii=False, indent=2)


def collect(root, document_ids):
    if (not isinstance(document_ids, list) or not 1 <= len(document_ids) <= 20
            or len(set(document_ids)) != len(document_ids)
            or any(not isinstance(i, str) or not i for i in document_ids)):
        raise ValueError('LIVE selection must contain 1..20 unique document IDs')
    root = Path(root)
    source = root / 'source'
    source.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'fetch', '--no-tags', 'origin', 'data'], check=True)
    revision = subprocess.check_output(['git', 'rev-parse', 'FETCH_HEAD'], text=True).strip()
    for name in ('canonical.sqlite3', 'canonical.previous.sqlite3', 'state.json'):
        with (source / name).open('xb') as stream:
            subprocess.run(['git', 'show', f'{revision}:{name}'], stdout=stream, check=True)
    spec = importlib.util.spec_from_file_location('rss_state', '.github/scripts/rss_state.py')
    transfer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transfer)
    db_path = root / 'live.sqlite3'
    transfer.load(source, db_path)
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    with sqlite3.connect(f'file:{db_path.resolve()}?mode=ro', uri=True) as db:
        active = {r[0] for r in db.execute("SELECT id FROM radar_items WHERE status='active'")}
    if not set(document_ids) <= active:
        raise ValueError('LIVE selection contains an unknown/inactive document ID')
    output = root / 'artifact'
    output.mkdir(mode=0o700)
    result = run(db_path, output / 'future-candidates.json',
                 document_ids=document_ids, limit=20, workers=6,
                 cache_dir=output / 'body-cache', trigger='SCHEDULED',
                 trigger_id='live-' + os.environ.get('GITHUB_RUN_ID', 'local'),
                 detection_mode='LIVE')
    if hashlib.sha256(db_path.read_bytes()).hexdigest() != before:
        raise RuntimeError('canonical snapshot changed during acquisition')
    preserve_source_inputs(db_path, output, result, document_ids, revision)
    (output / 'selection.json').write_text(json.dumps(stamp_export({
        'mode': 'LIVE', 'data_revision': revision, 'document_ids': document_ids,
        'canonical_sha256': before, 'backlog_included': False,
        'provenance_policy': 'No domain-based verification; existing metadata guards only',
        'summary': result['summary'],
    }), ensure_ascii=False, indent=2), encoding='utf-8')
    # Only aggregate metadata goes into the accessible Actions check; full text
    # stays in the short-lived artifact and is never written to public Git.
    rows = list(result['results'].values())
    counts = {s: sum(r.get('body_status') == s for r in rows)
              for s in ('FULL', 'PARTIAL', 'UNAVAILABLE')}
    counts['selected'] = len(document_ids)
    counts['verified_metadata'] = sum(r.get('provenance_verified') is True
                                      and r.get('publication_verified') is True
                                      for r in rows)
    print('::notice title=LIVE snapshot counts::' + json.dumps(counts))
    return result['summary']


if __name__ == '__main__':
    print(json.dumps(collect(Path(os.environ['RUNNER_TEMP']) / 'live-input',
                             json.loads(os.environ['LIVE_DOCUMENT_IDS']))))
