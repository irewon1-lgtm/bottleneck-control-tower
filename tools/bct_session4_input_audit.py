"""Read-only exact-version selection audit over the authenticated private CPU checkpoint.

Never fetches original URLs, loads an AI model, writes to Git or publishes body,
quotes, task text, raw CPU outputs or credentials. It observes at most the
source-free state already present in an authenticated prior checkpoint.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import tempfile

FORMAT = 'bct-session4-private-source-selection-audit-v1'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_targets(ledger_file, receipt_file):
    ledger_file=Path(ledger_file);receipt=json.loads(Path(receipt_file).read_text())
    if (receipt.get('status')!='PASS_BACKFILL_HOLD_ONLY'
            or digest(ledger_file.read_bytes())!=receipt['ledger_sha256']):
        raise ValueError('S4_TARGET_LEDGER_HASH_OR_RECEIPT_MISMATCH')
    db=sqlite3.connect(ledger_file.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise ValueError('S4_TARGET_SQLITE_INTEGRITY')
        targets=[]
        for id,hashed,payload in db.execute(
                'SELECT id,payload_sha256,payload FROM cases ORDER BY id'):
            if digest(payload.encode())!=hashed:
                raise ValueError('S4_TARGET_CASE_HASH_MISMATCH')
            row=json.loads(payload)
            if row['case_id']!=id or row.get('decision')!='HOLD' or row.get('auto_promoted') is not False:
                raise ValueError('S4_TARGET_CASE_NOT_HELD')
            src=row['source']
            if any(not isinstance(src.get(k),str) or not src[k] for k in
                   ('document_id','body_sha256','raw_sha256')):
                raise ValueError('S4_TARGET_SOURCE_IDENTITY_MISSING')
            targets.append({k:src[k] for k in
                            ('document_id','body_sha256','raw_sha256')})
        if len(targets)!=receipt['source_verified_documents']:
            raise ValueError('S4_TARGET_CASE_COUNT_MISMATCH')
        if len({(v['document_id'],v['body_sha256'],v['raw_sha256']) for v in targets})!=len(targets):
            raise ValueError('S4_TARGET_DUPLICATE_SOURCE_IDENTITY')
        return targets
    finally:db.close()


def completed_keys(checkpoint):
    checkpoint=Path(checkpoint);data=json.loads((checkpoint/'checkpoint.json').read_text())
    archive=checkpoint/data['archive']
    if (data['archive']!='checkpoint.sqlite3.gz'
            or digest(archive.read_bytes())!=data['archive_sha256']):
        raise ValueError('S4_PRIVATE_CHECKPOINT_SEAL_INVALID')
    with tempfile.TemporaryDirectory(prefix='s4-checkpoint-readonly-') as tmp:
        sqlite=Path(tmp)/'checkpoint.sqlite3'
        with gzip.open(archive,'rb') as source,sqlite.open('xb') as dest:
            size=0
            for chunk in iter(lambda:source.read(1024*1024),b''):
                size+=len(chunk)
                if size>128*1024**2:raise ValueError('S4_PRIVATE_SQLITE_BOUND')
                dest.write(chunk)
        if digest(sqlite.read_bytes())!=data['sqlite_sha256']:
            raise ValueError('S4_PRIVATE_SQLITE_HASH_MISMATCH')
        db=sqlite3.connect(sqlite.resolve().as_uri()+'?mode=ro',uri=True)
        try:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise ValueError('S4_PRIVATE_SQLITE_INTEGRITY')
            done=set()
            for kind,payload in db.execute("SELECT kind,payload FROM events WHERE kind IN ('CPU_RESUME_WINDOW','CPU_RESUME_FAILURE')"):
                record=json.loads(payload)
                done.add(record['key'])
            return done
        finally:db.close()


def classify(targets,plan,done):
    sources=list(plan['sources'].values())
    selected={d['artifact_id'] for d in plan['descriptors']}
    holds={d['body_key']:d['reason_code'] for d in plan['holds']}
    out=[]
    for target in targets:
        matches=[s for s in sources
                 if all(s.get(k)==target[k] for k in
                        ('document_id','body_sha256','raw_sha256'))]
        if len(matches)>1:raise ValueError('S4_CHECKPOINT_EXACT_SOURCE_DUPLICATE')
        if not matches:
            row={**target,'status':'EXACT_VERSION_ABSENT_FROM_LATEST_CHECKPOINT',
                 'pending_windows':None,'source_artifact_id':None}
        else:
            source=matches[0]
            tasks=source.get('tasks',[])
            if not isinstance(tasks,list) or any('key' not in x for x in tasks):
                raise ValueError('S4_PRIVATE_SOURCE_TASK_SCHEMA')
            remaining=sum(t['key'] not in done for t in tasks)
            descriptor=source.get('input_artifact')
            artifact=descriptor.get('artifact_id') if isinstance(descriptor,dict) else None
            hold=holds.get(source['body_key'])
            if remaining==0:status='EXACT_SOURCE_WINDOWS_TERMINAL_ALREADY'
            elif hold:status=hold
            elif artifact is None:status='EXACT_INPUT_ARTIFACT_DESCRIPTOR_MISSING'
            elif artifact in selected:status='SELECTED_BUT_READING_NOT_PROVEN_BY_INPUT_PLAN'
            else:status='UNEXPLAINED_PRIOR_INPUT_SELECTION'
            row={**target,'status':status,'pending_windows':remaining,
                 'source_artifact_id':artifact}
        out.append(row)
    return {'format':FORMAT,'source_count':len(out),
            'source_identities_verified':True,
            'status_counts':dict(sorted(Counter(x['status'] for x in out).items())),
            'pending_windows':sum(x['pending_windows'] or 0 for x in out),
            'private_checkpoint_source_versions':len(sources),
            'prior_artifact_limit':8,
            'prior_artifacts_selected':len(selected),
            'sources':out,
            'new_CPU_calls':0,'public_original_text':False,
            'production_writes':0,'can_mark_session4_complete':False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--target-ledger',type=Path,required=True)
    p.add_argument('--target-receipt',type=Path,required=True)
    p.add_argument('--pinned-transport',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        raise ValueError('S4_AUDIT_OUTPUT_ALREADY_EXISTS')
    spec=importlib.util.spec_from_file_location('bct_verified_pinned_transport',args.pinned_transport)
    if spec is None or spec.loader is None:raise ValueError('S4_PINNED_TRANSPORT_NOT_FOUND')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # Existing transport computes and validates its own pinned eligible input
    # artifact selection, unchanged. This audit never changes the plan.
    plan=module.checkpoint_inputs(args.checkpoint)
    result=classify(read_targets(args.target_ledger,args.target_receipt),plan,
                    completed_keys(args.checkpoint))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
    print('BCT_S4_SELECTION_AUDIT_JSON='+json.dumps(
        {k:result[k] for k in ('source_count','status_counts','pending_windows',
             'prior_artifact_limit','prior_artifacts_selected','new_CPU_calls','production_writes')},
        sort_keys=True))


if __name__=='__main__':main()
