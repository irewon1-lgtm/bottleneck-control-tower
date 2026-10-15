"""Source-free research restart; synthetic CPU is not actual extraction quality."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess,sys

import pytest
from bct.v4 import cpu_automation as q,cpu_resume as r,cpu_operations as op
from bct.v4.store import sha,Ledger,file_sha
from test_v4_cpu_automation import document,Extractor


def make_source(tmp_path, *, partial=False):
    d,raw=document('Atlas ordered Helios heat pumps.\nA second separate paragraph.')
    l=q.open_queue(tmp_path/'original');q.enqueue(l,d,raw,{})
    q.work(l,extractor=Extractor(),max_windows=1 if partial else 24)
    l.close();return d,raw


def cache_source(tmp_path,d,raw):
    cache=tmp_path/'cache';(cache/'documents').mkdir(parents=True);(cache/'raw').mkdir()
    d={**d,'raw_path':d['raw_sha256']+'.html'}
    (cache/'documents/doc.json').write_text(json.dumps(d));(cache/'raw'/d['raw_path']).write_bytes(raw)
    policy={'sources':{d['document_id']:{'body_sha256':d['body_sha256'],'raw_sha256':d['raw_sha256'],
        'transient_CPU_read':'PERMITTED','derived_state_storage':'PERMITTED','privacy_review':'CLEARED',
        'rights_basis':'Synthetic author-owned test fixture, not a real-source license','reviewed_by':'test'}}}
    return cache,policy


def test_complete_source_free_restart_preserves_results_and_dedup_without_originals(tmp_path):
    d,raw=make_source(tmp_path);source=tmp_path/'original/v4.sqlite3';before=file_sha(source)
    report=r.export_state(source,tmp_path/'separated');assert file_sha(source)==before
    assert report['CPU_windows_preserved']==2 and report['CPU_product_proposals_preserved']==1
    assert report['completed_body_keys']==1 and report['raw_bodies_present']==0
    l=q.open_queue(tmp_path/'separated')
    assert r.audit(l)['status']=='PASS_SOURCE_SEPARATED_SCHEMA'
    assert q.enqueue(l,d,raw,{})=='UNCHANGED_BODY_COMPLETED_SOURCE_SEPARATED'
    assert q.enqueue(l,{**d,'document_id':'same-body-new-page'},raw,{})=='UNCHANGED_BODY_COMPLETED_SOURCE_SEPARATED'
    assert l.db.execute('SELECT count(*)FROM documents').fetchone()[0]==0
    ref={'start':0,'end':5,'quote':d['body'][:5]}
    assert r.verify(l,d['document_id'],ref)['status']=='HELD_SOURCE_WITHHELD'
    assert r.verify(l,d['document_id'],ref,doc=d)['evidence_validated_now']
    bad=deepcopy(d);bad['body']+='Changed'
    with pytest.raises(ValueError,match='HASH_MISMATCH'):r.verify(l,d['document_id'],ref,doc=bad)
    op.checkpoint(l,tmp_path/'snapshot');l.close()
    script='from bct.v4 import cpu_operations as o,cpu_automation as q;import sys,json;o.restore(sys.argv[1],sys.argv[2]);l=q.open_queue(sys.argv[2]);x=q.work(l);assert x["new_windows"]==0 and not x["model_loaded"];print(json.dumps(q.state(l)));l.close()'
    p=subprocess.run([sys.executable,'-c',script,str(tmp_path/'snapshot'),str(tmp_path/'restarted')],capture_output=True,text=True,timeout=30)
    assert p.returncode==0,p.stderr
    assert json.loads(p.stdout)['source_separated']['CPU_windows_preserved']==2


def test_partial_resume_holds_missing_input_then_reads_only_uncommitted_window(tmp_path):
    d,raw=make_source(tmp_path,partial=True)
    r.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'separated')
    l=q.open_queue(tmp_path/'separated')
    assert r.summary(l)['awaiting_source_windows']==1
    assert r.hydrate(l,tmp_path/'missing',{})[0]['status']=='HELD_SOURCE_MISSING_OR_AMBIGUOUS'
    fake=Extractor();assert q.work(l,extractor=fake)['new_windows']==0 and fake.calls==0
    cache,policy=cache_source(tmp_path,d,raw)
    assert r.hydrate(l,cache,{})[0]['status']=='HELD_TRANSIENT_REVIEW'
    assert r.hydrate(l,cache,policy)[0]['status']=='SOURCE_REHYDRATED_NO_COMPLETED_WINDOW_RERUN'
    assert q.work(l,extractor=fake)['new_windows']==1 and fake.calls==1
    l.close();r.export_state(tmp_path/'separated/v4.sqlite3',tmp_path/'final')
    l=q.open_queue(tmp_path/'final');s=r.summary(l)
    assert s['CPU_windows_preserved']==2 and s['completed_body_keys']==1 and s['partial_documents']==0
    assert r.audit(l)['status']=='PASS_SOURCE_SEPARATED_SCHEMA';l.close()


def test_ingest_done_identity_before_archival_gate_does_not_capture_withheld_raw(tmp_path):
    d,raw=make_source(tmp_path);r.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'separated')
    cache,policy=cache_source(tmp_path,d,raw);l=q.open_queue(tmp_path/'separated')
    manifest={'format':'bct-new-rss-delta-v1','documents':[{'document_id':d['document_id'],'url':d['origin_url']}]}
    result=q.ingest_delta(l,manifest,cache,upstream_run_id='later',storage_policy={})
    assert result[0]['status']=='UNCHANGED_BODY_COMPLETED_SOURCE_SEPARATED'
    assert l.db.execute('SELECT count(*)FROM blobs').fetchone()[0]==0
    assert q.ingest_delta(l,manifest,cache,upstream_run_id='later',storage_policy={})[0]['status']=='ALREADY_IMPORTED'
    l.close()


def test_changed_pending_native_version_never_replays_old_receipts(tmp_path):
    d,raw=make_source(tmp_path,partial=True);r.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'separated')
    changed={**d,'raw_sha256':sha(raw+b' ')};cache,policy=cache_source(tmp_path,changed,raw+b' ')
    l=q.open_queue(tmp_path/'separated')
    assert r.hydrate(l,cache,policy)[0]['status']=='HELD_SOURCE_REHYDRATION_FAILED'
    assert not l.db.execute('SELECT 1 FROM documents').fetchall();l.close()


def test_schema_rejects_embedded_original_prose_even_with_zero_document_rows(tmp_path):
    make_source(tmp_path);r.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'separated')
    l=q.open_queue(tmp_path/'separated')
    with l.db:l.event('CPU_RESUME_RUN',{'body':'Do not publish arbitrary original prose.'})
    with pytest.raises(ValueError,match='VERBATIM_SOURCE'):r.audit(l)
    l.close()


def test_source_free_checkpoint_save_failure_preserves_committed_remote_and_recovers(tmp_path):
    make_source(tmp_path);r.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'separated')
    l=q.open_queue(tmp_path/'separated');op.checkpoint(l,tmp_path/'snapshot');l.close()
    bare=tmp_path/'private.git';repo=tmp_path/'writer'
    subprocess.run(['git','init','--bare',str(bare)],check=True,capture_output=True)
    subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(repo),'remote','add','origin',str(bare)],check=True)
    first=op._publish_checkpoint(repo,tmp_path/'snapshot','')
    with pytest.raises(ValueError,match='PARENT_CHANGED'):
        op._publish_checkpoint(repo,tmp_path/'snapshot','')
    actual=subprocess.check_output(['git','-C',str(repo),'ls-remote','origin',op.STATE_REF],text=True).split()[0]
    assert actual==first['commit']
    recovered=op._publish_checkpoint(repo,tmp_path/'snapshot',first['commit'])
    assert recovered['parent']==first['commit'] and recovered['history_unique_object_bytes']<op.STATE_HISTORY_LIMIT
    dest=tmp_path/'remote-checkpoint';dest.mkdir()
    subprocess.run(['git','-C',str(repo),'fetch','origin',op.STATE_REF],check=True,capture_output=True)
    for name in ('checkpoint.json','checkpoint.sqlite3.gz'):
        (dest/name).write_bytes(subprocess.check_output(['git','-C',str(repo),'show',recovered['commit']+':'+name]))
    op.restore(dest,tmp_path/'restored');l=q.open_queue(tmp_path/'restored')
    assert r.audit(l)['CPU_windows_preserved']==2;l.close()


def test_previous_scope_receipt_must_not_grant_public_write(monkeypatch,tmp_path):
    from bct.v4 import private_state as p
    make_source(tmp_path);r.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'separated')
    l=q.open_queue(tmp_path/'separated');op.checkpoint(l,tmp_path/'snapshot');l.close()
    scope={'private_repository':p.PRIVATE_REPO,'visibility':'private','private_contents_probe':201,
        'visible_private_repository_count':1,'operating_ref_create_denials':{'main':403,'data':422},'operating_refs_modified':False}
    with pytest.raises(ValueError,match='INVALID_PREVIOUSLY_VERIFIED'):
        p.publish(tmp_path/'git',tmp_path/'snapshot','','synthetic',{},verified_scope=scope,
                  api=lambda *a:pytest.fail('No authentication/ref-denial repetition'))


def test_readonly_ui_retains_discoveries_but_never_claims_missing_source_verified(tmp_path):
    from bct.v4.dashboard import ResearchReader
    make_source(tmp_path);r.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'separated')
    repo=Path(__file__).resolve().parents[1]
    reader=ResearchReader(repo,tmp_path/'separated/v4.sqlite3')
    data=reader.dashboard();assert data['counts']['discovery']==1
    row=data['records'][0];detail=reader.evidence(row['id'])
    assert not row['is_future_candidate'] and not detail['all_references_verified']
    assert all(not x['verified'] and x['quote'] is None for x in detail['references'])


def test_historical_target_and_quantity_fields_survive_without_copying_context(tmp_path):
    d,raw=make_source(tmp_path)
    old=Ledger(tmp_path/'legacy')
    with old.db:
        old.event('RECOVERY_EXISTING_REVIEWED_EVENT_PRESERVED',{'review_id':'synthetic-review','product':'Helios heat pumps','verdict':'PRESERVE',
            'original_review':{'role_in_original':'DEMAND_INCREASE','actuality_in_original':'ACTUAL',
                'target_in_original':{'product':'Helios heat pumps','specification':None,'region':None,'customer_group':None,'supply_pool':None},
                'fields_in_original':{'quantity':{'surface':'UNKNOWN','status':'UNKNOWN'},'unit':None,
                    'specification':{'surface':'long structured specification ' * 15}},
                'references':[{'document_id':d['document_id'],'body_sha256':d['body_sha256'],'start':0,'end':5,'quote':d['body'][:5]}]}})
    old.close()
    r.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'separated',legacy=tmp_path/'legacy/v4.sqlite3')
    l=q.open_queue(tmp_path/'separated');r.audit(l)
    history=r.rows(l.db,'CPU_RESUME_REVIEW')[0]['historical_fields']
    assert set(history['historical_target'])=={'product','specification','region','customer_group','supply_pool'}
    assert history['historical_target']['product']=='Helios heat pumps'
    assert history['historical_fields']['quantity']=={'surface':'UNKNOWN','status':'UNKNOWN'}
    assert set(history['historical_fields']['specification']['surface'])=={'withheld_value_sha256'}
    assert history['original_judgment']['role_in_original']=='DEMAND_INCREASE'
    assert 'quote'not in history['references'][0] and history['references'][0]['quote_sha256']==sha(d['body'][:5].encode())
    assert not l.db.execute('SELECT *FROM firsts').fetchall();l.close()
