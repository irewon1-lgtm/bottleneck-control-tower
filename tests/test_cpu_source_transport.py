"""CPU input transport preserves source bytes and the pinned queue's holds."""
import importlib.util
import re
from pathlib import Path
import stat
import zipfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def helper():
    spec = importlib.util.spec_from_file_location('cpu_source_transport', ROOT / '.github/scripts/receive_cpu_sources.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def zipped(cache, archive):
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as saved:
        for path in cache.rglob('*'):
            if path.is_file(): saved.write(path, path.relative_to(cache))
        saved.writestr('evaluations/giant.json', b'x' * 100_000)


def test_all_old_and_new_source_bytes_survive_without_unrelated_expansion(tmp_path):
    module = helper(); archive = tmp_path / 'cache.zip'
    members = {'documents/old.json': b'{"acquired_at":"2000-01-01","body":"old"}',
               'documents/malformed.json': b'{bad metadata', 'captures/failed.json': b'{"status":"FAILED"}',
               'raw/older.json': b'original metadata', 'raw/current.html': b'<p>original</p>'}
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as saved:
        for name, value in members.items(): saved.writestr(name, value)
        saved.writestr('evaluations/huge.json', b'x' * 100_000)
    before = archive.read_bytes(); destination = tmp_path / 'selected'
    proof = module.extract_sources(archive, destination, max_expanded=4096)
    assert {str(p.relative_to(destination)): p.read_bytes() for p in destination.rglob('*') if p.is_file()} == members
    assert proof['expanded_bytes'] == sum(map(len, members.values()))
    assert not (destination / 'evaluations').exists() and archive.read_bytes() == before


@pytest.mark.parametrize('bad', ['documents/../escape.json', 'raw/one/two.html', 'captures\\escape.json'])
def test_source_path_escape_is_rejected_before_destination_exists(tmp_path, bad):
    module = helper(); archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as saved: saved.writestr(bad, b'bad')
    with pytest.raises(ValueError, match='UNSAFE_SOURCE_PATH'):
        module.extract_sources(archive, tmp_path / 'selected')
    assert not (tmp_path / 'selected').exists()


@pytest.mark.parametrize('kind', ['duplicate', 'symlink'])
def test_duplicate_and_symlink_sources_fail_closed(tmp_path, kind):
    module = helper(); archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as saved:
        if kind == 'duplicate':
            saved.writestr('documents/one.json', b'{}')
            with pytest.warns(UserWarning): saved.writestr('documents/one.json', b'{"changed":true}')
        else:
            info = zipfile.ZipInfo('raw/linked.html'); info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16; saved.writestr(info, b'/private/path')
    with pytest.raises(ValueError): module.extract_sources(archive, tmp_path / 'selected')
    assert not (tmp_path / 'selected').exists()


def test_expansion_and_disk_budget_do_not_mutate_existing_inputs(tmp_path, monkeypatch):
    module = helper(); archive = tmp_path / 'cache.zip'
    with zipfile.ZipFile(archive, 'w') as saved: saved.writestr('raw/one.html', b'original')
    before = archive.read_bytes()
    with pytest.raises(ValueError, match='EXPANDED_LIMIT'):
        module.extract_sources(archive, tmp_path / 'selected', max_expanded=1)
    monkeypatch.setattr(module.shutil, 'disk_usage', lambda p: (100, 100, 0))
    with pytest.raises(ValueError, match='INSUFFICIENT_DISK'):
        module.extract_sources(archive, tmp_path / 'selected')
    assert not (tmp_path / 'selected').exists() and archive.read_bytes() == before


def test_artifact_identity_is_bound_to_successful_acquisition_run_and_digest():
    module = helper(); sha = 'a' * 40
    run = {'id': 123, 'path': '.github/workflows/precursor-acquisition.yml', 'head_sha': sha,
           'head_branch': 'main', 'event': 'workflow_run', 'conclusion': 'success',
           'head_repository': {'full_name': module.REPOSITORY}}
    artifact = {'id': 456, 'name': 'precursor-private-cache', 'expired': False,
                'size_in_bytes': 100, 'digest': 'sha256:' + 'b' * 64}
    assert module.validate_inputs(run, {'artifacts': [artifact]}, 123, sha)['id'] == 456
    for field, value in [('id', 124), ('head_sha', 'c' * 40), ('conclusion', 'failure'),
                         ('head_repository', {'full_name': 'other/repo'})]:
        with pytest.raises(ValueError, match='ACQUISITION_BINDING'):
            module.validate_inputs({**run, field: value}, {'artifacts': [artifact]}, 123, sha)
    with pytest.raises(ValueError, match='ARTIFACT_BINDING'):
        module.validate_inputs(run, {'artifacts': [{**artifact, 'expired': True}]}, 123, sha)


def test_download_refuses_existing_path_without_deleting_it(tmp_path):
    module = helper(); path = tmp_path / 'preserved.zip'; path.write_bytes(b'existing archive')
    with pytest.raises(ValueError, match='DESTINATION_EXISTS'):
        module.download({'id': 1, 'size_in_bytes': 100, 'digest': 'sha256:' + 'a' * 64}, path)
    assert path.read_bytes() == b'existing archive'


@pytest.mark.parametrize('other_creator', ['race', 'dangling_symlink'])
def test_download_cleanup_never_removes_a_path_this_call_did_not_create(tmp_path, monkeypatch, other_creator):
    module = helper(); path = tmp_path / 'preserved.zip'
    if other_creator == 'race':
        def disk_hook(_):
            path.write_bytes(b'other creator archive')
            return 20 * 1024**3
        monkeypatch.setattr(module, 'free_disk', disk_hook)
    else:
        path.symlink_to(tmp_path / 'not-created-target')
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **kw: pytest.fail('must not start download'))
    with pytest.raises((ValueError, FileExistsError)):
        module.download({'id': 1, 'size_in_bytes': 100, 'digest': 'sha256:' + 'a' * 64}, path)
    if other_creator == 'race': assert path.read_bytes() == b'other creator archive'
    else: assert path.is_symlink()


