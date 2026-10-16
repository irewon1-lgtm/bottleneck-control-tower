"""Backup integrity/commit semantics; not a production storage or forecast test."""
import json
from pathlib import Path
import pytest
from bct.v4 import release_archive as a, quantitative_private as p, quantitative as q
from bct.v4.store import Ledger, file_sha

PASSWORD = 'archive-test-only-not-an-account-secret-0123456789'


class Memory:
    tag = 'bct-v4-archive-test-1'
    parent = 'a' * 40
    def __init__(self):
        self.rows = []
        self.data = {}
    def assets(self):
        return [dict(x) for x in self.rows]
    def put(self, name, raw):
        if any(x['name'] == name for x in self.rows):
            raise ValueError('ARCHIVE_IMMUTABLE_NAME_ALREADY_EXISTS')
        row = {'id': len(self.rows) + 1, 'name': name, 'size': len(raw)}
        self.rows.append(row); self.data[row['id']] = raw
        return row
    def read(self, asset):
        return self.data[asset['id']]


def capsule(root, revision=0):
    root = Path(root); root.mkdir(parents=True)
    ledger = Ledger(root / 'ledger'); raw = root / 'sample.json'; raw.write_text('{"value":12}')
    m = {'url':'https://api.usaspending.gov/api/v2/transactions/', 'source_id':'usaspending',
         'path':str(raw), 'sha256':file_sha(raw), 'acquired_at':'2026-10-16', 'published_at':'UNKNOWN'}
    row = q.observation(m, 'synthetic-contract', 'synthetic-class', 'transaction_obligation', '12',
                        'USD', 'MONEY', '2026-09-01', {'format':'JSON','path':['value']})
    q.commit_page(ledger, 'synthetic-page', m, [row])
    for n in range(revision):
        with ledger.db:
            ledger.event('QUANTITATIVE_VALIDATION', {'reason':f'Synthetic revision {n}', 'originals_modified':False})
    proof = p.checkpoint(ledger, root / 'checkpoint'); ledger.close()
    return root / 'checkpoint', proof


def test_full_delta_checkpoint_exact_restore_and_noop_dedup(tmp_path):
    s = Memory(); cp, proof = capsule(tmp_path / 'v0')
    assert a.publish(s, cp, PASSWORD, expected_generation=-1)['kind'] == 'CHECKPOINT'
    count = len(s.rows)
    assert a.publish(s, cp, PASSWORD, expected_generation=0)['unchanged']
    assert len(s.rows) == count
    cp1, proof1 = capsule(tmp_path / 'v1', 1)
    assert a.publish(s, cp1, PASSWORD, expected_generation=0, max_deltas=1)['kind'] == 'PAGE_DELTA'
    cp2, proof2 = capsule(tmp_path / 'v2', 2)
    assert a.publish(s, cp2, PASSWORD, expected_generation=1, max_deltas=1)['kind'] == 'CHECKPOINT'
    for n, wanted in enumerate([proof, proof1, proof2]):
        got = a.restore(s, n, PASSWORD, tmp_path / f'restored{n}', expected_sqlite_sha256=wanted['sqlite_sha256'])
        assert got['sqlite_sha256'] == wanted['sqlite_sha256'] and got['tables'] == 8


def test_interrupted_upload_reuses_orphan_without_duplicate_data_or_commit(tmp_path):
    s = Memory(); cp, proof = capsule(tmp_path / 'v0')
    with pytest.raises(ValueError, match='INTERRUPTED'):
        a.publish(s, cp, PASSWORD, expected_generation=-1, interrupt_before_commit=True)
    assert a.generations(s) == [] and len(s.rows) == 1
    a.publish(s, cp, PASSWORD, expected_generation=-1)
    assert len(s.rows) == 2
    assert a.restore(s, 0, PASSWORD, tmp_path/'restored', expected_sqlite_sha256=proof['sqlite_sha256'])['restored']


def test_corrupt_ciphertext_refused_prior_valid_generation_restorable(tmp_path):
    s = Memory(); cp, proof = capsule(tmp_path/'v0'); a.publish(s, cp, PASSWORD, expected_generation=-1)
    cp1, proof1 = capsule(tmp_path/'v1', 1); a.publish(s, cp1, PASSWORD, expected_generation=0)
    m, _ = a.load_commit(s, 1, PASSWORD); key = m['patches'][0]['id']; original = s.data[key]
    s.data[key] = original[:-1] + bytes([original[-1] ^ 1])
    with pytest.raises(ValueError, match='CIPHERTEXT_HASH'):
        a.restore(s, 1, PASSWORD, tmp_path/'bad', expected_sqlite_sha256=proof1['sqlite_sha256'])
    assert not(tmp_path/'bad').exists()
    assert a.restore(s, 0, PASSWORD, tmp_path/'previous', expected_sqlite_sha256=proof['sqlite_sha256'])['restored']
    s.data[key] = original
    assert a.restore(s, 1, PASSWORD, tmp_path/'recovered', expected_sqlite_sha256=proof1['sqlite_sha256'])['restored']


