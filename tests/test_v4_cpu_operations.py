"""Preflight guard/storage/observations, never live prediction or7day results."""
from pathlib import Path
import json
import sqlite3
import subprocess
import sys

import pytest
import yaml

from bct.v4 import cpu_operations as op
from bct.v4.cpu_automation import open_queue
from bct.v4.store import sha

REPO=Path(__file__).resolve().parents[1]


def test_public_standard_minutes_free_and_cache_within_reserved_bound():
    r=op.free_guard({'full_name':'owner/repo','private':False,'visibility':'public'}, {'active_caches_size_in_bytes':0})
    assert r['minutes_remaining']=='N/A_PUBLIC_STANDARD_RUNNER_MINUTES_FREE'
    assert r['additional_artifact_uploads'] is False


@pytest.mark.parametrize('repo,usage,runner',[
 ({'private':True,'visibility':'private'},{'active_caches_size_in_bytes':0},'ubuntu-24.04'),
 ({'private':False,'visibility':'public'},{},'ubuntu-24.04'),
 ({'private':False,'visibility':'public'},{'active_caches_size_in_bytes':6*op.GIB},'ubuntu-24.04'),
 ({'private':False,'visibility':'public'},{'active_caches_size_in_bytes':0},'ubuntu-latest-large'),
])
def test_unknown_or_paid_possible_conditions_fail_closed(repo,usage,runner):
    with pytest.raises(ValueError):op.free_guard(repo,usage,runner=runner)


def test_github_runtime_identity_missing_never_assumed_free(monkeypatch):
    monkeypatch.delenv('GITHUB_REPOSITORY',raising=False)
    with pytest.raises(ValueError,match='WRONG_REPOSITORY'):op.github_guard()


