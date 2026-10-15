"""Read-only release evidence. Never writes operating refs or installs models.

The old full Gates0-6 receipt is NOT replaced by this check. Activating a new
operating release remains a distinct approval/application boundary.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import yaml
from bct.objective_lock import stamp_export


def manifest(root):
    root=Path(root).resolve()
    spec=importlib.util.spec_from_file_location('guard',root/'.github/scripts/bct_release_guard.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    paths={p.relative_to(root).as_posix():hashlib.sha1(b'blob '+str(len(p.read_bytes())).encode()+b'\0'+p.read_bytes()).hexdigest()
           for prefix in ['src','tests','.github/scripts','.github/workflows','config','docs']for p in (root/prefix).rglob('*')
           if p.is_file()and'__pycache__'not in p.parts and module.code_path(p.relative_to(root).as_posix())}
    return paths


def verify(root):
    root=Path(root).resolve();release=json.loads((root/'config/bct-operating-release.json').read_text())
    old=subprocess.check_output(['git','-C',str(root),'ls-tree','-r','--name-only',release['validated_code_sha']],text=True).splitlines()
    current=manifest(root)
    # Same path policy as the actual guard, including newly added workflows.
    spec=importlib.util.spec_from_file_location('guard',root/'.github/scripts/bct_release_guard.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    prior={n:subprocess.check_output(['git','-C',str(root),'rev-parse',release['validated_code_sha']+':'+n],text=True).strip()
           for n in old if module.code_path(n)}
    added=sorted(current.keys()-prior.keys());missing=sorted(prior.keys()-current.keys())
    changed=sorted(k for k in current.keys()&prior.keys()if current[k]!=prior[k])
    expected={'.github/workflows/v4-cpu-main-cache-seed.yml','.github/workflows/v4-cpu-private-research.yml','.github/workflows/v4-cpu-private-settings-check.yml'}
    if set(added)!=expected or missing or changed:raise ValueError('REVALIDATION_SCOPE_CHANGED_NOT_THE_THREE_ADDITIONS')
    checks={}
    for name in added:
        w=yaml.safe_load((root/name).read_text())
        if w['permissions'].get('contents')!='read':raise ValueError('PUBLIC_CONTENTS_WRITE_FORBIDDEN')
        if 'schedule'in w.get('on',w.get(True,{})):raise ValueError('ADDED_RESEARCH_SCHEDULE_FORBIDDEN')
        checks[name]={'blob':current[name],'permissions':w['permissions'],'new_schedule':False}
    sha=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    return stamp_export({'format':'bct-readonly-release-revalidation-1','checked_main_SHA':sha,'old_validated_SHA':release['validated_code_sha'],
                         'unchanged_previously_validated_files':len(prior),'added_workflows':checks,'complete_code_file_manifest':current,
                         'new_operating_release_applied':False,'old_Gates0_6_not_replaced':True,'operating_writes':0,'model_downloads':0,
                         'requires':'Successful pytest/JS and fixed230 offline QA steps of this SAME checkout, plus separate approved release application'})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    result=verify(args.root);Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items()if k!='complete_code_file_manifest'}))
