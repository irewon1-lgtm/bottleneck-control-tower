"""Only API-proven inert automatic jobs may sit between a bridge and reader."""
from copy import deepcopy
import re

import pytest

from bct.v4 import private_state as private

WORKFLOW='v4-cpu-private-research.yml'
PARENT={'producer_job':'publish','producer_run_id':'10','producer_attempt':'1'}


def skipped_run(run_id=20):
    return {'id':run_id,'run_attempt':1,'name':'V4 CPU private research consumer','workflow_id':42,
        'path':'.github/workflows/'+WORKFLOW,'event':'workflow_run','status':'completed','conclusion':'skipped',
        'head_branch':'main','head_sha':'b'*40,'repository':{'id':1,'full_name':private.PUBLIC_REPO},
        'head_repository':{'id':1,'full_name':private.PUBLIC_REPO}}


def skipped_jobs(run):
    return {'total_count':2,'jobs':[{'id':run['id']*10+n,'run_id':run['id'],'run_attempt':1,
        'workflow_name':run['name'],'head_branch':'main','head_sha':run['head_sha'],'name':name,
        'status':'completed','conclusion':'skipped','steps':[],
        'run_url':f'https://api.github.com/repos/{private.PUBLIC_REPO}/actions/runs/{run["id"]}'}
        for n,name in enumerate(('research','publish'))]}


@pytest.fixture
def evidence(monkeypatch):
    monkeypatch.setenv('GITHUB_WORKFLOW_REF',private.PUBLIC_REPO+'/.github/workflows/'+WORKFLOW+'@refs/heads/main')
    monkeypatch.setenv('GITHUB_RUN_ID','30')
    inert=skipped_run();publisher={'id':10,'run_attempt':1,'status':'completed','conclusion':'success'}
    data={'runs':[inert,publisher],'attempt':deepcopy(inert),'latest':deepcopy(inert),'jobs':skipped_jobs(inert),'calls':[]}
    def read(path):
        data['calls'].append(path)
        if '/actions/workflows/' in path:return {'workflow_runs':data['runs']}
        if re.search(r'/attempts/1/jobs\?per_page=100$',path):return data['jobs']
        if path.endswith('/attempts/1'):return data['attempt']
        if path.endswith('/actions/runs/20'):return data['latest']
        raise AssertionError('Unexpected metadata endpoint: '+path)
    return data,read


def test_bridge_a_then_failed_upstream_inert_b_then_valid_c_resumes_without_model(evidence):
    data,read=evidence
    result=private.verify_predecessor(PARENT,read=read)
    assert result['verified_before_CPU'] and result['previous_publisher_run']==10
    proof,=result['ignored_inert_automatic_runs']
    assert proof['run_id']==20 and proof['run_attempt']==1 and proof['jobs']==2
    assert re.fullmatch('[0-9a-f]{64}',proof['evidence_sha256'])
    assert any('/attempts/1/jobs?per_page=100' in path for path in data['calls'])


@pytest.mark.parametrize('change',[
    'manual','other_branch','failed','success_nonpublisher','wrong_repo','wrong_path','missing_head',
    'executed_research','hidden_publisher','unknown_job','missing_publish','missing_steps','unbound_job',
    'job_in_progress','job_wrong_head','job_wrong_run','job_wrong_attempt','attempt_wrong_head',
    'latest_rerun','latest_failed','pagination_gap','duplicate_jobs','job_attempt_bool','assigned_runner'])
def test_unknown_or_executed_work_never_becomes_a_skipped_proof(evidence,change):
    data,read=evidence;run=data['runs'][0];jobs=data['jobs']['jobs']
    if change=='manual':run['event']='workflow_dispatch'
    elif change=='other_branch':run['head_branch']='dev'
    elif change=='failed':run['conclusion']='failure'
    elif change=='success_nonpublisher':run['conclusion']='success'
    elif change=='wrong_repo':run['head_repository']['full_name']='untrusted/fork'
    elif change=='wrong_path':run['path']='.github/workflows/unrelated.yml'
    elif change=='missing_head':run.pop('head_sha')
    elif change=='executed_research':jobs[0].update(conclusion='success',steps=[{'conclusion':'success'}])
    elif change=='hidden_publisher':
        data['jobs']['jobs'].append({**jobs[1],'id':999,'name':'hidden-publisher','conclusion':'success'});data['jobs']['total_count']=3
    elif change=='unknown_job':jobs[0]['name']='unknown-job'
    elif change=='missing_publish':jobs.pop();data['jobs']['total_count']=1
    elif change=='missing_steps':jobs[0].pop('steps')
    elif change=='unbound_job':jobs[0].pop('run_url')
    elif change=='job_in_progress':jobs[0]['status']='in_progress'
    elif change=='job_wrong_head':jobs[0]['head_sha']='c'*40
    elif change=='job_wrong_run':jobs[0]['run_id']=21
    elif change=='job_wrong_attempt':jobs[0]['run_attempt']=2
    elif change=='attempt_wrong_head':data['attempt']['head_sha']='c'*40
    elif change=='latest_rerun':data['latest']['run_attempt']=2
    elif change=='latest_failed':data['latest']['conclusion']='failure'
    elif change=='pagination_gap':data['jobs']['total_count']=3
    elif change=='duplicate_jobs':jobs[1]=deepcopy(jobs[0])
    elif change=='job_attempt_bool':jobs[0]['run_attempt']=True
    elif change=='assigned_runner':jobs[0]['runner_id']=99
    with pytest.raises(ValueError):private.verify_predecessor(PARENT,read=read)


