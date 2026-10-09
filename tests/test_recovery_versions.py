from copy import deepcopy
from hashlib import sha256
import pytest
from bct.recovery_versions import append_observed_versions


def data(tmp_path,status='FULL'):
    body='Demand for high-voltage transformers increased. Qualified supply and timing are unknown.'
    digest=sha256(body.encode()).hexdigest();old='a'*64
    c={'results':{'doc':{'url':'https://example.test/source','body_sha256':old,
        'decision':'OBSERVE','score':7,'versions':{old:{'body_status':'PARTIAL','score':7}}}}}
    v=[{'document_id':'doc','source_version':'old','old_body_sha256':old,'old_failure':'FULL_SOURCE_NOT_OBTAINED'}]
    o={c['results']['doc']['url']:{'body_status':status,'body_sha256':digest,'body_chars':len(body),
        'attempted_at':'2026-10-09T18:00:00+00:00'}}
    (tmp_path/(digest+'.txt')).write_text(body)
    return c,v,o,digest


def test_changed_body_is_a_linked_new_version_without_replacing_previous_judgment(tmp_path):
    c,v,o,digest=data(tmp_path);before=deepcopy(c)
    result,added=append_observed_versions(c,v,o,tmp_path)
    assert c==before and len(added)==1
    r=result['results']['doc'];new=r['versions'][digest]
    assert r['score']==7 and r['body_sha256']=='a'*64 and r['decision']=='OBSERVE'
    assert 'score' not in new and new['publication_verified'] is False
    assert new['source_recovery']['prior_versions'][0]['failure']=='FULL_SOURCE_NOT_OBTAINED'
    rerun,newly_added=append_observed_versions(result,v,o,tmp_path)
    assert rerun==result and newly_added==[]


def test_partial_observation_is_never_promoted_and_corrupt_cache_is_rejected(tmp_path):
    c,v,o,digest=data(tmp_path,status='PARTIAL')
    result,_=append_observed_versions(c,v,o,tmp_path)
    assert result['results']['doc']['versions'][digest]['body_status']=='PARTIAL'
    (tmp_path/(digest+'.txt')).write_text('changed')
    with pytest.raises(ValueError,match='hash/extent'):
        append_observed_versions(c,v,o,tmp_path)
