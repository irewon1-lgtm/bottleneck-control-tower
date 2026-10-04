"""Objective/precursor regressions: synthetic functional tests, not real performance."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import pytest
from bct.forecast_discovery import discover, lead_time
from bct.objective_lock import objective_binding, stamp_export, require_objective, ObjectiveBlocked

NOW = '2020-01-10T00:00:00Z'
T = '2020-02-01T00:00:00Z'


def precursor_batch():
    texts = [('buyer', 'Customer commits orders for 100 transformer units needed on 2020-06-01.'),
             ('maker', 'Qualified transformer ramp becomes available on 2020-09-01, at 80 units.')]
    docs = []
    signals = []
    for role,(name,body) in zip(('DEMAND','SUPPLY'), texts):
        docs.append({'document_id':name, 'body':body, 'body_sha256':hashlib.sha256(body.encode()).hexdigest(),
                     'published_at':'2020-01-01T00:00:00Z', 'available_at':'2020-01-02T00:00:00Z',
                     'origin_id':name, 'origin_url':'https://'+name+'.example/original',
                     'origin_publisher':name, 'provenance_verified':True})
        signals.append({'document_id':name, 'locator':{'start':0,'end':len(body)},
                        'target_id':'transformer-230kv', 'target':'230kV power transformers',
                        'specification':'230kV', 'region':'US', 'supply_pool':'qualified US delivery',
                        'period':{'start':'2020-06-01','end':'2020-12-31'}, 'basis':'total',
                        'role':role, 'signal_type':'committed_order' if role=='DEMAND' else 'production_ramp',
                        'quantity':'UNKNOWN', 'unit':'units', 'need_date':'2020-06-01' if role=='DEMAND' else None,
                        'available_date':'2020-09-01' if role=='SUPPLY' else None,
                        'qualified':role=='SUPPLY', 'coverage_complete':False})
    return stamp_export({'documents':docs,'signals':signals,'confirmations':[]})


def replay(batch, now=NOW, previous=None):
    return discover(batch, now=now, mode='SYNTHETIC', previous=previous)


def public_reference(batch):
    batch['confirmations']=[{'target_id':'transformer-230kv', 'explicit':True, 'frozen':True,
                            'first_public_bottleneck_confirmation_at':T,
                            'evidence':{'url':'https://archive.example/confirmation', 'locator':{'start':0,'end':30}}}]
    return batch


def test_A_explicit_shortage_alone_never_forecast_candidate():
    b=precursor_batch();b['documents']=b['documents'][:1];b['signals']=b['signals'][:1]
    body='A shortage of power transformers was publicly reported.'
    b['documents'][0].update(body=body,body_sha256=hashlib.sha256(body.encode()).hexdigest())
    b['signals'][0]['locator']['end']=len(body)
    result=replay(b)
    assert not result['candidates']
    assert any(r['reason']=='PUBLIC_CONFIRMATION_NOT_PRECURSOR' for r in result['rejected_inputs'])


def test_B_independent_demand_ramp_without_shortage_creates_candidate():
    result=replay(precursor_batch())
    assert len(result['candidates'])==1
    c=result['candidates'][0]
    assert c['reason']=='POSSIBLE_TIMING_GAP' and c['comparison']['demand_quantity']=='UNKNOWN'
    assert 's_stage' not in c and result['layer']=='DISCOVERY'
    assert result['forecast_performance']['status']=='BLOCKED'


def test_C_sufficient_expansion_before_need_refutes_candidate():
    b=precursor_batch();b['signals'][0]['quantity']=100
    b['signals'][1].update(quantity=120,available_date='2020-05-01',coverage_complete=True)
    result=replay(b)
    assert not result['candidates'] and result['outcomes'][0]['state']=='CONTRADICTED'


def test_D_synthetic_pre_public_replay_measures_lead_time():
    # Synthetic timeline proves plumbing only. No historical real-world success claim.
    result=replay(public_reference(precursor_batch()))
    assert result['candidates'][0]['candidate_first_detected_at']=='2020-01-10T00:00:00+00:00'
    assert result['outcomes'][0]['lead_time_days']==22
    assert result['outcomes'][0]['early_detection_success'] is True
    assert result['forecast_performance']['status']=='BLOCKED'


def test_D_real_pre_public_holdout():
    path=os.environ.get('BCT_REAL_PRE_PUBLIC_HOLDOUT')
    if not path:
        pytest.skip('BLOCKED: independent frozen real pre-public holdout and archived precursor facts unavailable')
    manifest=json.loads(Path(path).read_text())
    assert manifest['dataset_kind']=='REAL_PRE_PUBLIC_HOLDOUT'
    assert manifest['independent_reference'] is True and manifest['unused_holdout'] is True
    assert manifest['pre_registered'] is True
    batch=manifest['batch'];require_objective(batch)
    assert batch['confirmations'] and all(x.get('frozen') is True for x in batch['confirmations'])
    # Actual archived bodies/provenance are provided by the independent dataset owner.
    result=discover(batch,now=manifest['cutoff'],mode='BACKFILL')
    assert result['outcomes'] and all(x['lead_time_days'] is not None and x['lead_time_days']>0 for x in result['outcomes'])


def test_E_after_public_confirmation_is_missed_not_success():
    result=replay(public_reference(precursor_batch()),now='2020-02-05T00:00:00Z')
    outcome=result['outcomes'][0]
    assert outcome['state']=='MISSED_EARLY_DETECTION'
    assert outcome['lead_time_days']==-4 and outcome['early_detection_success'] is False
    assert lead_time({'candidate_first_detected_at':T},T)['status']=='MISSED_EARLY_DETECTION'


@pytest.mark.parametrize('copy_kind',['origin','publisher','body','quote'])
def test_F_reprints_and_press_release_copies_are_not_independent(copy_kind):
    b=precursor_batch();a,z=b['documents']
    if copy_kind=='origin':z.update(origin_id=a['origin_id'],origin_url=a['origin_url'])
    elif copy_kind=='publisher':z['origin_publisher']=a['origin_publisher']
    else:
        z['body']=a['body'] if copy_kind=='body' else 'Wrapper '+a['body']+' end'
        z['body_sha256']=hashlib.sha256(z['body'].encode()).hexdigest()
        b['signals'][1]['locator']={'start':0 if copy_kind=='body' else 8,'end':len(a['body'])+(0 if copy_kind=='body' else 8)}
    assert not replay(b)['candidates']


@pytest.mark.parametrize('field',['objective_sha256','objective_version'])
def test_objective_mismatch_blocks_discovery_and_export(field):
    b=precursor_batch();b[field]='altered'
    with pytest.raises(ObjectiveBlocked):replay(b)
    with pytest.raises(ObjectiveBlocked):stamp_export(b)


def test_missing_objective_is_blocked():
    with pytest.raises(ObjectiveBlocked):replay({'documents':[]})


def test_lock_file_tampering_is_blocked(tmp_path):
    from bct.objective_lock import LOCK_PATH
    p=tmp_path/'lock.md';p.write_text(LOCK_PATH.read_text().replace('여러 독립적인','하나의'))
    with pytest.raises(ObjectiveBlocked):objective_binding(lock_path=p)


def test_live_cannot_backdate_and_history_keeps_first_detection():
    b=precursor_batch()
    with pytest.raises(ValueError):discover(b,now=NOW)
    first=replay(b);later=replay(public_reference(b),now='2020-02-05T00:00:00Z',previous=first)
    assert later['candidates'][0]['candidate_first_detected_at']==first['candidates'][0]['candidate_first_detected_at']
    assert later['outcomes'][0]['lead_time_days']==22


def test_future_unavailable_source_and_unverified_provenance_not_fused():
    for field,value in [('available_at','2020-02-05T00:00:00Z'),('provenance_verified',False)]:
        b=precursor_batch();b['documents'][1][field]=value
        assert not replay(b)['candidates']


def test_mismatched_scope_not_fused():
    b=precursor_batch();b['signals'][1]['region']='EU'
    assert not replay(b)['candidates']


def test_quantities_unknown_dates_unknown_do_not_create_candidate():
    b=precursor_batch();b['signals'][1]['available_date']=None
    assert not replay(b)['candidates']


def test_input_is_not_mutated():
    b=precursor_batch();copy=deepcopy(b);replay(b);assert b==copy


def test_cli_export_is_bound_and_mismatch_blocks_without_output(tmp_path):
    import subprocess,sys
    source=tmp_path/'input.json';out=tmp_path/'forecast.json'
    source.write_text(json.dumps(precursor_batch()))
    cmd=[sys.executable,'-m','bct.forecast_discovery','--input',str(source),'--output',str(out),
         '--mode','SYNTHETIC','--as-of',NOW]
    result=subprocess.run(cmd,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    exported=json.loads(out.read_text());require_objective(exported)
    assert len(exported['candidates'])==1 and out.stat().st_mode & 0o777 == 0o600
    bad=precursor_batch();bad['objective_sha256']='drift';source.write_text(json.dumps(bad));out.unlink()
    blocked=subprocess.run(cmd,capture_output=True,text=True)
    assert blocked.returncode==1 and 'BLOCKED' in blocked.stdout and not out.exists()


def test_confirmation_export_also_has_objective_and_bad_batch_cannot_write(tmp_path):
    from test_future_worker import sources
    from bct.future_manual_review import export_review_batch,import_review_results
    from bct.future_store import LocalJSONTransport
    paths=sources(tmp_path,1)
    path=tmp_path/'batch.json'
    batch=export_review_batch(LocalJSONTransport(),str(paths[1]),str(paths[2]),
                              cache_dir=paths[3],output=path,limit=1)
    require_objective(batch);assert batch['layer']=='CONFIRMATION'
    before=paths[2].read_bytes()
    batch['objective_version']='drift';path.write_text(json.dumps(batch))
    with pytest.raises(ObjectiveBlocked):
        import_review_results(LocalJSONTransport(),str(paths[1]),str(paths[2]),
                              batch_path=path,results_path=tmp_path/'not-used.json')
    assert paths[2].read_bytes()==before


def test_unknown_source_cannot_be_counted_as_independent_by_new_domain():
    b=precursor_batch();b['documents'][1].pop('origin_id')
    assert not replay(b)['candidates']


def test_same_origin_many_reprints_never_add_independence():
    b=precursor_batch();b['documents'][1].update(origin_id='buyer',origin_publisher='buyer',origin_url=b['documents'][0]['origin_url'])
    for i in range(4):
        doc=deepcopy(b['documents'][1]);doc['document_id']='copy-'+str(i)
        signal=deepcopy(b['signals'][1]);signal['document_id']=doc['document_id']
        b['documents'].append(doc);b['signals'].append(signal)
    assert not replay(b)['candidates']


def test_prior_first_detection_cannot_precede_source_availability():
    b=precursor_batch();previous=replay(b)
    previous['candidates'][0]['candidate_first_detected_at']='2019-01-01T00:00:00Z'
    with pytest.raises(ValueError):replay(b,previous=previous)


def test_wrong_objective_cannot_be_persisted_as_collection_metadata():
    from bct.future_store import apply_owned_patch
    with pytest.raises(ObjectiveBlocked):
        apply_owned_patch({},owner='collection',patch={'objective_version':'drift','objective_sha256':'drift'},operation_id='bad')


def test_discovery_quantity_gap_does_not_require_s3_coverage():
    b=precursor_batch();b['signals'][0]['quantity']=100
    b['signals'][1].update(quantity=80,available_date=None,coverage_complete=False)
    result=replay(b);c=result['candidates'][0]
    assert c['reason']=='POSSIBLE_QUANTITY_GAP'
    assert c['comparison']['supply_coverage']=='UNKNOWN' and 's_stage' not in c
    assert result['forecast_performance']['status']=='BLOCKED'
