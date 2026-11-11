import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

REPO = Path(__file__).resolve().parents[3]
RECEIPT = json.loads(Path(__file__).with_name('ACTIONS_RELEASE.json').read_text())['api_receipt']
VALIDATED = RECEIPT['gate_run']['head_sha']
MAIN = RECEIPT['cpu_run']['head_sha']

def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def tree(ref):
    return [{'path': line.split('\t', 1)[1], 'sha': line.split()[2],
             'type': line.split()[1]} for line in git('ls-tree', '-r', ref).decode().splitlines()]

remote_tree = tree(VALIDATED)
tree_sha = git('rev-parse', VALIDATED + '^{tree}').decode().strip()
resources = {
    '/actions/runs/' + str(RECEIPT['gate_run']['id']): RECEIPT['gate_run'],
    '/actions/runs/' + str(RECEIPT['gate_run']['id']) + '/jobs': RECEIPT['gate_jobs'],
    '/actions/artifacts/' + str(RECEIPT['gate_artifact']['id']): RECEIPT['gate_artifact'],
    '/git/commits/' + VALIDATED: {'tree': {'sha': tree_sha}},
    '/git/trees/' + tree_sha + '?recursive=1': {'tree': remote_tree, 'truncated': False},
}
def request(method, suffix):
    assert method == 'GET'
    return resources[suffix]

report = {'kind': 'isolated_actual_metadata_and_immutable_git_tree_replay',
          'network_requests_during_replay': 0, 'operating_writes': 0,
          'old_Gates_0_6_not_reexecuted_or_relabelled': True, 'replays': {}}
with tempfile.TemporaryDirectory(prefix='bct-release-replay-') as tmp:
    for label, ref in [('validated', VALIDATED), ('current_main', MAIN)]:
        root = Path(tmp) / label
        root.mkdir()
        with tarfile.open(fileobj=io.BytesIO(git('archive', ref))) as archive:
            archive.extractall(root, filter='data')
        guard = module('guard_' + label, root / '.github/scripts/bct_release_guard.py')
        release = json.loads((REPO / 'config/bct-operating-release.json').read_text())
        if label == 'validated':
            # The release guard/receipt were added after this immutable gate run.
            guard = module('guard_for_validated', REPO / '.github/scripts/bct_release_guard.py')
        try:
            result = guard.verify_release(request, release, root)
        except ValueError as exc:
            result = {'status': 'EXPECTED_REFUSAL', 'error': str(exc)}
        report['replays'][label] = {'ref': ref, 'result': result}
        if label == 'current_main':
            # Remove no files and change no hashes to make validation pass.
            old = {x['path']: x['sha'] for x in remote_tree if guard.code_path(x['path'])}
            current = {x['path']: x['sha'] for x in tree(ref) if guard.code_path(x['path'])}
            report['code_tree_diff'] = {'validated_files': len(old), 'main_files': len(current),
                'added': sorted(current.keys()-old.keys()), 'missing': sorted(old.keys()-current.keys()),
                'changed': [{'path': p, 'validated_blob': old[p], 'main_blob': current[p]}
                    for p in sorted(old.keys() & current.keys()) if old[p] != current[p]]}
            # Give the existing read-only helper access only to immutable local Git objects.
            (root / '.git').write_text('gitdir: ' + str(REPO / '.git') + '\n')
            helper = module('release_revalidate', REPO / 'tools/v4_release_revalidate.py')
            try:
                helper.verify(root)
            except ValueError as exc:
                report['current_main_existing_readonly_helper'] = {'status': 'EXPECTED_REFUSAL', 'error': str(exc)}
assert report['replays']['validated']['result']['status'] == 'PASS'
assert report['replays']['current_main']['result']['error'] == 'validated code/test file set changed or missing'
assert report['current_main_existing_readonly_helper']['error'] == 'REVALIDATION_SCOPE_CHANGED_NOT_THE_THREE_ADDITIONS'

print(json.dumps(report, indent=2))
