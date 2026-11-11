"""Preserve authenticated input ZIPs; never execute or renew a release Gate.

Only the existing Actions artifact service is used. A copied input retains its
original run and digest. Release proof renewal still requires real Gates and a
separate truthful release receipt. This module never writes a Git ref or DB.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
from urllib.parse import quote
import zipfile

REPOSITORY = 'irewon1-lgtm/bottleneck-control-tower'
MAX_ARCHIVE = 6 * 1024**3
MAX_WRAPPER_OVERHEAD = 2 * 1024**2
MAX_RECOVERY_EXPANDED = 512 * 1024**2
DISK_RESERVE = 2 * 1024**3
IDENTITY_FIELDS = ('artifact_id', 'run_id', 'head_sha', 'name', 'bytes', 'sha256')


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None: raise ValueError('ARCHIVE_TIMEZONE_REQUIRED')
    return result.astimezone(timezone.utc)


def expiry(metadata, *, now=None):
    now = now or datetime.now(timezone.utc)
    remaining = (instant(metadata['expires_at']) - now).total_seconds() / 86400
    return {'status': 'EXPIRED' if metadata.get('expired') or remaining <= 0 else
                     'EXPIRES_SOON' if remaining <= 7 else 'AVAILABLE',
            'expires_at': metadata['expires_at'], 'days_remaining': round(remaining, 3)}


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def validate_entries(entries):
    for key, entry in entries.items():
        if (not re.fullmatch('[a-z][a-z0-9-]{0,39}', key)
                or set(entry) != set(IDENTITY_FIELDS)
                or type(entry['artifact_id']) is not int or entry['artifact_id'] <= 0
                or type(entry['run_id']) is not int or entry['run_id'] <= 0
                or type(entry['bytes']) is not int or not 0 < entry['bytes'] <= MAX_ARCHIVE
                or not re.fullmatch('[0-9a-f]{40}', entry['head_sha'])
                or not re.fullmatch('[0-9a-f]{64}', entry['sha256'])):
            raise ValueError('ARCHIVE_REGISTRY_IDENTITY')
    return entries


def resume_origin(request, release):
    entry = request['resume_archive']
    validate_entries({'recovery': entry})
    identity = entry['run_id']; active = release['gate_run_id']
    if (str(identity) != str(request['resume_run_id']) or identity < active
            or entry['name'] != 'bct-recovery-checkpoint-' + str(identity)):
        raise ValueError('ARCHIVE_RESUME_ORIGIN_OR_ROLLBACK')
    partial = request.get('resume_input_only', False)
    if type(partial) is not bool: raise ValueError('ARCHIVE_RESUME_INPUT_ONLY_BOOLEAN')
    if partial:
        if identity <= active: raise ValueError('ARCHIVE_PARTIAL_INPUT_MUST_BE_NEWER')
    elif (identity != active or entry['head_sha'] != release['validated_code_sha']
          or entry['artifact_id'] != release['artifact_id'] or entry['sha256'] != release['artifact_sha256']):
        raise ValueError('ARCHIVE_SUCCESSFUL_RESUME_MUST_MATCH_LATEST_PROOF')
    return entry


def registry(path, request, release):
    value = json.loads(Path(path).read_text())
    if value.get('format') != 'bct-preserved-inputs-1' or 'recovery' in value['archives']:
        raise ValueError('ARCHIVE_REGISTRY_FORMAT')
    return validate_entries({**value['archives'], 'recovery': resume_origin(request, release)})


class API:
    def __init__(self): self.cache = {}

    def read(self, suffix):
        if suffix not in self.cache:
            process = subprocess.run(['gh', 'api', 'repos/' + REPOSITORY + suffix],
                                     capture_output=True, timeout=25)
            if len(process.stdout) > 2 * 1024**2: raise ValueError('ARCHIVE_METADATA_LIMIT')
            try: value = json.loads(process.stdout)
            except ValueError: raise ValueError('ARCHIVE_METADATA_UNAVAILABLE') from None
            if process.returncode:
                if str(value.get('status')) == '404': value = None
                else: raise ValueError('ARCHIVE_METADATA_PERMISSION_OR_NETWORK')
            self.cache[suffix] = value
        return self.cache[suffix]


def copy_name(entry): return 'bct-preserved-input-' + entry['sha256']


def original_metadata(api, entry):
    value = api.read('/actions/artifacts/' + str(entry['artifact_id']))
    if value is None: return None
    expected = {'id': entry['artifact_id'], 'name': entry['name'],
                'size_in_bytes': entry['bytes'], 'digest': 'sha256:' + entry['sha256']}
    if (any(value.get(k) != v for k, v in expected.items())
            or value.get('workflow_run', {}).get('id') != entry['run_id']
            or value.get('workflow_run', {}).get('head_sha') != entry['head_sha']):
        raise ValueError('ARCHIVE_ORIGINAL_BINDING')
    if entry['name'] == 'bct-recovery-checkpoint-' + str(entry['run_id']):
        run = api.read('/actions/runs/' + str(entry['run_id']))
        if (not run or run.get('status') != 'completed' or run.get('head_sha') != entry['head_sha']
                or run.get('path') != '.github/workflows/bct-recovery.yml'
                or run.get('head_repository', {}).get('full_name') != REPOSITORY):
            raise ValueError('ARCHIVE_ORIGINAL_RUN_PROVENANCE')
    return value


def copy_metadata(api, entry, artifact):
    if (not isinstance(artifact, dict) or artifact.get('name') != copy_name(entry) or artifact.get('expired') is not False
            or type(artifact.get('size_in_bytes')) is not int
            or not 0 < artifact['size_in_bytes'] <= entry['bytes'] + MAX_WRAPPER_OVERHEAD
            or not re.fullmatch('sha256:[0-9a-f]{64}', artifact.get('digest', ''))):
        raise ValueError('ARCHIVE_COPY_BINDING')
    run = api.read('/actions/runs/' + str(artifact['workflow_run']['id']))
    current = str((run or {}).get('id')) == os.environ.get('GITHUB_RUN_ID')
    if (not run or run.get('path') != '.github/workflows/bct-recovery.yml'
            or run.get('head_branch') != 'main'
            or run.get('head_repository', {}).get('full_name') != REPOSITORY
            or run.get('event') not in ('workflow_run', 'workflow_dispatch')
            or not (run.get('status') == 'completed' and run.get('conclusion') == 'success'
                    or current and run.get('status') == 'in_progress')):
        raise ValueError('ARCHIVE_COPY_PRODUCER')
    return artifact


def copies(api, entry):
    value = api.read('/actions/artifacts?name=' + quote(copy_name(entry)) + '&per_page=100')
    if not value or value.get('total_count', 0) > 100: raise ValueError('ARCHIVE_COPY_LIST_BOUND')
    available = []
    for artifact in value['artifacts']:
        if artifact.get('name') != copy_name(entry) or artifact.get('expired'): continue
        try:
            copy_metadata(api, entry, artifact)
        except ValueError as error:
            # A failed readback job can leave an uploaded object. It is not a
            # trusted copy, and must not hide a later successful preservation.
            if str(error) in ('ARCHIVE_COPY_BINDING', 'ARCHIVE_COPY_PRODUCER'): continue
            raise
        if expiry(artifact)['status'] != 'EXPIRED': available.append(artifact)
    return sorted(available, key=lambda a: a['expires_at'], reverse=True)


def download(artifact, destination, maximum):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink(): raise ValueError('ARCHIVE_DESTINATION_EXISTS')
    expected = artifact['size_in_bytes']
    if not 0 < expected <= maximum: raise ValueError('ARCHIVE_COMPRESSED_LIMIT')
    if shutil.disk_usage(destination.parent).free < expected + DISK_RESERVE:
        raise ValueError('ARCHIVE_DISK_RESERVE')
    created = False; written = 0
    try:
        with tempfile.TemporaryFile() as errors, destination.open('xb') as output:
            created = True
            with subprocess.Popen(['gh', 'api', f'repos/{REPOSITORY}/actions/artifacts/{artifact["id"]}/zip'],
                                  stdout=subprocess.PIPE, stderr=errors) as process:
                try:
                    while block := process.stdout.read(1024**2):
                        written += len(block)
                        if written > expected: raise ValueError('ARCHIVE_COMPRESSED_LIMIT')
                        output.write(block)
                    if process.wait(): raise ValueError('ARCHIVE_DOWNLOAD_FAILED')
                except BaseException:
                    process.kill(); process.wait(); raise
        if written != expected or 'sha256:' + digest(destination) != artifact['digest']:
            raise ValueError('ARCHIVE_DOWNLOAD_HASH_OR_SIZE')
    except BaseException:
        if created: destination.unlink(missing_ok=True)
        raise


def regular(entry):
    mode = entry.external_attr >> 16
    return not stat.S_ISLNK(mode) and stat.S_IFMT(mode) in (0, stat.S_IFREG)


def unwrap(wrapper, destination, entry):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink(): raise ValueError('ARCHIVE_DESTINATION_EXISTS')
    if shutil.disk_usage(destination.parent).free < entry['bytes'] + DISK_RESERVE:
        raise ValueError('ARCHIVE_DISK_RESERVE_FOR_INNER_COPY')
    created = False
    try:
        with zipfile.ZipFile(wrapper) as saved:
            names = saved.namelist()
            if sorted(names) != ['input.zip', 'preservation.json']: raise ValueError('ARCHIVE_WRAPPER_MEMBERS')
            source = saved.getinfo('input.zip'); metadata = saved.getinfo('preservation.json')
            if (not regular(source) or not regular(metadata) or source.flag_bits & 1 or metadata.flag_bits & 1
                    or source.file_size != entry['bytes'] or metadata.file_size > 64 * 1024):
                raise ValueError('ARCHIVE_WRAPPER_LIMIT')
            proof = json.loads(saved.read(metadata))
            if (proof.get('format') != 'bct-input-preservation-1' or proof.get('original') != entry
                    or proof.get('new_gate_execution') is not False or proof.get('release_proof_renewed') is not False):
                raise ValueError('ARCHIVE_WRAPPER_IDENTITY_NOT_A_NEW_GATE')
            with saved.open(source) as source_file, destination.open('xb') as output:
                created = True; written = 0
                while block := source_file.read(1024**2):
                    written += len(block)
                    if written > entry['bytes']: raise ValueError('ARCHIVE_ORIGINAL_SIZE')
                    output.write(block)
            if written != entry['bytes'] or digest(destination) != entry['sha256']:
                raise ValueError('ARCHIVE_ORIGINAL_HASH')
            return proof
    except BaseException:
        if created: destination.unlink(missing_ok=True)
        raise


def materialize(api, entry, destination, *, preserved_id=None):
    original = original_metadata(api, entry)
    if preserved_id is None and original is not None and expiry(original)['status'] != 'EXPIRED':
        download(original, destination, entry['bytes']); return {'source': 'original', 'artifact_id': original['id']}
    if preserved_id is None:
        available = copies(api, entry)
        if not available: raise ValueError('ARCHIVE_NO_VERIFIED_COPY_AVAILABLE')
        selected = available[0]
    else:
        selected = copy_metadata(api, entry, api.read('/actions/artifacts/' + str(preserved_id)))
        if expiry(selected)['status'] == 'EXPIRED': raise ValueError('ARCHIVE_COPY_EXPIRED')
    with tempfile.TemporaryDirectory(prefix='archive-wrapper-', dir=Path(destination).parent) as temporary:
        outer = Path(temporary) / 'copy.zip'
        if shutil.disk_usage(outer.parent).free < selected['size_in_bytes'] + entry['bytes'] + DISK_RESERVE:
            raise ValueError('ARCHIVE_DISK_RESERVE_FOR_WRAPPER_AND_INNER')
        download(selected, outer, entry['bytes'] + MAX_WRAPPER_OVERHEAD)
        unwrap(outer, destination, entry)
    return {'source': 'preserved', 'artifact_id': selected['id'], 'producer_run_id': selected['workflow_run']['id']}


def preserve(api, entry, destination):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink(): raise ValueError('ARCHIVE_DESTINATION_EXISTS')
    destination.mkdir()
    try:
        source = materialize(api, entry, destination / 'input.zip')
        proof = {'format': 'bct-input-preservation-1', 'original': entry, 'transport': source,
                 'original_sha256_verified': True, 'new_gate_execution': False, 'release_proof_renewed': False,
                 'source_originals_modified': False, 'evaluations_expanded': False}
        (destination / 'preservation.json').write_text(json.dumps(proof, indent=2) + '\n')
    except BaseException:
        shutil.rmtree(destination); raise
    return proof


def extract_recovery(original, staging):
    with zipfile.ZipFile(original) as saved:
        entries = saved.infolist(); names = [e.filename for e in entries]
        expanded = sum(e.file_size for e in entries)
        if len(entries) > 50000 or len(set(names)) != len(names) or expanded > MAX_RECOVERY_EXPANDED:
            raise ValueError('ARCHIVE_EXPANDED_LIMIT')
        if shutil.disk_usage(staging.parent).free < expanded + DISK_RESERVE:
            raise ValueError('ARCHIVE_DISK_RESERVE')
        for item in entries:
            path = PurePosixPath(item.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in item.filename or not regular(item) or item.flag_bits & 1:
                raise ValueError('ARCHIVE_UNSAFE_RECOVERY_MEMBER')
        saved.extractall(staging)


def restore(api, entry, request, destination, *, preserved_id=None):
    from bct.recovery_restore import verify_restored
    destination = Path(destination)
    if destination.exists() or destination.is_symlink(): raise ValueError('ARCHIVE_DESTINATION_EXISTS')
    if str(request['resume_run_id']) != str(entry['run_id']): raise ValueError('ARCHIVE_RESUME_RUN_IDENTITY')
    with tempfile.TemporaryDirectory(prefix='recovery-restore-', dir=destination.parent) as temporary:
        temporary = Path(temporary); original = temporary / 'input.zip'
        source = materialize(api, entry, original, preserved_id=preserved_id)
        staging = temporary / 'checkpoint'; staging.mkdir()
        extract_recovery(original, staging)
        proof = verify_restored(staging, request['resume_file_sha256'],
                                expected_cache_inventory=request['resume_cache_inventory_sha256'])
        checkpoint = json.loads((staging / 'checkpoint.json').read_text())
        if (str(checkpoint['run_id']) != str(entry['run_id']) or checkpoint.get('code_sha') != entry['head_sha']):
            raise ValueError('ARCHIVE_CHECKPOINT_RUN_IDENTITY')
        staging.rename(destination)
    return {'status': 'PASS_AUTHENTICATED_RESUME_INPUT', 'original_run_id': entry['run_id'],
            'original_sha256': entry['sha256'], 'transport': source, 'restore': proof,
            'new_gate_execution': False, 'release_proof_renewed': False}


def prepare_receipts(api, run_id, expected_sha, root, destination, *, partial=False):
    """Prepare two local metadata files only after the unchanged real verifier."""
    from bct.recovery_restore import LATEST_ROOT_STATE, verify_restored
    root, destination = Path(root).resolve(), Path(destination)
    if destination.exists() or destination.is_symlink(): raise ValueError('ARCHIVE_DESTINATION_EXISTS')
    previous = json.loads((root/'.github/bct-recovery-request.json').read_text())
    active = json.loads((root/'config/bct-operating-release.json').read_text())
    if run_id < int(previous['resume_run_id']) or run_id < active['gate_run_id']:
        raise ValueError('ARCHIVE_NEW_CHECKPOINT_WOULD_ROLL_BACK_INPUT')
    run = api.read('/actions/runs/' + str(run_id))
    if (not run or run.get('head_sha') != expected_sha or run.get('head_branch') != 'main'
            or run.get('path') != '.github/workflows/bct-recovery.yml'
            or run.get('status') != 'completed'
            or run.get('head_repository', {}).get('full_name') != REPOSITORY):
        raise ValueError('ARCHIVE_NEW_GATE_CODE_OR_BRANCH')
    if partial and (run_id <= active['gate_run_id'] or run.get('conclusion') not in ('failure', 'cancelled', 'timed_out')):
        raise ValueError('ARCHIVE_PARTIAL_CHECKPOINT_MUST_BE_NEWER_UNSUCCESSFUL_RUN')
    items = api.read('/actions/runs/' + str(run_id) + '/artifacts?per_page=100')
    selected = [a for a in items['artifacts'] if a.get('name') == 'bct-recovery-checkpoint-' + str(run_id)]
    if len(selected) != 1: raise ValueError('ARCHIVE_NEW_GATE_ARTIFACT_UNIQUE')
    artifact = selected[0]
    if (not re.fullmatch('sha256:[0-9a-f]{64}', artifact.get('digest', ''))
            or artifact.get('workflow_run', {}).get('id') != run_id
            or artifact.get('workflow_run', {}).get('head_sha') != expected_sha):
        raise ValueError('ARCHIVE_NEW_GATE_ARTIFACT_DIGEST')
    release = {'gate_run_id': run_id, 'validated_code_sha': expected_sha,
               'artifact_id': artifact['id'], 'artifact_sha256': artifact['digest'].split(':', 1)[1]}
    spec = importlib.util.spec_from_file_location('unchanged_release_guard', root/'.github/scripts/bct_release_guard.py')
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    def read_only(method, suffix):
        if method != 'GET': raise ValueError('ARCHIVE_VERIFICATION_WRITE_FORBIDDEN')
        return api.read(suffix)
    validation = ({'status': 'PARTIAL_INPUT_ONLY_NO_RELEASE_PROOF'} if partial else
                  guard.verify_release(read_only, release, root))
    if expiry(artifact)['status'] == 'EXPIRED': raise ValueError('ARCHIVE_NEW_GATE_ARTIFACT_EXPIRED')
    with tempfile.TemporaryDirectory(prefix='fresh-gate-receipts-', dir=destination.parent) as temporary:
        temporary = Path(temporary); source = temporary/'gate.zip'; checkpoint_root = temporary/'checkpoint'
        download(artifact, source, MAX_ARCHIVE); checkpoint_root.mkdir(); extract_recovery(source, checkpoint_root)
        checkpoint = json.loads((checkpoint_root/'checkpoint.json').read_text())
        if (str(checkpoint.get('run_id')) != str(run_id) or checkpoint.get('code_sha') != expected_sha
                or not partial and (checkpoint.get('status') != 'PASS'
                    or any(checkpoint.get('gate'+str(i)) != 'PASS' for i in range(7)))):
            raise ValueError('ARCHIVE_NEW_GATE_CHECKPOINT_NOT_PASS')
        names = {'checkpoint.json', 'source-recovery-attempts.jsonl'}
        if not partial:
            names.update(('e2e-recovery.json', 'e2e-original-230/operating-report.json'))
        # An early failed run has no new E2E proof. Preserve every prior
        # reading/source journal, but never relabel an old E2E as new proof.
        names.update(n for n in previous['resume_file_sha256']
                     if not partial or not n.startswith(('e2e-', 'e2e/')))
        names.update(n for n in LATEST_ROOT_STATE if (checkpoint_root/n).is_file())
        if any(not (checkpoint_root/n).is_file() for n in names):
            raise ValueError('ARCHIVE_NEW_GATE_DROPPED_PRIOR_ROOT_STATE')
        pins = {n: digest(checkpoint_root/n) for n in sorted(names)}
        proof = verify_restored(checkpoint_root, pins)
        entry = {'artifact_id': artifact['id'], 'run_id': run_id, 'head_sha': expected_sha,
                 'name': artifact['name'], 'bytes': artifact['size_in_bytes'], 'sha256': release['artifact_sha256']}
        updated = {**previous, 'resume_run_id': str(run_id), 'resume_archive': entry,
                   'resume_input_only': partial, 'resume_file_sha256': pins,
                   'resume_cache_inventory_sha256': proof['cache_inventory_sha256'],
                   'reason': ('Continue the latest authenticated partial checkpoint without claiming release proof.' if partial else
                              'Continue the latest actual successful Gate checkpoint, preserving completed readings, source journals and history.')}
        resume_origin(updated, active if partial else release)
        destination.mkdir()
        try:
            if not partial: (destination/'bct-operating-release.json').write_text(json.dumps(release, indent=2)+'\n')
            (destination/'bct-recovery-request.json').write_text(json.dumps(updated, indent=2)+'\n')
        except BaseException:
            shutil.rmtree(destination); raise
    return {'status': 'PREPARED_PARTIAL_RESUME_INPUT_NOT_RELEASE_PROOF' if partial else
                      'PREPARED_FROM_ACTUAL_CURRENT_CODE_GATE_SUCCESS', 'verification': validation,
            'resume_run_id': run_id, 'verified_root_files': len(pins), 'cache': proof,
            'source_journals_and_completed_readings_rolled_forward': True,
            'release_receipt_prepared': not partial, 'Git_refs_written': 0}


def inspect(api, entries, release, key, *, requested=False):
    report = {'format': 'bct-artifact-health-1', 'archives': {}, 'new_gate_execution': False,
              'proof_renewal_procedure': 'Run real current-code Gates0-6, verify required steps/artifact, then truthful receipt-only PR; copying cannot renew proof.'}
    for name, entry in entries.items():
        try:
            original = original_metadata(api, entry); available = copies(api, entry)
            state = expiry(original) if original else {'status': 'MISSING'}
            copy_state = expiry(available[0]) if available else {'status': 'MISSING'}
            due = (requested and name == key or state['status'] != 'AVAILABLE') and copy_state.get('days_remaining', 0) <= 14
            report['archives'][name] = {'original': state, 'preserved_copy_metadata': copy_state,
                'copy_bytes_read_in_inspection': False, 'preservation_due': due,
                'artifact_name': copy_name(entry), 'automatic_copy_allowed': name == 'recovery',
                'original_bytes': entry['bytes']}
        except (ValueError, KeyError, TypeError):
            report['archives'][name] = {'status': 'BLOCKED_METADATA_BINDING_OR_ACCESS', 'preservation_due': False}
    try:
        artifact = api.read('/actions/artifacts/' + str(release['artifact_id']))
        if artifact is None: state = {'status': 'MISSING'}
        elif (artifact.get('digest') != 'sha256:' + release['artifact_sha256']
                or artifact.get('workflow_run', {}).get('id') != release['gate_run_id']
                or artifact.get('workflow_run', {}).get('head_sha') != release['validated_code_sha']):
            state = {'status': 'BINDING_MISMATCH'}
        else: state = expiry(artifact)
        report['recorded_release_artifact'] = {**state, 'current_code_Gates_revalidated': False,
            'actual_Gates_and_receipt_renewal_due': state['status'] != 'AVAILABLE'}
    except (ValueError, KeyError, TypeError):
        report['recorded_release_artifact'] = {'status': 'BLOCKED_METADATA_ACCESS', 'current_code_Gates_revalidated': False}
    selected = report['archives'][key]
    report['preservation_due'] = selected['preservation_due']
    report['artifact_name'] = copy_name(entries[key])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'preserve', 'restore', 'prepare-receipts', 'prepare-resume'])
    parser.add_argument('--registry', default='config/bct-preserved-inputs.json')
    parser.add_argument('--key', default='recovery')
    parser.add_argument('--release', default='config/bct-operating-release.json')
    parser.add_argument('--request', default='.github/bct-recovery-request.json')
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--preserved-artifact-id', type=int)
    parser.add_argument('--preserve-requested', action='store_true')
    parser.add_argument('--gate-run-id', type=int)
    parser.add_argument('--expected-code-sha')
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args(); request = json.loads(Path(args.request).read_text())
    release = json.loads(Path(args.release).read_text())
    entries = registry(args.registry, request, release); entry = entries[args.key]; api = API()
    repo = api.read('')
    if not repo or repo.get('private') is not False or repo.get('visibility') != 'public':
        raise ValueError('ARCHIVE_PUBLIC_STANDARD_ACTIONS_REQUIRED')
    if args.action in ('prepare-receipts', 'prepare-resume'):
        result = prepare_receipts(api, args.gate_run_id, args.expected_code_sha, args.root, args.destination,
                                  partial=args.action == 'prepare-resume')
    elif args.action == 'inspect':
        result = inspect(api, entries, release, args.key,
                         requested=args.preserve_requested)
        if os.environ.get('GITHUB_OUTPUT'):
            with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
                output.write('preservation_due=' + str(result['preservation_due']).lower() + '\nartifact_name=' + result['artifact_name'] + '\n')
    elif args.action == 'preserve': result = preserve(api, entry, args.destination)
    else: result = restore(api, entry, request, args.destination,
                           preserved_id=args.preserved_artifact_id)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as output: output.write(json.dumps(result, indent=2) + '\n')
    print('BCT_ARTIFACT_INPUT_JSON=' + json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
