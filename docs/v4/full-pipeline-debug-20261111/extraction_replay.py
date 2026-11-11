"""Offline, hash-exact consumed development replay. No model or source request.

Run with the project Python from repository root. The score denominator is only
these two audited model-object statements, not corpus/CPU/holdout performance.
"""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

from bct import precursor_scope_reader as reader

ROOT = Path(__file__).resolve().parents[3]
AUDIT = '2aaaa91f'
BASELINE = '23a0615f1a10f2b938cb2b5401706a1995b4d4f2'


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def replay():
    source = ROOT / 'docs/v4/reading-quality/research-snapshot.sqlite3.gz'
    compressed = source.read_bytes()
    payload = gzip.decompress(compressed)
    assert sha(compressed) == '49b3a551b4f68d6270aded7d1a9f1b3440bc34ea01159a234137c01f7c2b8b6a'
    assert sha(payload) == 'a21227317a8d24225b54541e7a250138359b21793a64a19778db2abf3d0c4d29'
    audit_bytes = subprocess.check_output(['git', 'show', AUDIT + ':docs/v4/audits/zero-pair-20261017/additional-reproduction-results.json'], cwd=ROOT)
    cases = json.loads(audit_bytes)['actual_extraction_misses']
    with tempfile.TemporaryDirectory(prefix='bct-extraction-replay-') as tmp:
        dbpath = Path(tmp) / 'reading-quality.sqlite3'
        dbpath.write_bytes(payload)
        with sqlite3.connect(dbpath.as_uri() + '?mode=ro', uri=True) as db:
            integrity = db.execute('pragma integrity_check').fetchone()[0]
            documents = [json.loads(row[0]) for row in db.execute('select payload from documents')]
    assert integrity == 'ok'
    assert all(sha(d['body'].encode()) == d['body_sha256'] for d in documents)
    results = []
    score = dict(TP=0, FP=0, FN=0)
    for case in cases:
        document = next(d for d in documents if d['document_id'] == case['document_id'])
        before = deepcopy(document)
        assert document['body_sha256'] == case['body_sha256']
        line = next(line for line in reader.sentences(document, reader.allowed_lines(document)[0])
                    if {'start': line['start'], 'end': line['end']} == case['locator'])
        candidates = reader._products(document, line)
        picked = reader.bound_product(line, candidates)
        expected = case['source_product_present']
        exact = picked is not None and picked['value'] == expected
        score['TP'] += int(exact)
        score['FP'] += int(picked is not None and not exact)
        score['FN'] += int(not exact)
        if exact:
            assert picked['locator']['start'] == case['source_product_offset']
            assert document['body'][picked['locator']['start']:picked['locator']['end']] == expected
        assert document == before
        results.append({k: case[k] for k in ('document_id', 'body_sha256', 'locator', 'source_product_present', 'source_product_offset')} | {
            'candidates': [{'value': p['value'], 'locator': p['locator']} for p in candidates],
            'bound_product': picked['value'] if picked else None,
            'bound_locator': picked['locator'] if picked else None,
            'exact_model_object_match': exact})
    return {'scope': 'TWO_ALREADY_CONSUMED_AUDITED_MODEL_OBJECT_STATEMENTS_NOT_INDEPENDENT_EVALUATION',
            'baseline_code_sha': BASELINE, 'scope_reader_version': reader.VERSION,
            'scope_reader_sha256': sha(Path(reader.__file__).read_bytes()),
            'audit_commit': AUDIT, 'audit_result_sha256': sha(audit_bytes),
            'preserved_gzip_sha256': sha(compressed), 'restored_db_sha256': sha(payload),
            'sqlite_integrity': integrity, 'body_hashes_verified': len(documents),
            'fixed_statement_count': len(cases), 'metrics': score, 'cases': results,
            'new_model_inferences': 0, 'external_requests': 0, 'holdout_used': False,
            'independent_accuracy': 'BLOCKED_UNCHANGED', 'lead_performance': 'BLOCKED_UNCHANGED'}


if __name__ == '__main__':
    result = replay()
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result['metrics']))
