"""Public-only recovery forwards identical ACK bytes without advancing research."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

from bct.v4 import cpu_automation as q,cpu_operations as op,cpu_resume as resume,private_state as private


def acknowledged(tmp_path):
    ledger=q.open_queue(tmp_path/'safe')
    with ledger.db:ledger.db.execute("INSERT INTO metadata VALUES('cpu_source_separated_format',?)",(resume.FORMAT,))
    proof=op.checkpoint(ledger,tmp_path/'checkpoint');ledger.close()
    repo=tmp_path/'private';repo.mkdir()
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL).decode().strip()
    git('init');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
    git('remote','add','origin',private.PRIVATE_URL)
    for name in ('checkpoint.json','checkpoint.sqlite3.gz'):(repo/name).write_bytes((tmp_path/'checkpoint'/name).read_bytes())
    git('add','.');git('commit','-m','Original checkpoint')
    receipt={'version':'bct-private-persistence-1','checkpoint_commit':git('rev-parse','HEAD'),
        'sqlite_sha256':proof['sqlite_sha256'],'remote_restored_at':'2026-11-11T12:00:00+00:00',
        'publisher_run_id':10,'publisher_attempt':1,'publisher_workflow_sha':'a'*40,'publisher_execution_sha':'b'*40}
    (repo/'private-persistence.json').write_text(json.dumps(receipt));git('add','.');git('commit','-m','Original ACK')
    commit=git('rev-parse','HEAD');git('fetch','.',commit)
    spec=importlib.util.spec_from_file_location('public_writer_continuity',Path(__file__).resolve().parents[1]/'tools/v4_public_research_snapshot.py')
    writer=importlib.util.module_from_spec(spec);spec.loader.exec_module(writer)
    writer.emit(repo,None,tmp_path/'public',{'run_id':20,'run_attempt':1,'workflow_sha':'c'*40,'execution_sha':'b'*40})
    return repo,commit,proof


def test_a_ack_public_recovery_b_forwarded_bridge_allows_c_without_new_research(tmp_path,monkeypatch):
    repo,commit,proof=acknowledged(tmp_path)
    before=(tmp_path/'public/snapshot.json').read_bytes()
    result=private.prepare_public_bridge(repo,tmp_path/'public/snapshot.json',tmp_path/'forwarded')
    assert result['commit']==commit and result['sqlite_sha256']==proof['sqlite_sha256']
    assert result['new_CPU_windows']==result['private_CAS_writes']==0
    for name in ('checkpoint.json','checkpoint.sqlite3.gz'):
        assert (tmp_path/'forwarded'/name).read_bytes()==(tmp_path/'checkpoint'/name).read_bytes()
    monkeypatch.setenv('GITHUB_RUN_ID','20');monkeypatch.setenv('GITHUB_RUN_ATTEMPT','1');monkeypatch.setenv('GITHUB_JOB','publish')
    private.seal(tmp_path/'forwarded',tmp_path/'bridge/state.gpg','synthetic-only-passphrase-for-fixture-0123456789',commit)
    private.unseal(tmp_path/'bridge/state.gpg',tmp_path/'next','synthetic-only-passphrase-for-fixture-0123456789')
    parent=json.loads((tmp_path/'next/parent.json').read_text())
    assert parent['expected_parent']==commit and parent['producer_run_id']=='20'
    monkeypatch.setenv('GITHUB_WORKFLOW_REF',private.PUBLIC_REPO+'/.github/workflows/consumer.yml@refs/heads/main')
    monkeypatch.setenv('GITHUB_RUN_ID','30')
    metadata=lambda path:{'workflow_runs':[{'id':30,'status':'queued'}, {'id':20,'status':'completed','conclusion':'success','run_attempt':1}]}
    assert private.verify_predecessor(parent,read=metadata)['verified_before_CPU']
    assert (tmp_path/'public/snapshot.json').read_bytes()==before


def test_unverified_public_recovery_never_prepares_or_reseals_bridge(tmp_path):
    repo,_,_=acknowledged(tmp_path)
    snapshot=tmp_path/'public/snapshot.json';value=json.loads(snapshot.read_text());value['generation']['sqlite_sha256']='0'*64
    snapshot.write_text(json.dumps(value))
    with pytest.raises(ValueError):private.prepare_public_bridge(repo,snapshot,tmp_path/'forwarded')
    assert not (tmp_path/'forwarded').exists() and not (tmp_path/'bridge').exists()
