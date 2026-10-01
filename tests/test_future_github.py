import base64
import hashlib
import json

import pytest

from bct.future_github import GitHubTransport


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
