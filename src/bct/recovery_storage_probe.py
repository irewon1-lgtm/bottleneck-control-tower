"""Real remote fault/interleaving probe, restricted to the run's test branch."""
from copy import deepcopy

from .future_store import StoreConflict


class PublicationInterrupted(RuntimeError):
    pass


def verify_atomic_recovery(transport, run_id):
    if transport.branch != 'ops/bct-storage-probe-' + str(run_id):
        raise ValueError('fault injection requires the dedicated test branch')
    paths = ('future-candidates.json', 'future-tracking.json')
    before = {p: transport.read(p) for p in paths}
    documents = {p: deepcopy(s.document) for p, s in before.items()}
    documents[paths[0]].setdefault('summary', {})['atomic_recovery_probe'] = str(run_id)
    documents[paths[1]]['atomic_recovery_probe'] = str(run_id)
    expected = {p: s.sha for p, s in before.items()}
    original_requester = transport.requester
    initial_head = transport.head()
    staged = {}

    def interrupted(method, suffix, payload=None):
        if method == 'PATCH' and suffix.startswith('/git/refs/'):
            staged['unpublished_commit'] = payload['sha']
            raise PublicationInterrupted('test branch stopped before publication')
        return original_requester(method, suffix, payload)

    transport.requester = interrupted
    try:
        try:
            transport.write_many(documents, expected)
        except PublicationInterrupted:
            pass
        else:
            raise ValueError('interruption was not injected')
    finally:
        transport.requester = original_requester
    if transport.head() != initial_head or any(transport.read(p) != before[p] for p in paths):
        raise ValueError('interrupted generation changed the visible branch')
    competitor_head = None

    def overlapping(method, suffix, payload=None):
        nonlocal competitor_head
        result = original_requester(method, suffix, payload)
        if method == 'POST' and suffix == '/git/commits' and competitor_head is None:
            competitor = type(transport)(transport.repository, transport.branch, transport.token,
                                         requester=original_requester)
            current = competitor.read(paths[0])
            value = deepcopy(current.document)
            value.setdefault('summary', {})['competing_probe_writer'] = str(run_id)
            competitor.write(paths[0], value, current.sha)
            competitor_head = competitor.head()
        return result

    transport.requester = overlapping
    try:
        try:
            transport.write_many(documents, expected)
        except StoreConflict:
            pass
        else:
            raise ValueError('overlapping writer was not rejected')
    finally:
        transport.requester = original_requester
    if transport.head() != competitor_head or transport.read(paths[1]) != before[paths[1]]:
        raise ValueError('stale generation replaced the competing writer')
    latest = {p: transport.read(p) for p in paths}
    recovered = {p: deepcopy(s.document) for p, s in latest.items()}
    recovered[paths[0]].setdefault('summary', {})['atomic_recovery_probe'] = str(run_id)
    recovered[paths[1]]['atomic_recovery_probe'] = str(run_id)
    roots = transport.write_many(recovered, {p: s.sha for p, s in latest.items()})
    recovered_head = transport.head()
    if any(transport.read(p).document != recovered[p] for p in paths):
        raise ValueError('restarted generation readback differs')
    mutations = []

    def observe(method, suffix, payload=None):
        if method in ('POST', 'PATCH', 'PUT', 'DELETE'):
            mutations.append((method, suffix))
        return original_requester(method, suffix, payload)

    transport.requester = observe
    try:
        replay = transport.write_many(recovered, roots)
    finally:
        transport.requester = original_requester
    if mutations or replay != roots or transport.head() != recovered_head:
        raise ValueError('identical restarted generation was written again')
    return {'status': 'PASS', 'actual_remote_execution': True,
            'interrupted_head': initial_head, **staged,
            'competing_writer_commit': competitor_head, 'recovery_commit': recovered_head,
            'root_shas': roots, 'idempotent_replay_mutations': len(mutations)}
