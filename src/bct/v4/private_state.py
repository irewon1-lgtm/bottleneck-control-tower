"""Private-only checkpoint transport. Reuses the CPU ledger and bounded CAS writer.

No collector, model, stage rules, credentials generation or scheduler activation.
Public Actions/cache transport contains authenticated ciphertext, never a DB.
"""
import base64
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from . import cpu_operations as op
from .store import file_sha,now

PUBLIC_REPO='irewon1-lgtm/bottleneck-control-tower'
PRIVATE_REPO='irewon1-lgtm/bct-v4-private-state'
PRIVATE_URL='https://github.com/'+PRIVATE_REPO+'.git'
MAX_TRANSPORT=24*1024**2


def github_api(token,method,path,data=None):
    if not token:raise ValueError('PRIVATE_STATE_CREDENTIAL_MISSING')
    if not re.fullmatch(r'[A-Za-z0-9_\-]{20,512}',token):raise ValueError('PRIVATE_STATE_CREDENTIAL_FORMAT_INVALID')
    body=json.dumps(data).encode()if data is not None else None
    req=Request('https://api.github.com/'+path,data=body,method=method,
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                 'Content-Type':'application/json','User-Agent':'BCT-private-state'})
    try:
        with urlopen(req,timeout=25)as response:return response.status,json.load(response)
    except HTTPError as exc:return exc.code,{}  # Never expose headers or response text.
    except (OSError,ValueError)as exc:
        raise ValueError('PRIVATE_STATE_NETWORK_OR_AUTH_TRANSPORT_FAILED')from None


def writer_scope(token,*,api=github_api):
    """Real non-mutating ref-create denials, not account role flags.

    Creating an ALREADY EXISTING ref cannot update it. A broad credential returns
    422 (and is rejected); a private-only credential must get403/404 on BOTH refs.
    A constant private orphan blob proves contents-write without updating a ref.
    """
    code,repo=api(token,'GET','repos/'+PRIVATE_REPO)
    if code!=200 or repo.get('full_name')!=PRIVATE_REPO or repo.get('private')is not True:
        raise ValueError('PRIVATE_REPOSITORY_IDENTITY_OR_VISIBILITY_NOT_VERIFIED')
    code,visible=api(token,'GET','user/repos?visibility=private&per_page=100')
    if code!=200 or not isinstance(visible,list) or len(visible)!=1 or visible[0].get('full_name')!=PRIVATE_REPO:
        raise ValueError('PRIVATE_WRITER_REPOSITORY_SCOPE_NOT_EXCLUSIVE')
    denials={}
    for branch in ('main','data'):
        code,ref=api(token,'GET',f'repos/{PUBLIC_REPO}/git/ref/heads/{branch}')
        oid=ref.get('object',{}).get('sha','')
        if code!=200 or not re.fullmatch('[0-9a-f]{40}',oid):raise ValueError('OPERATING_REF_NOT_VERIFIED_NO_WRITE_PROBE')
        code,_=api(token,'POST',f'repos/{PUBLIC_REPO}/git/refs',{'ref':'refs/heads/'+branch,'sha':oid})
        if code not in (403,404):raise ValueError('PRIVATE_WRITER_OPERATING_REF_WRITE_NOT_DENIED')
        denials[branch]=code
    code,_=api(token,'POST',f'repos/{PRIVATE_REPO}/git/blobs',
               {'content':'BCT private-state constant permission probe; no source content','encoding':'utf-8'})
    if code!=201:raise ValueError('PRIVATE_CONTENTS_WRITE_NOT_VERIFIED')
    return {'private_repository':PRIVATE_REPO,'visibility':'private','operating_ref_create_denials':denials,
            'private_contents_probe':201,'visible_private_repository_count':1,'operating_refs_modified':False}


def _parent(value):
    if value and not re.fullmatch('[0-9a-f]{40}',value):raise ValueError('STATE_PARENT_CONTRACT')
    return value


def _gpg(payload,passphrase,*,decrypt=False):
    if not 40<=len(passphrase)<=256 or '\n'in passphrase or '\r'in passphrase:raise ValueError('STATE_TRANSPORT_PASSPHRASE_CONTRACT')
    if len(payload)>MAX_TRANSPORT:raise ValueError('STATE_TRANSPORT_SIZE_BOUND')
    with tempfile.TemporaryDirectory(prefix='bct-state-gpg-')as tmp:
        os.chmod(tmp,0o700)
        fd,write=os.pipe()
        try:
            os.write(write,(passphrase+'\n').encode());os.close(write)
            args=['gpg','--no-options','--batch','--no-tty','--homedir',tmp,'--pinentry-mode','loopback',
                  '--passphrase-fd',str(fd),'--no-symkey-cache','--max-output',str(MAX_TRANSPORT)]
            args+=['--decrypt']if decrypt else ['--symmetric','--cipher-algo','AES256','--compress-algo','none','--force-mdc']
            p=subprocess.run(args,input=payload,capture_output=True,pass_fds=(fd,),timeout=25)
        finally:os.close(fd)
    if p.returncode or len(p.stdout)>MAX_TRANSPORT:raise ValueError('STATE_TRANSPORT_AUTHENTICATION_OR_SIZE_FAILED')
    return p.stdout


