"""CAS-only Git persistence to the fixed review state ref; no DB/LIVE/main writes."""
import os
from pathlib import Path
import re
import subprocess

from bct.review_shadow import safe_root

REF='refs/heads/review-lead-shadow-state'


def command(*args, env=None, stdin=None):
    return subprocess.check_output(['git',*args],input=stdin,text=True,env=env).strip()


def persist(root,base):
    root=safe_root(root)
    if not (root/'shadow-activation.json').is_file():raise ValueError('SHADOW_NOT_INITIALIZED')
    if base and not re.fullmatch('[0-9a-f]{40}',base):raise ValueError('INVALID_REVIEW_BASE_SHA')
    current=command('ls-remote','origin',REF).split()
    if (current[0] if current else '')!=base:raise ValueError('REVIEW_BRANCH_CAS_CONFLICT')
    env={**os.environ,'GIT_INDEX_FILE':str(Path('var/review-state-git-index').resolve())}
    Path(env['GIT_INDEX_FILE']).unlink(missing_ok=True)
    if base:
        # The state branch must contain only this namespace. Never adopt another branch.
        prior=command('ls-tree','-r','--name-only',base).splitlines()
        if any(not p.startswith('review-lead-shadow/') for p in prior):raise ValueError('FOREIGN_REVIEW_BRANCH_TREE')
        for p in prior:
            if p.endswith('/summary.md'):continue  # derived view only
            local=root.parent/p
            if not local.is_file() or command('hash-object',str(local))!=command('rev-parse',base+':'+p):
                raise ValueError('PRIOR_REVIEW_RECORD_CHANGED')
        command('read-tree',base,env=env)
    else:command('read-tree','--empty',env=env)
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.name=='.review-lock':continue
        blob=command('hash-object','-w',str(p));target='review-lead-shadow/'+str(p.relative_to(root))
        command('update-index','--add','--cacheinfo','100644,'+blob+','+target,env=env)
    tree=command('write-tree',env=env)
    if base and tree==command('rev-parse',base+'^{tree}'):return base
    args=['-c','user.name=github-actions[bot]','-c','user.email=41898282+github-actions[bot]@users.noreply.github.com','commit-tree',tree]
    if base:args+=['-p',base]
    commit=command(*args,stdin='Append separate REVIEW_LEAD SHADOW records\n')
    # Non-forced push also refuses a race after the explicit base check.
    command('push','origin',commit+':'+REF)
    return commit

if __name__=='__main__':print(persist(Path('var/review-state/review-lead-shadow'),os.environ.get('BASE_REVIEW_SHA','')))
