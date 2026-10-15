"""Offline storage/permission tests; no GitHub scope or scheduled-operation claim."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from bct.v4 import cpu_operations as op,private_state as private
from bct.v4.cpu_automation import open_queue,ingest_delta
from bct.v4.store import sha

REPO=Path(__file__).resolve().parents[1]
TEST_PASSPHRASE='synthetic-local-transport-fixture-'*2


def checkpoint(tmp_path):
    ledger=open_queue(tmp_path/'queue')
    with ledger.db:ledger.event('SYNTHETIC_STORAGE_TEST',{'not_a_real_source':'preserve me'})
    proof=op.checkpoint(ledger,tmp_path/'checkpoint');ledger.close()
    return tmp_path/'checkpoint',proof


def fake_scope_api(calls,*,denial=403,visible_private=True,private_count=1):
    def api(token,method,path,data=None):
        calls.append((method,path,data))
        if path=='repos/'+private.PRIVATE_REPO:return 200,{'private':visible_private,'full_name':private.PRIVATE_REPO}
        if path.startswith('user/repos?'):return 200,[{'full_name':private.PRIVATE_REPO}]*private_count
        if method=='GET':return 200,{'object':{'sha':'a'*40}}
        if path.endswith('/git/refs'):return denial,{}
        if path=='repos/'+private.PRIVATE_REPO+'/git/blobs':return 201,{}
        raise AssertionError('Unplanned API operation')
    return api


def test_scope_requires_private_identity_and_denial_on_both_operating_refs():
    calls=[];r=private.writer_scope('SYNTHETIC_NOT_A_KEY',api=fake_scope_api(calls))
    assert r['operating_ref_create_denials']=={'main':403,'data':403}
    writes=[c for c in calls if c[0]=='POST'and c[1].startswith('repos/'+private.PUBLIC_REPO)]
    assert [c[2]['ref']for c in writes]==['refs/heads/main','refs/heads/data']
    assert all(c[2]['sha']=='a'*40 for c in writes)


def test_broad_token_existing_ref_422_is_not_accepted_as_a_denial():
    calls=[]
    with pytest.raises(ValueError,match='WRITE_NOT_DENIED'):
        private.writer_scope('SYNTHETIC',api=fake_scope_api(calls,denial=422))
    assert not any(c[1].endswith('/git/blobs')for c in calls)


def test_token_with_more_than_one_private_repository_is_refused():
    calls=[]
    with pytest.raises(ValueError,match='SCOPE_NOT_EXCLUSIVE'):
        private.writer_scope('SYNTHETIC',api=fake_scope_api(calls,private_count=2))
    assert not any(c[0]=='POST'for c in calls)


def test_public_destination_is_refused_before_any_write():
    calls=[]
    with pytest.raises(ValueError,match='VISIBILITY'):
        private.writer_scope('SYNTHETIC',api=fake_scope_api(calls,visible_private=False))
    assert len(calls)==1


def test_missing_private_token_never_falls_back_to_existing_GH_TOKEN(monkeypatch):
    monkeypatch.setenv('GH_TOKEN','SYNTHETIC_BROAD_CREDENTIAL_MUST_NOT_BE_USED')
    monkeypatch.setattr(private,'urlopen',lambda *a,**k:pytest.fail('Must not contact GitHub with fallback auth'))
    with pytest.raises(ValueError,match='PRIVATE_STATE_CREDENTIAL_MISSING'):private.writer_scope('')
    malformed='synthetic-secret-containing\nnewline'
    with pytest.raises(ValueError,match='CREDENTIAL_FORMAT_INVALID')as exc:
        private.github_api(malformed,'GET','repos/'+private.PRIVATE_REPO)
    assert malformed not in str(exc.value)


def test_ciphertext_handoff_restores_exact_tables_and_rejects_tampering(tmp_path):
    source,proof=checkpoint(tmp_path)
    out=tmp_path/'encrypted/state.gpg'
    private.seal(source,out,TEST_PASSPHRASE,'a'*40)
    assert b'preserve me'not in out.read_bytes()and b'SQLite format'not in out.read_bytes()
    r=private.unseal(out,tmp_path/'restored-packet',TEST_PASSPHRASE)
    assert r['expected_parent']=='a'*40
    assert json.loads((tmp_path/'restored-packet/checkpoint.json').read_text())==proof
    restored=op.restore(tmp_path/'restored-packet',tmp_path/'new-process-db')
    assert restored['sqlite_sha256']==proof['sqlite_sha256']
    p=subprocess.run([sys.executable,str(REPO/'tools/v4_cpu_private.py'),'unseal',
        '--packet',str(out),'--checkpoint',str(tmp_path/'fresh-process-packet')],cwd=REPO,
        env={**os.environ,'BCT_V4_STATE_PASSPHRASE':TEST_PASSPHRASE},capture_output=True,text=True,timeout=25)
    assert p.returncode==0,p.stderr
    assert json.loads((tmp_path/'fresh-process-packet/checkpoint.json').read_text())==proof
    assert TEST_PASSPHRASE not in p.stdout+p.stderr
    with pytest.raises(ValueError,match='AUTHENTICATION'):
        private.unseal(out,tmp_path/'wrong-key','different-synthetic-local-transport-fixture-'*2)
    broken=bytearray(out.read_bytes());broken[-20]^=1;out.write_bytes(broken)
    with pytest.raises(ValueError,match='AUTHENTICATION'):
        private.unseal(out,tmp_path/'bad-packet',TEST_PASSPHRASE)
    assert not(tmp_path/'bad-packet').exists()


def test_unknown_archival_terms_block_before_credentials_or_git(tmp_path):
    original=tmp_path/'original';original.mkdir()
    proof=json.loads((REPO/'docs/v4/cpu-automation/storage-proof.json').read_text())['ledger']
    proof={**proof,'archive':'checkpoint.sqlite3.gz'}
    (original/'checkpoint.json').write_text(json.dumps(proof))
    (original/'checkpoint.sqlite3.gz').write_bytes((REPO/'docs/v4/cpu-automation/ledger.sqlite3.gz').read_bytes())
    audit=op.checkpoint_storage_audit(original,scope='private')
    assert audit['status']=='BLOCKED'and len(audit['documents'])==3
    with pytest.raises(ValueError,match='PRIVATE_ARCHIVAL_REVIEW_BLOCKED'):
        private.publish(tmp_path/'git',original,'','',{},api=lambda *a:pytest.fail('No credential/network operation'))


def test_private_storage_is_not_public_redistribution_permission(tmp_path):
    l=open_queue(tmp_path/'queue');raw=b'<p>Synthetic test source.</p>';body='Synthetic test source.'
    d={'document_id':'fixture','body':body,'body_sha256':sha(body.encode()),'raw_sha256':sha(raw),'origin_url':'https://example.org/test'}
    l.capture(d,raw);op.checkpoint(l,tmp_path/'snapshot');l.close()
    policy={'sources':{'fixture':{'raw_sha256':sha(raw),'body_sha256':sha(body.encode()),
        'private_archival':'PERMITTED','privacy_review':'CLEARED','rights_basis':'Synthetic fixture','reviewed_by':'Test author'}}}
    assert op.checkpoint_storage_audit(tmp_path/'snapshot',policy,scope='private')['status']=='PASS_PRIVATE_STORAGE_REVIEW'
    assert op.public_checkpoint_audit(tmp_path/'snapshot',policy)['status']=='BLOCKED'


def test_unapproved_new_source_is_isolated_without_capturing_raw(tmp_path):
    cache=tmp_path/'cache';(cache/'documents').mkdir(parents=True);(cache/'raw').mkdir()
    body='Atlas ordered novel pumps in this synthetic storage test.';raw=('<article><p>'+body+'</p></article>').encode()
    doc={'document_id':'unapproved','origin_url':'https://example.org/new','raw_sha256':sha(raw),'body_sha256':sha(body.encode()),
         'body':body,'raw_path':sha(raw)+'.html','published_at':'2026-10-01','acquired_at':'2026-10-02',
         'provenance':'PASS','provenance_verified':True,'checks':{'http_success':True}}
    (cache/'raw'/doc['raw_path']).write_bytes(raw)
    (cache/'documents/doc.json').write_text(json.dumps(doc))
    manifest={'format':'bct-new-rss-delta-v1','documents':[{'document_id':'unapproved','url':doc['origin_url']}]}
    l=open_queue(tmp_path/'queue')
    result=ingest_delta(l,manifest,cache,upstream_run_id='fixture',storage_policy={})
    assert result[0]['reason']=='PRIVATE_ARCHIVAL_OR_PRIVACY_UNREVIEWED'
    assert l.db.execute('SELECT count(*) FROM documents').fetchone()==(0,)
    assert l.db.execute('SELECT count(*) FROM blobs').fetchone()==(0,)
    assert ingest_delta(l,manifest,cache,upstream_run_id='fixture',storage_policy={})[0]['status']=='ALREADY_IMPORTED'
    approved={'sources':{'unapproved':{'raw_sha256':sha(raw),'body_sha256':sha(body.encode()),
        'private_archival':'PERMITTED','privacy_review':'CLEARED','rights_basis':'Synthetic fixture','reviewed_by':'Test author'}}}
    result=ingest_delta(l,manifest,cache,upstream_run_id='fixture',storage_policy=approved)
    assert result[0]['status']=='QUEUED'and result[0]['reconsidered_after_private_review_change']
    assert ingest_delta(l,manifest,cache,upstream_run_id='fixture',storage_policy=approved)[0]['status']=='ALREADY_IMPORTED'
    l.close()


@pytest.mark.parametrize('condition',['good','stale','failed','rerun'])
def test_old_bridge_cannot_trigger_duplicate_cpu_after_unconfirmed_publication(monkeypatch,condition):
    monkeypatch.setenv('GITHUB_WORKFLOW_REF',private.PUBLIC_REPO+'/.github/workflows/consumer.yml@refs/heads/main')
    monkeypatch.setenv('GITHUB_RUN_ID','20')
    parent={'producer_job':'publish','producer_run_id':'10','producer_attempt':'1'}
    run={'id':10,'status':'completed','conclusion':'success','run_attempt':1}
    if condition=='stale':run['id']=11
    if condition=='failed':run['conclusion']='failure'
    if condition=='rerun':run['run_attempt']=2
    read=lambda p:{'workflow_runs':[{'id':21,'status':'queued'},run]}
    if condition=='good':assert private.verify_predecessor(parent,read=read)['verified_before_CPU']
    else:
        with pytest.raises(ValueError,match='PUBLICATION_UNCONFIRMED'):private.verify_predecessor(parent,read=read)


def test_private_git_uses_existing_CAS_and_restores_remote_before_clock_ack(tmp_path):
    def git(*args,cwd=None):return subprocess.check_output(['git',*args],cwd=cwd,stderr=subprocess.DEVNULL,text=True).strip()
    bare=tmp_path/'private.git';repo=tmp_path/'writer';git('init','--bare',str(bare));git('init',str(repo))
    git('remote','add','origin',private.PRIVATE_URL,cwd=repo)
    git('config','url.'+bare.as_uri()+'.insteadOf',private.PRIVATE_URL,cwd=repo)
    source,_=checkpoint(tmp_path)
    first=private.publish(repo,source,'','SYNTHETIC_NOT_A_KEY',{},api=fake_scope_api([]))
    assert first['remote_restore_verified']and first['persistence_receipt']['seven_day_start']is None
    assert git('rev-list','--count',op.STATE_REF,cwd=bare)=='2'
    # Synthetic acknowledged read tests storage timing, NOT actual discovery.
    l=open_queue(tmp_path/'queue')
    with l.db:l.event('CPU_OPERATION_OBSERVATION',{'scheduled_execution_verified':True,
        'successful_new_CPU_windows':1,'actually_read_new_characters':12,'private_persistence_required':True})
    op.checkpoint(l,tmp_path/'second');l.close()
    second=private.publish(repo,tmp_path/'second',first['commit'],'SYNTHETIC_NOT_A_KEY',{},api=fake_scope_api([]))
    assert second['persistence_receipt']['seven_day_start']
    assert second['persistence_receipt']['seven_day_status']=='OBSERVING_NOT_COMPLETED'
    receipt=json.loads(git('show',op.STATE_REF+':private-persistence.json',cwd=bare))
    assert receipt==second['persistence_receipt']
    assert git('rev-list','--count',op.STATE_REF,cwd=bare)=='4'
    assert 'SYNTHETIC_NOT_A_KEY'not in (repo/'.git/config').read_text()
    with pytest.raises(ValueError,match='PARENT_CHANGED'):
        private.publish(repo,source,first['commit'],'SYNTHETIC_NOT_A_KEY',{},api=fake_scope_api([]))


def test_private_workflow_separates_write_auth_and_only_caches_ciphertext():
    w=yaml.safe_load((REPO/'docs/v4/cpu-automation/preflight/activation-change.yml.proposed').read_text())
    assert w['permissions']=={'contents':'read','actions':'read'}
    reader=json.dumps(w['jobs']['research']);writer=json.dumps(w['jobs']['publish'])
    assert 'BCT_V4_PRIVATE_STATE_TOKEN'not in reader and 'BCT_V4_PRIVATE_STATE_TOKEN'in writer
    assert all(j['runs-on']=='ubuntu-24.04'for j in w['jobs'].values())
    for job in w['jobs'].values():
        for step in job['steps']:
            if step.get('uses','').startswith('actions/cache/save'):
                assert step['with']['path']in ['var/v4/cpu-private/result','var/v4/cpu-private/bridge']
            assert 'pip install'not in step.get('run','')
            assert 'bootstrap-model'not in step.get('run','')
            assert 'upload-artifact'not in step.get('uses','')
