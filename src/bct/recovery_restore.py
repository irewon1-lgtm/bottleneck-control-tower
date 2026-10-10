"""Fail closed on a resumed checkpoint or cache whose bytes changed."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil


LATEST_ROOT_STATE = (
    'source-audit.json',
    'source-recovery-attempts.jsonl',
    'source-recovery-versions.json',
    'evidence-recovery-observations.json',
    'evidence-recovery-searches.json',
    'evidence-recovery-versions.json',
    'local-reader-setup.json',
    'local-reader-probe.json',
    'private-local-reader-execution.jsonl',
    'recovery-preservation-seal.json',
    'queue-recovery-versions.json',
    'operating-engine-checkpoint.json',
)


def copy_latest_root_state(source, destination):
    """Carry verified latest journals through failures before their gate runs."""
    source, destination = Path(source), Path(destination)
    copied = []
    for name in LATEST_ROOT_STATE:
        path, target = source / name, destination / name
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError('latest recovery root state is not a regular file')
        if target.exists() and (target.is_symlink() or target.read_bytes() != path.read_bytes()):
            raise ValueError('latest recovery root state destination differs')
        if not target.exists():
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            copied.append(name)
    return {'status': 'PASS', 'copied_files': copied}


def copy_preserved_caches(source, destination):
    """Union verified historical bytes; never lose an older referenced hash.

    Validate the complete source and every existing destination before copying.
    Root checkpoints and source journals remain owned by the latest run.
    """
    source,destination=Path(source),Path(destination)
    files=[]
    for directory,suffix in (('private-source-cache','.txt'),('private-evidence-cache','.txt'),
                             ('private-evidence-raw','.bin'),('private-source-html','.html')):
        for path in (source/directory).glob('*'+suffix):
            target=destination/directory/path.name
            if (path.is_symlink() or not re.fullmatch(r'[0-9a-f]{64}',path.stem)
                    or hashlib.sha256(path.read_bytes()).hexdigest()!=path.stem):
                raise ValueError('historical cache content hash differs')
            if target.exists() and (target.is_symlink() or target.read_bytes()!=path.read_bytes()):
                raise ValueError('historical cache destination differs')
            files.append((path,target))
    copied=[]
    for path,target in files:
        if target.exists():continue
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,target)
        copied.append(target.relative_to(destination).as_posix())
    return {'status':'PASS','verified_files':len(files),'copied_files':copied,
            'root_metadata_unchanged':True}


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