def test_absent_bridge_in_bounded_lookback_remains_blocked(evidence):
    data,read=evidence;data['runs']=data['runs'][:1]
    with pytest.raises(ValueError):private.verify_predecessor(PARENT,read=read)


def test_exhausted_metadata_budget_remains_blocked(evidence,monkeypatch):
    _,read=evidence
    values=iter([0,46])
    monkeypatch.setattr(private.time,'monotonic',lambda:next(values,46))
    with pytest.raises(ValueError,match='BUDGET_EXHAUSTED'):private.verify_predecessor(PARENT,read=read)


def test_optional_repository_metadata_does_not_change_bound_identity(evidence):
    data,read=evidence
    data['attempt']['repository']['description']='Optional API enrichment'
    data['latest']['head_repository']['description']='Different optional API enrichment'
    assert private.verify_predecessor(PARENT,read=read)['verified_before_CPU']


def test_multiple_inert_runs_beyond_old_five_run_window_can_resume(monkeypatch):
    monkeypatch.setenv('GITHUB_WORKFLOW_REF',private.PUBLIC_REPO+'/.github/workflows/'+WORKFLOW+'@refs/heads/main')
    monkeypatch.setenv('GITHUB_RUN_ID','1000')
    runs=[skipped_run(n) for n in range(29,19,-1)]
    publisher={'id':10,'run_attempt':1,'status':'completed','conclusion':'success'}
    calls=[]
    def read(path):
        calls.append(path)
        if '/actions/workflows/' in path:return {'workflow_runs':runs+[publisher]}
        run_id=int(re.search(r'/actions/runs/(\d+)',path)[1]);run=next(r for r in runs if r['id']==run_id)
        return skipped_jobs(run) if '/jobs?' in path else run
    result=private.verify_predecessor(PARENT,read=read)
    assert len(result['ignored_inert_automatic_runs'])==10
    assert calls[0].endswith('per_page=100') and len(calls)==31


def test_inert_proof_survives_sourcefree_export_restore_and_public_projection(tmp_path,evidence):
    import importlib.util,json,subprocess
    from pathlib import Path
    from bct.v4 import cpu_automation as q,cpu_operations as op,cpu_resume as resume
    from test_v4_public_bridge_continuity import acknowledged
    _,read=evidence;proof=private.verify_predecessor(PARENT,read=read)
    fixture=tmp_path/'ack';fixture.mkdir()
    repo,_,_=acknowledged(fixture)
    ledger=q.open_queue(fixture/'safe')
    with ledger.db:ledger.event('CPU_OPERATION_OBSERVATION',{'upstream':{'bridge_predecessor_proof':proof}})
    ledger.close();resume.export_state(fixture/'safe/v4.sqlite3',tmp_path/'separated')
    ledger=q.open_queue(tmp_path/'separated');resume.audit(ledger);op.checkpoint(ledger,tmp_path/'packet');ledger.close()
    op.restore(tmp_path/'packet',tmp_path/'restored')
    ledger=q.open_queue(tmp_path/'restored');resume.audit(ledger)
    observed=json.loads(ledger.db.execute("SELECT payload FROM events WHERE kind='CPU_OPERATION_OBSERVATION'").fetchone()[0])
    assert observed['upstream']['bridge_predecessor_proof']==proof
    packet=tmp_path/'public-packet';checkpoint=op.checkpoint(ledger,packet);ledger.close()
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL).decode().strip()
    for name in ('checkpoint.json','checkpoint.sqlite3.gz'):(repo/name).write_bytes((packet/name).read_bytes())
    git('add','.');git('commit','-m','Fixture progress preserves inert proof')
    ack=json.loads((repo/'private-persistence.json').read_text());ack.update(checkpoint_commit=git('rev-parse','HEAD'),sqlite_sha256=checkpoint['sqlite_sha256'])
    (repo/'private-persistence.json').write_text(json.dumps(ack));git('add','.');git('commit','-m','Fixture ACK')
    git('fetch','.',git('rev-parse','HEAD'))
    path=Path(__file__).resolve().parents[1]/'tools/v4_public_research_snapshot.py'
    spec=importlib.util.spec_from_file_location('guard_public_fixture',path);writer=importlib.util.module_from_spec(spec);spec.loader.exec_module(writer)
    writer.emit(repo,None,tmp_path/'public',{'run_id':99,'run_attempt':1,'workflow_sha':'c'*40,'execution_sha':'b'*40})
    public=json.loads((tmp_path/'public/snapshot.json').read_text())
    assert public['proof']['new_process_restore_verified'] and public['counts']['new_CPU_windows']==0
    assert 'bridge_predecessor_proof' not in json.dumps(public)
