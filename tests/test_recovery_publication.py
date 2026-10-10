"""Derived publication cannot hide a stale reader, false FULL, or ref failure."""
from copy import deepcopy
import pytest

from bct.future_github import _raw
from bct.future_store import StoreConflict
from bct.recovery_preservation import seal
from bct.recovery_publication import PATHS, publish_projection
from tests.test_future_github_atomic import GitRemote
from tests.test_recovery_queue import fixture


def setup():
    c, t, versions, _, digest = fixture(status='FULL')
    remote = GitRemote(c)
    remote.trees['t0'][PATHS[1]] = remote.blob(_raw(t))
    change = {'owner': 'collection', 'patch': {'summary': {'new_documents_this_run': 1}},
              'operation_id': 'actual-queue-operation', 'prepared_document': deepcopy(c)}
    return remote, c, t, versions, digest, [change]


def publish(remote, c, t, versions, changes, cache, observations=None):
    return publish_projection(remote.transport(), changes, versions=versions,
        observations=observations or {}, cache=cache, preservation=seal(c, t),
        retained=seal(c, t), run_id='test-execution-only')


def test_latest_inflow_survives_and_corrected_full_is_not_counted(tmp_path):
    remote, c, t, versions, digest, changes = setup()
    fresh = deepcopy(c)
    fresh['results']['new'] = {'id': 'new', 'versions': {}, 'body_status': 'UNAVAILABLE'}
    transport = remote.transport()
    transport.write(PATHS[0], fresh, transport.read(PATHS[0]).sha)
    before = remote.head
    observations = {versions[0]['url']: {'body_sha256': digest, 'body_status': 'PARTIAL',
        'status': 'PARTIAL', 'reclassification_rule': 'ARTICLE_TERMINAL_ELLIPSIS_V1'}}
    receipt, queue = publish(remote, c, t, versions, changes, tmp_path, observations)
    saved = transport.read_at(PATHS[0], receipt['published_commit']).document
    assert 'new' in saved['results']
    assert saved['results']['doc'] == c['results']['doc']
    assert transport.read_at(PATHS[1], receipt['published_commit']).document == t
    assert queue['counts']['COMPLETED'] == 0 and queue['counts']['SOURCE_WAIT'] >= 1
    assert queue['legacy_read_results'] == queue['source_corrected_read_results'] == 1
    assert receipt['parent_commit'] == before
    assert saved['summary']['recovery_queue']['counts'] == receipt['queue_counts']
    assert receipt['failed_versions_preserved'] == 1


def test_queue_and_display_use_single_ref_move_and_replay_makes_no_mutation(tmp_path):
    remote, c, t, versions, _, changes = setup()
    receipt, _ = publish(remote, c, t, versions, changes, tmp_path)
    assert sum(m == 'PATCH' for m, _ in remote.calls) == 1
    tree = remote.trees[remote.commits[receipt['published_commit']]['tree']['sha']]
    assert 'future-candidates.ui.json.gz' in tree
    count = len(remote.calls)
    replay, _ = publish(remote, c, t, versions, changes, tmp_path)
    assert replay['published_commit'] == receipt['published_commit']
    assert not any(m in ('PATCH', 'PUT', 'POST') for m, _ in remote.calls[count:])


@pytest.mark.parametrize('endpoint', ['/git/trees', '/git/commits'])
def test_staged_failure_is_never_reported_as_publication_success(tmp_path, endpoint):
    remote, c, t, versions, _, changes = setup()
    remote.fail = ('POST', endpoint)
    before = remote.head
    with pytest.raises(RuntimeError, match='injected'):
        publish(remote, c, t, versions, changes, tmp_path)
    assert remote.head == before


def test_competing_ref_is_preserved_and_requires_rebuilding_projection(tmp_path):
    remote, c, t, versions, _, changes = setup()
    remote.race = True
    with pytest.raises(StoreConflict):
        publish(remote, c, t, versions, changes, tmp_path)
    assert remote.head == 'competitor'
    assert remote.transport().read(PATHS[0]).document == c


def test_derived_publisher_cannot_create_a_review_to_reduce_backlog(tmp_path):
    remote, c, t, versions, _, _ = setup()
    changes = [{'owner': 'review', 'patch': {'reviews': {'invented': {}}},
                'operation_id': 'unsafe'}]
    with pytest.raises(ValueError, match='cannot create review'):
        publish(remote, c, t, versions, changes, tmp_path)
    assert remote.head == 'c0'
