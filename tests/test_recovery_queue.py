from hashlib import sha256
import pytest
from bct.recovery_queue import project


def fixture(status='PARTIAL',read=True):
    body='Official text without adequate qualification and timing evidence.';digest=sha256(body.encode()).hexdigest()
    item={'body_sha256':digest,'body_chars':len(body),'body_status':status,
          'source_version':'v1','candidate':True,'url':'https://example.test/source'}
    candidates={'results':{'doc':{**item,'versions':{digest:item}}}}
    reviews={'old-reading':{'document_id':'doc','body_sha256':digest,'reader_version':'bct-v33-reader-1',
              'kind':'quick','read_start':0,'read_end':len(body),'disposition':'DATA_INSUFFICIENT',
              'read_complete':True,'reviewed_at':'2026-10-01T00:00:00+00:00'}} if read else {}
    tracking={'reviews':reviews,'runs':{}}
    versions=[{'document_id':'doc','old_body_sha256':digest,'source_version':'v1',
               'url':item['url'],'old_failure':'FULL_SOURCE_NOT_OBTAINED'}]
    return candidates,tracking,versions,body,digest


def test_partial_terminal_read_remains_source_wait_and_old_result_is_retained(tmp_path):
    c,t,v,body,digest=fixture()
    result=project(c,t,v,{},tmp_path)
    assert result['counts']['COMPLETED']==0 and result['counts']['SOURCE_WAIT']==1
    assert result['legacy_read_results']==result['legacy_partial_read_results']==1
    assert result['historical_completed_failed_overlap']==1
    assert result['completion_failure_state_overlap']==0
    assert t['reviews']['old-reading']['read_end']==len(body)


def test_real_exact_full_recovery_reopens_unread_work_without_completion(tmp_path):
    c,t,v,body,digest=fixture(read=False);(tmp_path/(digest+'.txt')).write_text(body)
    obs={v[0]['url']:{'body_status':'FULL','body_sha256':digest,'status':'FULL'}}
    result=project(c,t,v,obs,tmp_path)
    assert result['counts']['PENDING']==1 and result['counts']['COMPLETED']==0
    assert result['preserved_failure_versions']==1
    assert result['version_rows'][0]['old_failure']=='FULL_SOURCE_NOT_OBTAINED'
    (tmp_path/(digest+'.txt')).write_text('tampered')
    with pytest.raises(ValueError,match='hash/extent'):project(c,t,v,obs,tmp_path)


def test_different_source_version_or_a_permanent_denial_never_reopens_old_work(tmp_path):
    c,t,v,body,digest=fixture(read=False)
    obs={v[0]['url']:{'body_status':'FULL','body_sha256':'a'*64,'status':'FULL'}}
    assert project(c,t,v,obs,tmp_path)['counts']['SOURCE_WAIT']==1
    obs[v[0]['url']]={'status':'SOURCE_BLOCKED','body_status':'UNAVAILABLE'}
    assert project(c,t,v,obs,tmp_path)['counts']['FAILED']==1
    obs[v[0]['url']]={'status':'SOURCE_WAIT','body_status':'UNAVAILABLE','resume_after':2000}
    assert project(c,t,v,obs,tmp_path)['counts']['RETRY_SCHEDULED']==1


def test_full_reading_and_candidate_evidence_wait_are_two_distinct_axes(tmp_path):
    c,t,v,body,digest=fixture(status='FULL');v[0]['old_failure']='REQUIRED_EVIDENCE_MISSING'
    result=project(c,t,v,{},tmp_path)
    assert result['counts']['COMPLETED']==1 and result['counts']['EVIDENCE_WAIT']==0
    assert result['candidate_evidence_wait']==1 and result['legacy_read_results']==1
