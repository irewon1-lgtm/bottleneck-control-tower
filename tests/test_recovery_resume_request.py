"""The shipped recovery request must satisfy the real workflow's restore contract."""
import json
from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_default_resume_request_has_authenticated_same_release_inputs():
    request = json.loads((ROOT / '.github/bct-recovery-request.json').read_text())
    release = json.loads((ROOT / 'config/bct-operating-release.json').read_text())
    # Never resume an unavailable older request while citing a newer release.
    assert str(request['resume_run_id']) == str(release['gate_run_id'])
    pins = request['resume_file_sha256']
    assert {'checkpoint.json', 'source-recovery-attempts.jsonl',
            'source-recovery-versions.json', 'recovery-preservation-seal.json',
            'local-reader-setup.json', 'local-reader-probe.json',
            'native-claim-history.json'} <= pins.keys()
    assert all(re.fullmatch('[0-9a-f]{64}', value) for value in pins.values())
    assert re.fullmatch('[0-9a-f]{64}', request['resume_cache_inventory_sha256'])
    workflow = yaml.safe_load((ROOT / '.github/workflows/bct-recovery.yml').read_text())
    step = next(s for s in workflow['jobs']['storage']['steps']
                if s.get('name') == 'Verify restored checkpoint journal and every source cache hash')
    assert "request.get('resume_file_sha256',{})" in step['run']
    assert "expected_cache_inventory=request['resume_cache_inventory_sha256']" in step['run']
