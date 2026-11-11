"""A fresh public processing generation overlays, rather than rewrites, history."""
import importlib.util
import json
from pathlib import Path

import pytest

from bct.v4.public_research import encoded, seal
from bct.objective_lock import stamp_export
from test_v4_public_research import project

ROOT = Path(__file__).resolve().parents[1]


def exporter():
    spec = importlib.util.spec_from_file_location('static_public_export', ROOT / 'tools/v4_dashboard_static_export.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_current_processing_generation_and_original_historical_timestamp_remain_distinct(tmp_path):
    public = project(tmp_path / 'fixture')
    inputs = tmp_path / 'inputs'; inputs.mkdir()
    (inputs / 'research.json').write_bytes(encoded(public))
    transport = stamp_export({'format': 'bct-public-transport-cursor-1', 'artifact_id': None,
                              'artifact_created_at': None, 'pending_reason': 'SCAN_BOUND'})
    (inputs / 'transport.json').write_bytes(encoded(transport))
    destination = ROOT / 'var/v4/pages-site'
    exporter().export(ROOT, destination, '1' * 40, public_input=inputs)
    data = json.loads((destination / 'api/dashboard.json').read_text())
    manifest = json.loads((destination / 'build-manifest.json').read_text())
    assert data['historical_data_at'].startswith('2026-10-14')
    assert data['data_at'] == public['clocks']['data_at']
    assert data['operating_research']['generation'] == manifest['research_generation'] == public['generation']
    assert data['counts']['evidence'] == 511
    assert json.loads((destination / 'api/research.json').read_text()) == public
    assert data['public_transport'] == transport
    assert manifest['transport_cursor_sha256']
    assert 'PRIVATE ORIGINAL' not in (destination / 'api/research.json').read_text()


def test_invalid_public_receipt_cannot_replace_existing_static_export(tmp_path):
    public = project(tmp_path / 'fixture')
    public['trace'][0]['quote'] = 'new private source text'
    inputs = tmp_path / 'inputs'; inputs.mkdir()
    (inputs / 'research.json').write_bytes(encoded(seal(public)))
    destination = ROOT / 'var/v4/pages-site'; destination.mkdir(parents=True, exist_ok=True)
    marker = destination / 'keep-existing'; marker.write_text('preserved')
    with pytest.raises(ValueError, match='FIELDS'):
        exporter().export(ROOT, destination, '1' * 40, public_input=inputs)
    assert marker.read_text() == 'preserved'
