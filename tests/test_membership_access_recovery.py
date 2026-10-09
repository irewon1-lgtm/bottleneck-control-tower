from copy import deepcopy
import json
import pytest

from bct.future_body import extract_document,is_membership_landing_body,cache_body
from bct.recovery_sources import restore_observations
from bct.recovery_pilot import quarantine_corrected_readings
from bct.recovery_queue import corrected_version
from bct.recovery_restore import copy_preserved_caches

URL='https://www.northernminer.com/news/a-source/123/'
NOTICE='Keep reading The Northern Miner with a TNM NEWS+MARKETS Membership.\nAlready a member?\nSign In'


def test_login_redirect_with_closed_article_is_not_requested_full_source():
    html='<title>Free Article Limit Reached - The Northern Miner</title><link rel="canonical" href="https://www.northernminer.com/subscribe-login/"><article><p>'+NOTICE+'</p></article>'
    result=extract_document(html)
    assert result['body_status']=='UNAVAILABLE' and result['body']==''
    assert 'PAYWALL_OR_LOGIN_PREVIEW' in result['reasons']
    assert 'MEMBERSHIP_ACCESS_LIMIT' in result['reasons']


def test_generic_membership_news_and_sign_in_ui_do_not_establish_access_limit():
    assert not is_membership_landing_body('A membership organization orders new capacity.\nSign In',URL)
    assert not is_membership_landing_body(NOTICE,'https://company.example/news/')
    assert not is_membership_landing_body(NOTICE.replace('Already a member?','Newsletter signup'),URL)
    html='<article><p>A membership organization orders new capacity.</p></article>'
    assert extract_document(html)['body_status']=='FULL'


def test_cached_membership_landing_is_held_without_refetch_or_cache_deletion(tmp_path):
    digest=cache_body(tmp_path/'private-source-cache',NOTICE)
    before={'url':URL,'attempted':True,'status':'FULL','body_status':'FULL','body_sha256':digest,
            'body_chars':len(NOTICE),'reasons':[],'completeness':{'assessment':'ACCESSIBLE_STRUCTURE_ONLY'}}
    original=json.dumps(before); (tmp_path/'source-recovery-attempts.jsonl').write_text(original+'\n')
    observed,pending=restore_observations(tmp_path,tmp_path/'next')
    after=observed[URL]
    assert not pending and after['status']=='BLOCKED' and after['body_status']=='UNAVAILABLE'
    assert after['body_sha256']==digest and after['prior_observation_classification']['body_status']=='FULL'
    assert after['access_diagnostic']=={'category':'PAYWALL','state':'SOURCE_BLOCKED','retryable':False}
    assert (tmp_path/'private-source-cache'/(digest+'.txt')).read_text()==NOTICE
    assert (tmp_path/'source-recovery-attempts.jsonl').read_text()==original+'\n'
    assert corrected_version(after,digest) is after


def test_qualification_membership_reading_preserved_but_not_reused_as_completion():
    result={'document_id':'document','body_sha256':'hash','review':{'disposition':'DATA_INSUFFICIENT'}}
    pilot={'run_id':'old','mode':'QUALIFICATION','batches':[{'results':[result]}]};original=deepcopy(pilot)
    correction={'body_sha256':'hash','reclassification_rule':'MEMBERSHIP_ACCESS_LIMIT_V1'}
    resumable,held=quarantine_corrected_readings(pilot,{('document','hash'):correction})
    assert pilot==original and not resumable['batches'][0]['results'] and held[0]['result']==result
    assert held[0]['preserved_from_run_id']=='old'
    with pytest.raises(ValueError,match='exact source correction'):
        quarantine_corrected_readings(pilot,{('document','hash'):{**correction,'body_sha256':'wrong'}})


def test_historical_cache_union_retains_older_body_and_latest_checkpoint(tmp_path):
    source=tmp_path/'prior';output=tmp_path/'latest'
    digest=cache_body(source/'private-source-cache','old immutable source')
    cache_body(output/'private-source-cache','new immutable source')
    output.mkdir(exist_ok=True);(output/'checkpoint.json').write_text('latest owner')
    proof=copy_preserved_caches(source,output)
    assert proof['copied_files']==['private-source-cache/'+digest+'.txt']
    assert (output/'checkpoint.json').read_text()=='latest owner'
    assert len(list((output/'private-source-cache').glob('*.txt')))==2
    assert copy_preserved_caches(source,output)['copied_files']==[]


def test_historical_cache_tamper_fails_before_union(tmp_path):
    source=tmp_path/'prior';output=tmp_path/'latest';digest=cache_body(source/'private-source-cache','old')
    (source/'private-source-cache'/(digest+'.txt')).write_text('modified')
    with pytest.raises(ValueError,match='content hash differs'):copy_preserved_caches(source,output)
    assert not output.exists()
