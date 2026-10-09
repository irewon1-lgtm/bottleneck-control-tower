"""Fail closed on a resumed checkpoint or cache whose bytes changed."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def verify_restored(root, expected, *, expected_cache_inventory=None):
    root=Path(root)
    if not expected or 'checkpoint.json' not in expected or 'source-recovery-attempts.jsonl' not in expected:
        raise ValueError('pinned checkpoint and source journal hashes required')
    for name,digest in expected.items():
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or not re.fullmatch(r'[0-9a-f]{64}',digest):
            raise ValueError('invalid recovery restore hash binding')
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('restored checkpoint file hash differs')
    counts={};inventory=[]
    for directory,suffix in (('private-source-cache','.txt'),('private-evidence-cache','.txt'),
                             ('private-evidence-raw','.bin'),('private-source-html','.html')):
        count=0
        for path in (root/directory).glob('*'+suffix):
            if (not re.fullmatch(r'[0-9a-f]{64}',path.stem)
                    or hashlib.sha256(path.read_bytes()).hexdigest()!=path.stem):
                raise ValueError('restored private source content hash differs')
            count+=1
            inventory.append(path.relative_to(root).as_posix())
        counts[directory]=count
    inventory_digest=hashlib.sha256(json.dumps(sorted(inventory),separators=(',',':')).encode()).hexdigest()
    if expected_cache_inventory is not None and inventory_digest!=expected_cache_inventory:
        raise ValueError('restored private source inventory differs')
    return {'status':'PASS','verified_pinned_files':dict(expected),'verified_cache_files':counts,
            'cache_inventory_sha256':inventory_digest}
