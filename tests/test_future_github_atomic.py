"""Publication failures cannot expose partial generations or discard a writer."""
import base64
import hashlib
import json
from urllib.parse import unquote

import pytest

from bct import future_github as storage
from bct.future_store import StoreConflict, store_patch

PATH = 'future-candidates.json'


class GitRemote:
    def __init__(self, document):
        self.blobs = {}
        self.trees = {'t0': {PATH: self.blob(storage._raw(document)), 'keep.txt': self.blob(b'keep')}}
        self.commits = {'c0': {'tree': {'sha': 't0'}, 'parents': []}}
        self.head = 'c0'
        self.calls = []
        self.fail = None
        self.race = False
        self.corrupt = False

    def blob(self, raw):
        sha = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
        self.blobs[sha] = raw
        return sha

    def request(self, method, suffix, payload=None):
        self.calls.append((method, suffix))
        if self.fail == (method, suffix):
            raise RuntimeError('injected service error')
        if method == 'GET' and suffix.startswith('/git/ref/'):
            return {'object': {'sha': self.head}}
        if method == 'GET' and suffix.startswith('/git/commits/'):
            return self.commits[suffix.rsplit('/', 1)[1]]
        if method == 'GET' and suffix.startswith('/contents/'):
            path, ref = suffix[len('/contents/'):].split('?ref=')
            sha = self.trees[self.commits[ref]['tree']['sha']][unquote(path)]
            return {'sha': sha, 'encoding': 'none'}
        if method == 'GET' and suffix.startswith('/git/blobs/'):
            sha = suffix.rsplit('/', 1)[1]
            raw = b'corruption' if self.corrupt else self.blobs[sha]
            return {'sha': sha, 'content': base64.b64encode(raw).decode()}
        if method == 'POST' and suffix == '/git/blobs':
            return {'sha': self.blob(base64.b64decode(payload['content']))}
        if method == 'POST' and suffix == '/git/trees':
            tree = dict(self.trees[payload['base_tree']])
            tree.update({e['path']: e['sha'] for e in payload['tree']})
            key = 't' + str(len(self.trees));self.trees[key] = tree
            return {'sha': key}
        if method == 'POST' and suffix == '/git/commits':
            key = 'c' + str(len(self.commits))
            self.commits[key] = {'tree': {'sha': payload['tree']}, 'parents': payload['parents']}
            if self.race:
                self.race = False
                self.commits['competitor'] = {'tree': {'sha': 't0'}, 'parents': [self.head]}
                self.head = 'competitor'
            return {'sha': key}
        if method == 'PATCH' and suffix.startswith('/git/refs/'):
            assert payload['force'] is False
            if self.commits[payload['sha']]['parents'] != [self.head]:
                raise StoreConflict('not fast-forward')
            self.head = payload['sha']
            return {'object': {'sha': self.head}}
        raise AssertionError((method, suffix))

    def transport(self):
        return storage.GitHubTransport('owner/repo', 'test', 'test-token', requester=self.request)


def test_atomic_roundtrip_reuses_unchanged_shards_and_one_ref_move(monkeypatch):
    monkeypatch.setattr(storage, 'MAX_REQUEST_BYTES', 6000)
    monkeypatch.setattr(storage, 'MAX_SHARD_BYTES', 2000)
    document = {'results': {str(i): {'id': str(i), 'data': 'x' * 700} for i in range(10)}}
    remote = GitRemote({});t = remote.transport()
    t.write(PATH, document, t.read(PATH).sha)
    assert t.read(PATH).document == document
    assert sum(m == 'PATCH' for m, _ in remote.calls) == 1
    prior_head = remote.head
    calls = len(remote.calls)
    document['results']['0']['data'] = 'y' * 700
    t.write(PATH, document, t.read(PATH).sha)
    assert t.read(PATH).document == document
    delta = remote.calls[calls:]
    assert sum(m == 'POST' and s == '/git/blobs' for m, s in delta) == 3
    assert sum(m == 'PATCH' for m, _ in delta) == 1
    assert remote.commits[remote.head]['parents'] == [prior_head]
    assert 'keep.txt' in remote.trees[remote.commits[remote.head]['tree']['sha']]
    calls = len(remote.calls);t.write(PATH, document, t.read(PATH).sha)
    assert not any(m in ('POST', 'PATCH', 'PUT') for m, _ in remote.calls[calls:])


