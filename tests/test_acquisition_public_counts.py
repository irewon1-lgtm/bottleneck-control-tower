"""Public acquisition counters keep their actual units and never source text."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


def wrapper():
    spec=importlib.util.spec_from_file_location('public_acquisition_wrapper',ROOT/'.github/scripts/new_precursor_cycle.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def summary(verified=1,attempts=2,statuses=None):
    return {'new_verified_documents':verified,'new_seed_attempts':attempts,
        'new_seed_statuses':statuses or {'CAPTURED':verified,'HTTP_403':attempts-verified},
        'scope_complete_events':0,'independent_demand_supply_pairs':[],
        'common_future_window_pairs':[],'synthesized_targets':0,'early_preflight':0,
        'live_execution':{'state':'NO_EARLY_CANDIDATE','frozen':0},
        'additional_bodies_acquired':0,'valid_additional_primary_documents':0,
        'source_integrity_state':'PARTIAL_HOLD','unverified_source_holds':1,
        'PRIVATE_URL':'https://private.invalid/SECRET','source_quote':'SECRET_BODY'}


def test_public_summary_aggregates_new_counts_across_batches_without_replacing_snapshot_counts():
    module=wrapper();a=summary(2,3);b=summary(1,4)
    output=module.public_summary([a,b],cache_run_id='12',completed_at='2026-11-11T01:00:00Z')
    assert output['new_verified_documents']==3
    assert output['new_seed_attempts']==7 and output['new_seed_statuses']=={'CAPTURED':3,'HTTP_403':4}
    assert output['scope_complete_events']==b['scope_complete_events']
    assert 'SECRET'not in json.dumps(output)


def test_typed_public_receipt_preserves_seed_units_and_does_not_invent_body_http_counts():
    module=wrapper();public=module.public_summary([summary()],cache_run_id='12',completed_at='2026-11-11T01:00:00Z')
    manifest={'collection_started_at':'2026-11-11T00:00:00Z','documents':[{'url':'https://private.invalid/SECRET','document_id':'SECRET'}]}
    receipt=module.public_receipt(public,manifest,run_id=12,head_sha='a'*40,rss_run_id=10,
                                  manifest_sha256='b'*64,started_at='2026-11-11T00:10:00Z')
    assert receipt['format']=='bct-public-acquisition-1' and receipt['RSS_run_id']==10
    assert receipt['counts']['new_seed_attempts']==2
    assert receipt['units']['new_seed_attempts']=='SEED_CAPTURE_OUTCOMES_NOT_HTTP_REQUESTS'
    assert receipt['counts']['body_HTTP_requests'] is None
    assert receipt['counts']['body_pending'] is None
    assert receipt['counts']['new_URLs']==1
    assert 'SECRET'not in json.dumps(receipt) and 'objective_sha256'in receipt


def test_missing_legacy_attempt_metrics_remain_unknown_instead_of_becoming_zero():
    module=wrapper();row=summary();del row['new_seed_attempts'];del row['new_seed_statuses']
    public=module.public_summary([row],cache_run_id='12',completed_at='2026-11-11T01:00:00Z')
    assert public['new_seed_attempts'] is None and public['new_seed_statuses'] is None


@pytest.mark.parametrize('field,value',[('new_seed_attempts',True),('new_seed_attempts',-1),('new_seed_statuses',{'SECRET_URL':1})])
def test_invalid_or_free_form_public_counter_data_is_refused(field,value):
    module=wrapper();row=summary();row[field]=value
    with pytest.raises(ValueError):module.public_summary([row],cache_run_id='12',completed_at='2026-11-11T01:00:00Z')


def test_public_receipt_validator_rejects_private_fields_and_bad_binding():
    import importlib.util
    path=ROOT/'.github/scripts/public_acquisition.py';spec=importlib.util.spec_from_file_location('public_acquisition_validation',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    w=wrapper();public=w.public_summary([summary()],cache_run_id='12',completed_at='2026-11-11T01:00:00Z')
    value=w.public_receipt(public,{'collection_started_at':'2026-11-11T00:00:00Z','documents':[]},
        run_id=12,head_sha='a'*40,rss_run_id=10,manifest_sha256='b'*64,started_at='2026-11-11T00:10:00Z')
    assert module.validate_receipt(value)==value
    for extra in ({'source_quote':'SECRET'}, {'head_sha':'bad'}, {'RSS_run_id':True}):
        with pytest.raises(ValueError):module.validate_receipt({**value,**extra})


def test_reused_cycle_does_not_report_its_old_acquisitions_as_new(tmp_path,monkeypatch):
    module=wrapper();manifest={'collection_started_at':'2026-11-11T00:00:00Z','documents':[
        {'document_id':'new-id','url':'https://publisher.example/new','collected_at':'2026-11-11T00:00:00Z'}]}
    batch={**manifest,'batch_number':1};path=tmp_path/'cycles'/(module.collection.forecast_discovery.digest(batch)+'.json')
    path.parent.mkdir();path.write_text('preserved receipt');before=path.read_bytes()
    monkeypatch.setattr(module.collection,'cycle',lambda *args,**kwargs:summary(2,3))
    rows=module.run(manifest,tmp_path)
    assert rows[0]['new_verified_documents']==rows[0]['new_seed_attempts']==0
    assert rows[0]['new_seed_statuses']=={} and rows[0]['cycle_receipt_reused']is True
    assert path.read_bytes()==before


def test_receipt_attempts_are_typed_and_bound_in_public_schema():
    module=wrapper();public=module.public_summary([summary()],cache_run_id='12',cache_run_attempt=2,completed_at='2026-11-11T01:00:00Z')
    value=module.public_receipt(public,{'collection_started_at':'2026-11-11T00:00:00Z','documents':[]},
        run_id=12,run_attempt=2,head_sha='a'*40,rss_run_id=10,rss_run_attempt=3,
        manifest_sha256='b'*64,started_at='2026-11-11T00:10:00Z')
    assert value['run_attempt']==2 and value['RSS_run_attempt']==3 and public['cache_run_attempt']==2
    with pytest.raises(ValueError):module.public_receipt(public,{},run_id=12,run_attempt=True,head_sha='a'*40,rss_run_id=10,
        manifest_sha256='b'*64,started_at='2026-11-11T00:10:00Z')


def test_empty_delta_cli_writes_valid_attempt_bound_public_json_without_reading_old_bodies(tmp_path):
    import os
    import subprocess
    import sys
    manifest=tmp_path/'input.json';manifest.write_text(json.dumps({'format':'bct-new-rss-delta-v1',
        'collection_started_at':'2026-11-11T00:00:00Z','run_id':10,'run_attempt':3,'documents':[]}))
    cache=tmp_path/'cache';(cache/'documents').mkdir(parents=True)
    (cache/'documents/old.json').write_text('SECRET_DO_NOT_REPARSE_MALFORMED_BODY')
    env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PRECURSOR_MANIFEST':str(manifest),
        'PRECURSOR_STATE':str(cache),'PRECURSOR_SUMMARY':str(tmp_path/'index.json'),
        'PRECURSOR_NEW_DOCUMENT_FILES':str(tmp_path/'new-files.json'),
        'PRECURSOR_GRAPH_SOURCES':str(tmp_path/'graph-sources.json'),
        'PRECURSOR_PUBLIC_RECEIPT':str(tmp_path/'public'),'GITHUB_RUN_ID':'12',
        'GITHUB_RUN_ATTEMPT':'2','GITHUB_SHA':'a'*40,'RSS_RUN_ID':'10','RSS_RUN_ATTEMPT':'3'}
    result=subprocess.run([sys.executable,str(ROOT/'.github/scripts/new_precursor_cycle.py')],cwd=ROOT,
                          env=env,text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stderr
    index=json.loads((tmp_path/'index.json').read_text());receipt=json.loads((tmp_path/'public/snapshot.json').read_text())
    assert index['new_seed_attempts']==receipt['counts']['new_seed_attempts']==0
    assert receipt['run_attempt']==2 and receipt['RSS_run_attempt']==3
    assert json.loads((tmp_path/'graph-sources.json').read_text())=={'sources':[],'complete':True}
    assert 'SECRET'not in result.stdout and 'SECRET'not in json.dumps(receipt)
