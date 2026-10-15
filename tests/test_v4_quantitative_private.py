"""Synthetic transport/CAS tests, not numerical source accuracy or CPU operation."""
import gzip,json,os,subprocess
from pathlib import Path
import pytest
from bct.v4 import quantitative as q,quantitative_private as private,cpu_operations as op
from bct.v4.store import Ledger,sha,file_sha


def facts(tmp):
    l=Ledger(tmp/'ledger');raw=tmp/'data.json';raw.write_text('{"value":12}')
    m={'url':'https://api.usaspending.gov/api/v2/transactions/','source_id':'usaspending',
       'path':str(raw),'sha256':file_sha(raw),'acquired_at':'2026-10-15','published_at':'UNKNOWN'}
    row=q.observation(m,'synthetic-contract','synthetic-class','transaction_obligation','12','USD','MONEY','2026-09-01',{'format':'JSON','path':['value']})
    q.commit_page(l,'synthetic-page',m,[row]);return l,m,row


def git(*args,cwd=None):
    return subprocess.check_output(['git',*args],cwd=cwd,stderr=subprocess.DEVNULL,text=True).strip()


def test_q1_format_is_not_cpu_queue_and_new_process_restores_dedup(tmp_path):
    l,m,row=facts(tmp_path);proof=private.checkpoint(l,tmp_path/'checkpoint');l.close()
    with pytest.raises(ValueError,match='TABLES_OR_INTEGRITY'):op.restore(tmp_path/'checkpoint',tmp_path/'not-cpu')
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')}
    command=['python','-c','import sys;from bct.v4.quantitative_private import restore;restore(sys.argv[1],sys.argv[2])',str(tmp_path/'checkpoint'),str(tmp_path/'new-process')]
    subprocess.run(command,env=env,check=True,capture_output=True,timeout=25)
    assert file_sha(tmp_path/'new-process/v4.sqlite3')==proof['sqlite_sha256']
    l=Ledger(tmp_path/'new-process');before=file_sha(l.path)
    assert q.commit_page(l,'synthetic-page',m,[row])['status']=='UNCHANGED'
    assert file_sha(l.path)==before;l.close()


def test_unknown_raw_or_contact_and_live_data_cannot_publish(tmp_path):
    l,m,row=facts(tmp_path)
    with l.db:l.event('UNREVIEWED_BODY',{'text':'synthetic article'})
    with pytest.raises(ValueError,match='UNKNOWN_EVENT'):private.checkpoint(l,tmp_path/'blocked')
    l.close()


def test_q1_bounded_CAS_ref_isolation_failed_write_and_recovery(tmp_path,monkeypatch):
    l,m,row=facts(tmp_path);private.checkpoint(l,tmp_path/'checkpoint');l.close()
    bare=tmp_path/'remote.git';repo=tmp_path/'writer';git('init','--bare',str(bare));git('init',str(repo))
    git('config','user.name','synthetic test',cwd=repo);git('config','user.email','test@example.org',cwd=repo)
    git('remote','add','origin',str(bare),cwd=repo)
    (repo/'preserved').write_text('synthetic existing CPU state');git('add','preserved',cwd=repo);git('commit','-m','existing',cwd=repo)
    old=git('rev-parse','HEAD',cwd=repo)
    for ref in ['main','data','codex/bct-v4-cpu-research-state']:git('push','origin','HEAD:refs/heads/'+ref,cwd=repo)
    result=op._publish_checkpoint(repo,tmp_path/'checkpoint','',namespace='q1')
    assert result['research_ref']==private.STATE_REF
    for ref in ['main','data','codex/bct-v4-cpu-research-state']:
        assert git('rev-parse','refs/heads/'+ref,cwd=bare)==old
    with pytest.raises(ValueError,match='PARENT_CHANGED'):op._publish_checkpoint(repo,tmp_path/'checkpoint','',namespace='q1')
    # Existing history cap applies across CPU and Q1 branches, not per new ref.
    monkeypatch.setattr(op,'STATE_HISTORY_LIMIT',1)
    with pytest.raises(ValueError,match='64MIB'):op._publish_checkpoint(repo,tmp_path/'checkpoint',result['commit'],namespace='q1')
    assert git('rev-parse',private.STATE_REF,cwd=bare)==result['commit']
    monkeypatch.setattr(op,'STATE_HISTORY_LIMIT',64*1024**2)
    again=op._publish_checkpoint(repo,tmp_path/'checkpoint',result['commit'],namespace='q1')
    assert again['parent']==result['commit']
    with pytest.raises(ValueError,match='NAMESPACE'):op._publish_checkpoint(repo,tmp_path/'checkpoint','',namespace='main')


def test_q1_corrupt_restore_cannot_overwrite_existing_or_leave_success(tmp_path):
    l,_,_=facts(tmp_path);private.checkpoint(l,tmp_path/'checkpoint');l.close()
    private.restore(tmp_path/'checkpoint',tmp_path/'restored');before=file_sha(tmp_path/'restored/v4.sqlite3')
    with pytest.raises(ValueError,match='OVERWRITE'):private.restore(tmp_path/'checkpoint',tmp_path/'restored')
    assert file_sha(tmp_path/'restored/v4.sqlite3')==before
    archive=tmp_path/'checkpoint/checkpoint.sqlite3.gz';archive.write_bytes(archive.read_bytes()+b'corrupt')
    with pytest.raises(ValueError,match='HASH_OR_SIZE'):private.restore(tmp_path/'checkpoint',tmp_path/'bad')
    assert not(tmp_path/'bad/v4.sqlite3').exists()


