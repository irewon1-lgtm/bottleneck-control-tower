"""Exact Session 4 manual CPU transport pin cannot affect scheduled production."""
from pathlib import Path
import re
import yaml

OLD='6e788d18cf85fdb834b451bb35585a8b58925301'
S4='3ac2253c1a0a8807eff57b66b5dd88a02fcbd07c'
INPUT='43645932280'


def workflow():
    return yaml.safe_load((Path(__file__).resolve().parents[1]/
        '.github/workflows/v4-cpu-private-research.yml').read_text())


def test_one_source_only_manual_execution_has_identical_research_and_writer_pin():
    w=workflow()
    assert w['env']['CPU_CODE_SHA']==w['env']['EXPECTED_CPU_CODE_SHA']==OLD
    for name in ('research','publish'):
        env=w['jobs'][name]['env']
        pinned=env['CPU_CODE_SHA']
        assert pinned==env['EXPECTED_CPU_CODE_SHA']
        assert pinned.count(OLD)==1 and pinned.count(S4)==1 and pinned.count(INPUT)==1
        assert 'github.event_name == \'workflow_dispatch\'' in pinned
        assert 'inputs.purpose == \'manual-research\'' in pinned
        assert 'inputs.acquisition_run == \'43645932280\'' in pinned
        assert pinned.endswith("|| '"+OLD+"' }}")


def test_no_runtime_activation_bypass_or_private_token_to_reader():
    w=workflow()
    job=w['jobs']['research']
    assert "vars.BCT_V4_CPU_CODE_SHA == '"+OLD+"'" in job['if']
    assert "vars.BCT_V4_CPU_RESEARCH_ENABLED == 'true'" in job['if']
    assert 'BCT_V4_PRIVATE_STATE_TOKEN' not in str(job)
    assert all(z['runs-on']=='ubuntu-24.04' for z in w['jobs'].values())
    pub=w['jobs']['publish']
    assert pub['needs']=='research'
    assert w['permissions']=={'contents':'read','actions':'read'}
    assert 'BCT_V4_PRIVATE_STATE_TOKEN' not in str(w['jobs']['runtime-verify'])
