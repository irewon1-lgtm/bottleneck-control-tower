"""Pages accepts a typed public generation only from the successful writer."""
import importlib.util
import io
import json
from pathlib import Path
import zipfile

import pytest

from bct.objective_lock import stamp_export
from bct.v4.public_research import encoded
from test_v4_public_research import project

ROOT = Path(__file__).resolve().parents[1]


def module():
    spec = importlib.util.spec_from_file_location('pages_input', ROOT / 'tools/v4_pages_research_input.py')
    tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)
    return tool


def archive(public, *, extra=False, transport=None):
    import hashlib
    raw = encoded(public) + b'\n'
    manifest = stamp_export({'format': 'bct-public-research-artifact-1',
        'file_sha256': hashlib.sha256(raw).hexdigest(), 'snapshot_sha256': public['snapshot_sha256'],
        'generation': public['generation'],
        **(transport or {'transport_run_id': 103, 'transport_attempt': 1, 'transport_workflow_sha': 'e' * 40})})
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w') as zipped:
        zipped.writestr('snapshot.json', raw)
        zipped.writestr('manifest.json', encoded(manifest))
        if extra:
            zipped.writestr('private.sqlite3', b'private database must never be accepted')
    return result.getvalue()


def producer():
    return {'id': 103, 'run_attempt': 1, 'status': 'completed', 'head_sha': 'e' * 40,
            'head_branch': 'main', 'event': 'workflow_run', 'conclusion': 'success',
            'path': '.github/workflows/v4-cpu-private-research.yml',
            'head_repository': {'full_name': 'irewon1-lgtm/bottleneck-control-tower'}}


def test_pages_accepts_only_ack_bound_public_files_and_successful_publisher(tmp_path):
    tool = module(); public = project(tmp_path)
    accepted = tool.validate_cpu_artifact(producer(), [{'name': 'publish', 'conclusion': 'success'}], archive(public))
    assert accepted == public
    with pytest.raises(ValueError, match='PUBLISHER'):
        tool.validate_cpu_artifact(producer(), [{'name': 'publish', 'conclusion': 'skipped'}], archive(public))
    with pytest.raises(ValueError, match='FILES'):
        tool.validate_cpu_artifact(producer(), [{'name': 'publish', 'conclusion': 'success'}], archive(public, extra=True))


def test_run_head_attempt_and_snapshot_generation_must_agree(tmp_path):
    tool = module(); public = project(tmp_path)
    run = producer(); run['head_sha'] = '0' * 40
    with pytest.raises(ValueError, match='PRODUCER'):
        tool.validate_cpu_artifact(run, [{'name': 'publish', 'conclusion': 'success'}], archive(public))
    run = producer(); run['run_attempt'] = 2
    with pytest.raises(ValueError, match='PRODUCER'):
        tool.validate_cpu_artifact(run, [{'name': 'publish', 'conclusion': 'success'}], archive(public))


def test_old_pages_job_cannot_replace_a_newer_published_generation(tmp_path):
    tool = module(); generation = project(tmp_path)['generation']
    newer = {**generation, 'ack_sequence': generation['ack_sequence'] + 2}
    with pytest.raises(ValueError, match='STALE'):
        tool.require_not_older(generation, newer)
    # A code-only update can reuse the exact same acknowledged generation.
    tool.require_not_older(generation, generation)
    equivocation = {**generation, 'sqlite_sha256': '0' * 64}
    with pytest.raises(ValueError, match='GENERATION'):
        tool.require_not_older(equivocation, generation)
    # A retry of an older workflow can legitimately write a newer private ACK.
    retry = {**generation, 'producer_run_id': generation['producer_run_id'] - 1,
             'ack_sequence': generation['ack_sequence'] + 2, 'private_commit': '0' * 40}
    tool.require_not_older(retry, generation)


def test_recovery_transport_does_not_change_original_generation(tmp_path):
    tool = module(); public = project(tmp_path); run = producer()
    run.update(id=999, run_attempt=2, head_sha='a' * 40)
    transport = {'transport_run_id': 999, 'transport_attempt': 2, 'transport_workflow_sha': 'a' * 40}
    assert tool.validate_cpu_artifact(run, [{'name': 'publish', 'conclusion': 'success'}],
                                      archive(public, transport=transport)) == public
    assert public['generation']['producer_run_id'] == 103


def test_optional_health_failure_is_unknown_not_zero_or_research_failure(monkeypatch):
    tool = module()
    monkeypatch.setattr(tool, 'public_health', lambda: (_ for _ in ()).throw(ValueError('403')))
    assert tool.optional_public_health()['workflows'] == dict.fromkeys(('rss', 'acquisition', 'cpu', 'review'))


