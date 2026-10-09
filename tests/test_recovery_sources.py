import json
import pytest
from bct.future_body import cache_body
from bct.recovery_sources import restore_observations, host_cooldowns


def write(root, records):
    (root / 'source-recovery-attempts.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))


def test_resume_checks_bodies_and_does_not_retry_denied_sources(tmp_path):
    root = tmp_path / 'old';root.mkdir()
    digest = cache_body(root / 'private-source-cache', 'Real saved source snapshot.')
    write(root, [
        {'url':'https://a.test/doc','attempted':True,'body_sha256':digest,'status':'FULL'},
        {'url':'https://b.test/doc','attempted':True,'status':'SOURCE_BLOCKED',
         'access_diagnostic':{'category':'HTTP_403'}},
        {'url':'https://c.test/doc','attempted':False,'status':'SOURCE_WAIT','reason':'RUNNER_DEADLINE'},
    ])
    observed, pending = restore_observations(root, tmp_path/'new')
    assert set(observed) == {'https://a.test/doc','https://b.test/doc'}
    assert set(pending) == {'https://c.test/doc'}
    assert (tmp_path/'new'/(digest+'.txt')).read_text() == 'Real saved source snapshot.'
    (root/'private-source-cache'/(digest+'.txt')).write_text('corruption')
    with pytest.raises(ValueError, match='hash mismatch'):
        restore_observations(root, tmp_path/'new')


def test_rate_limit_cooldown_survives_runner_resume(tmp_path):
    write(tmp_path, [
        {'url':'https://a.test/doc','attempted':True,'status':'SOURCE_WAIT','resume_after':900,
         'access_diagnostic':{'category':'HTTP_429'}},
        {'url':'https://a.test/next','attempted':False,'status':'SOURCE_WAIT',
         'resume_after':900,'reason':'HOST_RATE_LIMIT'},
    ])
    observed, pending = restore_observations(tmp_path, tmp_path/'cache', now=800)
    assert len(observed)==1 and len(pending)==1
    assert host_cooldowns({**observed,**pending},now=800)=={'a.test':900}
    observed, pending = restore_observations(tmp_path,tmp_path/'cache',now=901)
    assert len(observed)==0 and len(pending)==2
    assert host_cooldowns(pending,now=901)=={}


def test_technical_error_requires_changed_code_before_retry(tmp_path):
    write(tmp_path,[{'url':'https://a.test/doc','attempted':True,'status':'ERROR'}])
    assert len(restore_observations(tmp_path,tmp_path/'cache')[0])==1
    assert len(restore_observations(tmp_path,tmp_path/'cache',retry_errors=True)[1])==1


def test_resume_corrects_control_only_full_but_preserves_observation_and_hash(tmp_path):
    digest = cache_body(tmp_path/'private-source-cache', 'Save Article')
    write(tmp_path, [{'url':'https://a.test/doc','attempted':True,
                     'body_sha256':digest,'body_status':'FULL','status':'FULL'}])
    observed, pending = restore_observations(tmp_path, tmp_path/'restored')
    record = observed['https://a.test/doc']
    assert not pending
    assert record['status'] == record['body_status'] == 'UNAVAILABLE'
    assert record['prior_observation_classification']['status'] == 'FULL'
    assert record['prior_observation_classification']['body_sha256'] == digest
    assert (tmp_path/'restored'/(digest+'.txt')).read_text() == 'Save Article'
    assert record['reclassification_rule'] == 'ARTICLE_CONTROL_ONLY_V1'
