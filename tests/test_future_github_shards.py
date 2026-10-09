import base64
from copy import deepcopy
import hashlib
import json
from urllib.parse import unquote

import pytest

from bct import future_github as storage
from bct.future_store import StoreConflict, store_patch


PATH = 'future-candidates.json'


class Remote:
    def __init__(self, document):
        self.files = {PATH: storage._raw(document)}
        self.blobs = {}
        self.writes = []
        self.fail_part = None
        self.conflict_root = False
        self.corrupt_read = None
        self.remember(self.files[PATH])

    def remember(self, raw):
        sha = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
        self.blobs[sha] = raw
        return sha

    def request(self, method, suffix, payload=None):
        if '/git/blobs/' in suffix:
            sha = suffix.rsplit('/', 1)[1]
            return {'sha': sha, 'content': base64.b64encode(self.blobs[sha]).decode()}
        path = unquote(suffix.split('/contents/', 1)[1].split('?', 1)[0])
        if method == 'GET':
            if path not in self.files:
                raise FileNotFoundError(path)
            raw = self.files[path]
            sha = self.remember(raw)
            return {'sha': sha, 'encoding': 'none'}  # Exercise immutable blob read.
        assert method == 'PUT'
        assert len(json.dumps(payload).encode()) <= storage.MAX_REQUEST_BYTES < 16 * 1024 * 1024
        self.writes.append(path)
        if path.endswith(self.fail_part or '.never'):
            raise OSError('forced middle-shard failure')
        if path == PATH and self.conflict_root:
            raise StoreConflict('concurrent writer')
        current = self.remember(self.files[path]) if path in self.files else None
        if payload.get('sha') != current:
            raise StoreConflict('stale SHA')
        raw = base64.b64decode(payload['content'])
        self.files[path] = raw
        sha = self.remember(raw)
        return {'content': {'sha': sha}}

    def transport(self):
        return storage.GitHubTransport('owner/repo', 'test-data', 'test-token', requester=self.request)


def payload(megabytes):
    return {'version': 'body-candidate-v3', 'results': {
        str(i): {'id': str(i), 'unknown': None, 'quantity': 1.0,
                 'evidence': 'x' * (1024 * 1024)} for i in range(megabytes)},
        'empty': [], 'metadata': {'한글': '보존'},
        'notifications': {'n': {'state': 'READY'}}}


@pytest.mark.parametrize('megabytes,sharded', [(1, False), (15, True), (19, True)])
def test_requested_sizes_and_exact_roundtrip(megabytes, sharded):
    original = payload(megabytes)
    remote = Remote({'version': 'old'})
    transport = remote.transport()
    previous = transport.read(PATH)
    transport.write(PATH, original, previous.sha)
    published = json.loads(remote.files[PATH])
    assert (published.get('format') == storage.MANIFEST_FORMAT) is sharded
    if sharded:
        assert remote.writes[-1] == PATH
        assert published['item_counts']['results'] == megabytes
        for n, part in enumerate(published['shards'], 1):
            assert part['path'].endswith(f'.part-{n:03d}.json')
            assert len(remote.files[part['path']]) <= 10 * 1024 * 1024
            assert hashlib.sha256(remote.files[part['path']]).hexdigest() == part['sha256']
    else:
        assert remote.writes == [PATH]
    restored = transport.read(PATH).document
    assert restored == original
    assert storage._sha(storage._raw(restored)) == storage._sha(storage._raw(original))
    assert len(restored['results']) == megabytes


