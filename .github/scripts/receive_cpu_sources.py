"""Bound existing CPU source inputs; never import the CPU engine or fetch sources."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile

REPOSITORY = 'irewon1-lgtm/bottleneck-control-tower'
SOURCE_FAMILIES = {'documents', 'raw', 'captures'}
MAX_ARCHIVE = 6 * 1024**3
# Actual saved inputs occupy 2,402,577,107 bytes. Evaluations alone occupy 49GB.
MAX_EXPANDED = 3 * 1024**3
DISK_RESERVE = 2 * 1024**3


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def free_disk(path):
    path = Path(path).resolve()
    while not path.exists():
        path = path.parent
    return shutil.disk_usage(path)[2]


def gh_json(path):
    result = subprocess.run(['gh', 'api', 'repos/' + REPOSITORY + '/' + path],
                            capture_output=True, text=True, timeout=25)
    if result.returncode:
        raise ValueError('CPU_SOURCE_METADATA_REQUEST_FAILED')
    return json.loads(result.stdout)


def validate_inputs(run, artifacts, run_id, expected_head):
    if (run.get('id') != run_id or run.get('head_sha') != expected_head
            or not re.fullmatch('[0-9a-f]{40}', expected_head)
            or run.get('path') != '.github/workflows/precursor-acquisition.yml'
            or run.get('head_branch') != 'main' or run.get('event') != 'workflow_run'
            or run.get('conclusion') != 'success'
            or run.get('head_repository', {}).get('full_name') != REPOSITORY):
        raise ValueError('CPU_SOURCE_ACQUISITION_BINDING')
    matches = [a for a in artifacts['artifacts'] if a.get('name') == 'precursor-private-cache']
    if (len(matches) != 1 or matches[0].get('expired') is not False
            or type(matches[0].get('id')) is not int
            or type(matches[0].get('size_in_bytes')) is not int
            or not 0 < matches[0]['size_in_bytes'] <= MAX_ARCHIVE
            or not re.fullmatch(r'sha256:[0-9a-f]{64}', matches[0].get('digest') or '')):
        raise ValueError('CPU_SOURCE_ARTIFACT_BINDING')
    return matches[0]


def download(artifact, destination):
    """The workflow supervises the whole command with a finite 300-second limit."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('CPU_SOURCE_DESTINATION_EXISTS')
    if free_disk(destination.parent) < artifact['size_in_bytes'] + MAX_EXPANDED + DISK_RESERVE:
        raise ValueError('CPU_SOURCE_INSUFFICIENT_DISK')
    written = 0; created = False
    try:
        with tempfile.TemporaryFile() as errors, destination.open('xb') as output:
            created = True
            with subprocess.Popen(['gh', 'api', f'repos/{REPOSITORY}/actions/artifacts/{artifact["id"]}/zip',
                                   '-H', 'Accept: application/vnd.github+json'],
                                  stdout=subprocess.PIPE, stderr=errors) as process:
                try:
                    while block := process.stdout.read(1024**2):
                        written += len(block)
                        if written > min(MAX_ARCHIVE, artifact['size_in_bytes']):
                            raise ValueError('CPU_SOURCE_COMPRESSED_LIMIT')
                        output.write(block)
                    if process.wait() != 0:
                        raise ValueError('CPU_SOURCE_DOWNLOAD_FAILED')
                except BaseException:
                    process.kill(); process.wait()
                    raise
        if written != artifact['size_in_bytes'] or digest(destination) != artifact['digest'].split(':', 1)[1]:
            raise ValueError('CPU_SOURCE_ARCHIVE_SIZE_OR_DIGEST_MISMATCH')
        return written
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise


