"""Append-only Q1 SQLite page checkpoints. Existing full backups/history stay intact."""
import base64
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
from .store import file_sha
from .quantitative import LIMIT

HEAD='q1-head.json'
FORMAT='bct-q1-sqlite-pages-1'
PAGE=4096
MAX_SQLITE=512*1024**2


def pack(raw):return gzip.compress(json.dumps(raw,separators=(',',':')).encode(),mtime=0)


def unpack(raw):
    from io import BytesIO
    with gzip.GzipFile(fileobj=BytesIO(raw))as f:
        value=f.read(MAX_SQLITE+1)
    if len(value)>MAX_SQLITE:raise ValueError('Q1_DELTA_EXPANSION_LIMIT')
    return json.loads(value)


def make_delta(before,after):
    """Exact pages, including header/index changes; no SQL or source execution."""
    before,after=Path(before),Path(after)
    if after.stat().st_size>MAX_SQLITE:raise ValueError('Q1_DELTA_SQLITE_LIMIT')
    changed=[]
    with before.open('rb')as a,after.open('rb')as b:
        offset=0
        while block:=b.read(PAGE):
            old=a.read(PAGE)
            if old!=block:changed.append([offset,base64.b64encode(block).decode()])
            offset+=PAGE
    value={'format':FORMAT,'base_sqlite_sha256':file_sha(before),'target_sqlite_sha256':file_sha(after),
           'target_size':after.stat().st_size,'pages':changed}
    raw=pack(value)
    if len(raw)>min(LIMIT,1024**2):raise ValueError('Q1_DELTA_BATCH_1MIB_STOP_BEFORE_PUBLISH')
    return raw,{'changed_pages':len(changed),'delta_bytes':len(raw),'sqlite_bytes':after.stat().st_size}


def apply_delta(db,raw):
    db=Path(db);v=unpack(raw)
    if v.get('format')!=FORMAT or file_sha(db)!=v['base_sqlite_sha256']:raise ValueError('Q1_DELTA_BASE_HASH')
    size=v['target_size']
    if type(size)is not int or not 0<size<=MAX_SQLITE:raise ValueError('Q1_DELTA_SIZE')
    last=-1
    with db.open('r+b')as f:
        for offset,value in v['pages']:
            if type(offset)is not int or offset%PAGE or offset<=last or offset>=size:raise ValueError('Q1_DELTA_PAGE_OFFSET')
            block=base64.b64decode(value,validate=True)
            if len(block)!=min(PAGE,size-offset):raise ValueError('Q1_DELTA_PAGE_LENGTH')
            f.seek(offset);f.write(block);last=offset
        f.truncate(size)
    if file_sha(db)!=v['target_sqlite_sha256']:raise ValueError('Q1_DELTA_TARGET_HASH')


def names(manifest):
    if manifest.get('format')!=FORMAT or not 1<=len(manifest['patches'])<=1024:raise ValueError('Q1_DELTA_MANIFEST')
    output=[]
    for p in manifest['patches']:
        name=p['path']
        if not re.fullmatch(r'q1-deltas/[0-9a-f]{64}\.json\.gz',name)or name in output:raise ValueError('Q1_DELTA_PATH')
        output.append(name)
    return output


