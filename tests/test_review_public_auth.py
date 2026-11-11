"""Public REVIEW authentication regression, using fake headers and local Git HTTP."""
import base64
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
from threading import Thread

import yaml


def test_public_receipt_step_uses_gh_cli_fallback_without_core_git_token_injection():
    workflow = yaml.safe_load(Path('.github/workflows/review-lead-shadow.yml').read_text())
    step, = [step for job in workflow['jobs'].values() for step in job['steps']
             if 'receive_review_inputs.py public ' in str(step.get('run', ''))]
    assert step['env'].get('GITHUB_TOKEN') == '${{ github.token }}'
    assert 'GH_TOKEN' not in step['env']


def isolated_git_environment():
    # Local protocol tests never inherit a token, Git auth setting or proxy.
    environment = {name: value for name, value in os.environ.items()
                   if not (name.startswith(('GIT_CONFIG_', 'GIT_TRACE', 'BCT_'))
                           or name in {'GH_TOKEN', 'GITHUB_TOKEN', 'GIT_ASKPASS',
                                       'SSH_ASKPASS', 'GIT_PROXY_COMMAND'}
                           or name.lower().endswith('_proxy'))}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                       GIT_TERMINAL_PROMPT='0', NO_PROXY='127.0.0.1,localhost')
    return environment


def git(repo, *args, environment, input=None):
    return subprocess.run(['git', '-C', str(repo), *args], env=environment,
                          input=input, capture_output=True, text=True, timeout=10)


@contextmanager
def git_http_server(directory, persisted_header):
    captured = []

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            headers = self.headers.get_all('Authorization', [])
            captured.append(headers)
            if headers != [persisted_header]:
                self.send_error(400, 'one authorization header required')
                return
            super().do_GET()

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(directory)))
    thread = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port), captured
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_real_git_http_rejects_duplicate_authorization_but_accepts_persisted_single_header(tmp_path):
    environment = isolated_git_environment()
    served = tmp_path / 'served'
    served.mkdir()
    bare = served / 'state.git'
    assert git(served, 'init', '--bare', str(bare), environment=environment).returncode == 0
    tree = git(bare, 'mktree', environment=environment, input='')
    assert tree.returncode == 0
    commit = git(bare, '-c', 'user.name=Local fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit-tree', tree.stdout.strip(), environment=environment, input='Fixture state\n')
    assert commit.returncode == 0
    head = commit.stdout.strip()
    for args in [('update-ref', 'refs/heads/data', head),
                 ('symbolic-ref', 'HEAD', 'refs/heads/data'), ('update-server-info',)]:
        assert git(bare, *args, environment=environment).returncode == 0
    client = tmp_path / 'client'
    client.mkdir()
    assert git(client, 'init', environment=environment).returncode == 0
    persisted = 'basic ' + base64.b64encode(b'x-access-token:fake-checkout-token').decode()
    injected = 'basic ' + base64.b64encode(b'x-access-token:fake-core-token').decode()
    with git_http_server(served, persisted) as (origin, captured):
        key = 'http.' + origin + '/.extraheader'
        assert git(client, 'remote', 'add', 'origin', origin + '/state.git',
                   environment=environment).returncode == 0
        assert git(client, 'config', '--local', key, 'AUTHORIZATION: ' + persisted,
                   environment=environment).returncode == 0

        # Reproduce the extra environment-level header injected by the core
        # when GH_TOKEN exists beside checkout's repository-local header.
        duplicate_environment = {**environment, 'GH_TOKEN': 'fake-core-token',
            'GIT_CONFIG_COUNT': '2', 'GIT_CONFIG_KEY_0': key,
            'GIT_CONFIG_VALUE_0': 'AUTHORIZATION: ' + injected,
            'GIT_CONFIG_KEY_1': 'credential.helper', 'GIT_CONFIG_VALUE_1': ''}
        rejected = git(client, 'ls-remote', 'origin', 'refs/heads/data',
                       environment=duplicate_environment)
        assert rejected.returncode != 0
        assert captured and all(len(headers) == 2 and set(headers) == {persisted, injected}
                                for headers in captured)

        captured.clear()
        # gh accepts GITHUB_TOKEN, whereas core Git's GH_TOKEN-only injection
        # is absent; Git retains the original checkout header on the wire.
        single_environment = {**environment, 'GITHUB_TOKEN': 'fake-gh-cli-token'}
        assert 'GH_TOKEN' not in single_environment and 'GIT_CONFIG_COUNT' not in single_environment
        accepted = git(client, 'ls-remote', 'origin', 'refs/heads/data',
                       environment=single_environment)
        assert accepted.returncode == 0, accepted.stderr
        assert accepted.stdout.strip() == head + '\trefs/heads/data'
        assert captured and all(headers == [persisted] for headers in captured)
