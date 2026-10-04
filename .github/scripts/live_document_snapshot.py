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
    (output / 'selection.json').write_text(json.dumps(stamp_export({
        'mode': 'LIVE', 'data_revision': revision, 'document_ids': document_ids,
        'canonical_sha256': before, 'backlog_included': False,
        'provenance_policy': 'No domain-based verification; existing metadata guards only',
        'summary': result['summary'],
    }), ensure_ascii=False, indent=2), encoding='utf-8')
    return result['summary']


if __name__ == '__main__':
    print(json.dumps(collect(Path(os.environ['RUNNER_TEMP']) / 'live-input',
                             json.loads(os.environ['LIVE_DOCUMENT_IDS']))))
