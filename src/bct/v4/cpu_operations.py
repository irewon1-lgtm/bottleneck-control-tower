"""Free-only preflight and checkpoint observations around the existing CPU queue.

No collector, new model, stage classifier, LIVE registration or scheduler.
"""
from datetime import datetime,timezone
import gzip
import json
import os
from pathlib import Path
import resource
import shutil
import sqlite3
import subprocess
import time
from urllib.request import Request,urlopen

from .store import file_sha,sha,now

GIB=1024**3
TABLES=('metadata','blobs','documents','captures','readings','runs','firsts','events')


def free_guard(repository,usage,*,runner='ubuntu-24.04',runtime=True,reserve_bytes=3*GIB):
    if repository.get('private') is not False or repository.get('visibility')!='public':
        raise ValueError('FREE_PUBLIC_REPOSITORY_NOT_VERIFIED')
    if runner!='ubuntu-24.04' or not runtime: raise ValueError('STANDARD_GITHUB_LINUX_NOT_VERIFIED')
    used=usage.get('active_caches_size_in_bytes')
    if type(used) is not int or used<0 or type(reserve_bytes) is not int or reserve_bytes<0 or used+reserve_bytes>8*GIB:
        raise ValueError('FREE_CACHE_8GIB_SAFETY_BOUND_NOT_MET')
    return {'status':'PASS_PUBLIC_STANDARD_LINUX_AND_CACHE_BELOW_FREE_BOUND',
            'repository':repository['full_name'],'runner':runner,'active_cache_bytes':used,
            'reserved_bytes':reserve_bytes,'free_cache_allowance_bytes':10*GIB,
            'safety_bound_bytes':8*GIB,'additional_artifact_uploads':False,
            'minutes_remaining':'N/A_PUBLIC_STANDARD_RUNNER_MINUTES_FREE',
            'account_billing_permission':'NOT_REQUIRED_FOR_PUBLIC_STANDARD_COMPUTE; not proof of total account bill',
            'basis':'https://docs.github.com/en/billing/concepts/product-billing/github-actions','checked_at':now()}


