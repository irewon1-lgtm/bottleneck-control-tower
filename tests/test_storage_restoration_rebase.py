"""A normal reader's concurrent append must survive sealed-record repair."""
from copy import deepcopy
import importlib.util
from pathlib import Path

from bct.future_store import Snapshot, StoreConflict
from bct.recovery_preservation import seal, verify, digest


spec = importlib.util.spec_from_file_location('storage_recovery',
    Path('.github/scripts/bct_storage_recovery.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_restore_rebases_concurrent_reader_without_erasing_review_or_drift():
    trusted = {'results': {'d': {'versions': {'h': {
        'body_sha256': 'h', 'body_status': 'PARTIAL', 'reaccess_status': 'AVAILABLE'}}}}}
    baseline = seal(trusted, {})
    changed = deepcopy(trusted)
    changed['results']['d']['versions']['h'].update(
        reaccess_status='SOURCE_CHANGED', access_checked_at='2026-10-12T15:02:42Z')
    class Remote:
        def __init__(self):
            self.documents = {'future-candidates.json': changed, 'future-tracking.json': {}}
            self.revision = 0
            self.last_commit = '0'
            self.calls = 0
        def head(self):
            return str(self.revision)
        def read_at(self, path, commit):
            assert commit == self.head()
            return Snapshot(deepcopy(self.documents[path]), path+commit)
        def write_many(self, documents, expected):
            self.calls += 1
            if self.calls == 1:
                self.documents['future-tracking.json']['reviews'] = {'new': {'kind': 'access', 'evidence': 'new'}}
                self.revision += 1
                raise StoreConflict('concurrent ref advance')
            assert expected == {p: p+self.head() for p in documents}
            self.documents = deepcopy(documents)
            self.revision += 1
            self.last_commit = self.head()
            return {p: p+self.head() for p in documents}
    remote = Remote()
    c, t, receipt = module.restore_generation(remote,
        remote.read_at('future-candidates.json', '0'), remote.read_at('future-tracking.json', '0'),
        baseline, trusted, [])
    assert receipt['status'] == 'PASS' and len(receipt['concurrent_conflicts']) == 1
    assert t.document['reviews']['new'] == {'kind': 'access', 'evidence': 'new'}
    assert verify(c.document, t.document, baseline)['status'] == 'PASS'
    before = changed['results']['d']['versions']['h']
    assert c.document['results']['d']['version_judgment_holds'][digest(before)]['observed_record'] == before


def test_generation_guard_blocks_stale_ref_without_writing():
    import pytest
    class Remote:
        def __init__(self):
            self.value = 'production-advanced'
            self.writes = 0
        def head(self):
            return self.value
        def write(self, *args):
            self.writes += 1
    remote = Remote()
    with pytest.raises(StoreConflict, match='sidecar SHA changed'):
        module.require_projection_head(remote, 'old-pinned-generation')
    assert remote.writes == 0
    assert module.require_projection_head(remote, 'production-advanced') == 'production-advanced'


def test_gate_and_cpu_writer_share_lock_but_rss_keeps_independent_lock():
    recovery = Path('.github/workflows/bct-recovery.yml').read_text()
    candidates = Path('.github/workflows/future-bottleneck.yml').read_text()
    rss = Path('.github/workflows/rss-live-check.yml').read_text()
    assert '  storage:\n    if:' in recovery
    storage_job = recovery.split('  storage:\n', 1)[1]
    assert '    concurrency:\n      group: future-bottleneck-results\n      cancel-in-progress: false' in storage_job
    assert 'concurrency:\n  group: future-bottleneck-results\n  cancel-in-progress: false' in candidates
    assert 'rss-canonical-data' in rss
    assert 'future-bottleneck-results' not in rss