def test_code_only_prepare_reads_durable_generation_after_artifact_expiry(tmp_path, monkeypatch):
    tool = module(); public = project(tmp_path / 'fixture')
    monkeypatch.setattr(tool, 'git_client', lambda: None)
    monkeypatch.setattr(tool, 'read_current', lambda git: {'research': public, 'acquisition': None})
    monkeypatch.setattr(tool, 'published_manifest', lambda: {'research_generation': public['generation']})
    monkeypatch.setattr(tool, 'api', lambda path: (_ for _ in ()).throw(ValueError('403')))
    destination = tmp_path / 'input'
    assert tool.prepare(destination)['research_generation'] == public['generation']
    assert json.loads((destination / 'research.json').read_text()) == public
    assert json.loads((destination / 'workflow.json').read_text())['workflows']['cpu'] is None


def test_deployment_rechecks_durable_generation_not_workflow_run_creation_order(tmp_path, monkeypatch):
    tool = module(); public = project(tmp_path / 'fixture')
    monkeypatch.setattr(tool, 'git_client', lambda: None)
    monkeypatch.setattr(tool, 'read_current', lambda git: {'research': public, 'acquisition': None})
    monkeypatch.setattr(tool, 'published_manifest', lambda: {})
    old = {**public['generation'], 'ack_sequence': 2}
    with pytest.raises(ValueError, match='STALE'):
        tool.guard({'research_generation': old})
    assert tool.guard({'research_generation': public['generation']})['status'].startswith('PASS')


def test_current_attempt_never_accepts_previous_attempt_artifact(monkeypatch):
    tool = module(); run = producer(); run['run_attempt'] = 2
    monkeypatch.setattr(tool, 'api', lambda path: {'artifacts': [
        {'name': 'bct-public-research-1', 'expired': False}]})
    assert tool.artifact_for(run, 'bct-public-research') is None


def test_code_only_sync_has_no_artifact_or_actions_api_prerequisite(tmp_path, monkeypatch):
    tool = module(); public = project(tmp_path / 'fixture')
    monkeypatch.setattr(tool, 'git_client', lambda: None)
    monkeypatch.setattr(tool, 'read_current', lambda git: {'research': public, 'acquisition': None})
    monkeypatch.setattr(tool, 'api', lambda path: (_ for _ in ()).throw(AssertionError('old artifact API must not run')))
    monkeypatch.setattr(tool, 'persist', lambda git, **kw: {'research_generation': public['generation'], **kw})
    result = tool.sync()
    assert result['research'] is None and result['research_generation'] == public['generation']


def test_failed_or_diagnostic_trigger_cannot_clear_durable_research(tmp_path, monkeypatch):
    tool = module(); public = project(tmp_path / 'fixture')
    monkeypatch.setattr(tool, 'git_client', lambda: None)
    monkeypatch.setattr(tool, 'read_current', lambda git: {'research': public, 'acquisition': None})
    run = producer(); run['conclusion'] = 'failure'
    monkeypatch.setattr(tool, 'api', lambda path: {'artifacts': []} if path.startswith('actions/artifacts?') else run)
    monkeypatch.setattr(tool, 'persist', lambda git, **kw: kw)
    result = tool.sync(103)
    assert result['research'] is None and result['acquisition'] is None


def test_direct_old_run_retry_can_advance_private_generation(tmp_path, monkeypatch):
    tool = module(); public = project(tmp_path / 'fixture')
    run = producer(); run.update(id=10, run_attempt=2)
    transport = {'transport_run_id': 10, 'transport_attempt': 2, 'transport_workflow_sha': 'e' * 40}
    monkeypatch.setattr(tool, 'git_client', lambda: None)
    monkeypatch.setattr(tool, 'read_current', lambda git: {'research': None, 'acquisition': None})
    def metadata(path):
        if path == 'actions/runs/10': return run
        if path.startswith('actions/artifacts?'): return {'artifacts': []}
        if '/artifacts?' in path: return {'artifacts': [{'name': 'bct-public-research-2', 'expired': False}]}
        assert '/attempts/2/jobs?' in path
        return {'jobs': [{'name': 'publish', 'conclusion': 'success'}]}
    monkeypatch.setattr(tool, 'api', metadata)
    monkeypatch.setattr(tool, 'artifact_bytes', lambda artifact: archive(public, transport=transport))
    monkeypatch.setattr(tool, 'persist', lambda git, **kw: kw)
    assert tool.sync(10)['research'] == public


def test_later_rss_catches_skipped_cpu_event_and_old_run_retry_by_artifact_creation(tmp_path, monkeypatch):
    from bct.v4.public_data import persist, read_current
    from test_v4_public_data import repository, version
    tool = module(); _, _, git = repository(tmp_path)
    public = project(tmp_path / 'fixture'); old = version(public, 2, 'a')
    persist(git, research=old)
    newer = version(public, 6, 'c', run_id=99)
    cpu = producer(); cpu.update(id=10, run_attempt=2)
    rss = {'id': 201, 'status': 'completed', 'path': '.github/workflows/rss-live-check.yml'}
    artifact = {'id': 900, 'created_at': '2026-11-11T12:00:00Z', 'name': 'bct-public-research-2',
                'expired': False, 'workflow_run': {'id': 10}}
    transport = {'transport_run_id': 10, 'transport_attempt': 2, 'transport_workflow_sha': 'e' * 40}
    monkeypatch.setattr(tool, 'git_client', lambda: git)
    def metadata(path):
        if path == 'actions/runs/201': return rss
        if path == 'actions/runs/10': return cpu
        if path.startswith('actions/artifacts?'): return {'artifacts': [artifact]}
        assert '/attempts/2/jobs?' in path
        return {'jobs': [{'name': 'publish', 'conclusion': 'success'}]}
    monkeypatch.setattr(tool, 'api', metadata)
    monkeypatch.setattr(tool, 'artifact_bytes', lambda a: archive(newer, transport=transport))
    result = tool.sync(201)
    assert result['research_generation']['ack_sequence'] == 6
    assert read_current(git)['cursor']['artifact_id'] == 900
    assert read_current(git)['research']['generation']['producer_run_id'] == 99