def extract_sources(archive, destination, *, max_expanded=MAX_EXPANDED):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('CPU_SOURCE_DESTINATION_EXISTS')
    selected = {}; counts = Counter(); expanded_by_family = Counter()
    with zipfile.ZipFile(archive) as saved:
        for entry in saved.infolist():
            family = entry.filename.replace('\\', '/').split('/')[0]
            if family not in SOURCE_FAMILIES:
                continue
            if entry.is_dir():
                continue
            parts = entry.filename.split('/')
            if len(parts) != 2 or parts[1] in ('', '.', '..') or '\\' in entry.filename:
                raise ValueError('CPU_SOURCE_UNSAFE_SOURCE_PATH')
            if entry.filename in selected:
                raise ValueError('CPU_SOURCE_DUPLICATE_MEMBER')
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                raise ValueError('CPU_SOURCE_NONREGULAR_MEMBER')
            if entry.flag_bits & 1:
                raise ValueError('CPU_SOURCE_ENCRYPTED_ZIP_MEMBER')
            selected[entry.filename] = entry
            counts[family] += 1; expanded_by_family[family] += entry.file_size
        expanded = sum(expanded_by_family.values())
        if expanded > max_expanded:
            raise ValueError('CPU_SOURCE_EXPANDED_LIMIT')
        free_before_extract = free_disk(destination.parent)
        if free_before_extract < expanded + DISK_RESERVE:
            raise ValueError('CPU_SOURCE_INSUFFICIENT_DISK')
        # No date/version/source filtering: exact originals, malformed records,
        # missing raw and ambiguity stay the pinned processor's responsibility.
        with tempfile.TemporaryDirectory(prefix='cpu-source-stage-', dir=destination.parent) as temp:
            staging = Path(temp) / 'cache'; staging.mkdir()
            written = 0
            for name, entry in selected.items():
                target = staging / name; target.parent.mkdir(exist_ok=True)
                with saved.open(entry) as source, target.open('xb') as output:
                    count = 0
                    while block := source.read(1024**2):
                        count += len(block); written += len(block)
                        if count > entry.file_size or written > max_expanded:
                            raise ValueError('CPU_SOURCE_EXPANDED_LIMIT')
                        output.write(block)
                    if count != entry.file_size:
                        raise ValueError('CPU_SOURCE_MEMBER_SIZE_MISMATCH')
            staging.rename(destination)
    return {'selected_member_counts': dict(counts), 'expanded_bytes_by_family': dict(expanded_by_family),
            'expanded_bytes': expanded, 'expanded_limit': max_expanded,
            'free_disk_bytes_before_extract': free_before_extract, 'disk_reserve_bytes': DISK_RESERVE,
            'all_source_versions_preserved': True, 'source_metadata_rewritten': False,
            'CPU_engine_changed': False, 'evaluations_expanded': False}


def receive(run_id, expected_head, rss_run_id, manifest_path, destination):
    manifest_path, destination = Path(manifest_path), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('CPU_SOURCE_DESTINATION_EXISTS')
    if not run_id > 0 or not rss_run_id > 0 or manifest_path.stat().st_size > 20 * 1024**2:
        raise ValueError('CPU_SOURCE_INPUT_MANIFEST_LIMIT')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('format') != 'bct-new-rss-delta-v1' or not isinstance(manifest.get('documents'), list):
        raise ValueError('CPU_SOURCE_RSS_MANIFEST_BINDING')
    artifact = validate_inputs(gh_json('actions/runs/' + str(run_id)),
                               gh_json(f'actions/runs/{run_id}/artifacts?per_page=100'), run_id, expected_head)
    destination.parent.mkdir(parents=True, exist_ok=True)
    free_before_download = free_disk(destination.parent)
    with tempfile.TemporaryDirectory(prefix='cpu-source-download-', dir=destination.parent) as temp:
        archive = Path(temp) / 'sources.zip'
        compressed = download(artifact, archive)
        proof = extract_sources(archive, destination)
    return {**proof, 'status': 'PASS_BOUNDED_CPU_INPUT_TRANSPORT', 'acquisition_run_id': run_id,
            'acquisition_head_sha': expected_head, 'RSS_run_id': rss_run_id,
            'RSS_manifest_sha256': digest(manifest_path), 'artifact_id': artifact['id'],
            'artifact_digest': artifact['digest'], 'compressed_bytes': compressed,
            'free_disk_bytes_before_download': free_before_download,
            'free_disk_bytes_after_cleanup': free_disk(destination.parent),
            'runtime_cache_present': (Path('.v4-cpu-env/bin/python').exists()
                and Path('.v4-cpu-runtime/models/gliner2-base-v1/model.safetensors').is_file()),
            'compressed_archive_removed': True, 'source_HTTP_requests': 0,
            'new_CPU_inferences': 0, 'DB_writes': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--expected-head', required=True)
    parser.add_argument('--rss-run-id', type=int, required=True)
    parser.add_argument('--rss-manifest', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    try:
        result = receive(args.run_id, args.expected_head, args.rss_run_id,
                         args.rss_manifest, args.destination)
    except Exception as error:
        reason = str(error) if isinstance(error, ValueError) and str(error).startswith('CPU_SOURCE_') else type(error).__name__
        result = {'status': 'BLOCKED_CPU_INPUT_TRANSPORT', 'reason': reason,
                  'expanded_limit': MAX_EXPANDED, 'disk_reserve_bytes': DISK_RESERVE,
                  'free_disk_bytes_at_failure': free_disk(args.destination.parent),
                  'source_HTTP_requests': 0, 'new_CPU_inferences': 0, 'DB_writes': 0}
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        with args.receipt.open('x') as output:
            json.dump(result, output, sort_keys=True)
    print('BCT_CPU_SOURCE_TRANSPORT_JSON=' + json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['status'] == 'PASS_BOUNDED_CPU_INPUT_TRANSPORT' else 1)
