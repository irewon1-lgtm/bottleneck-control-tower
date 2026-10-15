#!/usr/bin/env python3
"""Frozen offline BACKTEST. No collection, model inference or provider calls."""
import argparse
from copy import deepcopy
import gzip
import json
import re
from pathlib import Path
import shutil
import sqlite3

from bct.v4 import historical_backtest as h
from bct.v4.store import Ledger,file_sha,sha


def read(path):return json.loads(Path(path).read_text())

def tables(path):
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        return {t:{'rows':len(rows),'sha256':sha([[sha(v)if isinstance(v,bytes)else v for v in row]for row in rows])}
                for t in ('metadata','blobs','documents','captures','readings','runs','firsts','events')
                for rows in [db.execute(f'SELECT * FROM {t} ORDER BY 1').fetchall()]}
    finally:db.close()


def decision_sha(result):
    """Keep raw receipts; only the engine's random execution UUID may differ.

    All evidence IDs, input hashes, stage decisions and metrics are compared.
    This does not normalize or discard any source or prediction differences.
    """
    value=deepcopy(result)
    for row in value['results']:
        for tick in row.get('timeline',[]):
            engine=tick['engine'];batch=engine.get('batch_id')
            if not isinstance(batch,str) or not re.fullmatch(r'early-[0-9a-f]{32}',batch):
                raise ValueError('UNEXPECTED_ENGINE_EXECUTION_ID')
            del engine['batch_id']
    return sha(value)


def run(repo,root):
    e=repo/'docs/v4/historical-backtest';f=read(e/'execution-freeze.json')
    for p,digest in f['code'].items():
        if file_sha(repo/p)!=digest:raise ValueError('FROZEN_ENGINE_CODE_CHANGED:'+p)
    for p,digest in f['files'].items():
        if file_sha(repo/p)!=digest:raise ValueError('FROZEN_INPUT_OR_ADJUDICATION_CHANGED:'+p)
    bound=read(e/'run-freeze.json')
    if file_sha(e/'CPU-reading.json')!=bound['CPU_reading_sha256']:raise ValueError('CPU_RECEIPT_CHANGED')
    for name in ('INPUT','OUTCOME'):
        path=root/name/'v4.sqlite3'
        if file_sha(path)!=bound['databases'][name]:
            # sqlite3.backup may change header counters without changing a
            # table. Require the exact archive AND all8 frozen table digests.
            proof=read(e/'storage-proof.json')['ledgers'][name]
            if (proof.get('source_sqlite_sha256')!=bound['databases'][name]
                    or file_sha(path)!=proof['sqlite_sha256'] or tables(path)!=proof['tables']):
                raise ValueError('SOURCE_LEDGER_CHANGED:'+name)
    inputs=Ledger(root/'INPUT');original_input=file_sha(inputs.path)
    cases=read(e/'case-manifest.json')['cases'];prepared=deepcopy(cases)
    reading=read(e/'CPU-reading.json')
    for c in prepared:
        if c['id']=='diagnostic-ercot-winter-2021':c['inputs'][0]['CPU_reading']=reading
    # No outcome database or label file is opened until all engine calls end.
    outputs=[h.execute(c,inputs)for c in prepared];inputs.close()
    if file_sha(root/'INPUT/v4.sqlite3')!=original_input:raise ValueError('INPUT_REPLAY_MUTATED_SOURCE')
    outcomes=read(e/'outcome-adjudication.json')['outcomes'];by={o['case_id']:o for o in outcomes}
    oc=sqlite3.connect((root/'OUTCOME/v4.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    for o in outcomes:
        for ref in o.get('references',[]):
            row=oc.execute('select payload from documents where id=?',(ref['document_id'],)).fetchone()
            if row is None:raise ValueError('OUTCOME_ORIGINAL_MISSING')
            d=json.loads(row[0]);a,b=ref['start'],ref['end']
            if d['backtest_role']!='OUTCOME' or d['body_sha256']!=ref['body_sha256']or d['body'][a:b]!=ref['quote']:
                raise ValueError('OUTCOME_REFERENCE_MISMATCH')
    oc.close()
    assessed=[h.assess(c,r,by[c['id']],observed_through=bound['observed_through'])for c,r in zip(cases,outputs)]
    return h.summarize(outputs,assessed)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--root',type=Path,default=Path('var/v4/historical-backtest'));p.add_argument('--output',type=Path,required=True);p.add_argument('--save',action='store_true');p.add_argument('--restore',action='store_true');a=p.parse_args()
    repo=a.repo.resolve();e=repo/'docs/v4/historical-backtest';root=a.root.resolve()
    if a.restore:
        proof=read(e/'storage-proof.json')
        for name,r in proof['ledgers'].items():
            archive=e/r['archive'];dest=root/name/'v4.sqlite3';dest.parent.mkdir(parents=True,exist_ok=True)
            if file_sha(archive)!=r['archive_sha256']:raise ValueError('ARCHIVE_HASH_MISMATCH')
            with gzip.open(archive,'rb')as s,dest.open('xb')as t:shutil.copyfileobj(s,t)
            if file_sha(dest)!=r['sqlite_sha256']:raise ValueError('RESTORE_HASH_MISMATCH')
    result=run(repo,root)
    if a.save:
        ledger=Ledger(root/'RESULTS');key='historical-backtest-'+sha([read(e/'run-freeze.json'),result])
        ledger.save_run(key,result,'BACKTEST');ledger.close()
    if a.restore:
        ledger=Ledger(root/'RESULTS');rows=ledger.db.execute("select payload from runs where mode='BACKTEST'").fetchall()
        if len(rows)!=1 or decision_sha(json.loads(rows[0][0]))!=decision_sha(result):raise ValueError('RESTORED_REPLAY_DIFFERS')
        if ledger.db.execute('select count(*) from firsts').fetchone()[0]:raise ValueError('BACKTEST_REGISTERED_LIVE_FIRST')
        ledger.close()
    with a.output.open('x')as stream:json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'mode':result['mode'],'executed':sum(r['status']=='EXECUTED_BACKTEST'for r in result['results']),
        'unrun':sum(r['status']!='EXECUTED_BACKTEST'for r in result['results']),'metrics':result['metrics'],
        'raw_result_sha256':sha(result),'decision_result_sha256':decision_sha(result)},ensure_ascii=False))


if __name__=='__main__':main()