def test_nonterminal_artifact_cannot_be_lost_behind_cursor(tmp_path, monkeypatch):
    tool = module(); public = project(tmp_path / 'fixture'); run = producer()
    run.update(status='in_progress', conclusion=None)
    artifact = {'id': 900, 'created_at': '2026-11-11T12:00:00Z', 'name': 'bct-public-research-1',
                'expired': False, 'workflow_run': {'id': 103}}
    def metadata(path):
        if path.startswith('actions/artifacts?'): return {'artifacts': [artifact]}
        if path == 'actions/runs/103': return run
        return {'jobs': [{'name': 'publish', 'conclusion': 'success'}]}
    monkeypatch.setattr(tool, 'api', metadata)
    monkeypatch.setattr(tool, 'artifact_bytes', lambda a: archive(public))
    r, c, cursor, reason = tool.catch_up(None)
    assert r is None and cursor['artifact_id'] is None and reason == 'PRODUCER_IN_PROGRESS'
    # Completion notification is dropped. A later RSS-triggered scan still
    # starts before the unfinished artifact and can publish it once confirmed.
    run.update(status='completed', conclusion='success')
    r, c, cursor, reason = tool.catch_up(cursor)
    assert r == public and cursor['artifact_id'] == 900 and reason == 'NONE'


def test_bounded_backlog_preserves_verified_current_receipt_and_holds_cursor(tmp_path, monkeypatch):
    tool = module(); public = project(tmp_path / 'fixture')
    def metadata(path):
        page = int(path.rsplit('=', 1)[1])
        return {'artifacts': [{'id': 1001-(page-1)*100-index, 'created_at': '2026-11-11T12:00:00Z',
                               'name': 'unrelated', 'expired': False} for index in range(100)]}
    monkeypatch.setattr(tool, 'api', metadata)
    r, c, cursor, reason = tool.catch_up(None, public)
    assert r == public and cursor['artifact_id'] is None and reason == 'SCAN_BOUND'


@pytest.mark.parametrize('failure,reason', [(OSError('historical artifact 410'), 'TRANSPORT_UNAVAILABLE'),
                                          (ValueError('PAGES_PUBLIC_METADATA_UNAVAILABLE'), 'TRANSPORT_UNAVAILABLE'),
                                          (ValueError('historical invalid schema'), 'TRANSPORT_INVALID')])
def test_historical_transport_error_cannot_discard_verified_current_ack(tmp_path, monkeypatch, failure, reason):
    tool = module(); public = project(tmp_path / 'fixture')
    monkeypatch.setattr(tool, 'git_client', lambda: None)
    monkeypatch.setattr(tool, 'read_current', lambda git: {'research': None, 'acquisition': None, 'cursor': None})
    monkeypatch.setattr(tool, 'api', lambda path: producer())
    monkeypatch.setattr(tool, 'receive_run', lambda run: (public, None))
    monkeypatch.setattr(tool, 'catch_up', lambda *a: (_ for _ in ()).throw(failure))
    monkeypatch.setattr(tool, 'persist', lambda git, **kw: kw)
    result = tool.sync(103)
    assert result['research'] == public and result['cursor']['artifact_id'] is None
    assert result['catchup_pending_reason'] == reason


def test_valid_catchup_before_an_older_bad_artifact_is_retained(tmp_path, monkeypatch):
    tool = module(); public = project(tmp_path / 'fixture'); run = producer()
    entries = [{'id': i, 'created_at': '2026-11-11T12:00:00Z', 'name': 'bct-public-research-1',
                'expired': False, 'workflow_run': {'id': 103}} for i in (900, 899)]
    def metadata(path):
        if path.startswith('actions/artifacts?'): return {'artifacts': entries}
        if path == 'actions/runs/103': return run
        return {'jobs': [{'name': 'publish', 'conclusion': 'success'}]}
    monkeypatch.setattr(tool, 'api', metadata)
    monkeypatch.setattr(tool, 'artifact_bytes', lambda a: archive(public) if a['id'] == 900 else
                        (_ for _ in ()).throw(OSError('older artifact 410')))
    research, collection, cursor, reason = tool.catch_up(None)
    assert research == public and cursor['artifact_id'] is None and reason == 'TRANSPORT_UNAVAILABLE'
