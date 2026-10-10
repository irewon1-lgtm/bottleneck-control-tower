"""Permit resumed main candidates only after actual Gates 0–6 for this code."""
import hashlib
import json
import os
from pathlib import Path

from bct.future_github import GitHubTransport

REQUIRED = (
    'Gate 0 then real GitHub storage Gate 1',
    'Gate 2 original source access on GitHub runner',
    'Gate 3 full failed-source inventory',
    'Gate 4 official original verification and evidence holds',
    'Stage 5 cost-zero real-source reading pilot',
    'Gate 5 actual readings and atomic production queue recovery',
    'Restore original 230-source regression corpus',
    'Gate 6 real source E2E and required whole regressions',
)


def code_path(name):
    path = Path(name)
    if name == 'config/bct-operating-release.json':
        return False  # The actual release receipt is created after verification.
    return (name.startswith('src/') and path.suffix == '.py'
        or name.startswith('tests/')
        or name.startswith('.github/scripts/') and path.suffix in ('.py', '.cjs')
        or name.startswith('.github/workflows/') and path.suffix in ('.yml', '.yaml')
        or name.startswith('config/') and path.suffix == '.json'
        or name.startswith('docs/') and path.suffix in ('.js', '.html', '.css'))


def verify_release(request, release, local_root):
    run = request('GET', '/actions/runs/'+str(release['gate_run_id']))
    if (run['status'] != 'completed' or run['conclusion'] != 'success'
            or run['head_sha'] != release['validated_code_sha']
            or run['path'] != '.github/workflows/bct-recovery.yml'):
        raise ValueError('actual completed recovery for the released code required')
    jobs = request('GET', '/actions/runs/'+str(run['id'])+'/jobs')['jobs']
    selected = [job for job in jobs if job['name'] == 'storage']
    if len(selected) != 1:
        raise ValueError('operating recovery job unavailable')
    steps = {step['name']: step for step in selected[0]['steps']}
    if any(steps.get(name, {}).get('conclusion') != 'success' for name in REQUIRED):
        raise ValueError('Gates 0–6 include a failed, skipped, or missing actual execution')
    artifact = request('GET', '/actions/artifacts/'+str(release['artifact_id']))
    if (artifact.get('expired') or artifact.get('digest') != 'sha256:'+release['artifact_sha256']
            or artifact['workflow_run']['id'] != run['id']):
        raise ValueError('released verification artifact binding differs')
    commit = request('GET', '/git/commits/'+run['head_sha'])
    tree = request('GET', '/git/trees/'+commit['tree']['sha']+'?recursive=1')
    if tree.get('truncated'):
        raise ValueError('complete validated code tree required')
    remote = {entry['path']: entry['sha'] for entry in tree['tree'] if entry['type'] == 'blob'}
    paths = sorted(path for prefix in ('src', 'tests', '.github/scripts',
        '.github/workflows', 'config', 'docs') for path in Path(local_root, prefix).rglob('*')
        if path.is_file() and code_path(path.relative_to(local_root).as_posix())
        and '__pycache__' not in path.parts and path.suffix != '.pyc')
    expected_paths = {name for name in remote if code_path(name)
                      and '__pycache__' not in Path(name).parts and Path(name).suffix != '.pyc'}
    if not paths or {path.relative_to(local_root).as_posix() for path in paths} != expected_paths:
        raise ValueError('validated code/test file set changed or missing')
    for path in paths:
        raw = path.read_bytes()
        sha = hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
        if remote.get(path.relative_to(local_root).as_posix()) != sha:
            raise ValueError('main operating code differs from actually validated code')
    return {'status': 'PASS', 'gate_run_id': run['id'], 'verified_code_files': len(paths),
            'validated_code_sha': run['head_sha'], 'artifact_id': artifact['id']}


def main():
    if os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('operating release guard requires main')
    release = json.loads(Path('config/bct-operating-release.json').read_text())
    transport = GitHubTransport(os.environ['GITHUB_REPOSITORY'],
        'future-bottleneck-data', os.environ['GITHUB_TOKEN'])
    print(json.dumps(verify_release(transport.requester, release, Path('.'))))


if __name__ == '__main__':
    main()
