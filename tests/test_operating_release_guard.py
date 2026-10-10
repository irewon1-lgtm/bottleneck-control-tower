from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('operating_guard',
    Path(__file__).parents[1]/'.github/scripts/bct_release_guard.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def resources(tmp_path):
    (tmp_path/'src').mkdir()
    raw = b'preserved_engine = 1\n'
    (tmp_path/'src/engine.py').write_bytes(raw)
    sha = hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
    release = {'gate_run_id': 10, 'validated_code_sha': 'code', 'artifact_id': 20,
               'artifact_sha256': 'a'*64}
    documents = {
        '/actions/runs/10': {'id': 10, 'head_sha': 'code', 'status': 'completed',
            'conclusion': 'success', 'path': '.github/workflows/bct-recovery.yml'},
        '/actions/runs/10/jobs': {'jobs': [{'name': 'storage', 'steps': [
            {'name': name, 'conclusion': 'success'} for name in module.REQUIRED]}]},
        '/actions/artifacts/20': {'id': 20, 'expired': False, 'digest': 'sha256:'+'a'*64,
            'workflow_run': {'id': 10}},
        '/git/commits/code': {'tree': {'sha':'tree'}},
        '/git/trees/tree?recursive=1': {'tree': [{'type': 'blob', 'path':'src/engine.py', 'sha':sha}]},
    }
    return release, documents


def test_main_automatic_release_requires_matching_actual_gates_and_preserved_code(tmp_path):
    release, docs = resources(tmp_path)
    request = lambda method, suffix: deepcopy(docs[suffix])
    assert module.verify_release(request, release, tmp_path)['verified_code_files'] == 1
    (tmp_path/'src/engine.py').write_bytes(b'arbitrary behavior change\n')
    with pytest.raises(ValueError, match='code differs'):
        module.verify_release(request, release, tmp_path)


@pytest.mark.parametrize('broken', ['skip', 'artifact', 'revision', 'delete_test'])
def test_skip_wrong_artifact_wrong_revision_or_deleted_test_cannot_enable_auto_release(tmp_path, broken):
    release, docs = resources(tmp_path)
    if broken == 'skip':
        docs['/actions/runs/10/jobs']['jobs'][0]['steps'][-1]['conclusion'] = 'skipped'
    elif broken == 'artifact':
        docs['/actions/artifacts/20']['workflow_run']['id'] = 9
    elif broken == 'revision':
        docs['/actions/runs/10']['head_sha'] = 'older-code'
    else:
        docs['/git/trees/tree?recursive=1']['tree'].append(
            {'type':'blob', 'path':'tests/test_existing.py', 'sha':'missing-test'})
    with pytest.raises(ValueError):
        module.verify_release(lambda method, suffix:deepcopy(docs[suffix]), release, tmp_path)