def test_stale_parent_never_uploads_and_missing_object_not_silently_skipped(tmp_path):
    s = Memory(); cp, proof = capsule(tmp_path/'v0'); a.publish(s, cp, PASSWORD, expected_generation=-1)
    before = len(s.rows)
    with pytest.raises(ValueError, match='PARENT_CHANGED'):
        a.publish(s, cp, PASSWORD, expected_generation=-1)
    assert len(s.rows) == before
    s.rows = [x for x in s.rows if not x['name'].startswith('blob-')]
    with pytest.raises(ValueError, match='OBJECT_MISSING'):
        a.restore(s, 0, PASSWORD, tmp_path/'bad', expected_sqlite_sha256=proof['sqlite_sha256'])


def test_wrong_key_expected_hash_and_overwrite_are_refused(tmp_path):
    s = Memory(); cp, proof = capsule(tmp_path/'v0'); a.publish(s, cp, PASSWORD, expected_generation=-1)
    with pytest.raises(ValueError, match='AUTHENTICATION'):
        a.restore(s, 0, 'other-long-test-passphrase-not-a-real-secret-12345', tmp_path/'wrong-key', expected_sqlite_sha256=proof['sqlite_sha256'])
    with pytest.raises(ValueError, match='EXPECTED_TARGET_HASH'):
        a.restore(s, 0, PASSWORD, tmp_path/'wrong-hash', expected_sqlite_sha256='b'*64)
    target = tmp_path/'kept'; target.mkdir(); (target/'sentinel').write_text('keep')
    with pytest.raises(ValueError, match='REFUSES_OVERWRITE'):
        a.restore(s, 0, PASSWORD, target, expected_sqlite_sha256=proof['sqlite_sha256'])
    assert(target/'sentinel').read_text()=='keep'


def test_periodic_age_checkpoint_and_namespace_guard(tmp_path):
    from datetime import datetime, timezone, timedelta
    s = Memory(); cp, proof = capsule(tmp_path/'v0'); at = datetime(2026,10,16,tzinfo=timezone.utc)
    a.publish(s, cp, PASSWORD, expected_generation=-1, at=at)
    cp1, _ = capsule(tmp_path/'v1', 1)
    assert a.publish(s, cp1, PASSWORD, expected_generation=0, at=at+timedelta(days=7))['kind']=='CHECKPOINT'
    s.tag='bct-v4-archive-test-2'
    with pytest.raises(ValueError, match='NAMESPACE'):
        a.load_commit(s, 1, PASSWORD)


def test_api_budget_counts_other_archive_releases_before_upload(monkeypatch):
    s=a.Releases('test-token-not-printed','bct-v4-archive-test-2','a'*40);s.release_id=2
    monkeypatch.setattr(s,'assets',lambda:[])
    def request(method,path,value=None,**kw):
        assert method=='GET'  # No upload may happen after budget exhaustion.
        if '/releases?'in path:return 200,[{'tag_name':'bct-v4-archive-test-1','id':1}]
        return 200,[{'name':'old','size':a.PILOT_BYTES}]
    monkeypatch.setattr(s,'_request',request)
    with pytest.raises(ValueError,match='BUDGET_STOP'):
        s.put('blob-'+'a'*64+'.gpg',b'x')


def test_no_operating_cutover_or_new_schedule_is_configured():
    import yaml
    workflow=yaml.safe_load(Path('.github/workflows/v4-cpu-private-research.yml').read_text())
    assert workflow['permissions']['contents']=='read'
    assert 'schedule' not in workflow.get('on',workflow.get(True,{}))
    job=workflow['jobs']['archive-storage-trial']
    assert "github.event_name == 'workflow_dispatch'" in job['if']
    assert "github.ref == 'refs/heads/codex/bct-v4-integration'" in job['if']
    assert 'archive-storage-trial' in job['if']
    assert 'BCT_V4_PRIVATE_STATE_TOKEN' in job['steps'][1]['env']


def test_binary_redirect_strips_authorization_and_rejects_unknown_host(monkeypatch):
    from urllib.error import HTTPError
    seen=[]
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return b'cipher'
    class Opener:
        def open(self,request,timeout):
            seen.append(request)
            if len(seen)==1:
                raise HTTPError(request.full_url,302,'Found',{'Location':'https://release-assets.githubusercontent.com/test?signature=not-logged'},None)
            return Response()
    monkeypatch.setattr(a,'build_opener',lambda *args:Opener())
    s=a.Releases('test-private-token','bct-v4-archive-test-1','a'*40)
    assert s.read({'id':123})==b'cipher'
    assert seen[0].get_header('Authorization') and seen[1].get_header('Authorization') is None