def test_middle_failure_preserves_remote_and_sent_is_not_published_then_retries():
    original = payload(19)
    remote = Remote(original)
    prior = remote.files[PATH]
    remote.fail_part = '.part-002.json'
    change = dict(owner='notification', patch={'notifications': {'n': {'state': 'SENT'}}},
                  operation_id='actual-delivery')
    result = store_patch(remote.transport(), PATH, **change)
    assert result.status == 'PENDING'
    assert remote.files[PATH] == prior
    assert PATH not in remote.writes
    assert remote.transport().read(PATH).document['notifications']['n']['state'] == 'READY'
    assert 'actual-delivery' not in remote.transport().read(PATH).document.get('operations', {})
    # Reuse the successful immutable first shard; retry only the unfinished writes.
    first = remote.writes[0]
    remote.fail_part = None
    result = store_patch(remote.transport(), PATH, **change)
    assert result.status == 'APPLIED'
    assert remote.writes.count(first) == 1
    result = store_patch(remote.transport(), PATH, **change)
    assert result.status == 'ALREADY_APPLIED'


def test_new_shard_readback_uses_returned_immutable_sha_when_branch_lookup_lags():
    remote = Remote({})
    original_request = remote.request
    def lagging_branch(method, suffix, payload=None):
        if method == 'GET' and '/contents/' in suffix and '.shards/' in suffix:
            raise FileNotFoundError('new branch path not yet visible')
        return original_request(method, suffix, payload)
    transport = storage.GitHubTransport('owner/repo', 'test-data', 'test-token', requester=lagging_branch)
    transport.write(PATH, payload(19), transport.read(PATH).sha)
    assert remote.transport().read(PATH).document == payload(19)


def test_staged_immutable_blob_corruption_cannot_publish_manifest():
    remote = Remote({}); original_request = remote.request
    def corrupt_staged(method, suffix, payload=None):
        value = original_request(method, suffix, payload)
        if method == 'GET' and '/git/blobs/' in suffix and len(base64.b64decode(value['content'])) > 1024:
            value['content'] = base64.b64encode(b'corrupted').decode()
        return value
    transport = storage.GitHubTransport('owner/repo', 'test-data', 'test-token', requester=corrupt_staged)
    old = remote.files[PATH]
    with pytest.raises(ValueError, match='staged blob'):
        transport.write(PATH, payload(19), transport.read(PATH).sha)
    assert remote.files[PATH] == old


def test_existing_manifest_survives_failed_replacement_and_stale_cas():
    remote = Remote({})
    transport = remote.transport()
    transport.write(PATH, payload(19), transport.read(PATH).sha)
    prior = remote.files[PATH]
    update = payload(19)
    update['results']['0']['id'] = 'new-version'
    remote.fail_part = '.part-002.json'
    with pytest.raises(OSError):
        transport.write(PATH, update, transport.read(PATH).sha)
    assert remote.files[PATH] == prior
    assert transport.read(PATH).document == payload(19)
    remote.fail_part = None
    remote.conflict_root = True
    with pytest.raises(StoreConflict):
        transport.write(PATH, update, transport.read(PATH).sha)
    assert remote.files[PATH] == prior


def test_shard_corruption_and_count_mismatch_are_rejected():
    remote = Remote({})
    transport = remote.transport()
    transport.write(PATH, payload(19), transport.read(PATH).sha)
    manifest = json.loads(remote.files[PATH])
    parts = {p['path']: remote.files[p['path']] for p in manifest['shards']}
    bad = deepcopy(parts)
    bad[manifest['shards'][0]['path']] += b' '
    with pytest.raises(ValueError, match='hash/size'):
        storage.assemble(manifest, lambda p: bad[p['path']])
    manifest['total_item_count'] += 1
    with pytest.raises(ValueError, match='hash/count'):
        storage.assemble(manifest, lambda p: parts[p['path']])


def test_single_oversized_record_fails_before_any_write():
    remote = Remote({'keep': True})
    transport = remote.transport()
    prior = remote.files[PATH]
    with pytest.raises(ValueError, match='one data item'):
        transport.write(PATH, {'results': {'huge': 'x' * (19 * 1024 * 1024)}}, transport.read(PATH).sha)
    assert remote.writes == [] and remote.files[PATH] == prior


def test_legacy_single_file_read_is_unchanged():
    original = payload(1)
    remote = Remote(original)
    assert remote.transport().read(PATH).document == original
    assert remote.writes == []
