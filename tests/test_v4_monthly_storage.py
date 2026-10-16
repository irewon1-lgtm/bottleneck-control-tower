"""Monthly research primary semantics; rollover dates are simulated, not LIVE."""
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from bct.v4 import monthly_storage as m, release_archive as a, quantitative_private as p
from bct.v4.store import Ledger, file_sha
from test_v4_release_archive import capsule, Memory, PASSWORD


def evolve(cp, root):
    p.restore(cp, root/'ledger');l=Ledger(root/'ledger')
    with l.db:l.event('QUANTITATIVE_VALIDATION',{'reason':'monthly storage test append','originals_modified':False})
    proof=p.checkpoint(l,root/'checkpoint');l.close();return root/'checkpoint',proof


class Registry:
    def __init__(self):self.stores={};self.fail=False
    def factory(self, token, tag, parent):
        registry=self
        class Store(Memory):
            base='repos/irewon1-lgtm/bct-v4-private-state'
            def __init__(self):
                self.tag=tag;self.parent=parent
                if tag in registry.stores:self.rows,self.data=registry.stores[tag]
                else:self.rows,self.data=[],{}
            def ensure(self,create=True):
                if tag not in registry.stores and not create:raise ValueError('MISSING_RELEASE')
                registry.stores.setdefault(tag,(self.rows,self.data));return self
            def _request(self,method,path,value=None,**kw):
                assert method=='GET'
                if registry.fail:return 403,None
                if '/releases?'in path:return 200,[{'tag_name':t,'draft':False}for t in registry.stores]
                return 200,{'private':True,'full_name':a.transport.PRIVATE_REPO}
        return Store()


def setup(tmp_path):
    reg=Registry();pol=m.policy();at=datetime(2026,10,16,tzinfo=timezone.utc)
    obj=m.Monthly('test-token',PASSWORD,settings=pol,at=at,factory=reg.factory)
    cp,proof=capsule(tmp_path/'initial')
    seed={'backend':'git-seed','legacy_parent':obj.anchor,'sqlite_sha256':proof['sqlite_sha256']}
    return reg,obj,cp,proof,seed


def test_monthly_full_append_restore_dedup_and_stale_parent(tmp_path):
    reg,obj,cp,proof,seed=setup(tmp_path)
    first=obj.publish(cp,seed);assert first['kind']=='CHECKPOINT' and first['Git_writes']==0
    cp1,p1=evolve(cp,tmp_path/'next');second=obj.publish(cp1,first['storage'])
    assert second['kind']=='PAGE_DELTA'
    got=obj.receive(tmp_path/'reloaded');assert got['verified']['sqlite_sha256']==p1['sqlite_sha256']
    before=len(next(iter(reg.stores.values()))[0])
    assert obj.publish(cp1,second['storage'])['unchanged']
    assert len(next(iter(reg.stores.values()))[0])==before
    assert obj.publish(cp1,first['storage'])['recovered_lost_acknowledgment']
    assert len(next(iter(reg.stores.values()))[0])==before
    with pytest.raises(ValueError,match='PARENT_CHANGED'):obj.publish(cp,first['storage'])


def test_next_month_is_full_and_links_previous_completed_manifest(tmp_path):
    reg,obj,cp,proof,seed=setup(tmp_path);first=obj.publish(cp,seed)
    next_month=m.Monthly('test-token',PASSWORD,settings=obj.p,at=datetime(2026,11,1,tzinfo=timezone.utc),factory=reg.factory)
    assert next_month.publish(cp,first['storage'])['unchanged'] and len(reg.stores)==1
    cp1,p1=evolve(cp,tmp_path/'next');second=next_month.publish(cp1,first['storage'])
    assert second['kind']=='CHECKPOINT' and second['patches']==0
    man,_=a.load_commit(next_month.store(),0,PASSWORD)
    assert man['monthly_context']['previous_month']==first['storage']
    assert next_month.receive(tmp_path/'reloaded')['verified']['sqlite_sha256']==p1['sqlite_sha256']
    assert len(reg.stores)==2