def test_unreviewed_record_text_cannot_hide_inside_a_numeric_event(tmp_path):
    l,m,row=facts(tmp_path)
    item=q.records(l)[0];item['record']['source_text']='synthetic article body'
    with l.db:l.event(q.OBS,item)
    with pytest.raises(ValueError,match='UNREVIEWED_RECORD'):private.audit(l.db)
    l.close()


def test_incremental_checkpoint_restores_exact_bytes_and_preserves_full_history(tmp_path):
    from bct.v4 import quantitative_delta as delta
    l,m,row=facts(tmp_path);base=tmp_path/'base';private.checkpoint(l,base)
    bare=tmp_path/'remote.git';writer=tmp_path/'writer';git('init','--bare',str(bare));git('clone',str(bare),str(writer))
    import shutil
    for name in ['checkpoint.json','checkpoint.sqlite3.gz']:shutil.copyfile(base/name,writer/name)
    git('add','.',cwd=writer);git('-c','user.name=test','-c','user.email=test@example.org','commit','-m','existing base',cwd=writer)
    parent=git('rev-parse','HEAD',cwd=writer);git('push','origin','HEAD:'+private.STATE_REF,cwd=writer)
    base_archive=git('rev-parse',parent+':checkpoint.sqlite3.gz',cwd=writer)
    env=os.environ.copy()
    for iteration in range(2):
        with l.db:l.event('QUANTITATIVE_VALIDATION',{'reason':'synthetic append '+str(iteration),'originals_modified':False})
        cp=tmp_path/('next'+str(iteration));private.checkpoint(l,cp)
        receipt=delta.publish(writer,cp,parent,env);parent=receipt['commit']
        assert receipt['incremental']['delta_bytes']<cp.joinpath('checkpoint.sqlite3.gz').stat().st_size
        assert git('rev-parse',parent+':checkpoint.sqlite3.gz',cwd=writer)==base_archive
        def read(*args):return subprocess.check_output(['git','-C',str(writer),*args])
        dest=tmp_path/('restored'+str(iteration));delta.receive(read,parent,dest)
        assert file_sha(dest/'checkpoint.sqlite3.gz')==file_sha(cp/'checkpoint.sqlite3.gz')
        private.restore(dest,tmp_path/('reload'+str(iteration)))
    with pytest.raises(ValueError,match='PARENT_CHANGED'):delta.publish(writer,cp,'0'*40,env)
    manifest=json.loads(read('show',parent+':'+delta.HEAD));assert len(manifest['patches'])==2
    with pytest.raises(ValueError,match='PATH'):delta.names({**manifest,'patches':[{'path':'../../outside','sha256':'x'}]})
    before=tmp_path/'one';after=tmp_path/'two';before.write_bytes(b'a'*4096);after.write_bytes(b'b'*4096)
    patch,_=delta.make_delta(before,after);before.write_bytes(b'c'*4096)
    with pytest.raises(ValueError,match='BASE_HASH'):delta.apply_delta(before,patch)
    l.close()


def test_page_checkpoint_budget_failure_and_corruption_preserve_prior_state(tmp_path,monkeypatch):
    from bct.v4 import quantitative_delta as delta
    import shutil
    l,m,row=facts(tmp_path);base=tmp_path/'base';private.checkpoint(l,base)
    remote=tmp_path/'remote.git';writer=tmp_path/'writer';git('init','--bare',str(remote));git('clone',str(remote),str(writer))
    for name in ['checkpoint.json','checkpoint.sqlite3.gz']:shutil.copyfile(base/name,writer/name)
    git('add','.',cwd=writer);git('-c','user.name=test','-c','user.email=test@example.org','commit','-m','base',cwd=writer)
    original=git('rev-parse','HEAD',cwd=writer)
    for ref in [private.STATE_REF,'refs/heads/main','refs/heads/data']:git('push','origin','HEAD:'+ref,cwd=writer)
    with l.db:l.event('QUANTITATIVE_VALIDATION',{'reason':'synthetic storage retry','originals_modified':False})
    target=tmp_path/'target';private.checkpoint(l,target);l.close()
    monkeypatch.setattr(op,'STATE_HISTORY_LIMIT',1)
    with pytest.raises(ValueError,match='CUMULATIVE'):delta.publish(writer,target,original,os.environ.copy())
    assert git('ls-remote','origin',private.STATE_REF,cwd=writer).split()[0]==original
    monkeypatch.setattr(op,'STATE_HISTORY_LIMIT',64*1024**2)
    receipt=delta.publish(writer,target,original,os.environ.copy());commit=receipt['commit']
    for branch in ['main','data']:assert git('ls-remote','origin','refs/heads/'+branch,cwd=writer).split()[0]==original
    def read(name):return subprocess.check_output(['git','-C',str(writer),'show',commit+':'+name])
    damaged=tmp_path/'damaged';damaged.mkdir();manifest=json.loads(read(delta.HEAD))
    for name in ['checkpoint.json','checkpoint.sqlite3.gz',delta.HEAD]+delta.names(manifest):
        p=damaged/name;p.parent.mkdir(exist_ok=True);p.write_bytes(read(name))
    first=damaged/delta.names(manifest)[0];first.write_bytes(b'invalid patch')
    before=file_sha(damaged/'checkpoint.sqlite3.gz')
    with pytest.raises(ValueError,match='PATCH_HASH'):delta.materialize(damaged,tmp_path/'incomplete')
    assert not(tmp_path/'incomplete').exists()and file_sha(damaged/'checkpoint.sqlite3.gz')==before
