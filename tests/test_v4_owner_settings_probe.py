"""The owner-settings diagnostic must never update an operating ref or run CPU."""
import ast
import base64
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3

import pytest
import yaml

from bct.v4 import private_state

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/v4-cpu-private-settings-check.yml'


def workflow():
    return yaml.safe_load(WORKFLOW.read_text())


def python_block(step):
    return step['run'].split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]


def test_manual_settings_probe_has_no_schedule_write_permission_or_inference():
    w = workflow()
    assert set(w.get('on', w.get(True))) == {'workflow_dispatch'}
    assert w['permissions'] == {'contents': 'read', 'actions': 'read'}
    job = w['jobs']['publisher_permission_check']
    assert job['runs-on'] == 'ubuntu-24.04'
    assert job['steps'][0]['with']['persist-credentials'] is False
    for step in job['steps']:
        if "<<'PY'" in step.get('run', ''):
            ast.parse(python_block(step))
    text = WORKFLOW.read_text()
    assert 'extract_windows' not in text and 'pip install' not in text
    assert 'purpose=seed' not in text


@pytest.mark.parametrize('status,denied', [(403, True), (404, True), (422, False)])
def test_denials_only_never_repeats_private_get_or_changes_existing_refs(monkeypatch, capsys, status, denied):
    monkeypatch.setenv('AUTH_DENIALS_ONLY', 'true')
    monkeypatch.setenv('STATE_TOKEN', 'synthetic-private-test-only')
    monkeypatch.delenv('GH_TOKEN', raising=False)
    calls = []
    def api(token, method, path, data=None):
        assert token == 'synthetic-private-test-only'
        assert method == 'POST' and path == f'repos/{private_state.PUBLIC_REPO}/git/refs'
        assert data['ref'] in ('refs/heads/main', 'refs/heads/data')
        assert re.fullmatch('[0-9a-f]{40}', data['sha'])
        calls.append(data['ref'])
        return status, {}
    monkeypatch.setattr(private_state, 'github_api', api)
    monkeypatch.setattr(private_state, 'writer_scope', lambda *a, **k: pytest.fail('No repeat private scope probe'))
    step = workflow()['jobs']['publisher_permission_check']['steps'][-1]
    with pytest.raises(SystemExit) as exc:
        exec(compile(python_block(step), str(WORKFLOW), 'exec'), {})
    assert exc.value.code == 0  # diagnostic completion, NOT activation PASS
    result = json.loads(capsys.readouterr().out.split('BCT_PRIVATE_SCOPE_JSON=', 1)[1])
    assert result['status'] == 'DIAGNOSTIC_ONLY' and result['public_write_denied'] is denied
    assert result['source_DB_uploaded'] is False
    assert calls == ['refs/heads/main', 'refs/heads/data']


def test_roundtrip_uploads_only_nonproduction_metadata_and_reads_immutable_blobs(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(WORKFLOW.parents[2])
    monkeypatch.setenv('REMOTE_ROUNDTRIP', 'true')
    monkeypatch.setenv('STATE_TOKEN', 'synthetic-private-test-only')
    monkeypatch.setenv('STATE_PASSPHRASE', 'synthetic-connection-key-'.ljust(64, 'x'))
    monkeypatch.setenv('GITHUB_RUN_ID', '12345')
    files, blobs = {}, {}
    def oid(body):
        return hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
    def api(token, method, path, data=None):
        assert token == 'synthetic-private-test-only'
        if path == 'repos/' + private_state.PRIVATE_REPO:
            return 200, {'full_name': private_state.PRIVATE_REPO, 'private': True, 'size': 0}
        if path.startswith('user/repos?'):
            return 200, [{'full_name': private_state.PRIVATE_REPO}]
        if path.endswith('/git/refs'):
            return (403, {}) if method == 'POST' else (409, {})
        if '/git/ref/heads/' in path:
            return 200, {'object': {'sha': 'a' * 40}}
        if '/git/trees/' in path:
            return 200, {'truncated': False, 'tree': [{'type': 'blob', 'path': p, 'sha': oid(b)} for p, b in files.items()]}
        if path.endswith('/git/blobs'):
            return 201, {}
        if '/git/blobs/' in path:
            return 200, {'encoding': 'base64', 'content': base64.b64encode(blobs[path.rsplit('/', 1)[1]]).decode()}
        assert method == 'PUT' and '/contents/' in path  # never repeat binary path GET
        name = path.split('/contents/', 1)[1]
        assert name.startswith(('connection-check/', 'metadata-receipts/12345/'))
        assert name not in files  # immutable; no replacement of a prior version
        body = base64.b64decode(data['content'])
        assert len(body) < 64 * 1024
        files[name] = body; blobs[oid(body)] = body
        return 201, {'content': {'sha': oid(body)}}
    monkeypatch.setattr(private_state, 'github_api', api)
    step = workflow()['jobs']['publisher_permission_check']['steps'][-1]
    with pytest.raises(SystemExit) as exc:
        exec(compile(python_block(step), str(WORKFLOW), 'exec'), {})
    assert exc.value.code == 0
    report = json.loads(capsys.readouterr().out.split('BCT_PRIVATE_SCOPE_JSON=', 1)[1])
    assert report['metadata_receipts'] == 41 and report['original_articles_uploaded'] == 0
    assert report['original_semantic_DB_restored_remotely'] is False
    assert report['CPU_enabled'] is False and report['seven_day_start'] is None
    for prefix in ('connection-check', 'metadata-receipts/12345'):
        dbpath = tmp_path / (prefix.replace('/', '-') + '.sqlite3')
        dbpath.write_bytes(gzip.decompress(files[prefix + '/checkpoint.sqlite3.gz']))
        with sqlite3.connect(dbpath) as db:
            for table in ('documents', 'blobs', 'readings', 'runs', 'firsts'):
                assert db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0
            for kind, payload in db.execute('SELECT kind,payload FROM events'):
                row = json.loads(payload)
                if kind == 'PRIOR_COMPLETION_IDENTIFIER_ONLY':
                    assert set(row) == {'document_id', 'body_key', 'receipt_sha256', 'record_kind'}
                else:
                    assert kind in ('METADATA_ONLY_NOT_PRODUCTION_SEED', 'CONNECTION_CHECK_NOT_PRODUCTION')
