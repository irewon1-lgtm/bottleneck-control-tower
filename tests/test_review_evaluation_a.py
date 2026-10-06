"""Synthetic functional boundaries, not lead accuracy or historical reevaluation."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import pytest
from bct import review_leads as r
from test_review_leads import fixture

spec=importlib.util.spec_from_file_location('evaluation_a','tools/review_evaluation_a.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)


def listing(rows=(),access='PASS',complete=True):
    return {'runs':list(rows),'access':access,'complete':complete}


def test_same_run_never_adds_twice():
    run={'id':1,'status':'completed','conclusion':'success'}
    snapshot={'workflows':{'acquisition':listing([run,run])}}
    assert a.diagnose(snapshot)['acquisition']['unique_runs_in_query']==1
    assert a.diagnose(snapshot)==a.diagnose(deepcopy(snapshot))


@pytest.mark.parametrize('hour', [3, 7, 11, 15, 19, 23])
@pytest.mark.parametrize('seconds', [-1, 0, 1])
def test_scheduled_slot_equal_instants_around_all_six_slots(hour, seconds):
    kst=timezone(timedelta(hours=9))
    slot=datetime(2026, 10, 6, hour, tzinfo=kst)
    observed=slot+timedelta(seconds=seconds)
    actual=a.scheduled_slot(observed.isoformat())
    assert actual==a.scheduled_slot(observed.astimezone(timezone.utc).isoformat())
    previous=slot-timedelta(hours=4) if seconds<0 else slot
    following=slot if seconds<0 else slot+timedelta(hours=4)
    assert actual['last_RSS_nominal_UTC']==previous.astimezone(timezone.utc).isoformat()
    assert actual['next_RSS_nominal_UTC']==following.astimezone(timezone.utc).isoformat()


@pytest.mark.parametrize('seconds', [-1, 0, 1])
def test_scheduled_slot_kst_midnight(seconds):
    observed=datetime(2026, 10, 6, tzinfo=timezone(timedelta(hours=9)))+timedelta(seconds=seconds)
    actual=a.scheduled_slot(observed.isoformat())
    assert actual['last_RSS_nominal_UTC']=='2026-10-05T14:00:00+00:00'
    assert actual['next_RSS_nominal_UTC']=='2026-10-05T18:00:00+00:00'


def test_scheduled_slot_preserves_existing_utc_output():
    actual=a.scheduled_slot('2026-10-06T03:46:19+00:00')
    assert actual=={
        'last_RSS_nominal_UTC':'2026-10-06T02:00:00+00:00',
        'next_RSS_nominal_UTC':'2026-10-06T06:00:00+00:00',
        'source_sha256':a.sha(Path('.github/workflows/rss-live-check.yml').read_bytes()),
        'basis':'checked-out RSS workflow bytes',
        'acquisition_expected':'After successful RSS completion; no own cron',
        'shadow_expected':'After acquisition completion; conditional; no own cron',
        'late_tolerance':'UNAPPROVED', 'zero_alert_threshold':'UNAPPROVED'}


def test_scheduled_slot_requires_explicit_timezone():
    with pytest.raises(ValueError, match='must include timezone'):
        a.scheduled_slot('2026-10-06T00:00:00')


def test_absence_permission_and_artifact_failure_are_distinct():
    s={'workflows':{'acquisition':listing(), 'SHADOW':listing(access='BLOCKED',complete=False)},
       'artifact_access':{'download':'BLOCKED','restore':'NOT_PERFORMED'}}
    d=a.diagnose(s)
    assert d['acquisition']['execution']=='NO_EXECUTION'
    assert d['SHADOW']['execution']=='UNKNOWN'
    assert d['artifact_delivery']['download']=='BLOCKED'
    assert d['semantic']['EXCLUDED']=='UNKNOWN'


def test_pending_never_excluded():
    s={'workflows':{},'state_metrics':{'pending_documents':a.metric(3,'queue','cumulative'),
       'completed_documents':a.metric(0,'semantic','cumulative'),'EXCLUDED':a.metric(0,'first','cumulative')}}
    assert a.diagnose(s)['semantic']['pending_documents']['value']==3
    assert a.diagnose(s)['semantic']['EXCLUDED']['value']==0


def test_draft_cannot_activate_or_invent_dates():
    cfg=json.loads(Path('review-leads/evaluation-a/config.json').read_text())
    assert a.draft_epoch(cfg) is None
    assert a.validate_draft('review-leads/evaluation-a')
    for key in ('t0','epoch'):
        bad=deepcopy(cfg);bad[key]='invented'
        with pytest.raises(ValueError,match='UNAPPROVED'):a.draft_epoch(bad)


def synthetic_sidecar():
    bundle,contract,ref=fixture();card=r.make_card(bundle['annotations'][0],r.documents(bundle),contract)
    value={'hypothesis_version':'H0','target':card['target'],
      'scope_fields':card['source_supported_scope'],'evidence':[card['confirmed_facts'][0]['reference']],
      'observed_changes':card['confirmed_facts'],'claim':'Investigate whether the contracted need precedes qualified ramp.',
      'assumptions':['Customer timing is UNKNOWN'],'prediction_period':'UNKNOWN',
      'refutation_conditions':['Sufficient applicable supply before obligation'],
      'recorded_at':'2026-10-06T01:00:00+00:00',
      'exposure':{'input_documents':[{'document_id':bundle['documents'][0]['document_id'],
                  'body_sha256':bundle['documents'][0]['body_sha256']}],
       'started_at':'UNKNOWN','completed_at':'UNKNOWN','annotator':'synthetic',
       'method':'SYNTHETIC_TEST','web_search_used':False,'search_references':[],
       'model_knowledge_basis':'UNKNOWN'}}
    return bundle,card,value


def test_sidecar_preserves_card_and_source_and_uses_real_first():
    b,c,v=synthetic_sidecar();before=deepcopy((b,c))
    v['review_lead_first_at']='1900-01-01'
    result=a.hypothesis_sidecar(b,c,v)
    assert (b,c)==before
    assert result['review_lead_first_at']==c['first_review_recorded_at']
    assert result['market_candidate_first_at']=='UNKNOWN'
    assert result['cohort']=='EXPLORATORY_EXCLUDED' and not result['performance_evaluation']
    assert result['prediction_period']=='UNKNOWN'
    bad=deepcopy(v);bad['evidence'][0]['quote']='invented'
    with pytest.raises(ValueError):a.hypothesis_sidecar(b,c,bad)


def test_changed_hypothesis_requires_new_version_time():
    b,c,v=synthetic_sidecar();v['hypothesis_version']='H1'
    with pytest.raises(AssertionError):a.hypothesis_sidecar(b,c,v)
    v['previous_hypothesis_hash']='previous';v['previous_recorded_at']=v['recorded_at']
    with pytest.raises(AssertionError):a.hypothesis_sidecar(b,c,v)
    v['recorded_at']='2026-10-06T02:00:00+00:00'
    assert a.hypothesis_sidecar(b,c,v)['review_lead_first_at']==c['first_review_recorded_at']


def test_write_boundary_and_immutable_sidecar(tmp_path):
    for ref in ('refs/heads/main','refs/heads/data','refs/heads/live-state','refs/heads/review-lead-shadow-state'):
        with pytest.raises(ValueError):a.validate_state_ref(ref)
    assert a.validate_state_ref(a.STATE_REF)==a.STATE_REF
    operational=tmp_path/'store';operational.mkdir();(operational/'session.json').write_text('unchanged')
    with pytest.raises(ValueError):a.append_sidecar(operational/'evaluation-a',{'synthetic':True})
    with pytest.raises(ValueError):a.append_sidecar(tmp_path/'review-lead-shadow',{})
    root=tmp_path/'evaluation-a';record={'synthetic':True,'at':'2026-10-06'}
    path=a.append_sidecar(root,record);before=path.read_bytes()
    assert a.append_sidecar(root,record)==path and path.read_bytes()==before
    assert (operational/'session.json').read_text()=='unchanged'


def test_observation_does_not_change_store(tmp_path,monkeypatch):
    store=tmp_path/'production';store.mkdir()
    for name in ('body','queue','first','history'):(store/name).write_text('immutable '+name)
    before={p.name:a.sha(p.read_bytes()) for p in store.iterdir()}
    monkeypatch.setattr(a,'api',lambda path:{'access':'BLOCKED','reason':'API_REQUEST_FAILED','http_status':403})
    monkeypatch.setattr(a,'runs',lambda wf:listing(access='BLOCKED',complete=False))
    monkeypatch.setattr(a,'read_state',lambda:{'access':'BLOCKED','metrics':'UNKNOWN'})
    class P:
        returncode=1;stdout=b'';stderr=b''
    monkeypatch.setattr(a.subprocess,'run',lambda *args,**kwargs:P())
    monkeypatch.setattr(a.subprocess,'check_output',lambda *args,**kwargs:'unknown')
    out=a.collect('synthetic')
    assert out['throughput']['new_verified_documents']['value']=='UNKNOWN'
    assert before=={p.name:a.sha(p.read_bytes()) for p in store.iterdir()}
    assert out['last_observer_execution_at']=='UNKNOWN'


def test_observer_template_is_inactive_read_only_and_independent():
    import yaml
    path=Path('review-leads/evaluation-a/observer-workflow.yml.template')
    wf=yaml.safe_load(path.read_text())
    assert wf['permissions']=={'contents':'read','actions':'read'}
    assert not Path('.github/workflows/evaluation-observer.yml').exists()
    assert 'workflow_run:' not in path.read_text() and 'pull_request:' not in path.read_text()
    assert 'git push' not in path.read_text()
