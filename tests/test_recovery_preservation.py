from copy import deepcopy
import pytest
from bct.recovery_preservation import digest,verify,seal


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