def test_new_primary_cannot_drop_any_previous_processing_history(tmp_path):
    reg,obj,cp,proof,seed=setup(tmp_path);first=obj.publish(cp,seed)
    cp1,p1=evolve(cp,tmp_path/'next');second=obj.publish(cp1,first['storage'])
    before=len(next(iter(reg.stores.values()))[0])
    with pytest.raises(ValueError,match='EXISTING_HISTORY_LOST'):obj.publish(cp,second['storage'])
    assert len(next(iter(reg.stores.values()))[0])==before


def test_first_month_cannot_seed_with_unrelated_or_newer_untracked_state(tmp_path):
    reg,obj,cp,proof,seed=setup(tmp_path);cp1,_=evolve(cp,tmp_path/'next')
    with pytest.raises(ValueError,match='FIRST_SEED'):obj.publish(cp1,seed)
    assert reg.stores=={}


def test_release_access_failure_and_corruption_never_fall_back_to_old_git(tmp_path,monkeypatch):
    reg,obj,cp,proof,seed=setup(tmp_path);obj.publish(cp,seed)
    monkeypatch.setattr(p,'remote_checkpoint',lambda *args:pytest.fail('must not fall back to Git'))
    reg.fail=True
    with pytest.raises(ValueError,match='UNVERIFIED'):obj.receive(tmp_path/'denied',git_repo=tmp_path/'git')
    reg.fail=False
    rows,data=next(iter(reg.stores.values()));key=next(x['id']for x in rows if x['name'].startswith('blob-'));old=data[key];data[key]=b'bad'
    with pytest.raises(ValueError,match='CIPHERTEXT_HASH'):obj.receive(tmp_path/'bad',git_repo=tmp_path/'git')
    assert not(tmp_path/'bad').exists();data[key]=old
    assert obj.receive(tmp_path/'recovered')['verified']['restored']


def test_encrypted_handoff_preserves_exact_monthly_input_cursor(tmp_path):
    reg,obj,cp,proof,seed=setup(tmp_path);cur=obj.publish(cp,seed)['storage']
    p.seal(cp,tmp_path/'handoff.gpg',PASSWORD,obj.anchor,storage=cur)
    got=p.unseal(tmp_path/'handoff.gpg',tmp_path/'decoded',PASSWORD)
    assert got['storage']==cur and got['verified']['sqlite_sha256']==proof['sqlite_sha256']


def test_scope_month_horizon_and_monthly_budget_are_finite(tmp_path,monkeypatch):
    with pytest.raises(ValueError,match='HORIZON_ENDED'):
        m.Monthly('test-token',PASSWORD,at=datetime(2028,10,1,tzinfo=timezone.utc)).publish(None,None)
    s=a.Releases('test-token','bct-v4-archive-monthly-2026-10','a'*40);s.release_id=2
    monkeypatch.setattr(s,'assets',lambda:[{'name':'old','size':a.MONTHLY_BYTES}])
    def api(method,path,*args,**kw):
        assert method=='GET'
        if '/releases?'in path:return 200,[{'tag_name':s.tag,'id':2}]
        return 200,[{'size':a.MONTHLY_BYTES}]
    monkeypatch.setattr(s,'_request',api)
    with pytest.raises(ValueError,match='BUDGET_STOP'):s.put('commit-00000002.gpg',b'x')


def test_archives_remain_readable_after_write_horizon_expires(tmp_path):
    reg,obj,cp,proof,seed=setup(tmp_path);obj.publish(cp,seed)
    after=m.Monthly('test-token',PASSWORD,settings=obj.p,at=datetime(2029,1,1,tzinfo=timezone.utc),factory=reg.factory)
    assert after.receive(tmp_path/'after-expiry')['verified']['sqlite_sha256']==proof['sqlite_sha256']
    with pytest.raises(ValueError,match='HORIZON_ENDED'):after.publish(cp,after.head())


def test_research_batch_carries_cursor_and_legacy_upload_is_disabled():
    text=Path('tools/v4_quantitative_batch.py').read_text()
    assert "storage=result.get('storage')" in text
    assert "MONTHLY_STATE_EXISTS_REFUSE_STALE_GIT_RESEARCH_READ" in text
    assert "receipt=Monthly(" in text
    assert "REFUSE_STALE_GIT_CUTOVER" in text
    assert 'LEGACY_TRANSFER_PUBLISH_DISABLED' in Path('tools/v4_quantitative_private.py').read_text()
