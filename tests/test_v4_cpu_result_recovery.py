"""Exact failed-result recovery is storage work, never new CPU reading."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from bct.v4 import cpu_automation as q, cpu_operations as op, cpu_resume as resume, private_state as private
from bct.v4.store import sha
from test_v4_cpu_automation import document, Extractor

RUN=43060982183
ATTEMPT=1
WORKFLOW_SHA='41b1f74931f86f9c6d9f243be741efa0bfe68a04'
EXECUTION_SHA='58817b1fed0791e2a4ac591b1e684cab8e7f3b61'
PARENT='662060fbc29eacce875bd6fff7910cdb5fd72745'
PASSPHRASE='synthetic-author-owned-result-recovery-fixture-'*2
REPO=Path(__file__).resolve().parents[1]


def module():
    assert importlib.util.find_spec('bct.v4.cpu_result_recovery'), 'Authenticated saved CPU result recovery is missing'
    from bct.v4 import cpu_result_recovery
    return cpu_result_recovery


def metadata():
    run={'id':RUN,'run_attempt':1,'event':'workflow_dispatch','head_branch':'main',
         'head_sha':WORKFLOW_SHA,'head_repository':{'full_name':private.PUBLIC_REPO},
         'path':'.github/workflows/v4-cpu-private-research.yml','status':'completed','conclusion':'failure'}
    jobs={'total_count':3,'jobs':[
        {'id':130663160270,'name':'research','status':'completed','conclusion':'success','run_id':RUN},
        {'id':130663163145,'name':'runtime-verify','status':'completed','conclusion':'skipped','run_id':RUN},
        {'id':130663731583,'name':'publish','status':'completed','conclusion':'failure','run_id':RUN}]}
    cache={'total_count':1,'actions_caches':[{'id':10365971981,'key':f'v4-cpu-private-result-{RUN}-1',
        'ref':'refs/heads/main','size_in_bytes':1064174}]}
    return run,jobs,cache


def reader(run=None,jobs=None,cache=None):
    r,j,c=metadata();r=run or r;j=jobs or j;c=cache or c
    calls=[]
    def read(path):
        calls.append(path)
        if path.endswith('/jobs?per_page=100'):return deepcopy(j)
        if '/actions/caches?'in path:return deepcopy(c)
        if '/actions/runs/'in path:return deepcopy(r)
        raise AssertionError('Unplanned metadata endpoint')
    return read,calls


def test_exact_failed_main_run_and_cache_identity_produces_only_original_cache_key():
    read,calls=reader();proof=module().verify(RUN,ATTEMPT,read=read)
    assert proof['status']=='PASS_EXACT_FAILED_RESEARCH_RESULT_METADATA'
    assert proof['cache_key']==f'v4-cpu-private-result-{RUN}-1'
    assert proof['original_execution_sha']==EXECUTION_SHA and proof['original_expected_parent']==PARENT
    assert proof['new_CPU_windows']==0 and proof['model_loads']==0
    assert len(calls)>=4 and calls[0]==calls[-1]


@pytest.mark.parametrize('run_id,attempt',[(RUN+1,1),(RUN,2),('43060982183',1),(True,1)])
def test_other_or_ambiguous_requests_never_access_cache_or_network(run_id,attempt):
    with pytest.raises(ValueError,match='EXACT_AUTHORIZED_RESULT'):
        module().verify(run_id,attempt,read=lambda _:pytest.fail('Reject before metadata'))


@pytest.mark.parametrize('changes',[
    {'conclusion':'success'},{'status':'in_progress'},{'head_branch':'feature'},
    {'head_sha':'a'*40},{'head_repository':{'full_name':'untrusted/fork'}},
    {'run_attempt':2},{'run_attempt':True},{'path':'.github/workflows/another.yml'},
])
def test_producer_mismatch_blocks_before_plaintext_or_publish(changes):
    run,jobs,cache=metadata();run.update(changes);read,_=reader(run,jobs,cache)
    with pytest.raises(ValueError,match='RESULT_PRODUCER'):module().verify(RUN,ATTEMPT,read=read)


@pytest.mark.parametrize('failure', ['research_not_success','publisher_not_failed','duplicate_job','cache_other_ref','cache_other_id','cache_other_size','missing_cache'])
def test_result_cannot_come_from_wrong_job_or_cache(failure):
    run,jobs,cache=metadata()
    if failure=='research_not_success':jobs['jobs'][0]['conclusion']='failure'
    elif failure=='publisher_not_failed':jobs['jobs'][2]['conclusion']='success'
    elif failure=='duplicate_job':jobs['jobs'].append(deepcopy(jobs['jobs'][0]));jobs['total_count']=4
    elif failure=='cache_other_ref':cache['actions_caches'][0]['ref']='refs/heads/feature'
    elif failure=='cache_other_id':cache['actions_caches'][0]['id']+=1
    elif failure=='cache_other_size':cache['actions_caches'][0]['size_in_bytes']+=1
    else:cache={'total_count':0,'actions_caches':[]}
    read,_=reader(run,jobs,cache)
    with pytest.raises(ValueError):module().verify(RUN,ATTEMPT,read=read)


def packet(tmp_path,monkeypatch,*,producer_job='research',parent=PARENT,observation_patch=None):
    # Source-free synthetic sealed fixture: does not call or load a real model.
    monkeypatch.setenv('GITHUB_RUN_ID',str(RUN));monkeypatch.setenv('GITHUB_RUN_ATTEMPT','1')
    monkeypatch.setenv('GITHUB_JOB',producer_job);monkeypatch.setenv('CPU_CODE_SHA',EXECUTION_SHA)
    monkeypatch.setenv('GITHUB_WORKFLOW_SHA',WORKFLOW_SHA)
    ledger=q.open_queue(tmp_path/'queue')
    observation={'consumer_run_id':RUN,'consumer_attempt':1,'execution_mode':'MANUAL_ACTUAL_INPUT',
        'scheduled':False,'new_CPU_windows':24,'successful_new_CPU_windows':24,
        'actually_read_new_characters':4114,'new_analysis_results':6,'analysis_runtime_failures':0,
        'complete_analyzed_new_CPU_documents':0,'seven_day_start':None}
    observation.update(observation_patch or {})
    with ledger.db:
        ledger.db.execute("INSERT INTO metadata VALUES('cpu_source_separated_format',?)",(resume.FORMAT,))
        ledger.event('CPU_OPERATION_OBSERVATION',observation)
        for n in range(24):
            ledger.event('CPU_RESUME_WINDOW',{'key':sha(['synthetic-window',n]),'CPU_spans':[],
                'inference_producer':{'run_id':RUN,'run_attempt':1,'execution_sha':EXECUTION_SHA,'workflow_sha':WORKFLOW_SHA}})
    op.checkpoint(ledger,tmp_path/'checkpoint');ledger.close()
    sealed=tmp_path/'state.gpg';private.seal(tmp_path/'checkpoint',sealed,PASSPHRASE,parent)
    return sealed


def test_authenticated_saved_windows_restore_without_model_and_keep_original_identity(tmp_path,monkeypatch):
    sealed=packet(tmp_path,monkeypatch);before=sealed.read_bytes();read,_=reader()
    proof=module().authenticate(RUN,1,sealed,tmp_path/'recovered',PASSPHRASE,read=read)
    assert sealed.read_bytes()==before
    assert proof['new_CPU_windows']==proof['model_loads']==0
    assert proof['restored_original_new_CPU_windows']==24
    parent=json.loads((tmp_path/'recovered/parent.json').read_text())
    assert parent['producer_run_id']==str(RUN) and parent['producer_job']=='research'
    assert parent['expected_parent']==PARENT
    script='from bct.v4 import cpu_operations as o,cpu_resume as r;import sys,json;o.restore(sys.argv[1],sys.argv[2]);l=r.Ledger(sys.argv[2]);print(json.dumps(r.audit(l)));l.close()'
    child=subprocess.run([sys.executable,'-c',script,str(tmp_path/'recovered'),str(tmp_path/'new-process')],
                         capture_output=True,text=True,timeout=30)
    assert child.returncode==0,child.stderr
    assert json.loads(child.stdout)['CPU_windows_preserved']==24
    assert PASSPHRASE not in json.dumps(proof)


@pytest.mark.parametrize('changes',[
    {'producer_job':'publish'},{'parent':'a'*40},
    {'observation_patch':{'consumer_run_id':RUN+1}},
    {'observation_patch':{'new_CPU_windows':0}},
    {'observation_patch':{'scheduled':True}},
])
def test_encrypted_but_wrong_producer_or_observation_never_becomes_publish_input(tmp_path,monkeypatch,changes):
    sealed=packet(tmp_path,monkeypatch,**changes);read,_=reader()
    with pytest.raises(ValueError):module().authenticate(RUN,1,sealed,tmp_path/'recovered',PASSPHRASE,read=read)
    assert not(tmp_path/'recovered').exists()


def test_recovery_workflow_excludes_research_and_uses_original_exact_result_cache():
    workflow=(REPO/'.github/workflows/v4-cpu-private-research.yml').read_text()
    assert 'recover-result' in workflow and 'result_run:'in workflow and 'result_attempt:'in workflow
    assert 'steps.recover.outputs.cache_key'in workflow
    assert 'Authenticate saved failed CPU result without rereading' in workflow
    publish=workflow.split('\n  publish:\n',1)[1].split('\n  q1-key:',1)[0]
    assert publish.count("inputs.purpose == 'recover-result'")>=7
    assert "inputs.purpose == 'recover-result'"not in workflow.split('\n  research:\n',1)[1].split('\n  publish:\n',1)[0].split('\n    runs-on:',1)[0]


def test_result_recovery_does_not_replace_packet_with_durable_bridge():
    import yaml
    data=yaml.safe_load((REPO/'.github/workflows/v4-cpu-private-research.yml').read_text())
    steps={row['name']:row for row in data['jobs']['publish']['steps'] if 'name'in row}
    durable=steps['Recover latest durable private state after incomplete forwarding']
    assert "recover-result"not in durable['if'], 'Saved new windows must not be replaced by old bridge state'
    public=steps['Fetch the existing ACK for public recovery without a private write']
    assert "recover-result"not in public['if']
