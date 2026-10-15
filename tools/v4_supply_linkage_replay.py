#!/usr/bin/env python3
"""Offline, read-only replay of the frozen source review; no CPU/API calls.

Example: .venv/bin/python tools/v4_supply_linkage_replay.py \
  --restore /tmp/bct-supply-restored --proof /tmp/bct-supply-proof.json
"""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import sqlite3

from bct.v4 import supply_linkage
from bct.v4.dashboard import ResearchReader
from bct.v4.store import file_sha, sha

TABLES = ('metadata','blobs','documents','captures','readings','runs','firsts','events')


def digests(db):
    result = {}
    for table in TABLES:
        rows = db.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall()
        result[table] = {'rows': len(rows), 'sha256': sha([
            [sha(v) if isinstance(v, bytes) else v for v in r] for r in rows])}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--ledger', type=Path)
    p.add_argument('--restore', type=Path)
    p.add_argument('--proof', type=Path, required=True)
    a = p.parse_args(); root = a.repo.resolve(); e = root/'docs/v4/supply-linkage'
    expected = json.loads((e/'engine-results.json').read_text())
    stored = json.loads((e/'storage-proof.json').read_text())
    path = a.ledger or root/'var/v4/supply-linkage/ledger/v4.sqlite3'
    if a.restore:
        archive = e/'research-snapshot.sqlite3.gz'
        if file_sha(archive) != stored['snapshot_file_sha256']: raise ValueError('SNAPSHOT_HASH_MISMATCH')
        a.restore.mkdir(parents=True, exist_ok=True)
        path = a.restore/'v4.sqlite3'
        with gzip.open(archive, 'rb') as source, path.open('xb') as target:
            shutil.copyfileobj(source, target)
        if file_sha(path) != stored['sqlite_sha256']: raise ValueError('RESTORED_SQLITE_HASH_MISMATCH')
    path = path.resolve(); before = file_sha(path)
    db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)
    db.execute('PRAGMA query_only=ON')
    if db.execute('PRAGMA integrity_check').fetchone() != ('ok',): raise ValueError('INTEGRITY_FAILURE')
    docs = [json.loads(r[0]) for r in db.execute('SELECT payload FROM documents ORDER BY id')]
    cases = json.loads((e/'case-reviews.json').read_text())['cases']
    result = supply_linkage.analyze(docs,cases,as_of=expected['as_of'])
    if sha(result) != sha(expected): raise ValueError('FINAL_CODE_REPLAY_DIFFERS_FROM_SAVED_RESULTS')
    tables = digests(db)
    if tables != stored['tables']: raise ValueError('RESTORE_TABLE_DIFFERENCE')
    if db.execute("SELECT COUNT(*) FROM firsts WHERE mode='LIVE'").fetchone()[0]: raise ValueError('UNEXPECTED_LIVE_FIRST')
    db.close()
    reader = ResearchReader(root,path); view = reader.dashboard()
    for row in view['records']:
        if not reader.evidence(row['id'])['all_references_verified']: raise ValueError('UI_REFERENCE_REQUERY_FAILED')
    if file_sha(path) != before: raise ValueError('READ_ONLY_REPLAY_MUTATED_DATABASE')
    proof = {'status':'PASS_OFFLINE_NEW_PROCESS_REPLAY_RESTORE_REQUERY', 'tables':tables,
             'result_sha256':sha(result), 'database_sha256':before,
             'case_review_records':len(cases), 'adopted_facts':result['engine']['counts']['events'],
             'UI_records':len(view['records']), 'new_API_calls':0,'new_CPU_inferences':0,
             'new_LIVE_firsts':0,'AI_accuracy':'NOT_TESTED','forecast_performance':'NOT_RUN'}
    with a.proof.open('x') as stream: json.dump(proof,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in proof.items() if k!='tables'},ensure_ascii=False))


if __name__=='__main__': main()
