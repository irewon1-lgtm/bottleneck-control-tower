from copy import deepcopy
import json
from pathlib import Path
import pytest

from bct import precursor_collection as collection, forecast_discovery
from bct.recovery_freeze import resolve_activation


def inputs():
    amendment = json.loads((Path(__file__).parents[1]/'config/bct-recovery-freeze-amendment.json').read_text())
    current = collection.hashes()
    previous = {**current, 'forecast_discovery.py': amendment['previous_sha256']}
    activation = {'engine_hashes': previous, 'excluded_document_ids': ['old'],
                  'new_document_cutover': '2026-10-05T00:00:00Z', 'policy': 'preserve'}
    return activation, current, amendment, Path(forecast_discovery.__file__).read_bytes()


def test_authorized_import_change_preserves_original_activation_and_every_other_field():
    activation, current, amendment, raw = inputs()
    before = deepcopy(activation)
    effective = resolve_activation(activation, current, amendment, raw)
    assert activation == before
    assert effective['engine_hashes'] == current
    assert effective['engine_hash_amendment']['previous_engine_hashes'] == before['engine_hashes']
    assert {k:v for k,v in effective.items() if k not in ('engine_hashes','engine_hash_amendment')} == {
        k:v for k,v in before.items() if k != 'engine_hashes'}


@pytest.mark.parametrize('broken', ['other_engine', 'source_change', 'missing_approval', 'wrong_previous'])
def test_unknown_engine_change_or_wider_edit_cannot_use_the_import_amendment(broken):
    activation, current, amendment, raw = inputs()
    if broken == 'other_engine':
        current['early_forecast.py'] = 'unknown'
    elif broken == 'source_change':
        raw += b'\n# an additional edit\n'
    elif broken == 'missing_approval':
        amendment['authorization'] = ''
    else:
        activation['engine_hashes']['forecast_discovery.py'] = 'unknown'
    with pytest.raises(ValueError):
        resolve_activation(activation, current, amendment, raw)


def test_existing_collector_activation_is_append_only_and_effective_binding_survives_resume(tmp_path):
    activation, current, _, _ = inputs()
    path = tmp_path/'activation.json'
    original = json.dumps(activation, indent=2).encode()
    path.write_bytes(original)
    effective = collection.init(tmp_path, {})
    assert path.read_bytes() == original and effective['engine_hashes'] == current
    records = list((tmp_path/'activation-amendments').glob('*.json'))
    assert len(records) == 1
    prior = records[0].read_bytes()
    assert collection.init(tmp_path, {}) == effective
    assert records[0].read_bytes() == prior and path.read_bytes() == original
