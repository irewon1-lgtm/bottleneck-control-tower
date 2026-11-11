"""Copy the exact historical230 source bytes from an already extracted cache.

This standard-library helper does not fetch, initialize state, run QA or import
an engine. The production fingerprint is fixed and is not a command-line input.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

FIXED230_FINGERPRINT = 'acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec'
AS_OF = '2026-10-08T14:11:35+00:00'
MAX_METADATA_FILE = 2*1024**2
MAX_METADATA_SCAN = 64*1024**2
MAX_COPY_BYTES = 64*1024**2


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024**2), b''): value.update(block)
    return value.hexdigest()


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None: raise ValueError('TIMEZONE_REQUIRED')
    return parsed.astimezone(timezone.utc)


def regular(path):
    if path.is_symlink() or not path.is_file(): raise ValueError('FIXED230_SOURCE_NOT_REGULAR_FILE')
    return path.stat().st_size


def copy_fixed230(cache, destination):
    cache = Path(cache); destination = Path(destination)
    if destination.exists() or destination.is_symlink(): raise ValueError('FIXED230_DESTINATION_EXISTS')
    if cache.resolve() in destination.resolve().parents: raise ValueError('FIXED230_DESTINATION_INSIDE_SOURCE')
    if (cache.is_symlink() or not cache.is_dir() or any((cache/p).is_symlink() for p in ('documents', 'raw'))):
        raise ValueError('FIXED230_SOURCE_DIRECTORY_REQUIRED')
    if not destination.parent.is_dir(): raise ValueError('FIXED230_DESTINATION_PARENT_REQUIRED')
    documents = []; files = {}; metadata_bytes = 0
    for path in sorted((cache/'documents').glob('*.json')):
        size = regular(path); metadata_bytes += size
        if size > MAX_METADATA_FILE or metadata_bytes > MAX_METADATA_SCAN:
            raise ValueError('FIXED230_METADATA_SCAN_LIMIT')
        with path.open('rb') as source: raw_metadata = source.read(MAX_METADATA_FILE+1)
        if len(raw_metadata) != size: raise ValueError('FIXED230_METADATA_CHANGED_OR_LIMIT')
        try:
            document = json.loads(raw_metadata)
            selected = document.get('provenance') == 'PASS' and timestamp(document['acquired_at']) <= timestamp(AS_OF)
        except (ValueError, KeyError, TypeError, AttributeError): continue
        if not selected: continue
        documents.append(document)
        files['documents/'+path.name] = (size, hashlib.sha256(raw_metadata).hexdigest())
    if len(documents) != 230: raise ValueError('FIXED230_SELECTION_MISMATCH')
    vector = [{k: d[k] for k in ('document_id', 'body_sha256', 'raw_sha256')} for d in documents]
    if digest(vector) != FIXED230_FINGERPRINT: raise ValueError('FIXED230_FINGERPRINT_MISMATCH')
    originals = {}
    for document in documents:
        if (not isinstance(document.get('body'), str)
                or hashlib.sha256(document['body'].encode()).hexdigest() != document['body_sha256']):
            raise ValueError('FIXED230_BODY_HASH_MISMATCH')
        originals[document['raw_sha256']] = '.html'
        if document.get('sec_filing_metadata'):
            originals[document['sec_filing_metadata']['raw_sha256']] = '.json'
    copied_bytes = sum(size for size, _ in files.values())
    if copied_bytes > MAX_COPY_BYTES: raise ValueError('FIXED230_COPY_LIMIT')
    for expected, suffix in originals.items():
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('FIXED230_RAW_HASH_INVALID')
        name = 'raw/'+expected+suffix; path = cache/name
        size = regular(path)
        copied_bytes += size
        if copied_bytes > MAX_COPY_BYTES: raise ValueError('FIXED230_COPY_LIMIT')
        if file_hash(path) != expected: raise ValueError('FIXED230_RAW_HASH_MISMATCH')
        files[name] = (size, expected)
    if shutil.disk_usage(destination.parent).free < copied_bytes: raise ValueError('FIXED230_INSUFFICIENT_DISK')
    # mkdir is exclusive even for an existing empty directory. Only files under
    # this newly created destination may be cleaned up if a copy fails.
    destination.mkdir(); written_total = 0
    try:
        for name, (expected_size, expected_hash) in files.items():
            target = destination/name; target.parent.mkdir(exist_ok=True)
            written = 0; value = hashlib.sha256()
            with (cache/name).open('rb') as source, target.open('xb') as output:
                for block in iter(lambda: source.read(1024**2), b''):
                    written += len(block); written_total += len(block)
                    if written > expected_size or written_total > MAX_COPY_BYTES:
                        raise ValueError('FIXED230_COPY_LIMIT_OR_SOURCE_CHANGED')
                    value.update(block); output.write(block)
            if written != expected_size or value.hexdigest() != expected_hash or file_hash(target) != expected_hash:
                raise ValueError('FIXED230_COPIED_BYTES_CHANGED')
        if any(file_hash(cache/name) != expected for name, (_, expected) in files.items()):
            raise ValueError('FIXED230_ORIGINAL_CHANGED_DURING_COPY')
    except BaseException:
        shutil.rmtree(destination)
        raise
    return {'status': 'PASS_EXACT_FIXED230_LITERAL_COPY', 'source_input_sha256': digest(vector),
            'documents': len(documents), 'body_hashes_verified': len(documents), 'raw_hashes_verified': len(originals),
            'copied_files': len(files), 'copied_bytes': copied_bytes, 'copy_limit_bytes': MAX_COPY_BYTES,
            'metadata_scan_bytes': metadata_bytes, 'copied_file_hash_map_sha256': digest({k: v[1] for k, v in files.items()}),
            'source_originals_modified': False, 'activation_copied': False, 'QA_executed': False,
            'HTTP_requests': 0, 'LIVE_writes': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists() or args.receipt.is_symlink(): raise ValueError('FIXED230_RECEIPT_EXISTS')
    if any(root.resolve() == args.receipt.resolve() or root.resolve() in args.receipt.resolve().parents
           for root in (args.cache, args.destination)):
        raise ValueError('FIXED230_RECEIPT_MUST_BE_OUTSIDE_SOURCE_AND_COPY')
    result = copy_fixed230(args.cache, args.destination)
    with args.receipt.open('x') as output: output.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__': main()