def materialize(source,destination):
    from .quantitative_private import restore
    source,destination=Path(source),Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    try:
        if not(source/HEAD).exists():
            for name in ('checkpoint.json','checkpoint.sqlite3.gz'):shutil.copyfile(source/name,destination/name)
        else:
            head=json.loads((source/HEAD).read_text());names(head)
            base=json.loads((source/'checkpoint.json').read_text())
            if base['archive_sha256']!=head['base_archive_sha256']:raise ValueError('Q1_DELTA_BASE_ARCHIVE')
            with tempfile.TemporaryDirectory(prefix='q1-delta-restore-')as tmp:
                root=Path(tmp)/'base';root.mkdir();db=root/'v4.sqlite3'
                # Hash-bound base + final full audit avoid re-auditing all historical
                # records at every delta. No validation is skipped on final state.
                archive=source/'checkpoint.sqlite3.gz'
                if archive.stat().st_size>LIMIT or file_sha(archive)!=base['archive_sha256']:raise ValueError('Q1_DELTA_BASE_ARCHIVE_HASH')
                with gzip.open(archive,'rb')as src,db.open('xb')as out:
                    count=0
                    while block:=src.read(1048576):
                        count+=len(block)
                        if count>MAX_SQLITE:raise ValueError('Q1_DELTA_BASE_SIZE')
                        out.write(block)
                if file_sha(db)!=base['sqlite_sha256']:raise ValueError('Q1_DELTA_BASE_SQLITE_HASH')
                for item in head['patches']:
                    path=source/item['path']
                    if path.stat().st_size>LIMIT or file_sha(path)!=item['sha256']:raise ValueError('Q1_DELTA_PATCH_HASH')
                    apply_delta(db,path.read_bytes())
                proof=head['target_proof']
                if file_sha(db)!=proof['sqlite_sha256']:raise ValueError('Q1_DELTA_HEAD_HASH')
                with db.open('rb')as src,(destination/'checkpoint.sqlite3.gz').open('xb')as dst:
                    with gzip.GzipFile(fileobj=dst,mode='wb',mtime=0)as out:shutil.copyfileobj(src,out)
                if file_sha(destination/'checkpoint.sqlite3.gz')!=proof['archive_sha256']:raise ValueError('Q1_DELTA_CANONICAL_ARCHIVE_HASH')
                (destination/'checkpoint.json').write_text(json.dumps(proof))
        with tempfile.TemporaryDirectory(prefix='q1-delta-proof-')as tmp:return restore(destination,Path(tmp)/'verified')
    except Exception:
        shutil.rmtree(destination) # Only the newly created incomplete restore.
        raise


def receive(git,commit,destination):
    """git callback returns bytes; fixed filenames only, no arbitrary Git paths."""
    destination=Path(destination)
    with tempfile.TemporaryDirectory(prefix='q1-remote-pages-')as tmp:
        root=Path(tmp)
        for name in ('checkpoint.json','checkpoint.sqlite3.gz'):(root/name).write_bytes(git('show',commit+':'+name))
        if HEAD in git('ls-tree','--name-only',commit).decode().splitlines():
            raw=git('show',commit+':'+HEAD);head=json.loads(raw);(root/HEAD).write_bytes(raw)
            for name in names(head):
                path=root/name;path.parent.mkdir(exist_ok=True);path.write_bytes(git('show',commit+':'+name))
        return materialize(root,destination)


