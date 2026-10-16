"""Deployment gates for the source-separated consumer, never a schedule test."""
import ast,json,re
from pathlib import Path
import yaml


def test_deployed_consumer_requires_exact_configured_code_and_explicit_enable():
    path=Path(__file__).resolve().parents[1]/'.github/workflows/v4-cpu-private-research.yml'
    w=yaml.safe_load(path.read_text());triggers=w.get('on',w.get(True))
    assert set(triggers)=={'workflow_run','workflow_dispatch'}
    assert triggers['workflow_run']['workflows']==['New precursor evidence acquisition']
    assert w['permissions']=={'contents':'read','actions':'read'}
    sha=w['env']['CPU_CODE_SHA'];assert re.fullmatch('[0-9a-f]{40}',sha)
    assert sha==w['env']['EXPECTED_CPU_CODE_SHA']
    guard=w['jobs']['research']['if']
    assert "vars.BCT_V4_CPU_CODE_SHA == '"+sha+"'"in guard
    assert "vars.BCT_V4_CPU_RESEARCH_ENABLED == 'true'"in guard
    assert "head_branch == 'main'"in guard and "conclusion == 'success'"in guard
    assert 'BCT_V4_PRIVATE_STATE_TOKEN'not in json.dumps(w['jobs']['research'])
    text=path.read_text()
    assert 'verify-scope'not in text and 'upload-artifact'not in text
    # The approved manual official-format job needs the existing lightweight
    # XLSX/core dependencies. The scheduled CPU path must still never install
    # anything. Check the actual execution boundary, not an unrelated job's text.
    installers=[]
    for name,job in w['jobs'].items():
        for step in job['steps']:
            if 'pip install'not in step.get('run',''):continue
            installers.append((name,step))
            assert name=='q1-source-process'
            assert step['if']=="${{ inputs.purpose == 'official-sources' }}"
            assert step['run']=="timeout 120 python -m pip install -e '.[quantitative]' --disable-pip-version-check"
    assert len(installers)==1
    prior=w['jobs']['q1-source-prior']['if']
    assert "github.event_name == 'workflow_dispatch'"in prior
    assert "github.ref == 'refs/heads/codex/bct-v4-integration'"in prior
    assert w['jobs']['q1-source-process']['needs']=='q1-source-prior'
    assert 'BCT_V4_PRIVATE_STATE_TOKEN'not in json.dumps(w['jobs']['q1-source-process'])
    import tomllib
    project=tomllib.loads((path.parents[2]/'pyproject.toml').read_text())['project']
    assert project['optional-dependencies']['quantitative']==['openpyxl==3.1.5']
    assert all(not any(x in d.lower()for x in ['torch','transformers','gliner','cuda'])for d in project['dependencies'])
    assert '--reuse-verified-scope'in text
    for job in w['jobs'].values():
        assert job['runs-on']=='ubuntu-24.04'
        for step in job['steps']:
            if "<<'PYCODE'"in step.get('run',''):
                ast.parse(step['run'].split("<<'PYCODE'\n",1)[1].rsplit('\nPYCODE',1)[0])
            if step.get('uses','').startswith('actions/cache/save'):
                assert step['with']['path']in ('var/v4/cpu-private/result','var/v4/cpu-private/bridge','var/v4/quantitative/q1-transfer','var/v4/quantitative/q1-source-probe','var/v4/quantitative/q1-source-bridge/prior','var/v4/quantitative/q1-source-bridge/result')