def test_exact_commit_readback_ignores_transient_mutable_ref_lag():
    remote = GitRemote({});t = remote.transport()
    document = {'results': {'new': {'id': 'new'}}}
    t.write(PATH, document, t.read(PATH).sha)
    published = t.last_commit
    # Simulate an immediately repeated ref read returning the prior head.
    remote.head = 'c0'
    assert t.read(PATH).document == {}
    assert t.read_at(PATH, published).document == document


@pytest.mark.parametrize('endpoint', ['/git/blobs', '/git/trees', '/git/commits', '/git/refs/heads/test'])
def test_failed_stage_never_publishes_or_marks_saved(endpoint):
    remote = GitRemote({'results': {}, 'notifications': {'n': {'state': 'READY'}}})
    before = remote.head
    remote.fail = ('PATCH' if endpoint.startswith('/git/refs') else 'POST', endpoint)
    result = store_patch(remote.transport(), PATH, owner='notification',
                         patch={'notifications': {'n': {'state': 'SENT'}}}, operation_id='n')
    assert result.status == 'PENDING' and remote.head == before
    assert remote.transport().read(PATH).document['notifications']['n']['state'] == 'READY'


def test_concurrent_ref_move_is_rejected_and_preserving_rebase_succeeds():
    remote = GitRemote({'results': {}});t = remote.transport();remote.race = True
    old = t.read(PATH)
    with pytest.raises(StoreConflict):
        t.write(PATH, {'results': {}, 'summary': {'x': 1}}, old.sha)
    assert remote.head == 'competitor'
    result = store_patch(t, PATH, owner='collection', patch={'summary': {'x': 1}}, operation_id='ours')
    assert result.status == 'APPLIED'
    assert remote.commits[remote.head]['parents'] == ['competitor']


def test_corrupt_blob_never_publishes():
    remote = GitRemote({});t = remote.transport();old = t.read(PATH);remote.corrupt = True
    with pytest.raises(ValueError):
        t.write(PATH, {'results': {'new': 1}}, old.sha)
    assert remote.head == 'c0'


def test_response_diagnostics_distinguish_missing_header_and_rate_limit():
    no_header = storage.error_details('PUT', '/contents/a', 403, {}, b'{"message":"Forbidden"}')
    assert no_header['category'] == 'UNCLASSIFIED'
    assert no_header['retry_after'] is None and no_header['retry_after_observed'] is False
    secondary = storage.error_details('POST', '/git/blobs', 403,
        {'Retry-After': '60', 'X-RateLimit-Remaining': '4999', 'X-GitHub-Request-Id': 'id-1'},
        b'{"message":"secondary rate limit"}')
    assert secondary['category'] == 'SECONDARY_RATE_LIMIT' and secondary['request_id'] == 'id-1'
    primary = storage.error_details('GET', '/contents/a', 403,
        {'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': '2000'}, b'{}')
    assert primary['category'] == 'PRIMARY_RATE_LIMIT'
    denied = storage.error_details('PUT', '/contents/a', 403, {},
        b'{"message":"Resource not accessible by integration; token secret"}')
    assert denied['category'] == 'ACCESS_DENIED' and 'secret' not in json.dumps(denied)


def dual_remote():
    remote=GitRemote({'results':{}})
    remote.trees['t0']['future-tracking.json']=remote.blob(storage._raw({'reviews':{}}))
    return remote


def test_restart_and_overlapping_writer_probe_preserves_both_roots():
    from bct.recovery_storage_probe import verify_atomic_recovery
    remote = dual_remote()
    transport = storage.GitHubTransport('owner/repo', 'ops/bct-storage-probe-123',
                                       'test-token', requester=remote.request)
    receipt = verify_atomic_recovery(transport, '123')
    assert receipt['status'] == 'PASS' and receipt['idempotent_replay_mutations'] == 0
    assert transport.read(PATH).document['summary'] == {
        'competing_probe_writer': '123', 'atomic_recovery_probe': '123'}
    assert transport.read('future-tracking.json').document['reviews'] == {}
    assert receipt['unpublished_commit'] != receipt['recovery_commit']


