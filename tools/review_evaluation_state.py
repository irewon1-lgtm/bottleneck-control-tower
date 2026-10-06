"""Only the dedicated evaluation ref is writable. Operational stores are never restored here."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_evaluation_a as observer

REF=observer.STATE_REF


def git(*args,env=None,stdin=None):
    return subprocess.check_output(['git',*args],input=stdin,text=True,env=env).strip()


def valid_path(path):
    if path in ('evaluation-a/epoch.json','evaluation-a/latest.json'):return True
    return bool(re.fullmatch(r'evaluation-a/reports/[A-Za-z0-9_-]+\.json',path))


def entries(base):
    result=[]
    for line in git('ls-tree','-r',base).splitlines():
        head,path=line.split('\t',1)
        if head.split()[:2]!=['100644','blob'] or not valid_path(path):raise ValueError('FOREIGN_EVALUATION_TREE')
        result.append(path)
    return result


def restore(root):
    root=observer.guard_output(root);root.mkdir(parents=True,exist_ok=True)
    remote=git('ls-remote','origin',REF).split()
    if not remote:return ''
    base=remote[0];git('fetch','--no-tags','origin',REF)
    for path in entries(base):
        dest=root.parent/path
        if dest.is_symlink() or any(p.is_symlink() for p in dest.parents):raise ValueError('STATE_SYMLINK')
        raw=subprocess.check_output(['git','show',base+':'+path])
        if dest.exists() and dest.read_bytes()!=raw:raise ValueError('RESTORE_WOULD_OVERWRITE')
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            with dest.open('xb') as f:f.write(raw)
    return base


def prior(root):
    root=observer.guard_output(root);path=root/'latest.json'
    if not path.exists():raise ValueError('NO_PERSISTED_OBSERVER_CHECKPOINT')
    pointer=json.loads(path.read_text());name=pointer['report_path']
    if not valid_path('evaluation-a/'+name):raise ValueError('INVALID_PRIOR_REPORT_PATH')
    source=root/name
    if source.is_symlink() or observer.sha(source.read_bytes())!=pointer['report_sha256']:
        raise ValueError('PRIOR_REPORT_INTEGRITY')
    return source


def checkpoint(root,report):
    root=observer.guard_output(root);report=Path(report)
    if report.parent!=root/'reports' or not valid_path('evaluation-a/reports/'+report.name):
        raise ValueError('EVALUATION_REPORT_ONLY')
    value=json.loads(report.read_text())
    value={'report_path':'reports/'+report.name,'report_sha256':observer.sha(report.read_bytes()),
        'observed_at':value['observed_at'],'observer_run_id':value['observer_run_id']}
    (root/'latest.json').write_text(json.dumps(value,indent=2))


def persist(root,base):
    root=observer.guard_output(root);observer.validate_state_ref(REF)
    if not (root/'epoch.json').is_file():raise ValueError('APPROVED_EPOCH_REQUIRED')
    observer.validate_epoch(json.loads((root/'epoch.json').read_text()))
    if base and not re.fullmatch('[a-f0-9]{40}',base):raise ValueError('INVALID_BASE')
    current=git('ls-remote','origin',REF).split()
    if (current[0] if current else '')!=base:raise ValueError('EVALUATION_CAS_CONFLICT')
    prior(root)  # verify derived pointer before persisting
    if base:
        for path in entries(base):
            if path=='evaluation-a/latest.json':continue
            local=root.parent/path
            if not local.is_file() or git('hash-object',str(local))!=git('rev-parse',base+':'+path):
                raise ValueError('IMMUTABLE_EVALUATION_RECORD_CHANGED')
    with tempfile.TemporaryDirectory(prefix='bct-eval-index-') as tmp:
        env={**os.environ,'GIT_INDEX_FILE':str(Path(tmp)/'index')}
        git('read-tree',base if base else '--empty',env=env)
        for path in sorted(root.rglob('*')):
            if path.is_symlink():raise ValueError('STATE_SYMLINK')
            if not path.is_file():continue
            name='evaluation-a/'+str(path.relative_to(root))
            if not valid_path(name):raise ValueError('UNEXPECTED_LOCAL_EVALUATION_FILE')
            blob=git('hash-object','-w',str(path))
            git('update-index','--add','--cacheinfo','100644,'+blob+','+name,env=env)
        tree=git('write-tree',env=env)
    if base and tree==git('rev-parse',base+'^{tree}'):return base
    args=['-c','user.name=github-actions[bot]','-c','user.email=41898282+github-actions[bot]@users.noreply.github.com','commit-tree',tree]
    if base:args+=['-p',base]
    commit=git(*args,stdin='Append approved read-only evaluation observations\n')
    git('push','origin',commit+':'+REF)
    return commit


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['restore','prior','checkpoint','persist'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--base',default='');p.add_argument('--report',type=Path)
    a=p.parse_args()
    if a.action=='restore':print(restore(a.root))
    elif a.action=='prior':print(prior(a.root))
    elif a.action=='checkpoint':checkpoint(a.root,a.report)
    else:print(persist(a.root,a.base))

if __name__=='__main__':main()
