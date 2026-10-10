from hashlib import sha256
from urllib.error import HTTPError
import pytest
from bct.recovery_capture import capture, cached_body


def response(raw,truncated=False):
    return {'raw':raw,'final_url':'https://www.nist.gov/article','status':200,
            'content_type':'text/html','truncated':truncated}


def test_actual_raw_and_body_are_preserved_without_host_based_provenance(tmp_path):
    raw=b'<article><p>NIST research describes electrical measurements.</p></article>'
    observation=capture('https://www.nist.gov/article',tmp_path,fetch=lambda _:response(raw))
    assert observation['raw_sha256']==sha256(raw).hexdigest()
    assert (tmp_path/'private-evidence-raw'/(observation['raw_sha256']+'.bin')).read_bytes()==raw
    assert observation['source_proof']['provenance']=='BLOCKED'
    assert observation['source_proof']['provenance_verified'] is False
    assert 'electrical measurements' in cached_body(tmp_path,observation)


def test_truncated_or_tampered_capture_cannot_pass(tmp_path):
    raw=b'<article><p>A closed article is insufficient if the capture is truncated.</p></article>'
    observation=capture('https://www.nist.gov/article',tmp_path,fetch=lambda _:response(raw,True))
    assert observation['body_status']=='PARTIAL'
    assert observation['source_proof']['checks']['untruncated_capture'] is False
    path=tmp_path/'private-evidence-cache'/(observation['body_sha256']+'.txt');path.write_text('changed')
    with pytest.raises(ValueError,match='body hash mismatch'):cached_body(tmp_path,observation)


def test_access_denial_remains_a_distinct_source_hold(tmp_path):
    def denied(_):raise HTTPError('https://www.nist.gov/article',403,'Denied',{},None)
    result=capture('https://www.nist.gov/article',tmp_path,fetch=denied)
    assert result['status']=='SOURCE_BLOCKED'
    assert result['access_diagnostic']['category']=='HTTP_403'
    assert 'source_proof' not in result
