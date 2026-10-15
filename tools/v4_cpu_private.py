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
    p.add_argument('--reuse-verified-scope',action='store_true',help='Reuse trusted committed owner connection proof; no authentication/ref-denial retest')
    a=p.parse_args();policy=json.loads(Path('docs/v4/cpu-automation/preflight/publication-policy.json').read_text())
    if a.action=='verify-scope':result=private.writer_scope(os.environ.get('BCT_V4_PRIVATE_STATE_TOKEN',''))
    elif a.action=='prepare-seed':
        from v4_cpu_resume import prepare
        prepared=a.checkpoint.parent/'source-separated-seed'
        result=prepare(prepared)
        shutil.copytree(prepared/'checkpoint',a.checkpoint)
        result.update(original_changed=False,source_articles_copied=False)
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
        scope=None
        if a.reuse_verified_scope:
            proof=json.loads(Path('docs/v4/cpu-automation/preflight/connection-results.json').read_text())
            if proof['actual_remote_evidence']['run_id']!=38709974717:raise ValueError('OWNER_SCOPE_PROOF_NOT_PINNED')
            scope=proof['actual_remote_evidence']['receipts']['BCT_PRIVATE_SCOPE_JSON']['scope']
        result=private.publish(a.repository,a.checkpoint,parent,os.environ.get('BCT_V4_PRIVATE_STATE_TOKEN',''),policy,verified_scope=scope)
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
            from bct.v4 import cpu_resume as resume
            if ledger.db.execute("SELECT value FROM metadata WHERE key='cpu_source_separated_format'").fetchone()!=(resume.FORMAT,):
                raise ValueError('SOURCE_SEPARATED_RESTART_REQUIRED')
            with ledger.worker():
                rehydrated=resume.hydrate(ledger,a.cache,policy)
                imports=ingest_delta(ledger,json.loads((a.rss/'new-document-manifest.json').read_text()),a.cache,
                    upstream_run_id=str(schedule['RSS_run_id']),storage_policy=policy,source_separated=True)
            result=op.observe(ledger,trigger='VERIFIED_SCHEDULE_PENDING_PRIVATE_PUBLICATION',execute=True,
                extractor=CPUExtractor(a.runtime),schedule_context=context,persistence_required=True,
                upstream={'new_URLs':sum(x['status']!='ALREADY_IMPORTED'for x in imports),
                          'new_body_documents':sum(x['status']=='QUEUED'for x in imports)})
            safe_root=a.root.parent/'source-separated-next'
            resume.export_state(ledger.path,safe_root)
            safe=resume.Ledger(safe_root)
            try:
                resume.audit(safe)
                op.checkpoint(safe,a.root.parent/'next-checkpoint')
            finally:safe.close()
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