def seal(source,destination,passphrase,expected_parent):
    source,destination=Path(source),Path(destination)
    proof=json.loads((source/'checkpoint.json').read_text());archive=source/'checkpoint.sqlite3.gz'
    if proof['archive']!=archive.name or archive.stat().st_size>16*1024**2 or file_sha(archive)!=proof['archive_sha256']:
        raise ValueError('STATE_CHECKPOINT_HASH_OR_SIZE')
    payload={'version':'bct-private-handoff-1','expected_parent':_parent(expected_parent),
             'proof':proof,'archive_base64':base64.b64encode(archive.read_bytes()).decode(),
             'producer_run_id':os.environ.get('GITHUB_RUN_ID'),'producer_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),
             'producer_job':os.environ.get('GITHUB_JOB')}
    encrypted=_gpg(json.dumps(payload).encode(),passphrase)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb')as out:out.write(encrypted)
    destination.chmod(0o600)
    return {'encrypted_bytes':len(encrypted),'encrypted_sha256':file_sha(destination),'plaintext_in_public_cache':False}


def unseal(source,destination,passphrase):
    source,destination=Path(source),Path(destination)
    if source.stat().st_size>MAX_TRANSPORT:raise ValueError('STATE_TRANSPORT_SIZE_BOUND')
    payload=json.loads(_gpg(source.read_bytes(),passphrase,decrypt=True))
    if payload.get('version')!='bct-private-handoff-1':raise ValueError('STATE_HANDOFF_CONTRACT')
    parent=_parent(payload['expected_parent']);proof=payload['proof']
    if proof['archive']!='checkpoint.sqlite3.gz':raise ValueError('STATE_ARCHIVE_PATH_CONTRACT')
    archive=base64.b64decode(payload['archive_base64'],validate=True)
    from .store import sha
    if len(archive)>16*1024**2 or sha(archive)!=proof['archive_sha256']:raise ValueError('STATE_CHECKPOINT_HASH_OR_SIZE')
    # Authenticate, validate SQLite/hash/table digests before creating the output.
    with tempfile.TemporaryDirectory(prefix='bct-state-handoff-')as tmp:
        staging=Path(tmp)/'checkpoint';staging.mkdir()
        (staging/'checkpoint.json').write_text(json.dumps(proof))
        (staging/'checkpoint.sqlite3.gz').write_bytes(archive)
        op.restore(staging,Path(tmp)/'verify')
        destination.mkdir(parents=True,exist_ok=False)
        (destination/'checkpoint.json').write_text(json.dumps(proof))
        (destination/'checkpoint.sqlite3.gz').write_bytes(archive)
        (destination/'parent.json').write_text(json.dumps({k:payload[k]for k in
            ('expected_parent','producer_run_id','producer_attempt','producer_job')}))
    return {'expected_parent':parent,'authenticated':True,'SQLite_and_8_table_hashes_verified':True}


def verify_predecessor(parent,*,read=None):
    """Never analyze from an old cached DB after a failed/unfinished publication.

    Git CAS would refuse its later write, but would be too late to avoid duplicate
    CPU work. This public read-only run check happens BEFORE loading the model.
    Cache eviction or a newer failed run requires explicit private-state recovery.
    """
    if parent.get('producer_job')!='publish':raise ValueError('STATE_BRIDGE_NOT_FROM_PUBLISHER')
    workflow=os.environ.get('GITHUB_WORKFLOW_REF','').split('@')[0].split('/')[-1]
    if not workflow.endswith(('.yml','.yaml')):raise ValueError('STATE_WORKFLOW_IDENTITY_MISSING')
    if read is None:
        def read(path):
            p=subprocess.run(['gh','api',path],capture_output=True,text=True,timeout=25)
            if p.returncode:raise ValueError('STATE_PREDECESSOR_METADATA_BLOCKED')
            return json.loads(p.stdout)
    result=read(f'repos/{PUBLIC_REPO}/actions/workflows/{workflow}/runs?per_page=5')
    current=int(os.environ.get('GITHUB_RUN_ID','0'))
    previous=next((r for r in result.get('workflow_runs',[])if int(r['id'])<current),None)
    if (not previous or previous.get('conclusion')!='success' or previous.get('status')!='completed'
            or str(previous['id'])!=str(parent.get('producer_run_id'))
            or str(previous.get('run_attempt'))!=str(parent.get('producer_attempt'))):
        raise ValueError('STATE_BRIDGE_STALE_OR_PREVIOUS_PUBLICATION_UNCONFIRMED')
    return {'previous_publisher_run':previous['id'],'verified_before_CPU':True}


