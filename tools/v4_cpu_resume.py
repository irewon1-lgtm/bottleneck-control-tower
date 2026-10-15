#!/usr/bin/env python3
"""Prepare an immutable source-separated seed from verified existing backups."""
import argparse,gzip,json,sqlite3,tempfile
from pathlib import Path
from bct.v4 import cpu_resume as resume,cpu_operations as op
from bct.v4.store import file_sha,Ledger,sha

def unpack(archive,proof,destination):
    if file_sha(archive)!=proof.get('archive_sha256',proof.get('snapshot_sha256')):raise ValueError('BASELINE_ARCHIVE_HASH_MISMATCH')
    destination.mkdir(parents=True,exist_ok=False)
    path=destination/'v4.sqlite3';path.write_bytes(gzip.decompress(Path(archive).read_bytes()))
    if proof.get('sqlite_sha256') and file_sha(path)!=proof['sqlite_sha256']:raise ValueError('BASELINE_SQLITE_HASH_MISMATCH')
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)as db:
        actual=op.table_digests(db) if 'archive_sha256'in proof else {t:{'rows':len(rr),'sha256':sha([[v.hex()if isinstance(v,bytes)else v for v in row]for row in rr])}for t in op.TABLES for rr in [db.execute(f'SELECT * FROM {t} ORDER BY rowid').fetchall()]}
        if actual!=proof['tables']:raise ValueError('BASELINE_TABLES_MISMATCH')
    return path

def prepare(output):
    output=Path(output).resolve()
    if output.exists():raise ValueError('REFUSE_RESUME_OUTPUT_OVERWRITE')
    with tempfile.TemporaryDirectory(prefix='bct-resume-baselines-')as tmp:
        tmp=Path(tmp)
        current=json.loads(Path('docs/v4/cpu-automation/storage-proof.json').read_text())['ledger']
        legacy=json.loads(Path('docs/v4/cpu-recovery/storage-proof.json').read_text())
        a=unpack('docs/v4/cpu-automation/ledger.sqlite3.gz',current,tmp/'current')
        b=unpack('docs/v4/cpu-recovery/research-snapshot.sqlite3.gz',legacy,tmp/'legacy')
        result=resume.export_state(a,output/'ledger',legacy=b)
    l=Ledger(output/'ledger')
    try:
        result['schema_audit']=resume.audit(l)['status']
        result['checkpoint']=op.checkpoint(l,output/'checkpoint')
    finally:l.close()
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args();r=prepare(args.output)
    print(json.dumps({k:v for k,v in r.items()if k!='checkpoint'},indent=2))
