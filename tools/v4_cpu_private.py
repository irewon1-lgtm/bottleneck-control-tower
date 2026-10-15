#!/usr/bin/env python3
"""Private-state storage bridge; no installation, collection or automatic stages."""
import argparse
import json
import os
from pathlib import Path
import shutil

from bct.v4 import cpu_operations as op,private_state as private
from bct.v4.store import file_sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['audit','prepare-seed','verify-scope','seal','unseal','process','publish'])
    p.add_argument('--checkpoint',type=Path,default=Path('var/v4/cpu-private/checkpoint'))
    p.add_argument('--packet',type=Path,default=Path('var/v4/cpu-private/sealed/state.gpg'))
    p.add_argument('--parent',default='')
    p.add_argument('--parent-file',type=Path)
    p.add_argument('--root',type=Path,default=Path('var/v4/cpu-private/ledger'))
    p.add_argument('--repository',type=Path,default=Path('var/v4/cpu-private/git'))
    p.add_argument('--runtime',type=Path,default=Path('.v4-cpu-runtime'))
    p.add_argument('--rss',type=Path,default=Path('var/v4/cpu-private/rss'))
    p.add_argument('--cache',type=Path,default=Path('var/v4/cpu-private/source'))
    p.add_argument('--output',type=Path)
    a=p.parse_args();policy=json.loads(Path('docs/v4/cpu-automation/preflight/publication-policy.json').read_text())
    if a.action=='verify-scope':result=private.writer_scope(os.environ.get('BCT_V4_PRIVATE_STATE_TOKEN',''))
    elif a.action=='prepare-seed':
        original=Path('docs/v4/cpu-automation/ledger.sqlite3.gz')
        proof=json.loads(Path('docs/v4/cpu-automation/storage-proof.json').read_text())['ledger']
        if file_sha(original)!=proof['archive_sha256']:raise ValueError('BASELINE_HASH_MISMATCH')
        a.checkpoint.mkdir(parents=True,exist_ok=False)
        with (a.checkpoint/'checkpoint.sqlite3.gz').open('xb')as out,original.open('rb')as src:shutil.copyfileobj(src,out)
        proof={**proof,'archive':'checkpoint.sqlite3.gz'}
        (a.checkpoint/'checkpoint.json').write_text(json.dumps(proof))
        result={'baseline_copied_without_CPU':True,'original_changed':False}
    elif a.action=='audit':result=op.checkpoint_storage_audit(a.checkpoint,policy,scope='private')
    elif a.action=='unseal':result=private.unseal(a.packet,a.checkpoint,os.environ.get('BCT_V4_STATE_PASSPHRASE',''))
    elif a.action=='seal':
        parent=json.loads(a.parent_file.read_text())if a.parent_file else {}
        parent=parent.get('expected_parent',parent.get('commit',a.parent))
        result=private.seal(a.checkpoint,a.packet,os.environ.get('BCT_V4_STATE_PASSPHRASE',''),parent)
    elif a.action=='publish':
        if os.environ.get('GITHUB_REF')!='refs/heads/main':raise ValueError('PRIVATE_PUBLICATION_REQUIRES_APPROVED_MAIN_WORKFLOW')
        op.github_guard()
        parent=json.loads(a.parent_file.read_text())['expected_parent']if a.parent_file else a.parent
        result=private.publish(a.repository,a.checkpoint,parent,os.environ.get('BCT_V4_PRIVATE_STATE_TOKEN',''),policy)
    else:
        from bct.v4.cpu_automation import open_queue,ingest_delta
        from bct.v4.adapters import CPUExtractor
        op.github_guard();context=op.github_schedule_context();schedule=op.verified_schedule(context)
        private.verify_predecessor(json.loads((a.checkpoint/'parent.json').read_text()))
        if op.checkpoint_storage_audit(a.checkpoint,policy,scope='private')['status']!='PASS_PRIVATE_STORAGE_REVIEW':
            raise ValueError('PRIVATE_ARCHIVAL_REVIEW_BLOCKED')
        op.restore(a.checkpoint,a.root)
        ledger=open_queue(a.root)
        try:
            with ledger.worker():
                imports=ingest_delta(ledger,json.loads((a.rss/'new-document-manifest.json').read_text()),a.cache,
                    upstream_run_id=str(schedule['RSS_run_id']),storage_policy=policy)
            result=op.observe(ledger,trigger='VERIFIED_SCHEDULE_PENDING_PRIVATE_PUBLICATION',execute=True,
                extractor=CPUExtractor(a.runtime),schedule_context=context,persistence_required=True,
                upstream={'new_URLs':sum(x['status']!='ALREADY_IMPORTED'for x in imports),
                          'new_body_documents':sum(x['status']=='QUEUED'for x in imports)})
            op.checkpoint(ledger,a.root.parent/'next-checkpoint')
        finally:ledger.close()
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open('x')as out:json.dump(result,out)
    # Public job logs deliberately contain no source, quotes, products, task text,
    # errors from upstream documents, raw output or credentials.
    print(json.dumps({'action':a.action,'status':result.get('status','DONE'),
        **{k:result[k]for k in ('authenticated','encrypted_bytes','remote_restore_verified','commit',
            'operating_ref_create_denials','private_contents_probe','CPU_documents_processed',
            'new_CPU_windows','successful_new_CPU_windows','actually_read_new_characters',
            'CPU_pending','wall_seconds','peak_RSS_KiB','persistence_receipt')if k in result}}))


if __name__=='__main__':main()