def publish(repo,source,expected_parent,token,policy,*,api=github_api):
    """Writer job only. No credential in Git URLs, argv, files, outputs or logs."""
    review=op.checkpoint_storage_audit(source,policy,scope='private')
    if review['status']!='PASS_PRIVATE_STORAGE_REVIEW':raise ValueError('PRIVATE_ARCHIVAL_REVIEW_BLOCKED')
    scope=writer_scope(token,api=api)
    repo=Path(repo);repo.mkdir(parents=True,exist_ok=True)
    def git(*args,env=None):
        p=subprocess.run(['git','-C',str(repo),*args],env=env,capture_output=True,timeout=25)
        if p.returncode:raise ValueError('PRIVATE_STATE_GIT_FAILED')
        return p.stdout
    if not(repo/'.git').exists():
        git('init');git('remote','add','origin',PRIVATE_URL)
    if git('config','--get','remote.origin.url').decode().strip()!=PRIVATE_URL:raise ValueError('PRIVATE_STATE_REMOTE_MISMATCH')
    auth=base64.b64encode(('x-access-token:'+token).encode()).decode()
    env={**os.environ,'GIT_CONFIG_COUNT':'2','GIT_CONFIG_KEY_0':'http.https://github.com/.extraheader',
         'GIT_CONFIG_VALUE_0':'AUTHORIZATION: basic '+auth,'GIT_CONFIG_KEY_1':'credential.helper',
         'GIT_CONFIG_VALUE_1':'','GIT_TERMINAL_PROMPT':'0'}
    result=op._publish_checkpoint(repo,source,_parent(expected_parent),git_env=env)
    # Fresh remote fetch and a second SQLite restore, not just local commit success.
    git('fetch','--no-tags','origin',op.STATE_REF,env=env)
    if git('rev-parse','FETCH_HEAD').decode().strip()!=result['commit']:raise ValueError('PRIVATE_REMOTE_COMMIT_CHANGED')
    with tempfile.TemporaryDirectory(prefix='bct-private-requery-')as tmp:
        prior=Path(tmp)/'checkpoint';prior.mkdir()
        for name in ('checkpoint.json','checkpoint.sqlite3.gz'):
            (prior/name).write_bytes(git('show',result['commit']+':'+name))
        restored=op.restore(prior,Path(tmp)/'restored')
        with sqlite3.connect((Path(tmp)/'restored/v4.sqlite3').as_uri()+'?mode=ro',uri=True)as db:
            row=db.execute("SELECT payload FROM events WHERE kind='CPU_OPERATION_OBSERVATION' ORDER BY seq DESC LIMIT 1").fetchone()
            observation=json.loads(row[0])if row else {}
    if restored['sqlite_sha256']!=review['sqlite_sha256']:raise ValueError('PRIVATE_REMOTE_RESTORE_HASH_MISMATCH')
    previous={}
    if expected_parent:
        names=git('ls-tree','--name-only',expected_parent).decode().splitlines()
        if 'private-persistence.json'in names:previous=json.loads(git('show',expected_parent+':private-persistence.json'))
    first=previous.get('seven_day_start')
    if (observation.get('scheduled_execution_verified')is True
            and observation.get('successful_new_CPU_windows',0)>0
            and observation.get('actually_read_new_characters',0)>0):
        first=first or now()
    receipt={'version':'bct-private-persistence-1','checkpoint_commit':result['commit'],
             'sqlite_sha256':restored['sqlite_sha256'],'remote_restored_at':now(),
             'seven_day_start':first,'seven_day_status':'OBSERVING_NOT_COMPLETED'if first else 'NOT_STARTED',
             'new_validated_windows':observation.get('successful_new_CPU_windows',0),
             'API_calls':0,'LIVE_registration':False}
    # A small receipt commit ACKs the already restored DB; identical compressed
    # DB blobs deduplicate in Git. No second model run or full DB copy is made.
    acknowledged=op._publish_checkpoint(repo,source,result['commit'],git_env=env,persistence_receipt=receipt)
    git('fetch','--no-tags','origin',op.STATE_REF,env=env)
    if (git('rev-parse','FETCH_HEAD').decode().strip()!=acknowledged['commit']
            or json.loads(git('show',acknowledged['commit']+':private-persistence.json'))!=receipt):
        raise ValueError('PRIVATE_PERSISTENCE_RECEIPT_NOT_CONFIRMED')
    return {**acknowledged,'repository':PRIVATE_REPO,'visibility':'private','scope_proof':scope,
            'remote_restore_verified':True,'persistence_receipt':receipt}
