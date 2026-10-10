"""Resolve only the explicitly authorized unused-import hash amendment.

Old activation bytes are immutable. An effective activation links the old
hashes and approval; no scoring, TARGET, source or cutover field is changed.
"""
from copy import deepcopy
import hashlib
import json


def resolve_activation(activation, current_hashes, amendment, forecast_bytes):
    previous = activation['engine_hashes']
    if previous == current_hashes:
        return deepcopy(activation)
    name = 'forecast_discovery.py'
    if (amendment.get('format') != 'bct-recovery-freeze-amendment-v1'
            or amendment.get('path') != 'src/bct/forecast_discovery.py'
            or amendment.get('runtime_behavior_change') is not False
            or amendment.get('historical_evidence_unchanged') is not True
            or amendment.get('other_three_frozen_engines_unchanged') is not True
            or not amendment.get('authorization') or not amendment.get('authorized_at')
            or set(previous) != set(current_hashes)
            or {key for key in previous if previous[key] != current_hashes[key]} != {name}
            or previous[name] != amendment['previous_sha256']
            or current_hashes[name] != amendment['amended_sha256']):
        raise ValueError('frozen engine change lacks the exact authorized amendment')
    old_import = b'from .objective_lock import ObjectiveBlocked, objective_binding, require_objective, stamp_export\n'
    new_import = b'from .objective_lock import ObjectiveBlocked, require_objective, stamp_export\n'
    if (forecast_bytes.count(new_import) != 1
            or hashlib.sha256(forecast_bytes).hexdigest() != current_hashes[name]
            or hashlib.sha256(forecast_bytes.replace(new_import, old_import, 1)).hexdigest() != previous[name]):
        raise ValueError('authorized import-only engine reconstruction differs')
    effective = deepcopy(activation)
    effective['engine_hashes'] = deepcopy(current_hashes)
    effective['engine_hash_amendment'] = {
        'previous_engine_hashes': deepcopy(previous),
        'amendment_sha256': hashlib.sha256(json.dumps(amendment, sort_keys=True,
            ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
        'authorization': amendment['authorization'], 'authorized_at': amendment['authorized_at'],
        'source_behavior_change': False, 'original_activation_preserved': True}
    return effective