def test_workflow_uses_reviewed_execution_pin_for_small_input_helper_and_cpu():
    workflow = yaml.load((ROOT / '.github/workflows/v4-cpu-private-research.yml').read_text(), Loader=yaml.BaseLoader)
    assert re.fullmatch('[0-9a-f]{40}',workflow['env']['CPU_CODE_SHA'])
    assert workflow['env']['CPU_CODE_SHA']==workflow['env']['EXPECTED_CPU_CODE_SHA']
    steps = workflow['jobs']['research']['steps']
    checkout = next(s for s in steps if s.get('uses') == 'actions/checkout@v4')
    assert checkout['with']['ref'] == '${{ env.CPU_CODE_SHA }}'
    assert checkout['with']['persist-credentials'] == 'false'
    verify = next(s for s in steps if s.get('name', '').startswith('Verify actual upstream identity'))
    receive = next(s for s in steps if 'receive_cpu_delta.py' in s.get('run', ''))
    assert steps.index(verify) < steps.index(receive)
    assert 'verified_schedule' in verify['run'] and 'gh run download' not in verify['run']
    assert 'timeout 300 python .github/scripts/receive_cpu_delta.py' in receive['run']
    assert '--expected-head "$ACQUISITION_HEAD"' in receive['run']
    assert 'gh run download "$ACQUISITION_RUN"' not in receive['run']
    process = next(s for s in steps if s.get('name', '').startswith('Consume approved'))
    assert 'timeout 120 .v4-cpu-env/bin/python tools/v4_cpu_private.py process --checkpoint var/v4/cpu-private/prior' in process['run']
    assert '--input-receipt var/v4/cpu-private/input-receipt.json' in process['run']
    assert '--manual-acquisition-run "$ACQUISITION_RUN"' in process['run']
