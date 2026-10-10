from copy import deepcopy
import pytest
from bct.recovery_preservation import digest,verify,seal,restore_version_records


def inputs():
    candidates={'results':{'doc':{'versions':{'body':{'body_status':'FULL','body_chars':10,'candidate':True}},'url':'https://a.test/doc'}}}
    review={'kind':'quick','document_id':'doc','body_sha256':'body','reader_version':'bct-v33-reader-1',
            'read_start':0,'read_end':10,'disposition':'IRRELEVANT'}
    failure={'id':'failed','type':'queue_resolution','state':'FAIL'}
    tracking={'reviews':{'review':review},'runs':[failure],'targets':[]}
    baseline={'document_ids':['doc'],'version_hashes':{'doc':['body']},'completed_versions':[['doc','body']],
              'review_hashes':{'review':digest(review)},'failed_run_hashes':{'failed':digest(failure)}}
    return candidates,tracking,baseline


def test_equal_counts_cannot_hide_replaced_review_or_failure():
    candidates,tracking,baseline=inputs()
    assert verify(candidates,tracking,baseline)['status']=='PASS'
    corrupted=deepcopy(tracking);corrupted['reviews']['review']['disposition']='DATA_INSUFFICIENT'
    with pytest.raises(ValueError,match='review changed'):verify(candidates,corrupted,baseline)
    corrupted=deepcopy(tracking);corrupted['runs'][0]['state']='COMPLETED'
    with pytest.raises(ValueError,match='failure history'):verify(candidates,corrupted,baseline)


def test_new_inflow_allowed_but_old_versions_must_remain():
    candidates,tracking,baseline=inputs()
    candidates['results']['new']={'versions':{}}
    assert verify(candidates,tracking,baseline)['preserved_candidates']==1
    candidates['results']['doc']['versions'].clear()
    with pytest.raises(ValueError,match='version missing'):verify(candidates,tracking,baseline)


def test_recovered_seal_preserves_new_reads_and_version_judgments_beyond_static_baseline():
    candidates,tracking,_=inputs()
    candidates['results']['doc']['versions']['body']['score']=7
    baseline=seal(candidates,tracking)
    assert verify(candidates,tracking,baseline)['status']=='PASS'
    candidates['results']['doc']['versions']['body']['score']=8
    with pytest.raises(ValueError,match='version judgment'):verify(candidates,tracking,baseline)


def test_restore_sealed_version_only_keeps_new_observation_and_versions():
    trusted,tracking,_=inputs()
    trusted['results']['doc']['observation']='old'
    baseline=seal(trusted,tracking)
    current=deepcopy(trusted)
    current['results']['doc']['observation']='new'
    current['results']['doc']['acquisition']={'history':['new source check']}
    current['results']['doc']['versions']['body']['score']=99
    current['results']['doc']['versions']['new-body']={'body_status':'PARTIAL'}

    repaired,receipts=restore_version_records(current,baseline,trusted)

    assert verify(repaired,tracking,baseline)['status']=='PASS'
    assert repaired['results']['doc']['observation']=='new'
    assert repaired['results']['doc']['acquisition']=={'history':['new source check']}
    assert repaired['results']['doc']['versions']['new-body']=={'body_status':'PARTIAL'}
    assert receipts==[{'document_id':'doc','body_sha256':'body',
                       'before_sha256':digest(current['results']['doc']['versions']['body']),
                       'restored_sha256':baseline['version_record_hashes']['doc']['body']}]


def test_restore_refuses_untrusted_replacement():
    trusted,tracking,_=inputs();baseline=seal(trusted,tracking)
    current=deepcopy(trusted);current['results']['doc']['versions']['body']['score']=99
    bad=deepcopy(trusted);bad['results']['doc']['versions']['body']['score']=7
    with pytest.raises(ValueError,match='trusted generation'):
        restore_version_records(current,baseline,bad)
