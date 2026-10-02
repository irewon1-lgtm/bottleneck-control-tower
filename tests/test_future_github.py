import base64
import hashlib
import json

import pytest

from bct.future_github import GitHubTransport
from bct.future_store import Snapshot


def blob(document):
    raw = json.dumps(document).encode()
    sha = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
    return {'sha': sha, 'encoding': 'base64', 'content': base64.b64encode(raw).decode()}


def test_large_file_read_pins_immutable_blob_and_conditional_write():
    old = blob({'unknown': {'keep': 1}})
    calls = []
    def request(method, suffix, payload=None):
        calls.append((method, suffix, payload))
        if method == 'PUT':
            assert payload['sha'] == old['sha']
            assert payload['branch'] == 'test-data'
            assert json.loads(base64.b64decode(payload['content']))['unknown'] == {'keep': 1}
            return {'content': {'sha': 'saved-sha'}}
        if '/contents/' in suffix:
            return {'sha': old['sha'], 'encoding': 'none'}
        assert suffix == '/git/blobs/' + old['sha']
        return old
    transport = GitHubTransport('owner/repo', 'test-data', 'test-token', requester=request)
    state = transport.read('future-candidates.json')
    assert state.document == {'unknown': {'keep': 1}}
    assert transport.write('future-candidates.json', state.document, state.sha) == 'saved-sha'
    with pytest.raises(ValueError):
        transport.read('canonical.sqlite3')


def test_transport_rejects_content_not_matching_returned_sha():
    value = blob({'version': 1})
    value['sha'] = '0' * 40
    transport = GitHubTransport('owner/repo', 'test', 'test-token', requester=lambda *a: value)
    with pytest.raises(ValueError, match='SHA disagree'):
        transport.read('future-tracking.json')


def test_github_change_envelope_preserves_original_preparation_context(monkeypatch, tmp_path):
    from bct import future_github
    change = {'owner': 'review', 'operation_id': 'ours',
              'prepared_document': {'progress': {'d:hash:reader': {'last_review_id': 'old'}}},
              'patch': {'reviews': {'ours': {'document_id': 'd', 'body_sha256': 'hash', 'reader_version': 'reader'}},
                        'progress': {'d:hash:reader': {'last_review_id': 'ours'}}}}
    latest = {'reviews': {'other': {'document_id': 'd', 'body_sha256': 'hash', 'reader_version': 'reader'}},
              'progress': {'d:hash:reader': {'last_review_id': 'other'}}}
    class Transport:
        writes = 0
        def read(self, path):
            return Snapshot(latest, 'latest')
        def write(self, *args):
            self.writes += 1
            raise AssertionError('stale judgment must not be written')
    transport = Transport()
    source, pending = tmp_path / 'change.json', tmp_path / 'pending.json'
    source.write_text(json.dumps(change))
    monkeypatch.setattr(future_github, 'GitHubTransport', lambda *args: transport)
    monkeypatch.setattr('sys.argv', ['future_github', '--repository', 'owner/repo', '--path',
                                  'future-tracking.json', '--change', str(source), '--pending', str(pending)])
    with pytest.raises(SystemExit) as stopped:
        future_github.main()
    assert stopped.value.code == 1 and transport.writes == 0
    assert json.loads(pending.read_text()) == change
