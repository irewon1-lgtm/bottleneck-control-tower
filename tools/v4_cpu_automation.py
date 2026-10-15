#!/usr/bin/env python3
"""Consume an existing RSS delta/body artifact once. No RSS/network/API calls.

Default status only. --execute-cpu is an explicit bounded local invocation,
not a timer, GitHub schedule, AI Shadow or operational candidate registration.
"""
import argparse
import json
from pathlib import Path

from bct.v4.cpu_automation import open_queue, ingest_delta, seed_completed, work, state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('var/v4/cpu-automation/ledger'))
    p.add_argument('--manifest',type=Path)
    p.add_argument('--cache',type=Path)
    p.add_argument('--reconsider-held',action='store_true',help='Only if an upstream cached document was added/changed; no network retry')
    p.add_argument('--upstream-run-id')
    p.add_argument('--seed-completed',type=Path)
    p.add_argument('--restore',type=Path,help='Verified gzip archive beside storage-proof.json; fresh root only')
    p.add_argument('--execute-cpu',action='store_true')
    p.add_argument('--max-windows',type=int,default=24)
    p.add_argument('--seconds',type=int,default=45)
    p.add_argument('--output',type=Path)
    p.add_argument('--backup',type=Path,help='New destination only; existing Ledger backup/integrity contract')
    a = p.parse_args()
    if a.manifest and (not a.cache or not a.upstream_run_id): p.error('manifest requires cache and upstream-run-id')
    restored = None
    if a.restore:
        import gzip
        import shutil
        from bct.v4.store import file_sha
        proof = json.loads((a.restore.parent/'storage-proof.json').read_text())
        hits = [r for r in proof.values() if r['archive']==a.restore.name]
        if len(hits)!=1 or file_sha(a.restore)!=hits[0]['archive_sha256']:
            raise ValueError('RESTORE_ARCHIVE_HASH_MISMATCH')
        destination = a.root/'v4.sqlite3'
        if destination.exists(): raise ValueError('RESTORE_REQUIRES_FRESH_ROOT')
        a.root.mkdir(parents=True,exist_ok=True)
        with gzip.open(a.restore,'rb') as src,destination.open('xb') as dst:
            shutil.copyfileobj(src,dst)
        if file_sha(destination)!=hits[0]['sqlite_sha256']:
            raise ValueError('RESTORED_SQLITE_HASH_MISMATCH')
        restored = {'archive_sha256':file_sha(a.restore),'sqlite_sha256':file_sha(destination)}
    l = open_queue(a.root)
    try:
        with l.worker():
            output = {'trigger':'MANUAL_DEVELOPMENT_NOT_SCHEDULED'}
            if restored: output['restored'] = restored
            if a.seed_completed: output['reused_legacy_documents'] = seed_completed(l,a.seed_completed)
            if a.manifest: output['imports'] = ingest_delta(l,json.loads(a.manifest.read_text()),a.cache,upstream_run_id=a.upstream_run_id,reconsider_held=a.reconsider_held)
            if a.execute_cpu: output['work'] = work(l,max_windows=a.max_windows,seconds=a.seconds)
            output['queue'] = state(l)
            if a.backup:
                l.backup(a.backup)
                from bct.v4.store import file_sha
                output['backup']={'path':str(a.backup),'sha256':file_sha(a.backup)}
            output.update(API_calls=0,API_tokens=0,API_cost_KRW=0)
            text = json.dumps(output,ensure_ascii=False,indent=2)+'\n'
            if a.output:
                a.output.parent.mkdir(parents=True,exist_ok=True)
                with a.output.open('x') as f: f.write(text)
            else: print(text)
    finally: l.close()


if __name__=='__main__': main()