def publish(repo,source,parent,env):
    from .quantitative_private import STATE_REF,restore
    from .cpu_operations import STATE_HISTORY_LIMIT
    repo,source=Path(repo),Path(source)
    def git(*args,input=None,extra=None):
        p=subprocess.run(['git','-C',str(repo),*args],input=input,capture_output=True,env={**env,**(extra or{})},timeout=25)
        if p.returncode:raise ValueError('Q1_DELTA_GIT_FAILED')
        return p.stdout
    current=git('ls-remote','origin',STATE_REF).decode().split()
    if not current or current[0]!=parent:raise ValueError('RESEARCH_STATE_PARENT_CHANGED_NO_OVERWRITE')
    git('fetch','--no-tags','origin','+refs/heads/*:refs/remotes/origin/*')
    if git('rev-parse','--is-shallow-repository').strip()!=b'false':raise ValueError('RESEARCH_STATE_HISTORY_INCOMPLETE')
    with tempfile.TemporaryDirectory(prefix='q1-page-write-')as tmp:
        temp=Path(tmp);prior=temp/'prior';receive(git,parent,prior)
        (temp/'old').mkdir()
        with gzip.open(prior/'checkpoint.sqlite3.gz','rb')as src,(temp/'old/v4.sqlite3').open('xb')as out:shutil.copyfileobj(src,out)
        restore(source,temp/'new')
        prior_proof=json.loads((prior/'checkpoint.json').read_text())
        target_proof=json.loads((source/'checkpoint.json').read_text())
        if prior_proof['sqlite_sha256']==target_proof['sqlite_sha256']:
            refs=git('for-each-ref','--format=%(objectname)','refs/remotes/origin').decode().splitlines()
            objects=git('rev-list','--objects',parent,*refs).decode().splitlines()
            sizes=git('cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)',input=('\n'.join(x.split()[0]for x in objects)+'\n').encode())
            history=sum(int(x.split()[2])for x in sizes.decode().splitlines())
            if history>STATE_HISTORY_LIMIT:raise ValueError('RESEARCH_STATE_CUMULATIVE_64MIB_LIMIT')
            return {'research_ref':STATE_REF,'parent':parent,'commit':parent,'archive_sha256':target_proof['archive_sha256'],
                    'operating_branches_written':False,'artifact_uploads':0,'history_unique_object_bytes':history,'history_limit_bytes':STATE_HISTORY_LIMIT,
                    'incremental':{'changed_pages':0,'delta_bytes':0,'unchanged':True},'unchanged_full_base_preserved':True}
        # Reuse the existing audited checkpoint's exact target proof.
        proof=json.loads((source/'checkpoint.json').read_text());blob,stats=make_delta(temp/'old/v4.sqlite3',temp/'new/v4.sqlite3')
        if HEAD in git('ls-tree','--name-only',parent).decode().splitlines():head=json.loads(git('show',parent+':'+HEAD))
        else:head={'format':FORMAT,'base_archive_sha256':json.loads((prior/'checkpoint.json').read_text())['archive_sha256'],'patches':[]}
        import hashlib
        digest=hashlib.sha256(blob).hexdigest();path='q1-deltas/'+digest+'.json.gz'
        head['patches'].append({'path':path,'sha256':digest});head['target_proof']=proof;names(head)
        patch=temp/'patch';patch.write_bytes(blob);manifest=temp/HEAD;manifest.write_text(json.dumps(head,sort_keys=True))
        index={'GIT_INDEX_FILE':str(temp/'index')};git('read-tree',parent,extra=index)
        for name,local in [(path,patch),(HEAD,manifest)]:
            oid=git('hash-object','-w',str(local)).decode().strip();git('update-index','--add','--cacheinfo',f'100644,{oid},{name}',extra=index)
        tree=git('write-tree',extra=index).decode().strip()
        commit=git('-c','user.name=BCT research','-c','user.email=bct-research@users.noreply.github.com','commit-tree',tree,'-p',parent,input=b'Append bounded Q1 SQLite page checkpoint\n').decode().strip()
        refs=git('for-each-ref','--format=%(objectname)','refs/remotes/origin').decode().splitlines()
        objects=git('rev-list','--objects',commit,*refs).decode().splitlines()
        sizes=git('cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)',input=('\n'.join(x.split()[0]for x in objects)+'\n').encode())
        history=sum(int(x.split()[2])for x in sizes.decode().splitlines())
        if history>STATE_HISTORY_LIMIT:raise ValueError('RESEARCH_STATE_CUMULATIVE_64MIB_LIMIT')
        # The prior chain was fully verified by receive. Verify this new page
        # transition exactly; replaying/auditing that prior chain again is redundant.
        apply_delta(temp/'old/v4.sqlite3',blob)
        if file_sha(temp/'old/v4.sqlite3')!=proof['sqlite_sha256']:raise ValueError('Q1_DELTA_CANDIDATE_HASH')
        git('push','origin',commit+':'+STATE_REF)
    return {'research_ref':STATE_REF,'parent':parent,'commit':commit,'archive_sha256':proof['archive_sha256'],
            'operating_branches_written':False,'artifact_uploads':0,'history_unique_object_bytes':history,
            'history_limit_bytes':STATE_HISTORY_LIMIT,'incremental':stats,'unchanged_full_base_preserved':True,
            'projection':{'available_bytes_after':STATE_HISTORY_LIMIT-history,'same_sized_additional_checkpoints_upper_bound':(STATE_HISTORY_LIMIT-history)//max(1,stats['delta_bytes']+len(json.dumps(head))+2048),'scope':'Observed patch size only, not a guarantee for future collection volume'}}
