"""Offline evidence check only; NOT a production seed or an activation command.

Retain originals. A separate derivative contains only BCT completion receipts,
IDs and digests, never article text, model spans or quotes. This does not recover
the original semantic research results and grants no rights to store new pages.
Run with PYTHONPATH=src .venv/bin/python <this-file> --source <queue.sqlite3>
--output <new ignored directory>. No network, model or credentials are used.
"""
import argparse
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

from bct.v4 import cpu_automation as queue, cpu_operations as op
from bct.v4.evidence_path import reference
from bct.v4.reading_quality import coverage
from bct.v4.store import file_sha, sha


def check(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('REFUSE_EXISTING_OUTPUT')
    original_sha = file_sha(source)
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as db:
        assert db.execute("SELECT value FROM metadata WHERE key='cpu_queue_format'").fetchone() == (queue.VERSION,)
        tables = op.table_digests(db)
        docs = {k: json.loads(p) for k, p in db.execute('SELECT id,payload FROM documents')}
        def rows(kind):
            return [json.loads(p) for p, in db.execute('SELECT payload FROM events WHERE kind=? ORDER BY seq', (kind,))]
        legacy, queued, readings = rows('CPU_QUEUE_LEGACY_COMPLETE'), rows('CPU_QUEUE_DOCUMENT'), rows('CPU_QUEUE_WINDOW_RESULT')
        completed = {r['key']: r for r in readings}
        receipts = [{k: r[k] for k in ('body_key', 'document_id', 'source_body_sha256', 'windows', 'receipt_sha256')} for r in legacy]
        windows = 0
        for item in queued:
            doc = docs[item['document_id']]
            assert sha(doc['body'].encode()) == doc['body_sha256']
            raw = db.execute('SELECT data FROM blobs WHERE id=?', (doc['raw_sha256'],)).fetchone()[0]
            assert sha(raw) == doc['raw_sha256']
            done = []
            for task in item['tasks']:
                r = completed[task['key']]
                assert r['status'] == 'REVIEW_PENDING'
                assert r['body_key'] == item['body_key'] and r['document_id'] == doc['document_id']
                assert r['window'] == task['window']
                assert r['actually_read_characters'] == len(r['window']['text'])
                assert r['CPU']['model'] == queue.MODEL and r['CPU']['revision'] == queue.MODEL_REVISION
                reference(doc, {**r['window'], 'quote': r['window']['text']})
                done.append(r['window'])
            cov = coverage(doc['body'], done)
            assert not any(re.sub(r'\s', '', doc['body'][g['start']:g['end']]) for g in cov['unread_ranges'])
            receipts.append({'body_key': item['body_key'], 'document_id': doc['document_id'],
                'source_body_sha256': doc['body_sha256'], 'windows': len(done),
                'receipt_sha256': sha([completed[t['key']] for t in item['tasks']])})
            windows += len(done)
        # Explicit allowlist: no URL, body, raw, CPU output, quote, contact or
        # arbitrary source-derived field can be carried into the derivative.
        for r in receipts:
            assert set(r) == {'body_key', 'document_id', 'source_body_sha256', 'windows', 'receipt_sha256'}
            for k in ('body_key', 'source_body_sha256', 'receipt_sha256'):
                assert re.fullmatch('[0-9a-f]{64}', r[k])
            assert re.fullmatch('[A-Za-z0-9_-]+', r['document_id'])
            assert type(r['windows']) is int and r['windows'] > 0
    ledger = queue.open_queue(output / 'metadata-only')
    with ledger.db:
        ledger.event('CPU_METADATA_ONLY_DERIVATIVE', {'source_sqlite_sha256': original_sha,
            'source_table_digests': tables, 'originals_retained': True,
            'production_seed': False, 'original_results_recoverable_here': False})
        for r in receipts:
            ledger.event('CPU_QUEUE_LEGACY_COMPLETE', r)
    class NoInference:
        def extract_windows(self, *args, **kwargs):
            raise AssertionError('CPU_MUST_NOT_RUN')
    result = queue.work(ledger, extractor=NoInference())
    assert result['new_windows'] == 0 and result['model_loaded'] is False
    assert queue.state(ledger)['pending_windows'] == 0
    proof = op.checkpoint(ledger, output / 'checkpoint')
    assert all(proof['tables'][t]['rows'] == 0 for t in ('blobs', 'documents', 'captures', 'readings', 'runs', 'firsts'))
    ledger.close()
    audit = op.checkpoint_storage_audit(output / 'checkpoint', scope='private')
    assert audit['status'] == 'PASS_PRIVATE_STORAGE_REVIEW' and audit['documents'] == []
    # Fresh interpreter verifies restore, all eight tables and repeat-open state.
    p = subprocess.run([sys.executable, '-c',
        'import json,sys;from bct.v4 import cpu_operations as o,cpu_automation as q;'
        'r=o.restore(sys.argv[1],sys.argv[2]);l=q.open_queue(sys.argv[2]);'
        'assert q.state(l)["pending_windows"]==0;l.close();print(json.dumps(r))',
        str(output / 'checkpoint'), str(output / 'restored')], capture_output=True, text=True, timeout=25)
    assert p.returncode == 0, p.stderr
    restored = json.loads(p.stdout)
    assert file_sha(source) == original_sha
    return {'status': 'PASS_OFFLINE_METADATA_ALTERNATIVE_ONLY',
        'original_documents_checked': len(docs), 'cached_windows_verified_not_rerun': windows,
        'older_completion_receipts_retained': len(legacy), 'completion_receipts_total': len(receipts),
        'source_sqlite_sha256_unchanged': original_sha, 'originals_modified': False,
        'article_text_blobs_quotes_copied': 0, 'model_loads': 0,
        'derivative_archive_bytes': (output / 'checkpoint/checkpoint.sqlite3.gz').stat().st_size,
        'derivative_sqlite_sha256': proof['sqlite_sha256'], 'new_process_restore': restored,
        'private_audit': audit, 'remote_publication': 'NOT_RUN_TOKEN_ACCESS_BLOCKED',
        'production_seed': False,
        'limitations': ['Not an original DB restore; semantic results stay in the preserved original.',
            'No new source archival permission granted; existing source gate remains.',
            'Not wired to production queue or enabled automation.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.source, args.output), indent=2))