def restore_baseline(root):
    result=subprocess.run([sys.executable,str(REPO/'tools/v4_cpu_automation.py'),
        '--restore',str(REPO/'docs/v4/cpu-automation/ledger.sqlite3.gz'),'--root',str(root)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_real_completed_queue_checkpoint_new_process_restore_no_model_load(tmp_path):
    restore_baseline(tmp_path/'queue');l=open_queue(tmp_path/'queue')
    class Forbidden:
        def extract_windows(self,*args,**kwargs):raise AssertionError('Completed input must not call model')
    r=op.observe(l,trigger='SYNTHETIC_PREFLIGHT_TEST',execute=True,extractor=Forbidden())
    assert r['new_CPU_windows']==0 and not r['model_loaded_by_queue']
    assert r['seven_day_start'] is None and r['queue']['completed_windows']==67
    proof=op.checkpoint(l,tmp_path/'checkpoint');before=op.table_digests(l.db);l.close()
    command=[sys.executable,str(REPO/'tools/v4_cpu_preflight.py'),'restore','--checkpoint',str(tmp_path/'checkpoint'),'--root',str(tmp_path/'restored')]
    r=json.loads(subprocess.check_output(command,cwd=REPO))
    assert r['tables']==8
    restored=open_queue(tmp_path/'restored');assert op.table_digests(restored.db)==before
    assert restored.db.execute("select count(*) from events where kind='CPU_OPERATION_OBSERVATION'").fetchone()==(1,)
    resumed=op.observe(restored,trigger='SECOND_DEVELOPMENT_RUN',execute=True,extractor=Forbidden())
    assert resumed['prior_observations']==1 and resumed['new_CPU_windows']==0
    assert resumed['seven_day_status'].startswith('NOT_RUN')
    assert restored.db.execute('select count(*) from firsts').fetchone()==(0,);restored.close()


def test_bad_checkpoint_not_silently_reset_or_replaced(tmp_path):
    restore_baseline(tmp_path/'queue');l=open_queue(tmp_path/'queue');op.checkpoint(l,tmp_path/'checkpoint');l.close()
    archive=tmp_path/'checkpoint/checkpoint.sqlite3.gz';archive.write_bytes(archive.read_bytes()+b'tampered')
    with pytest.raises(ValueError,match='HASH'):op.restore(tmp_path/'checkpoint',tmp_path/'fresh')
    assert not(tmp_path/'fresh/v4.sqlite3').exists()


def test_checkpoint_restore_refuses_existing_checkpoint_even_same_bytes(tmp_path):
    restore_baseline(tmp_path/'queue');l=open_queue(tmp_path/'queue');op.checkpoint(l,tmp_path/'checkpoint');l.close()
    before=sha((tmp_path/'queue/v4.sqlite3').read_bytes())
    with pytest.raises(ValueError,match='OVERWRITE'):op.restore(tmp_path/'checkpoint',tmp_path/'queue')
    assert sha((tmp_path/'queue/v4.sqlite3').read_bytes())==before


def test_user_supplied_schedule_word_cannot_start_seven_day_test(tmp_path):
    l=open_queue(tmp_path)
    r=op.observe(l,trigger='schedule',scheduled_for='2026-10-15T02:00:00Z')
    assert not r['scheduled_execution_verified'] and r['seven_day_start'] is None
    assert r['new_CPU_windows']==0 and r['API_calls']==0;l.close()


def test_runtime_verify_hash_does_not_download_or_load(tmp_path,monkeypatch):
    model=tmp_path/'models/gliner2-base-v1';model.mkdir(parents=True);(model/'file').write_bytes(b'known')
    manifest={'files':[{'path':'file','sha256':sha(b'known')}]}
    monkeypatch.setattr(op,'urlopen',lambda *a,**k:(_ for _ in ()).throw(AssertionError('network')))
    r=op.runtime_probe(tmp_path,manifest)
    assert r['model_load_health_probe'] is False and r['network_model_downloads']==0
    assert r['process_peak_RSS_KiB']>0
    (model/'file').write_bytes(b'changed')
    with pytest.raises(ValueError,match='HASH'):op.runtime_probe(tmp_path,manifest)


def test_no_schedule_or_operating_storage_or_secrets_in_preflight_workflow():
    text=(REPO/'.github/workflows/v4-cpu-preflight.yml').read_text();w=yaml.safe_load(text)
    triggers=w.get('on',w.get(True))
    assert set(triggers)=={'push'} and triggers['push']['branches']==['codex/bct-v4-integration']
    assert w['permissions']=={'contents':'read','actions':'read'}
    assert w['concurrency']['group']!='rss-canonical-data'
    assert 'secrets.' not in text and 'upload-artifact' not in text
    assert all(j['runs-on']=='ubuntu-24.04' for j in w['jobs'].values())
    assert 'fail-on-cache-miss: true' in text and 'timeout 120' in text
    assert 'pip install' not in '\n'.join(s.get('run','')for s in w['jobs']['restore']['steps'])


def schedule_context():
    acq={'id':2,'name':'New precursor evidence acquisition','event':'workflow_run','head_branch':'main','conclusion':'success'}
    rss={'id':1,'name':'RSS live environment check','event':'schedule','head_branch':'main','conclusion':'success','created_at':'2026-10-15T00:09:10Z'}
    return {'event_name':'workflow_run','event':{'workflow_run':{'id':2}},'acquisition_run':acq,
            'rss_run':rss,'acquisition_job_log':'    RSS_RUN_ID: 1\n'}


def test_verified_schedule_chain_keeps_nominal_vs_actual_distinct():
    result=op.verified_schedule(schedule_context())
    assert result['verified'] and result['nominal_cron_slot'] is None
    assert result['RSS_actual_created_at']=='2026-10-15T00:09:10Z'


@pytest.mark.parametrize('mutation',['manual','wrong_log','wrong_parent','failed'])
def test_manual_replay_or_unproven_parent_not_regular_operation(mutation):
    c=schedule_context()
    if mutation=='manual':c['rss_run']['event']='workflow_dispatch'
    elif mutation=='wrong_log':c['acquisition_job_log']='RSS_RUN_ID: 9'
    elif mutation=='wrong_parent':c['event']['workflow_run']['id']=9
    else:c['acquisition_run']['conclusion']='failure'
    with pytest.raises(ValueError,match='CHAIN'):op.verified_schedule(c)


def test_web_projection_reports_actual_preflight_without_starting_shadow(tmp_path):
    from bct.v4.dashboard import ResearchReader
    restore_baseline(tmp_path/'queue');l=open_queue(tmp_path/'queue')
    op.observe(l,trigger='DEVELOPMENT_PREFLIGHT',execute=True);p=l.path;l.close()
    ui=ResearchReader(REPO,p).dashboard()
    ops=ui['automation']['cpu_research']['operations']
    assert ops['observations']==1 and ops['latest']['new_CPU_windows']==0
    assert ops['latest']['peak_RSS_KiB']>0 and ops['seven_day_status']=='NOT_RUN'
    assert ui['counts']['future_candidates']=={'S1':0,'S2':0,'S3':0}


def test_preflight_cannot_request_real_schedule_receipt(monkeypatch):
    monkeypatch.setenv('GITHUB_EVENT_NAME','push')
    monkeypatch.setenv('GITHUB_REPOSITORY','irewon1-lgtm/bottleneck-control-tower')
    monkeypatch.setattr(op.subprocess,'run',lambda *a,**k:(_ for _ in ()).throw(AssertionError('must not fetch')))
    with pytest.raises(ValueError,match='WORKFLOW_TRIGGER'):op.github_schedule_context()


def test_verified_regular_but_empty_cpu_queue_does_not_start7day(tmp_path):
    l=open_queue(tmp_path)
    r=op.observe(l,trigger='workflow_run',execute=True,schedule_context=schedule_context())
    assert r['scheduled_execution_verified'] and r['new_CPU_windows']==0
    assert r['seven_day_start'] is None
    assert op.observation_summary(l.db)['first_verified_scheduled_CPU_success'] is None;l.close()