def test_remote_fault_probe_refuses_production_branch():
    from bct.recovery_storage_probe import verify_atomic_recovery
    remote = dual_remote()
    transport = remote.transport()
    with pytest.raises(ValueError, match='dedicated test branch'):
        verify_atomic_recovery(transport, '123')
    assert not remote.calls


def test_restarted_probe_verifies_immutable_commit_and_waits_for_ref_visibility(monkeypatch):
    from bct import recovery_storage_probe as probe
    remote = dual_remote()
    original = remote.request
    delayed = []
    publications = 0
    def request(method, suffix, payload=None):
        nonlocal publications
        if method == 'GET' and suffix.startswith('/git/ref/') and delayed:
            return {'object': {'sha': delayed.pop(0)}}
        before = remote.head
        value = original(method, suffix, payload)
        if method == 'PATCH' and suffix.startswith('/git/refs/'):
            publications += 1
            if publications == 2:
                delayed.extend([before, before])
        return value
    slept = []
    monkeypatch.setattr(probe.time, 'sleep', slept.append)
    transport = storage.GitHubTransport('owner/repo', 'ops/bct-storage-probe-123',
                                       'test-token', requester=request)
    receipt = probe.verify_atomic_recovery(transport, '123')
    assert receipt['status'] == 'PASS' and receipt['immutable_generation_readback']
    assert receipt['recovery_commit'] == remote.head
    assert receipt['recovered_ref_observations'] == [
        receipt['competing_writer_commit'], receipt['competing_writer_commit'], remote.head]
    assert slept == [1, 2]
    assert receipt['idempotent_replay_mutations'] == 0
    assert publications == 2


def test_probe_visibility_deadline_and_unrelated_writer_do_not_retry_writes(monkeypatch):
    from bct import recovery_storage_probe as probe
    remote = dual_remote(); transport = remote.transport()
    with pytest.raises(StoreConflict, match='another writer'):
        probe.observe_published_head(transport, 'known', {'previous'})
    ticks = iter([0, 31])
    monkeypatch.setattr(probe.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(TimeoutError, match='visibility still delayed'):
        probe.observe_published_head(transport, 'known', {'c0'})
    assert not any(method in ('POST', 'PATCH', 'PUT', 'DELETE') for method, _ in remote.calls)


def test_readings_and_queue_publish_in_one_generation():
    remote=dual_remote();t=remote.transport()
    paths=(PATH,'future-tracking.json');expected={p:t.read(p).sha for p in paths}
    docs={PATH:{'results':{},'summary':{'completed':1}},'future-tracking.json':{'reviews':{'actual':{'read_end':100}}}}
    roots=t.write_many(docs,expected)
    assert {p:t.read(p).document for p in paths}==docs
    assert roots=={p:t.read(p).sha for p in paths}
    assert sum(m=='PATCH' for m,s in remote.calls)==1
    assert remote.commits[remote.head]['parents']==['c0']


def test_a_stale_tracking_snapshot_cannot_publish_fresh_queue():
    remote=dual_remote();t=remote.transport();expected={PATH:t.read(PATH).sha,'future-tracking.json':'stale'}
    with pytest.raises(StoreConflict):
        t.write_many({PATH:{'results':{},'summary':{'completed':1}},'future-tracking.json':{'reviews':{'r':1}}},expected)
    assert remote.head=='c0'
    assert not any(m in ('POST','PATCH') for m,s in remote.calls)


def test_multi_document_publication_failure_keeps_both_originals():
    remote=dual_remote();t=remote.transport();expected={p:t.read(p).sha for p in (PATH,'future-tracking.json')}
    remote.fail=('POST','/git/trees')
    with pytest.raises(RuntimeError):
        t.write_many({PATH:{'results':{},'summary':{'completed':1}},'future-tracking.json':{'reviews':{'r':1}}},expected)
    assert remote.head=='c0' and t.read(PATH).document=={'results':{}}
    assert t.read('future-tracking.json').document=={'reviews':{}}
