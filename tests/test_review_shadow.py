"""Synthetic isolated-transport safety tests, not detection performance."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from bct import review_shadow as shadow, review_leads as r
from bct.objective_lock import stamp_export
from test_review_leads import fixture
from test_review_intake import packets


def initialized(tmp_path,monkeypatch):
    root=tmp_path/'review-lead-shadow'
    monkeypatch.setattr(r,'now',lambda:'2026-10-05T17:00:00+00:00')
    shadow.initialize(root)
    b,c,ref=fixture();b['documents'][0].update(published_at='2026-10-05T17:01:00+00:00',
        acquired_at='2026-10-05T17:02:00+00:00',available_at='2026-10-05T17:02:01+00:00')
    monkeypatch.setattr(r,'now',lambda:'2026-10-05T17:03:00+00:00')
    return root,b,c,ref


def test_1_new_document_preserves_operational_bytes(tmp_path,monkeypatch):
    core=tmp_path/'operations';core.mkdir();(core/'db.sqlite').write_bytes(b'unchanged DB');(core/'output.json').write_bytes(b'original successful output')
    before=shadow.snapshot(core);root,b,_,_=initialized(tmp_path,monkeypatch)
    result=shadow.run(b,root,packets=packets(b))
    assert shadow.snapshot(core)==before and len(result['alerts'])==1


def test_2_forced_review_failure_after_successful_storage(tmp_path,monkeypatch):
    core=tmp_path/'operations';core.mkdir();(core/'saved-source').write_text('source saved');(core/'success').write_text('collector success')
    before=shadow.snapshot(core);root,b,_,_=initialized(tmp_path,monkeypatch)
    def failure(*a,**kw):raise RuntimeError('forced shadow failure')
    monkeypatch.setattr(shadow.intake,'process',failure)
    with pytest.raises(RuntimeError,match='forced'):shadow.run(b,root)
    assert shadow.snapshot(core)==before


def test_3_duplicate_first_no_duplicate_alert(tmp_path,monkeypatch):
    root,b,_,_=initialized(tmp_path,monkeypatch);shadow.run(b,root,packets=packets(b))
    before=shadow.snapshot(root/'store'/'first')
    result=shadow.run(b,root,packets=packets(b));assert not result['alerts']
    assert shadow.snapshot(root/'store'/'first')==before


def test_4_same_scope_new_evidence_append(tmp_path,monkeypatch):
    root,b,_,_=initialized(tmp_path,monkeypatch);first=shadow.run(b,root,packets=packets(b))['records'][0]['review_id']
    original=shadow.snapshot(root/'store'/'first');new=deepcopy(b);d=new['documents'][0]
    d.update(document_id='second-origin',origin_id='new-original');d['body']+=' Additional actual fact.';d['body_sha256']=d['version']=r.digest(d['body'].encode())
    def rebind(x):
        if isinstance(x,dict):
            if 'locator' in x:x.update(document_id=d['document_id'],body_sha256=d['body_sha256'])
            for v in x.values():rebind(v)
        elif isinstance(x,list):
            for v in x:rebind(v)
    rebind(new['annotations']);result=shadow.run(new,root,packets=packets(new))
    assert result['records'][0]['review_id']==first
    assert shadow.snapshot(root/'store'/'first')==original
    assert len(r.load_store(root/'store')['records'][0]['history'])==1
    assert result['alerts'][0]['kind']=='REVIEW_LEAD_UPDATE'
    assert result['alerts'][0]['independent_origin_verification']=='UNKNOWN'


def test_5_missing_semantic_queue_no_alert_completion_append(tmp_path,monkeypatch):
    root,b,_,_=initialized(tmp_path,monkeypatch);result=shadow.run(b,root)
    assert result['records'][0]['final_status']=='HOLD' and not result['alerts']
    qpath=next((root/'queue').glob('*.json'));before=qpath.read_bytes();q=r.sealed_read(qpath)
    assert q['semantic_review_method']=='PENDING_AI_OR_MANUAL'
    assert q['mode']=='PROSPECTIVE_REVIEW' and q['first_review_recorded_at']=='UNKNOWN'
    assert q['published_at']!=q['acquired_at']!=q['available_at']
    done=shadow.run(stamp_export({'documents':[]}),root,packets=packets(b))
    assert done['records'][0]['final_status']=='REVIEW_LEAD' and qpath.read_bytes()==before
    semantic=r.sealed_read(next((root/'semantic').glob('*.json')))
    assert semantic['annotator'] and semantic['annotation_method']


def test_6_confirmation_not_success(tmp_path,monkeypatch):
    root,b,_,ref=initialized(tmp_path,monkeypatch);ps=packets(b)
    ps[0]['annotation']['confirmation']={'document':'YES','same_TARGET':'YES','references':[ref('Actual shortage at facility PX-1 is confirmed.')]}
    out=shadow.run(b,root,packets=ps)
    assert out['records'][0]['final_status']=='CONFIRMATION' and not out['alerts']
    assert out['EARLY_success_count']==0


def test_7_old_acquisition_never_prospective(tmp_path,monkeypatch):
    root,b,_,_=initialized(tmp_path,monkeypatch);b['documents'][0]['acquired_at']='2020-01-02T00:00:00+00:00'
    skipped=shadow.run(b,root);assert skipped['omitted_backfill'][0]['mode']=='BACKFILL' and not skipped['records']
    out=shadow.run(b,root,packets=packets(b),allow_backfill=True)
    assert out['records'][0]['mode']=='BACKFILL'
    first=r.load_store(root/'store')['records'][0]['first'];assert first['first_review_recorded_at']=='2026-10-05T17:03:00+00:00'


def test_8_operational_store_and_symlink_forbidden(tmp_path):
    for name in ['LIVE','v2-shadow','early-store']:
        base=tmp_path/name;root=base/'review-lead-shadow';root.mkdir(parents=True)
        with pytest.raises(ValueError,match='OPERATIONAL'):shadow.initialize(root)
    foreign=tmp_path/'other'/'review-lead-shadow';foreign.mkdir(parents=True);(foreign/'session.json').write_text('session')
    with pytest.raises(ValueError,match='FOREIGN'):shadow.initialize(foreign)
    linked=tmp_path/'link'/'review-lead-shadow';linked.parent.mkdir();linked.symlink_to(foreign,target_is_directory=True)
    with pytest.raises(ValueError,match='NAMESPACE'):shadow.initialize(linked)


def test_refutation_explicit_append_preserves_first(tmp_path,monkeypatch):
    root,b,_,ref=initialized(tmp_path,monkeypatch);out=shadow.run(b,root,packets=packets(b));rid=out['records'][0]['review_id'];before=shadow.snapshot(root/'store'/'first')
    event=stamp_export({'kind':'REFUTATION','summary':'Synthetic exact scope refutation','annotator':'Synthetic reader',
        'annotation_method':'SYNTHETIC_TEST','annotated_at':'2026-10-05T17:04:00+00:00','same_TARGET':'YES',
        'status_after':'REFUTED','references':[ref('PX-1')]})
    shadow.followup(b,root,rid,event);assert shadow.snapshot(root/'store'/'first')==before
    assert r.load_store(root/'store')['records'][0]['current_status']=='REFUTED'


def test_real_capture_handoff_shadow_keeps_source_output_bytes(tmp_path,monkeypatch):
    from bct import precursor_collection as collection
    from test_precursor_collection import html, manifest
    cache=tmp_path/'capture-cache';delta=manifest(['buyer']);url=delta['documents'][0]['url']
    raw=html('buyer','The customer signed firm orders for 100 units in 2031. Facility PX-1 is commissioning.')
    monkeypatch.setattr(collection.acquisition,'fetch',lambda u:(raw,u,200,'text/html'))
    monkeypatch.setattr(collection.acquisition,'now',lambda:'2026-10-05T03:00:00+00:00')
    root=tmp_path/'review-lead-shadow';monkeypatch.setattr(r,'now',lambda:'2026-10-05T02:00:00+00:00');shadow.initialize(root)
    activation=collection.init(cache,delta);saved=collection.capture(cache,url,'buyer',activation,collected_at=delta['documents'][0]['collected_at'])
    assert saved['provenance']=='PASS'
    before=shadow.snapshot(cache);delta_path=tmp_path/'delta.json';delta_path.write_text(json.dumps(delta))
    monkeypatch.setattr(r,'now',lambda:'2026-10-05T04:00:00+00:00')
    bundle=shadow.handoff(delta_path,cache,tmp_path/'handoff')
    assert len(bundle['documents'])==1
    out=shadow.run(bundle,root)
    assert out['records'][0]['mode']=='PROSPECTIVE_REVIEW'
    assert shadow.snapshot(cache)==before
    monkeypatch.setattr(shadow.intake,'process',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('failure')))
    with pytest.raises(RuntimeError):shadow.run(bundle,root)
    assert shadow.snapshot(cache)==before


def test_workflow_only_adds_optional_handoff_without_changing_core():
    import subprocess,yaml
    baseline=subprocess.check_output(['git','show','83aaf61:.github/workflows/precursor-acquisition.yml'],text=True)
    current=Path('.github/workflows/precursor-acquisition.yml').read_text();assert current==baseline
    old=yaml.safe_load(baseline);new=yaml.safe_load(current)
    added=new['jobs']['acquire']['steps'][len(old['jobs']['acquire']['steps']):]
    assert added==[]
    assert old['jobs']['acquire']['if']==new['jobs']['acquire']['if']
    assert old['permissions']==new['permissions'] and old['concurrency']==new['concurrency']
    wf=yaml.safe_load(Path('.github/workflows/review-lead-shadow.yml').read_text())
    assert 'conclusion' not in wf['jobs']['shadow']['if']  # upstream evaluation failure is independent
    assert wf['concurrency']['group']!='rss-canonical-data'
    assert all('needs' not in job for job in wf['jobs'].values())
    text=Path('.github/workflows/review-lead-shadow.yml').read_text()
    assert 'refs/heads/live-state' not in text and 'refs/heads/data' not in text
    assert 'BCT_REVIEW_SHADOW_ENABLED' in text
    assert 'precursor-private-cache' in text and 'workflow_run.created_at' in text


def test_git_persistence_is_own_branch_append_only_and_cas(tmp_path,monkeypatch):
    import importlib.util,subprocess
    spec=importlib.util.spec_from_file_location('persist','.github/scripts/persist_review_shadow.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    repo=tmp_path/'repo';repo.mkdir();remote=tmp_path/'remote.git'
    subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
    subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(repo),'remote','add','origin',str(remote)],check=True)
    monkeypatch.chdir(repo);root=repo/'var/review-state/review-lead-shadow';root.mkdir(parents=True)
    (root/'shadow-activation.json').write_text('{"synthetic":true}')
    (root/'first.json').write_text('{"original":true}')
    first=mod.persist(root,'');(root/'history.json').write_text('{"followup":true}')
    second=mod.persist(root,first);assert first!=second
    with pytest.raises(ValueError,match='CAS'):mod.persist(root,first)
    (root/'first.json').write_text('{"modified":true}')
    with pytest.raises(ValueError,match='CHANGED'):mod.persist(root,second)
    refs=subprocess.check_output(['git','ls-remote','origin'],text=True)
    assert 'refs/heads/review-lead-shadow-state' in refs and 'refs/heads/main' not in refs and 'refs/heads/live-state' not in refs


def test_generic_named_operational_ancestor_and_followup_path_blocked(tmp_path,monkeypatch):
    base=tmp_path/'generic-store';base.mkdir();(base/'session.json').write_text('protected')
    with pytest.raises(ValueError,match='ANCESTOR'):shadow.initialize(base/'review-lead-shadow')
    root,b,_,_=initialized(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='INVALID_REVIEW_ID'):
        shadow.followup(b,root,'../../operations',stamp_export({'kind':'REVIEW'}))


def test_completed_semantic_document_unannotated_redelivery_does_not_fail(tmp_path,monkeypatch):
    root,b,_,_=initialized(tmp_path,monkeypatch);shadow.run(b,root,packets=packets(b))
    before=shadow.snapshot(root/'store'/'first');out=shadow.run(b,root)
    assert out['records'][0]['delivery']=='DUPLICATE' and not out['alerts']
    assert shadow.snapshot(root/'store'/'first')==before
