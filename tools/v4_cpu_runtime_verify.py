#!/usr/bin/env python3
"""Verify the restored approved runtime without installation, inputs or inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

PIN = '221fa92b1cbff8950716ec373eac793ca340c873'
LOCK_SHA = '99aa48b5c7381c3c451769f8fbb8b21ef4f745a8e7b7c5dbdb15deb0312a8bb9'
MANIFEST_SHA = '5588cb168c4dcdac419b2a1ea269c2d5bbcc94d18e760949d2ac48b2bc43384b'
CREDENTIALS = {'GH_TOKEN', 'GITHUB_TOKEN', 'BCT_V4_PRIVATE_STATE_TOKEN', 'BCT_V4_STATE_PASSPHRASE'}


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def inventory(text):
    result = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9+_.-]+)', line.strip())
        if not match:
            raise ValueError('RUNTIME_DISTRIBUTION_FORMAT')
        name = re.sub(r'[-_.]+', '-', match[1]).lower()
        if name in result:
            raise ValueError('RUNTIME_DISTRIBUTION_DUPLICATE')
        result[name] = match[2]
    return result


def verify_inventory(lock, freeze):
    expected, actual = inventory(Path(lock).read_text()), inventory(freeze)
    if actual != expected:
        raise ValueError('LOCKED_DISTRIBUTIONS_MISMATCH')
    return {'packages': len(actual), 'extra_packages': [], 'installed': dict(sorted(actual.items()))}


def health_environment(environment, code_root):
    result = {k: v for k, v in environment.items() if k not in CREDENTIALS}
    result.update(PYTHONPATH=str(Path(code_root).resolve() / 'src'), HF_HUB_OFFLINE='1',
                  TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                  OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
    return result


def checked(command, *, environment):
    process = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=120)
    if process.returncode:
        raise ValueError('RUNTIME_VERIFICATION_SUBPROCESS_FAILED')
    return process.stdout


def verify(code_root, runtime, *, expected_code_pin=PIN):
    code_root, runtime = Path(code_root).resolve(), Path(runtime).resolve()
    if sys.version_info[:3] != (3, 12, 15) or sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise ValueError('RUNTIME_PYTHON_OR_PLATFORM_MISMATCH')
    environment = health_environment(os.environ, code_root)
    if not isinstance(expected_code_pin,str) or not re.fullmatch('[0-9a-f]{40}',expected_code_pin):
        raise ValueError('RUNTIME_EXPECTED_EXECUTION_PIN_INVALID')
    if checked(['git', '-C', str(code_root), 'rev-parse', 'HEAD'], environment=environment).strip() != expected_code_pin:
        raise ValueError('RUNTIME_EXECUTION_CODE_PIN_MISMATCH')
    lock = code_root / 'scripts/v4/requirements.lock'
    manifest_path = code_root / 'docs/v4/cpu-automation/preflight/model-manifest.json'
    if digest(lock) != LOCK_SHA or digest(manifest_path) != MANIFEST_SHA:
        raise ValueError('RUNTIME_LOCK_OR_MANIFEST_MISMATCH')
    freeze = checked([sys.executable, '-m', 'pip', 'freeze', '--all'], environment=environment)
    packages = verify_inventory(lock, freeze)
    checked([sys.executable, '-m', 'pip', 'check'], environment=environment)
    manifest = json.loads(manifest_path.read_text())
    model = runtime / 'models/gliner2-base-v1'
    files = []
    for entry in manifest['files']:
        path = (model / entry['path']).resolve()
        if not path.is_relative_to(model) or digest(path) != entry['sha256']:
            raise ValueError('RUNTIME_MODEL_FILE_MISMATCH')
        files.append({'path': entry['path'], 'sha256': entry['sha256'], 'bytes': path.stat().st_size})
    payload = sum(p.stat().st_size for root in (Path(sys.executable).parent.parent, runtime)
                  for p in root.rglob('*') if p.is_file())
    if payload >= 3 * 1024 ** 3:
        raise ValueError('RUNTIME_PAYLOAD_3GIB_LIMIT')
    # Only load/eval the pinned local model. No extract/read/queue/DB operation.
    child_code = ('import json,sys;from pathlib import Path;'
                  'from bct.v4 import cpu_automation,cpu_resume,cpu_review,public_research;'
                  'from bct.v4.cpu_operations import runtime_probe;'
                  'print("BCT_OFFLINE_HEALTH="+json.dumps(runtime_probe(Path(sys.argv[1]),'
                  'json.loads(Path(sys.argv[2]).read_text()),load=True)))')
    output = checked([sys.executable, '-c', child_code, str(runtime), str(manifest_path)],
                     environment=environment)
    health = [json.loads(line.split('=', 1)[1]) for line in output.splitlines()
              if line.startswith('BCT_OFFLINE_HEALTH=')]
    if len(health) != 1 or not health[0]['model_load_health_probe'] or health[0]['new_CPU_inferences'] != 0:
        raise ValueError('RUNTIME_OFFLINE_HEALTH_PROOF_INVALID')
    return {'status': 'PASS_SAME_APPROVED_SEED_RUNTIME_VERIFIED', 'execution_code_SHA': expected_code_pin,
            'approved_seed_execution_code_SHA':PIN,
            'python': platform.python_version(), 'platform': 'Linux-X64', 'lock_sha256': LOCK_SHA,
            'manifest_sha256': MANIFEST_SHA, 'packages': packages, 'pip_check': 'PASS',
            'model': manifest['model'], 'revision': manifest['revision'], 'model_files': files,
            'model_file_bytes': sum(item['bytes'] for item in files), 'runtime_payload_bytes': payload,
            'offline_health': health[0], 'new_CPU_inferences': 0, 'DB_writes': 0,
            'pipeline_imports_verified':['cpu_automation','cpu_resume','cpu_review','public_research'],
            'model_downloads': 0, 'runtime_installs': 0, 'private_credentials_passed': False,
            'CPU_enabled_changed': False, 'old_runtime_binary_identity': 'NOT_CLAIMED'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=Path('.v4-cpu-runtime'))
    parser.add_argument('--expected-code-pin',default=PIN,help='Reviewed immutable execution SHA; model and lock hashes stay fixed')
    args = parser.parse_args()
    print('BCT_RUNTIME_VERIFY_JSON=' + json.dumps(verify(args.code_root, args.runtime,expected_code_pin=args.expected_code_pin), sort_keys=True))
