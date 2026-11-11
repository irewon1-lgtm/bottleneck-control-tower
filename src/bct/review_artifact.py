"""Extract only this acquisition's saved captures and proof originals for REVIEW.

The existing handoff and activated judgment code still verify every source.
Historical cache entries and unrelated evaluations are never expanded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from .review_intake import timestamp

MAX_ARCHIVE = 6 * 1024**3
MAX_EXPANDED = 256 * 1024**2
MAX_CAPTURE = 2 * 1024**2
DISK_RESERVE = 1024**3


def download(repository, artifact_id, expected_size, destination, *, expected_digest=None):
    """Keep the compressed archive only temporarily; block before filling disk."""
    destination = Path(destination)
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repository) or not str(artifact_id).isdigit():
        raise ValueError('REVIEW_ARTIFACT_IDENTITY')
    if not 0 < expected_size <= MAX_ARCHIVE:
        raise ValueError('REVIEW_ARTIFACT_COMPRESSED_LIMIT')
    if expected_digest is not None and not re.fullmatch(r'sha256:[0-9a-f]{64}', expected_digest):
        raise ValueError('REVIEW_ARTIFACT_HASH_METADATA')
    if destination.exists() or destination.is_symlink():
        raise ValueError('REVIEW_ARTIFACT_DESTINATION_EXISTS')
    if shutil.disk_usage(destination.parent)[2] < expected_size + MAX_EXPANDED + DISK_RESERVE:
        raise ValueError('REVIEW_ARTIFACT_INSUFFICIENT_DISK')
    written = 0
    created = False
    try:
        # Do not emit gh's redirected signed download URLs on failure.
        with tempfile.TemporaryFile() as errors, destination.open('xb') as out:
            created = True
            with subprocess.Popen(['gh', 'api', f'repos/{repository}/actions/artifacts/{artifact_id}/zip',
                                   '-H', 'Accept: application/vnd.github+json'],
                                  stdout=subprocess.PIPE, stderr=errors) as process:
                try:
                    while block := process.stdout.read(1024**2):
                        written += len(block)
                        if written > min(MAX_ARCHIVE, expected_size):
                            raise ValueError('REVIEW_ARTIFACT_COMPRESSED_LIMIT')
                        out.write(block)
                    if process.wait() != 0:
                        raise ValueError('REVIEW_ARTIFACT_DOWNLOAD_FAILED')
                except BaseException:
                    process.kill()
                    process.wait()
                    raise
        if written != expected_size:
            raise ValueError('REVIEW_ARTIFACT_SIZE_MISMATCH')
        if expected_digest is not None:
            with destination.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected_digest.split(':')[1]:
                    raise ValueError('REVIEW_ARTIFACT_HASH_MISMATCH')
        return written
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise


def extract_archive(archive, destination, cutover, *, max_expanded=MAX_EXPANDED):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('REVIEW_ARTIFACT_DESTINATION_EXISTS')
    since = timestamp(cutover)
    with zipfile.ZipFile(archive) as saved:
        entries = {}
        captures = []
        for item in saved.infolist():
            if item.filename.startswith(('captures/', 'raw/')):
                if item.is_dir():
                    continue
                parts = item.filename.split('/')
                if len(parts) != 2 or parts[1] in ('', '.', '..') or '\\' in item.filename:
                    raise ValueError('REVIEW_ARTIFACT_UNSAFE_CAPTURE_PATH')
                if item.filename in entries:
                    raise ValueError('REVIEW_ARTIFACT_DUPLICATE_MEMBER')
                entries[item.filename] = item
                if parts[0] == 'captures' and parts[1].endswith('.json'):
                    captures.append(item)
        selected = {}
        raw_names = set()
        for item in captures:
            if item.file_size > MAX_CAPTURE:
                raise ValueError('REVIEW_ARTIFACT_CAPTURE_LIMIT')
            metadata = saved.read(item)
            try:
                capture = json.loads(metadata)
                if timestamp(capture.get('acquired_at', capture.get('collected_at', ''))) < since:
                    continue
            except (ValueError, KeyError, TypeError, AttributeError):
                # Preserve the unchanged handoff's explicit malformed-capture receipt.
                capture = {}
            selected[item.filename] = item
            raw_hash = capture.get('raw_sha256', '')
            if isinstance(raw_hash, str) and re.fullmatch('[0-9a-f]{64}', raw_hash):
                name = 'raw/' + raw_hash + '.html'
                if name in entries:
                    selected[name] = entries[name]
                    raw_names.add(name)
        expanded = sum(item.file_size for item in selected.values())
        if expanded > max_expanded:
            raise ValueError('REVIEW_ARTIFACT_EXPANDED_LIMIT')
        if shutil.disk_usage(destination.parent)[2] < expanded + DISK_RESERVE:
            raise ValueError('REVIEW_ARTIFACT_INSUFFICIENT_DISK')
        # Publish the new temporary cache only after every selected ZIP CRC passes.
        with tempfile.TemporaryDirectory(prefix='review-artifact-', dir=destination.parent) as staging:
            root = Path(staging) / 'cache'
            root.mkdir()
            for name, item in selected.items():
                target = root / name
                target.parent.mkdir(exist_ok=True)
                with saved.open(item) as src, target.open('xb') as out:
                    shutil.copyfileobj(src, out, length=1024**2)
            root.rename(destination)
    return {'selected_captures': len(selected) - len(raw_names), 'selected_raw_files': len(raw_names),
            'expanded_bytes': expanded, 'expanded_limit': max_expanded,
            'historical_cache_modified': False, 'frozen_reader_modified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--artifact-id', required=True)
    parser.add_argument('--expected-size', type=int, required=True)
    parser.add_argument('--expected-digest', required=True)
    parser.add_argument('--cutover', required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='review-download-') as temporary:
        archive = Path(temporary) / 'cache.zip'
        size = download(args.repository, args.artifact_id, args.expected_size, archive,
                        expected_digest=args.expected_digest)
        receipt = extract_archive(archive, args.destination, args.cutover)
    print(json.dumps({**receipt, 'compressed_bytes': size, 'compressed_archive_removed': True}))


if __name__ == '__main__':
    main()
