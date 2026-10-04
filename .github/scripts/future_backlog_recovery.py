"""Bounded recovery through the existing collection pipeline, not a new reader.

The immutable request contains only IDs already in the operational database.
Bodies remain in the existing private cache and an authenticated, short-lived
Actions artifact; no third-party full text is published to a repository.
"""
import argparse
import json
import shutil
from pathlib import Path

from bct.future_bottleneck import run


def recover(db, candidates, tracking, cache, request, output):
    value = json.loads(Path(request).read_text())
    ids = value['document_ids']
    if not isinstance(ids, list) or len(ids) != len(set(ids)) or len(ids) > 1523:
        raise ValueError('invalid frozen operational document selection')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'future-candidates.json'
    shutil.copy2(candidates, target)
    for index in range(0, len(ids), 300):
        state = run(db, target, limit=300, workers=6, cache_dir=cache,
                    tracking_path=tracking, document_ids=ids[index:index + 300],
                    trigger='SCHEDULED', trigger_id=value['operation_id'],
                    patch_output=output / f'collection-change-{index // 300}.json')
        print(json.dumps({'batch': index // 300, 'processed': state['summary']['processed_this_run']}))


def main():
    p = argparse.ArgumentParser()
    for name in ('db', 'candidates', 'tracking', 'cache', 'request', 'output'):
        p.add_argument('--' + name, required=True, type=Path)
    recover(**vars(p.parse_args()))


if __name__ == '__main__':
    main()
