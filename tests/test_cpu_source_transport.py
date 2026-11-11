"""CPU input transport preserves source bytes and the pinned queue's holds."""
import importlib.util
import hashlib
import gzip
import json
from pathlib import Path
import stat
import sqlite3
import zipfile

import pytest

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


def test_full_and_subset_cache_preserve_malformed_missing_and_ambiguous_holds(tmp_path):
    from bct.v4 import cpu_automation as queue
    from test_v4_cpu_automation import document
    module = helper(); cache = tmp_path / 'cache'; (cache / 'documents').mkdir(parents=True); (cache / 'raw').mkdir()
    doc, raw = document(); doc['raw_path'] = 'old-runner/' + doc['raw_sha256'] + '.html'
    (cache / 'documents/one.json').write_text(json.dumps(doc)); (cache / 'documents/duplicate.json').write_text(json.dumps(doc))
    (cache / 'documents/malformed.json').write_bytes(b'{bad metadata')
    (cache / 'raw' / Path(doc['raw_path']).name).write_bytes(raw)
    manifest = {'format': 'bct-new-rss-delta-v1', 'documents': [
        {'document_id': 'missing', 'url': 'https://official.example/missing'},
        {'document_id': doc['document_id'], 'url': doc['origin_url']}]}
    archive = tmp_path / 'cache.zip'; zipped(cache, archive); selected = tmp_path / 'selected'
    module.extract_sources(archive, selected)
    results = []
    for name, source in [('full', cache), ('bounded', selected)]:
        ledger = queue.open_queue(tmp_path / name)
        result = queue.ingest_delta(ledger, manifest, source, upstream_run_id='fixture')
        results.append([(r['status'], r.get('reason')) for r in result]); ledger.close()
    assert results[0] == results[1] == [('HELD_ISOLATED', 'UPSTREAM_BODY_NOT_AVAILABLE_NO_REFETCH'),
                                        ('HELD_ISOLATED', 'UPSTREAM_VERSION_AMBIGUOUS')]


@pytest.mark.parametrize('failed_first', [False, True])
def test_prior_partial_source_and_committed_window_survive_without_date_filter(tmp_path, failed_first):
    from bct.v4 import cpu_automation as queue, cpu_resume as resume
    from test_v4_cpu_resume import make_source, cache_source
    module = helper()
    if failed_first:
        from test_v4_cpu_automation import document, Extractor
        doc, raw = document('Atlas ordered Helios heat pumps.\nA second separate paragraph.')
        ledger = queue.open_queue(tmp_path / 'original'); queue.enqueue(ledger, doc, raw, {})
        queue.work(ledger, extractor=Extractor(fail=True), max_windows=1); ledger.close()
    else:
        doc, raw = make_source(tmp_path, partial=True)
    cache, policy = cache_source(tmp_path, doc, raw); archive = tmp_path / 'cache.zip'; zipped(cache, archive)
    selected = tmp_path / 'selected'; module.extract_sources(archive, selected)
    results = []
    for name, source in [('full', cache), ('bounded', selected)]:
        resume.export_state(tmp_path / 'original/v4.sqlite3', tmp_path / name)
        ledger = queue.open_queue(tmp_path / name)
        result = resume.hydrate(ledger, source, policy)
        results.append((result, queue.state(ledger)['pending_windows'],
                        len(queue.events(ledger, 'CPU_QUEUE_WINDOW_RESULT')))); ledger.close()
    assert results[0] == results[1]
    assert results[0][1:] == (1, 1)


def test_saved_original_raw_fixture_and_metadata_bytes_survive(tmp_path):
    """Reuse one existing frozen native fixture without fetching or CPU work."""
    module = helper(); frozen = ROOT / 'docs/v4/cpu-automation/ledger.sqlite3.gz'
    before = hashlib.sha256(frozen.read_bytes()).hexdigest()
    database = tmp_path / 'original.sqlite3'; database.write_bytes(gzip.decompress(frozen.read_bytes()))
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        payload, raw = db.execute('SELECT d.payload,b.data FROM documents d JOIN blobs b ON b.id=d.raw_id ORDER BY d.id LIMIT 1').fetchone()
    doc = json.loads(payload)
    assert hashlib.sha256(raw).hexdigest() == doc['raw_sha256']
    archive = tmp_path / 'saved.zip'
    with zipfile.ZipFile(archive, 'w') as saved:
        saved.writestr('documents/original.json', payload.encode())
        saved.writestr('raw/' + doc['raw_sha256'] + '.html', raw)
        saved.writestr('evaluations/unrelated.json', b'not CPU input')
    selected = tmp_path / 'selected'; module.extract_sources(archive, selected)
    assert (selected / 'documents/original.json').read_bytes() == payload.encode()
    assert (selected / 'raw' / (doc['raw_sha256'] + '.html')).read_bytes() == raw
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == before
