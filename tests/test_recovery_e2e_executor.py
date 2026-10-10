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


class GenerationTransport:
    def __init__(self,heads):
        self.heads=iter(heads);self.reads=[]
    def head(self):return next(self.heads)
    def read_at(self,path,commit):
        self.reads.append((path,commit))
        return SimpleNamespace(path=path,commit=commit)


def test_atomic_generation_reads_both_roots_from_one_commit():
    transport=GenerationTransport(['generation-a'])
    commit,candidates,tracking=module.read_atomic_generation(transport)
    assert commit=='generation-a'
    assert candidates.commit==tracking.commit==commit
    assert transport.reads==[('future-candidates.json',commit),('future-tracking.json',commit)]


def test_latest_generation_accepts_one_advance_but_rejects_a_moving_ref():
    transport=GenerationTransport(['generation-b','generation-b'])
    commit,candidates,tracking=module.read_latest_stable_generation(transport)
    assert commit==candidates.commit==tracking.commit=='generation-b'
    with pytest.raises(RuntimeError,match='changed repeatedly'):
        module.read_latest_stable_generation(GenerationTransport(['generation-b','generation-c']))


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
