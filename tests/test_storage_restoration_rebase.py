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
