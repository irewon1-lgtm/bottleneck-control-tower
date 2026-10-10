"""Required checks cannot be masked by a successful command that skipped tests."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

spec=importlib.util.spec_from_file_location('e2e_executor',Path(__file__).parents[1]/'.github/scripts/bct_e2e_recovery.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_null_body_hash_is_skipped_before_private_cache_path_construction(tmp_path):
    assert module.private_source_path(tmp_path,None) is None
    assert module.private_source_path(tmp_path,'a'*64) == tmp_path/'private-source-cache'/('a'*64+'.txt')


@pytest.mark.parametrize('class_name,test_name,reason,blocked',[
    ('tests.test_future_store','test_preserving_merge','environment missing',True),
    ('tests.test_forecast_discovery','test_D_real_pre_public_holdout',
     'BLOCKED: independent frozen real pre-public holdout and archived precursor facts unavailable',False)])
def test_zero_exit_does_not_approve_a_required_skipped_check(tmp_path,monkeypatch,class_name,test_name,reason,blocked):
    monkeypatch.setenv('GITHUB_RUN_ID','unit-test-only')
    def command(args,**kwargs):
        marker=next((a for a in args if a.startswith('--junitxml=')),None)
        if marker:
            Path(marker.split('=',1)[1]).write_text(
                '<testsuites><testsuite><testcase classname="'+class_name+'" name="'+test_name+'">'
                '<skipped message="'+reason+'"/></testcase></testsuite></testsuites>')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess,'run',command)
    report=module.quality(tmp_path)
    assert any(c['status']=='FAIL' for c in report['checks']) is blocked
    assert report['prediction_performance']=='UNVERIFIED'
    assert report['skipped_tests'][0]['prediction_only_external_blocker'] is (not blocked)