def github_guard():
    repo=os.environ.get('GITHUB_REPOSITORY')
    if repo!='irewon1-lgtm/bottleneck-control-tower': raise ValueError('WRONG_REPOSITORY')
    def api(path):
        p=subprocess.run(['gh','api',path],capture_output=True,text=True,timeout=25)
        if p.returncode: raise ValueError('GITHUB_READ_PERMISSION_OR_NETWORK_BLOCKED')
        return json.loads(p.stdout)
    hosted=(os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted' and os.environ.get('RUNNER_OS')=='Linux')
    return free_guard(api('repos/'+repo),api('repos/'+repo+'/actions/cache/usage'),runtime=hosted)


def model_files(root,manifest):
    model=Path(root)/'models/gliner2-base-v1'
    for entry in manifest['files']:
        p=(model/entry['path']).resolve()
        if not p.is_relative_to(model.resolve()) or file_sha(p)!=entry['sha256']:
            raise ValueError('PINNED_MODEL_FILE_HASH_MISMATCH')
    return sum(p.stat().st_size for p in model.rglob('*')if p.is_file())


def bootstrap_model(root,manifest):
    """Only the already selected, pinned, Apache2 model; no alternate weights."""
    from .adapters import MODEL,MODEL_REVISION
    if (manifest['model'],manifest['revision'],manifest['weights_license'])!=(MODEL,MODEL_REVISION,'apache-2.0'):
        raise ValueError('EXISTING_MODEL_CONTRACT_MISMATCH')
    model=Path(root)/'models/gliner2-base-v1';model.mkdir(parents=True,exist_ok=True)
    downloads=0
    for entry in manifest['files']:
        path=(model/entry['path']).resolve()
        if not path.is_relative_to(model.resolve()): raise ValueError('MODEL_PATH_ESCAPE')
        if path.exists() and file_sha(path)==entry['sha256']: continue
        path.parent.mkdir(parents=True,exist_ok=True)
        url=f'https://huggingface.co/{MODEL}/resolve/{MODEL_REVISION}/{entry["path"]}'
        temporary=path.with_suffix(path.suffix+'.partial')
        with urlopen(Request(url,headers={'User-Agent':'BCT-CPU-cache-preflight'}),timeout=30)as src,temporary.open('wb')as out:
            shutil.copyfileobj(src,out,1024*1024)
        if file_sha(temporary)!=entry['sha256']: raise ValueError('PINNED_DOWNLOAD_HASH_MISMATCH')
        temporary.replace(path);downloads+=1
    (model/'bct-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return {'downloaded_files':downloads,'verified_bytes':model_files(root,manifest),'model':MODEL,'revision':MODEL_REVISION}


def runtime_probe(root,manifest,*,load=False):
    start=time.monotonic();cc=time.process_time();size=model_files(root,manifest)
    if load:
        from .adapters import CPUExtractor
        m=CPUExtractor(root);m.load()
        import torch
        if torch.get_num_threads()!=4: raise ValueError('CPU_THREAD_CONTRACT')
    return {'at':now(),'model_bytes':size,'model_load_health_probe':load,'new_CPU_inferences':0,
            'CPU_threads':4 if load else None,'wall_seconds':time.monotonic()-start,
            'CPU_seconds':time.process_time()-cc,'process_peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'host_memory_bytes':os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE'),
            'host_CPU_logical':os.cpu_count(),'network_model_downloads':0,
            'meaning':'Health probe only; never a read of completed1210/67windows'}


def table_digests(db):
    return {t:{'rows':len(rows),'sha256':sha([[sha(v)if isinstance(v,bytes)else v for v in row]for row in rows])}
            for t in TABLES for rows in [db.execute(f'SELECT * FROM {t} ORDER BY 1').fetchall()]}


def checkpoint(ledger,dest):
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    backup=dest/'checkpoint.sqlite3';ledger.backup(backup)
    archive=dest/'checkpoint.sqlite3.gz'
    with backup.open('rb')as src,archive.open('xb')as dst:
        with gzip.GzipFile(fileobj=dst,mode='wb',mtime=0)as out:shutil.copyfileobj(src,out)
    proof={'sqlite_sha256':file_sha(backup),'archive_sha256':file_sha(archive),'tables':table_digests(ledger.db),
           'archive':archive.name,'created_at':now(),'durability':'CACHE_IS_EVICTABLE_NOT_A_PERMANENT_BACKUP'}
    (dest/'checkpoint.json').write_text(json.dumps(proof,indent=2)+'\n')
    backup.unlink()  # disposable local backup copy only; native DB/archive retained.
    return proof


def restore(source,root):
    source,root=Path(source),Path(root);p=json.loads((source/'checkpoint.json').read_text());archive=source/p['archive']
    if archive.resolve().parent!=source.resolve() or file_sha(archive)!=p['archive_sha256']:
        raise ValueError('CHECKPOINT_ARCHIVE_HASH_MISMATCH')
    if (root/'v4.sqlite3').exists(): raise ValueError('REFUSE_CHECKPOINT_OVERWRITE')
    root.mkdir(parents=True,exist_ok=True)
    with gzip.open(archive,'rb')as src,(root/'v4.sqlite3').open('xb')as out:shutil.copyfileobj(src,out)
    if file_sha(root/'v4.sqlite3')!=p['sqlite_sha256']: raise ValueError('CHECKPOINT_SQLITE_HASH_MISMATCH')
    with sqlite3.connect((root/'v4.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
        if (db.execute("SELECT value FROM metadata WHERE key='cpu_queue_format'").fetchone()!=('bct-cpu-research-queue-1',)
                or table_digests(db)!=p['tables'] or db.execute('PRAGMA integrity_check').fetchone()!=('ok',)):
            raise ValueError('CHECKPOINT_TABLES_OR_INTEGRITY_MISMATCH')
    return {'restored':True,'tables':len(p['tables']),'sqlite_sha256':p['sqlite_sha256']}


def observe(ledger,*,trigger,scheduled_for=None,upstream=None,execute=False,extractor=None,schedule_context=None,persistence_required=False):
    """One bounded 120-second-supervised command uses the existing queue.

    This preflight does not certify a scheduler. Only independently verified
    scheduled executions with a successful source-validated CPU read may open
    observation. The push-preflight CLI never supplies that verified context.
    """
    from .cpu_automation import state,work
    scheduled=verified_schedule(schedule_context) if schedule_context is not None else {'verified':False}
    before=state(ledger);start=time.monotonic();cc=time.process_time();at=now()
    with ledger.worker():
        result=work(ledger,extractor=extractor,max_windows=24,seconds=45)if execute else None
        after=state(ledger)
        prior=[json.loads(p)for p, in ledger.db.execute("SELECT payload FROM events WHERE kind='CPU_OPERATION_OBSERVATION'")]
        payload={'version':'bct-cpu-operation-observation-1','started_at':at,'finished_at':now(),
            'trigger':trigger,'scheduled_for':scheduled_for,'scheduled_execution_verified':scheduled['verified'],
            'schedule_proof':scheduled,
            'seven_day_start':None,'seven_day_status':'NOT_RUN_NO_VERIFIED_SCHEDULED_CPU_SUCCESS',
            'upstream':upstream or {},'new_URLs':(upstream or {}).get('new_URLs',0),'new_body_documents':(upstream or {}).get('new_body_documents',0),
            'CPU_documents_processed':len({c['document_id']for c in after['coverage']if c['read_characters']>next((d['read_characters']for d in before['coverage']if d['document_id']==c['document_id']),0)}),
            'new_CPU_windows':0 if result is None else result['new_windows'],
            'successful_new_CPU_windows':(after['completed_windows']-after['failed_windows'])-(before['completed_windows']-before['failed_windows']),
            'actually_read_new_characters':after['actually_read_characters']-before['actually_read_characters'],
            'CPU_pending':after['pending_windows'],'review_pending_windows':after['completed_windows']-after['failed_windows'],
            'isolated_errors':after['failed_windows']+after['isolated_imports'],
            'backlog_change':after['pending_windows']-before['pending_windows'],
            'wall_seconds':time.monotonic()-start,'CPU_seconds':time.process_time()-cc,
            'peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'queue':after,'model_loaded_by_queue':bool(result and result.get('model_loaded',result['new_windows']>0)),
            'prior_observations':len(prior),'API_calls':0,'API_tokens':0,'API_cost_KRW':0,
            'candidate_registration':False,'AI_adoption':'FAIL_UNCHANGED','lead_performance':'BLOCKED_UNCHANGED'}
        payload['private_persistence_required']=persistence_required
        if persistence_required:payload['seven_day_status']='NOT_STARTED_PENDING_PRIVATE_PERSISTENCE'
        if not persistence_required and scheduled['verified'] and payload['actually_read_new_characters']>0 and payload['successful_new_CPU_windows']>0:
            previous=[r['finished_at']for r in prior if not r.get('private_persistence_required') and r.get('scheduled_execution_verified') and r.get('actually_read_new_characters',0)>0 and r.get('successful_new_CPU_windows',0)>0]
            payload['seven_day_start']=min(previous)if previous else payload['finished_at']
            payload['seven_day_status']='OBSERVING_NOT_COMPLETED_REQUIRES7REAL_DAYS_AND_CONTINUITY_REVIEW'
        with ledger.db:ledger.event('CPU_OPERATION_OBSERVATION',payload)
    return payload


def verified_schedule(context):
    """Require official run metadata plus upstream job-log binding, not a label.

    This is a future activation boundary, not called by the push preflight CLI.
    Raw job logs are not stored or displayed; only their hash and run IDs.
    """
    import re
    event=context['event'];acq=context['acquisition_run'];rss=context['rss_run']
    parent=event.get('workflow_run',{})
    ids=set(re.findall(r'\bRSS_RUN_ID:\s*(\d+)\b',context['acquisition_job_log']))
    if (context.get('event_name')!='workflow_run' or parent.get('id')!=acq.get('id')
            or acq.get('name')!='New precursor evidence acquisition' or acq.get('event')!='workflow_run'
            or acq.get('head_branch')!='main' or acq.get('conclusion')!='success'
            or rss.get('name')!='RSS live environment check' or rss.get('event')!='schedule'
            or rss.get('head_branch')!='main' or rss.get('conclusion')!='success'
            or ids!={str(rss.get('id'))}):
        raise ValueError('SCHEDULE_CHAIN_NOT_VERIFIED')
    return {'verified':True,'RSS_run_id':rss['id'],'acquisition_run_id':acq['id'],
            'RSS_actual_created_at':rss['created_at'],'nominal_cron_slot':None,
            'configured_UTC_slots':['02:00','06:00','10:00','14:00','18:00','22:00'],
            'acquisition_job_log_sha256':sha(context['acquisition_job_log'].encode()),
            'nominal_slot_note':'Run metadata does not prove which nominal cron invocation fired'}


def observation_summary(db):
    rows=[json.loads(p)for p, in db.execute("SELECT payload FROM events WHERE kind='CPU_OPERATION_OBSERVATION' ORDER BY seq")]
    starts=[r['finished_at']for r in rows if not r.get('private_persistence_required') and r.get('scheduled_execution_verified') and r.get('actually_read_new_characters',0)>0 and r.get('successful_new_CPU_windows',0)>0]
    return {'observations':len(rows),'latest':rows[-1]if rows else None,
        'first_verified_scheduled_CPU_success':min(starts)if starts else None,
        'seven_day_status':'NOT_RUN'if not starts else'OBSERVING_REQUIRES_CONTINUITY_REVIEW',
        'automatic_completion':False,'cache_is_permanent_storage':False}


def github_schedule_context():
    """Fetch chain evidence in an approved automatic job only, never preflight."""
    import re
    if os.environ.get('GITHUB_EVENT_NAME')!='workflow_run' or os.environ.get('GITHUB_REPOSITORY')!='irewon1-lgtm/bottleneck-control-tower':
        raise ValueError('NOT_AN_APPROVED_UPSTREAM_WORKFLOW_TRIGGER')
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    parent=event.get('workflow_run',{}).get('id')
    if type(parent) is not int: raise ValueError('UPSTREAM_RUN_ID_MISSING')
    repo=os.environ['GITHUB_REPOSITORY']
    def command(args):
        p=subprocess.run(args,capture_output=True,text=True,timeout=25)
        if p.returncode: raise ValueError('SCHEDULE_EVIDENCE_ACCESS_BLOCKED')
        return p.stdout
    acq=json.loads(command(['gh','api',f'repos/{repo}/actions/runs/{parent}']))
    log=command(['gh','run','view',str(parent),'--repo',repo,'--log'])
    ids=set(re.findall(r'\bRSS_RUN_ID:\s*(\d+)\b',log))
    if len(ids)!=1: raise ValueError('RSS_PARENT_LOG_BINDING_MISSING_OR_AMBIGUOUS')
    rss_id=next(iter(ids));rss=json.loads(command(['gh','api',f'repos/{repo}/actions/runs/{rss_id}']))
    context={'event_name':'workflow_run','event':event,'acquisition_run':acq,'rss_run':rss,'acquisition_job_log':log}
    verified_schedule(context)
    return context


STATE_REF='refs/heads/codex/bct-v4-cpu-research-state'
STATE_HISTORY_LIMIT=64*1024**2


def public_checkpoint_audit(source,policy=None):
    return checkpoint_storage_audit(source,policy,scope='public')


def checkpoint_storage_audit(source,policy=None,*,scope='public'):
    """Inspect a verified snapshot, never publish source text or matched secrets.

    Public HTTP access/provenance is not permission to redistribute a raw page.
    Approvals belong to reviewed repository policy, not acquisition artifacts.
    A review binds both native and body hashes; changed versions need review.
    This is a publication gate, not a claim that a pattern scan proves privacy.
    """
    import re
    import tempfile
    from urllib.parse import urlsplit
    if scope not in ('public','private'):raise ValueError('UNKNOWN_STORAGE_SCOPE')
    policy=policy or {};reviews=policy.get('sources',{})
    permission='redistribution'if scope=='public'else 'private_archival'
    findings=[];sources=[]
    with tempfile.TemporaryDirectory(prefix='bct-publication-audit-')as tmp:
        restore(source,Path(tmp)/'db')
        with sqlite3.connect((Path(tmp)/'db/v4.sqlite3').as_uri()+'?mode=ro',uri=True)as db:
            if db.execute("SELECT value FROM metadata WHERE key='cpu_source_separated_format'").fetchone():
                from types import SimpleNamespace
                from .cpu_resume import audit as separated_audit
                try:separated_audit(SimpleNamespace(db=db))
                except ValueError:
                    findings.append({'table':'events','reason':'SOURCE_SEPARATED_STATE_SCHEMA_INVALID'})
            for doc_id,raw_id,payload in db.execute('SELECT id,raw_id,payload FROM documents'):
                d=json.loads(payload);raw=db.execute('SELECT data FROM blobs WHERE id=?',(raw_id,)).fetchone()if raw_id else None
                text=(raw[0].decode('utf-8',errors='replace')if raw else '')+'\n'+d.get('body','')
                review=reviews.get(doc_id,{})
                hashes_match=(raw is not None and sha(raw[0])==raw_id==d.get('raw_sha256')
                              and sha(d.get('body','').encode())==d.get('body_sha256'))
                approved=(hashes_match and review.get('raw_sha256')==raw_id
                    and review.get('body_sha256')==d.get('body_sha256')
                    and review.get(permission)=='PERMITTED'
                    and review.get('privacy_review')=='CLEARED'
                    and bool(review.get('rights_basis')) and bool(review.get('reviewed_by')))
                sources.append({'document_id':doc_id,'origin_host':urlsplit(d.get('origin_url','')).hostname,
                    'raw_sha256':raw_id,'body_sha256':d.get('body_sha256'),
                    'raw_bytes':len(raw[0])if raw else 0,'body_characters':len(d.get('body','')),
                    'contact_pattern_count':len(re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',text)),
                    'copyright_notice':bool(re.search(r'copyright|all rights reserved|©',text,re.I)),
                    'content_hashes_match':hashes_match,'hash_bound_rights_and_privacy_review':approved})
                if not approved:findings.append({'table':'documents','record_id':doc_id,'reason':
                    'RAW_REDISTRIBUTION_OR_PRIVACY_UNREVIEWED'if scope=='public'else 'PRIVATE_ARCHIVAL_OR_PRIVACY_UNREVIEWED'})
            for blob_id, in db.execute('SELECT id FROM blobs WHERE id NOT IN (SELECT raw_id FROM documents WHERE raw_id IS NOT NULL)'):
                findings.append({'table':'blobs','record_id':blob_id,'reason':'UNREVIEWED_ORPHAN_RAW_CONTENT'})
            # Include original blobs AND all nested outputs/events, not just body.
            patterns=[r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                      r'\b(?:gsk_|ghp_|github_pat_|sk-proj-)[A-Za-z0-9_\-]{20,}',
                      r'(?i)\b(?:authorization|proxy-authorization)["\x27]?\s*[:=]\s*["\x27]?Bearer\s+[^\s"\x27]{8,}',
                      r'(?i)[?&](?:access_token|auth_token|api_key|session_token|password|secret)=[^\s&"\x27]{4,}']
            for table,column in [('blobs','data'),('documents','payload'),('readings','payload'),('runs','payload'),('events','payload'),('metadata','value')]:
                for record_id,value in db.execute(f'SELECT rowid,{column} FROM {table}'):
                    text=value.decode('utf-8',errors='replace')if isinstance(value,bytes)else value
                    if any(re.search(pattern,text)for pattern in patterns):
                        findings.append({'table':table,'record_id':record_id,'reason':'POSSIBLE_AUTHENTICATION_MATERIAL'})
            if db.execute('SELECT count(*) FROM firsts').fetchone()[0]:
                findings.append({'table':'firsts','reason':'CANDIDATE_OR_LIVE_FIRSTS_PRESENT'})
    return {'status':'BLOCKED'if findings else 'PASS_PUBLICATION_REVIEW'if scope=='public'else 'PASS_PRIVATE_STORAGE_REVIEW',
            'scope':scope,
            'sqlite_sha256':json.loads((Path(source)/'checkpoint.json').read_text())['sqlite_sha256'],
            'documents':sources,'findings':findings,'scan_is_not_a_privacy_certificate':True,
            'originals_modified':False}


def publish_checkpoint(repo,source,expected_parent,*,publication_policy=None):
    """Prepared CAS writer for a dedicated research ref, never main/data.

    Historical commits are preserved; the cumulative object bound stops writes.
    Fixed ref code does NOT branch-scope a GitHub contents:write token. Server
    permissions must be separately verified before activating a writer job.
    """
    import tempfile
    repo,source=Path(repo),Path(source)
    proof=json.loads((source/'checkpoint.json').read_text());archive=source/'checkpoint.sqlite3.gz'
    if proof['archive']!=archive.name or file_sha(archive)!=proof['archive_sha256'] or archive.stat().st_size>16*1024**2:
        raise ValueError('RESEARCH_CHECKPOINT_HASH_OR_SIZE')
    if public_checkpoint_audit(source,publication_policy)['status']!='PASS_PUBLICATION_REVIEW':
        raise ValueError('PUBLIC_RESEARCH_CHECKPOINT_REVIEW_BLOCKED')
    return _publish_checkpoint(repo,source,expected_parent)


def _publish_checkpoint(repo,source,expected_parent,*,git_env=None,persistence_receipt=None,namespace="cpu"):
    """Shared bounded CAS transport; callers must enforce storage/credential policy."""
    import tempfile
    if namespace not in {"cpu","q1"}:raise ValueError("RESEARCH_STATE_NAMESPACE")
    state_ref=STATE_REF if namespace=="cpu" else "refs/heads/codex/bct-v4-quantitative-state"
    restore_checkpoint=restore
    if namespace=="q1":
        from .quantitative_private import restore as restore_checkpoint
    repo,source=Path(repo),Path(source)
    proof=json.loads((source/'checkpoint.json').read_text());archive=source/'checkpoint.sqlite3.gz'
    if proof['archive']!=archive.name or file_sha(archive)!=proof['archive_sha256'] or archive.stat().st_size>16*1024**2:
        raise ValueError('RESEARCH_CHECKPOINT_HASH_OR_SIZE')
    with tempfile.TemporaryDirectory(prefix='bct-cpu-state-verify-')as temporary:
        verified=Path(temporary)/'verified'
        restore_checkpoint(source,verified)
        with sqlite3.connect((verified/'v4.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)as db:
            if db.execute('SELECT count(*) FROM firsts').fetchone()[0]:
                raise ValueError('RESEARCH_CHECKPOINT_MUST_NOT_REGISTER_LIVE_OR_CANDIDATE_FIRSTS')
    def git(*args,env=None,input=None):
        p=subprocess.run(['git','-C',str(repo),*args],input=input,capture_output=True,text=True,
                         env={**os.environ,**(env or {}),**(git_env or {})},timeout=25)
        if p.returncode: raise ValueError('RESEARCH_STATE_GIT_OPERATION_FAILED')
        return p.stdout.strip()
    current=git('ls-remote','origin',state_ref)
    current=current.split()[0]if current else ''
    if current!=expected_parent: raise ValueError('RESEARCH_STATE_PARENT_CHANGED_NO_OVERWRITE')
    # The same fixed ref is used at both CAS check and push. No caller can
    # redirect this writer to an operational branch.
    if current:git('fetch','--no-tags','origin',state_ref)
    if current:
        shallow=Path(git('rev-parse','--git-path','shallow'))
        if not shallow.is_absolute():shallow=repo/shallow
        if shallow.exists() and set(shallow.read_text().split())&set(git('rev-list',current).split()):
            raise ValueError('RESEARCH_STATE_HISTORY_INCOMPLETE')
    with tempfile.TemporaryDirectory(prefix='bct-cpu-research-index-')as temp:
        env={**os.environ,'GIT_INDEX_FILE':str(Path(temp)/'index')}
        git('read-tree',current if current else '--empty',env=env)
        for name in ('checkpoint.json','checkpoint.sqlite3.gz'):
            blob=git('hash-object','-w',str((source/name).resolve()))
            git('update-index','--add','--cacheinfo',f'100644,{blob},{name}',env=env)
        if persistence_receipt is not None:
            receipt=Path(temp)/'private-persistence.json'
            receipt.write_text(json.dumps(persistence_receipt,sort_keys=True))
            blob=git('hash-object','-w',str(receipt))
            git('update-index','--add','--cacheinfo',f'100644,{blob},private-persistence.json',env=env)
        tree=git('write-tree',env=env)
        command=['-c','user.name=BCT CPU research','-c','user.email=bct-research@users.noreply.github.com','commit-tree',tree]
        if current:command+=['-p',current]
        commit=git(*command,input='Preserve isolated CPU research checkpoint\n')
        # Count unique raw Git object bytes across the complete research history,
        # including old compressed DB blobs. Do not rely on pack/delta ratios or
        # truncate/delete prior snapshots to fit. Local candidate objects are
        # harmless if this check refuses the remote write.
        extra=[]
        if namespace=='q1':
            git('fetch','--no-tags','origin','+refs/heads/*:refs/remotes/origin/*')
            if git('rev-parse','--is-shallow-repository')!='false':raise ValueError('RESEARCH_STATE_HISTORY_INCOMPLETE')
            extra=git('for-each-ref','--format=%(objectname)','refs/remotes/origin').splitlines()
        objects=git('rev-list','--objects',commit,*extra)
        sizes=git('cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)',
                  input='\n'.join(line.split()[0]for line in objects.splitlines())+'\n')
        history_bytes=sum(int(line.split()[2])for line in sizes.splitlines())
        if history_bytes>STATE_HISTORY_LIMIT:
            raise ValueError('RESEARCH_STATE_CUMULATIVE_64MIB_LIMIT')
        git('push','origin',commit+':'+state_ref)
    return {'research_ref':state_ref,'parent':current,'commit':commit,'archive_sha256':proof['archive_sha256'],
            'operating_branches_written':False,'artifact_uploads':0,
            'history_unique_object_bytes':history_bytes,'history_limit_bytes':STATE_HISTORY_LIMIT}
