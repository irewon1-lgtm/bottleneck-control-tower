import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).parents[1]/'.github/scripts'))
spec = importlib.util.spec_from_file_location(
    'publication_wait', Path(__file__).parents[1]/'.github/scripts/bct_wait_publication.py')
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class Transport:
    def __init__(self, runs):
        self.runs = runs
        self.posts = 0

    def _root(self, path, commit):
        assert path == 'config/bct-operating-release.json' and commit == 'main-sha'
        return json.dumps({'gate_run_id': 1}).encode(), 'blob'

    def requester(self, method, suffix, payload=None):
        if method == 'GET' and suffix == '/git/ref/heads/main':
            return {'object': {'sha': 'main-sha'}}
        if method == 'GET' and suffix.startswith('/actions/runs?'):
            return {'workflow_runs': self.runs}
        if method == 'POST':
            self.posts += 1
            return {}
        raise AssertionError((method, suffix))


def test_next_independent_cycle_archives_completed_request_and_dispatches_fresh(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_RUN_ID', '34')
    monkeypatch.setattr(module, 'verify_release', lambda *args: None)
    prior = {'run_id': '33', 'main_sha': 'main-sha', 'requested_at': '2000-01-01T00:00:00Z',
             'state': 'COMPLETED', 'candidate_run_id': 101, 'pages_run_id': 102}
    (tmp_path/'operating-publication-request.json').write_text(json.dumps(prior))
    def run(ident, created, workflow, event):
        return {'id': ident, 'head_sha': 'main-sha', 'created_at': created,
                'path': '.github/workflows/'+workflow, 'event': event,
                'status': 'completed', 'conclusion': 'success'}
    transport = Transport([
        run(101, '2000-01-01T00:00:00Z', 'future-bottleneck.yml', 'repository_dispatch'),
        run(102, '2000-01-01T00:00:00Z', 'ui-pages.yml', 'workflow_run'),
        run(301, '9998-01-01T00:00:00Z', 'future-bottleneck.yml', 'repository_dispatch'),
        run(302, '9999-01-01T00:00:00Z', 'ui-pages.yml', 'workflow_run'),
    ])
    assert module.dispatch_and_wait(tmp_path, transport, deadline=module.time.monotonic()+1) == (301, 302)
    assert transport.posts == 1
    assert json.loads((tmp_path/'operating-publication-history.json').read_text()) == [prior]
    assert json.loads((tmp_path/'operating-publication-request.json').read_text())['run_id'] == '34'


def test_uncertain_dispatch_is_reconciled_without_a_second_post(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_RUN_ID', '32')
    monkeypatch.setattr(module, 'verify_release', lambda *args: None)
    requested = datetime.now(timezone.utc).isoformat()
    (tmp_path/'operating-publication-request.json').write_text(json.dumps({
        'run_id': '31', 'main_sha': 'main-sha', 'requested_at': requested,
        'state': 'REQUESTING'}))
    runs = [
        {'id': 101, 'head_sha': 'main-sha', 'created_at': requested,
         'path': '.github/workflows/future-bottleneck.yml',
         'event': 'repository_dispatch', 'status': 'completed', 'conclusion': 'success'},
        {'id': 102, 'head_sha': 'main-sha', 'created_at': requested,
         'path': '.github/workflows/ui-pages.yml',
         'event': 'workflow_run', 'status': 'completed', 'conclusion': 'success'},
    ]
    transport = Transport(runs)
    assert module.dispatch_and_wait(tmp_path, transport, deadline=module.time.monotonic()+1) == (101, 102)
    assert transport.posts == 0
    proof = json.loads((tmp_path/'operating-publication-request.json').read_text())
    assert proof['state'] == 'COMPLETED' and proof['candidate_run_id'] == 101
    assert proof['run_id'] == '31' and proof['resumed_by_run_id'] == '32'


def test_completed_candidate_dispatches_pages_once_and_waits(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_RUN_ID', '33')
    monkeypatch.setattr(module, 'verify_release', lambda *args: None)
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)
    candidate = {'id': 201, 'head_sha': 'main-sha', 'created_at': '9998-01-01T00:00:00Z',
        'path': '.github/workflows/future-bottleneck.yml',
        'event': 'repository_dispatch', 'status': 'completed', 'conclusion': 'success'}
    page = {'id': 202, 'head_sha': 'main-sha', 'created_at': '9999-01-01T00:00:00Z',
        'path': '.github/workflows/ui-pages.yml',
        'event': 'repository_dispatch', 'status': 'completed', 'conclusion': 'success'}

    class DelayedPages(Transport):
        queries = 0

        def requester(self, method, suffix, payload=None):
            if method == 'GET' and suffix.startswith('/actions/runs?'):
                self.queries += 1
                return {'workflow_runs': [candidate] if self.queries == 1 else [page, candidate]}
            return super().requester(method, suffix, payload)

    transport = DelayedPages([candidate])
    assert module.dispatch_and_wait(tmp_path, transport, deadline=module.time.monotonic()+60) == (201, 202)
    assert transport.posts == 2  # one candidate request, then one Pages request
    proof = json.loads((tmp_path/'operating-publication-request.json').read_text())
    assert proof['pages_state'] == 'DISPATCHED' and proof['state'] == 'COMPLETED'
