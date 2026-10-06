"""Synthetic storage/binding safety; not semantic or performance evaluation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

s=load('evaluation_state','tools/review_evaluation_state.py')
a=s.observer


def test_approved_document_binding_and_limits():
    m=a.validate_approved('review-leads/evaluation-a')
    epoch={'version':m['version'],'preregistration_sha256':m['preregistration_sha256'],
      'main_sha':'a'*40,'t0':'2026-10-06T02:00:00Z','epoch':'synthetic-test',
      'formal_evaluation_started':False,'B_stage_started':False,
      'server_event':{'id':123,'event':'push','head_branch':'main','head_sha':'a'*40,
                      'created_at':'2026-10-06T02:00:00Z'}}
    assert a.validate_epoch(epoch)==epoch
    bad={**epoch,'t0':'2026-10-01T02:00:00Z'}
    with pytest.raises(ValueError,match='SERVER_EVENT'):a.validate_epoch(bad)
    with pytest.raises(ValueError,match='B_NOT_APPROVED'):a.validate_epoch({**epoch,'B_stage_started':True})


def test_real_git_restore_keeps_last_observer_and_append_only(tmp_path,monkeypatch):
    remote=tmp_path/'remote.git';repo=tmp_path/'repo';repo.mkdir()
    subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
    subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(repo),'remote','add','origin',str(remote)],check=True)
    monkeypatch.chdir(repo)
    # Synthetic Git storage fixture; approved binding has a separate test above.
    monkeypatch.setattr(a,'validate_epoch',lambda value:value)
    root=repo/'evaluation-a';(root/'reports').mkdir(parents=True)
    (root/'epoch.json').write_text('{"synthetic":true}')
    report=root/'reports'/'1.json';report.write_text(json.dumps({'observed_at':'2026-10-06T02:00:00Z','observer_run_id':'1'}))
    s.checkpoint(root,report);first=s.persist(root,'')
    clone=tmp_path/'reader';clone.mkdir()
    subprocess.run(['git','init',str(clone)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(clone),'remote','add','origin',str(remote)],check=True)
    monkeypatch.chdir(clone);restored=clone/'evaluation-a'
    assert s.restore(restored)==first
    previous=json.loads(s.prior(restored).read_text())
    assert previous['observed_at']=='2026-10-06T02:00:00Z'
    # Collector attaches persisted previous time rather than resetting UNKNOWN.
    monkeypatch.setattr(a,'api',lambda path:{'access':'BLOCKED','reason':'synthetic','http_status':403})
    monkeypatch.setattr(a,'runs',lambda wf:{'access':'PASS','runs':[],'complete':True,'total_count':0})
    monkeypatch.setattr(a,'read_state',lambda:{'access':'ABSENT','metrics':'UNKNOWN'})
    class P:
        returncode=1;stdout=b'';stderr=b''
    old=a.subprocess.run;oldout=a.subprocess.check_output
    monkeypatch.setattr(a.subprocess,'run',lambda *args,**kwargs:P())
    monkeypatch.setattr(a.subprocess,'check_output',lambda *args,**kwargs:'unknown')
    # Supply isolated fixed code fingerprint sources and schedule for the collector.
    for path in ('src/bct/review_intake.py','src/bct/review_shadow.py','src/bct/review_leads.py',
                 'review-leads/contract.json','BCT_OBJECTIVE_LOCK.md'):
        p=clone/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('synthetic')
    p=clone/'.github/workflows/rss-live-check.yml';p.parent.mkdir(parents=True,exist_ok=True);p.write_text("cron: '0 10 * * *'")
    observation=a.collect('2',previous)
    assert observation['last_observer_execution_at']=='2026-10-06T02:00:00Z'
    monkeypatch.setattr(a.subprocess,'run',old);monkeypatch.setattr(a.subprocess,'check_output',oldout)
    next_report=restored/'reports'/'2.json';next_report.write_text(json.dumps(observation))
    s.checkpoint(restored,next_report);second=s.persist(restored,first)
    assert second!=first and json.loads(s.prior(restored).read_text())['observer_run_id']=='2'
    with pytest.raises(ValueError,match='CAS'):s.persist(restored,first)
    (restored/'reports'/'1.json').write_text('changed')
    with pytest.raises(ValueError,match='IMMUTABLE'):s.persist(restored,second)
    refs=s.git('ls-remote','origin')
    assert a.STATE_REF in refs
    assert all(ref not in refs for ref in ('refs/heads/main','refs/heads/data','refs/heads/live-state','refs/heads/review-lead-shadow-state'))


def test_foreign_state_and_operational_ref_rejected():
    assert not s.valid_path('evaluation-a/reports/../../data/file.json')
    assert not s.valid_path('live-state/session.json')
    for ref in ('refs/heads/main','refs/heads/data','refs/heads/live-state','refs/heads/review-lead-shadow-state'):
        with pytest.raises(ValueError):a.validate_state_ref(ref)


def test_observer_is_main_only_independent_and_no_alarm():
    import yaml
    wf=yaml.safe_load(Path('.github/workflows/review-evaluation-observer.yml').read_text())
    assert wf['permissions']=={'contents':'write','actions':'read'}
    assert wf['concurrency']['group']=='review-lead-evaluation-state'
    assert wf['jobs']['observe']['if']=="github.ref == 'refs/heads/main'"
    text=Path('.github/workflows/review-evaluation-observer.yml').read_text()
    assert '--prior-report' in text and 'workflow_run:' not in text and 'pull_request:' not in text
    assert 'BCT_REVIEW_SHADOW_ENABLED' not in text
    assert 'new_precursor_cycle.py' not in text and 'review_shadow run' not in text
