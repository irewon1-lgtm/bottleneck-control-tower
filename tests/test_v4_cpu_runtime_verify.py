"""Runtime recovery checks use only package metadata and tiny authored fixtures."""
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def verifier():
    spec = importlib.util.spec_from_file_location('runtime_verify', ROOT / 'tools/v4_cpu_runtime_verify.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_installed_inventory_requires_all_and_only_exact_locked_versions(tmp_path):
    module = verifier()
    lock = tmp_path / 'requirements.lock'
    lock.write_text('torch==2.8.0+cpu\nPyYAML==6.0.3\n')
    proof = module.verify_inventory(lock, 'torch==2.8.0+cpu\nPyYAML==6.0.3\n')
    assert proof['packages'] == 2 and proof['extra_packages'] == []
    for freeze in ('torch==2.8.0\nPyYAML==6.0.3\n', 'torch==2.8.0+cpu\n',
                   'torch==2.8.0+cpu\nPyYAML==6.0.3\nextra==1\n'):
        with pytest.raises(ValueError, match='LOCKED_DISTRIBUTIONS_MISMATCH'):
            module.verify_inventory(lock, freeze)


def test_nonversion_requirement_or_freeze_fails_without_echoing_url(tmp_path):
    module = verifier()
    lock = tmp_path / 'requirements.lock'
    lock.write_text('torch==2.8.0+cpu\n')
    with pytest.raises(ValueError, match='RUNTIME_DISTRIBUTION_FORMAT') as caught:
        module.verify_inventory(lock, 'bad @ https://private:credential@example.invalid/pkg\n')
    assert 'credential' not in str(caught.value)


def test_health_environment_removes_credentials_and_forces_offline():
    module = verifier()
    env = module.health_environment({'PATH': '/bin', 'GH_TOKEN': 'never-export',
        'BCT_V4_PRIVATE_STATE_TOKEN': 'private', 'BCT_V4_STATE_PASSPHRASE': 'secret',
        'GITHUB_TOKEN': 'no-export'}, ROOT)
    assert not any(name in env for name in module.CREDENTIALS)
    assert env['HF_HUB_OFFLINE'] == env['TRANSFORMERS_OFFLINE'] == '1'
    assert env['PYTHONPATH'] == str(ROOT / 'src')


def test_runtime_job_only_restores_approved_cache_and_has_no_secrets_or_inference():
    workflow = yaml.load((ROOT / '.github/workflows/v4-cpu-private-research.yml').read_text(), Loader=yaml.BaseLoader)
    assert 'runtime-verify' in workflow['on']['workflow_dispatch']['inputs']['purpose']['options']
    job = workflow['jobs']['runtime-verify']
    assert "inputs.purpose == 'runtime-verify'" in job['if']
    assert "github.ref == 'refs/heads/codex/bct-v4-integration'" in job['if']
    text = yaml.dump(job)
    assert 'secrets.' not in text and 'pip install' not in text
    assert 'bootstrap-model' not in text and ' process ' not in text
    cache = next(s for s in job['steps'] if s.get('uses') == 'actions/cache/restore@v4')
    assert cache['with']['fail-on-cache-miss'] == 'true'
    checkouts = [s['with'] for s in job['steps'] if s.get('uses') == 'actions/checkout@v4']
    assert any(s.get('ref') == '${{ env.CPU_CODE_SHA }}' for s in checkouts)
    assert '--expected-code-pin "$CPU_CODE_SHA"' in job['steps'][-1]['run']
