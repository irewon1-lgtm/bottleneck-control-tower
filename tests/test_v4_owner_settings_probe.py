"""The owner-settings diagnostic must never update an operating ref or run CPU."""
import ast
import json
from pathlib import Path
import re

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
