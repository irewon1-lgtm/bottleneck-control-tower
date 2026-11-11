"""Manual development replay of saved sources through the frozen REVIEW intake.

Only the small numeric/hash receipt may be uploaded. Source files and a copied
review state live under RUNNER_TEMP; no state publisher or inference is called.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from bct import review_shadow
from bct.objective_lock import stamp_export
from bct.review_artifact import download, extract_archive
from bct.review_intake import timestamp

REPOSITORY = 'irewon1-lgtm/bottleneck-control-tower'
TARGET_REF = 'refs/heads/codex/bct-v4-integration'
UPSTREAM_RUN_ID = 42939818925
UPSTREAM_SHA = '28d0b8c648c0218ab2e74a1fa04ca8d63e659933'
CUTOVER = '2026-11-11T01:33:31Z'
ARTIFACT_ID = 13821760877
ARTIFACT_SIZE = 4598165007
ARTIFACT_DIGEST = 'sha256:949e95d2efda7a3fd3e7a124eb0d6569b56b54dcd1a3d5fd7f053dc75b8dfb72'
REVIEW_SHA = '0ad6ba0a9a6cea0211c760b3e19502ad9e29a54c'
PRE_INTAKE_REVIEW_SHA = '76ba081f28aa9fcce639af87c8e0e57ba0a76bb0'
FIXED230_FINGERPRINT = 'acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec'
FIXED230_AS_OF = '2026-10-08T14:11:35+00:00'


def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            value.update(block)
    return value.hexdigest()


def snapshot(state, *, core=False):
    return {str(p.relative_to(state)): file_hash(p) for p in sorted(Path(state).rglob('*'))
            if p.is_file() and p.name not in ('summary.md', '.review-lock')
            and not (core and p.relative_to(state).parts[0] in ('runs', 'runtime-recovery'))}


def verify_preserved(state, before):
    if any(not (Path(state)/p).is_file() or file_hash(Path(state)/p) != h for p, h in before.items()):
        raise ValueError('EXISTING_REVIEW_FILE_CHANGED')
    return len(before)


def stage_counts(result):
    records = result['records']
    fresh = [r for r in records if r.get('delivery') not in ('DUPLICATE', 'DUPLICATE_BODY')]
    return {'intake_records': len(records), 'new_intake_records_in_copy': len(fresh),
            'duplicate_records': len(records)-len(fresh),
            'new_HOLD_records_in_copy': sum(r['final_status'] == 'HOLD' for r in fresh),
            'new_semantic_completions': sum(r['semantic_review']['status'] == 'COMPLETED' for r in fresh),
            'semantic_pending_records': sum(r['semantic_review']['status'] == 'PENDING' for r in records),
            'status_counts': dict(Counter(r['final_status'] for r in records)),
            'omitted_backfill': len(result['omitted_backfill']), 'alerts': len(result['alerts'])}


def validate_inputs(run, artifacts):
    if (run.get('id') != UPSTREAM_RUN_ID or run.get('head_sha') != UPSTREAM_SHA
            or run.get('path') != '.github/workflows/precursor-acquisition.yml'
            or run.get('head_branch') != 'main' or run.get('event') != 'workflow_run'
            or run.get('created_at') != CUTOVER
            or run.get('head_repository', {}).get('full_name') != REPOSITORY):
        raise ValueError('REVIEW_UPSTREAM_BINDING')
    found = [a for a in artifacts['artifacts'] if a.get('id') == ARTIFACT_ID]
    if (len(found) != 1 or found[0].get('name') != 'precursor-private-cache'
            or found[0].get('expired') is not False or found[0].get('size_in_bytes') != ARTIFACT_SIZE
            or found[0].get('digest') != ARTIFACT_DIGEST):
        raise ValueError('REVIEW_ARTIFACT_BINDING')
    return found[0]


def gh_json(path):
    return json.loads(subprocess.check_output(['gh', 'api', 'repos/'+REPOSITORY+'/'+path], stderr=subprocess.PIPE))


def historical_source_inventory(saved, expected_fingerprint=FIXED230_FINGERPRINT):
    """Hash-only optional audit; unrelated historical bodies are never extracted.

    A date is only a selection aid. Only the exact old fingerprint can identify
    the fixed corpus; even a match is not a new Gates or primary-source run.
    """
    metadata_bytes = 0; documents = []
    for member in sorted(saved.infolist(), key=lambda m: m.filename):
        if not member.filename.startswith('documents/') or not member.filename.endswith('.json'): continue
        if len(member.filename.split('/')) != 2 or member.file_size > 2*1024**2:
            raise ValueError('HISTORICAL_DOCUMENT_METADATA_LIMIT')
        metadata_bytes += member.file_size
        if metadata_bytes > 64*1024**2: raise ValueError('HISTORICAL_DOCUMENT_METADATA_LIMIT')
        document = json.loads(saved.read(member))
        if document.get('provenance') != 'PASS': continue
        try: within = timestamp(document['acquired_at']) <= timestamp(FIXED230_AS_OF)
        except (ValueError, TypeError, KeyError): continue
        if within: documents.append(document)
    vector = [{k: d[k] for k in ('document_id', 'body_sha256', 'raw_sha256')} for d in documents]
    fingerprint = hashlib.sha256(json.dumps(vector, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    result = {'historical_selection_cutoff': FIXED230_AS_OF, 'selected_documents': len(documents),
              'metadata_bytes_read': metadata_bytes, 'input_fingerprint': fingerprint,
              'expected_fingerprint': expected_fingerprint, 'exact_fingerprint_match': fingerprint == expected_fingerprint,
              'source_originals_reverified': False, 'Gates_revalidated': False}
    if fingerprint != expected_fingerprint or len(documents) != 230:
        return {**result, 'status': 'BLOCKED_EXACT_FIXED230_SNAPSHOT_NOT_IDENTIFIED'}
    body_hashes = all(hashlib.sha256(d['body'].encode()).hexdigest() == d['body_sha256'] for d in documents)
    needed = {'raw/'+d['raw_sha256']+'.html': d['raw_sha256'] for d in documents}
    needed.update({'raw/'+d['sec_filing_metadata']['raw_sha256']+'.json': d['sec_filing_metadata']['raw_sha256']
                   for d in documents if d.get('sec_filing_metadata')})
    members = {m.filename: m for m in saved.infolist()}
    missing = sum(name not in members for name in needed)
    expanded = sum(members[name].file_size for name in needed if name in members)
    if expanded > 256*1024**2: raise ValueError('HISTORICAL_RAW_READ_LIMIT')
    hashes_verified = 0
    for name, expected in needed.items():
        if name not in members: continue
        digest = hashlib.sha256()
        with saved.open(members[name]) as source:
            for block in iter(lambda: source.read(1024**2), b''): digest.update(block)
        hashes_verified += digest.hexdigest() == expected
    complete = body_hashes and not missing and hashes_verified == len(needed)
    return {**result, 'status': 'EXACT_HISTORICAL_CACHE_BYTES_AVAILABLE' if complete else 'BLOCKED_HISTORICAL_RAW_BYTES_MISSING_OR_CHANGED',
            'body_hashes_verified': body_hashes, 'required_originals': len(needed), 'missing_originals': missing,
            'raw_hashes_verified': hashes_verified, 'raw_bytes_read': expanded, 'input_hash_vector': vector}


def copy_review_state(destination, commit=REVIEW_SHA):
    # Fetch the exact pinned public object, never check out or update its ref.
    if commit not in (REVIEW_SHA, PRE_INTAKE_REVIEW_SHA): raise ValueError('UNREVIEWED_STATE_COPY')
    subprocess.run(['git', 'fetch', '--no-tags', '--depth=1', 'origin', commit], check=True)
    tree = subprocess.check_output(['git', 'ls-tree', '-r', '-l', commit], text=True)
    rows = [line.split('\t', 1) for line in tree.splitlines()]
    if len(rows) > 20000 or sum(int(header.split()[3]) for header, _ in rows) > 512*1024**2:
        raise ValueError('REVIEW_STATE_COPY_LIMIT')
    for header, name in rows:
        if (header.split()[:2] != ['100644', 'blob'] or not name.startswith('review-lead-shadow/')
                or '..' in name.split('/') or '\\' in name):
            raise ValueError('REVIEW_STATE_FOREIGN_PATH')
    destination.mkdir()
    with subprocess.Popen(['git', 'archive', commit], stdout=subprocess.PIPE) as process:
        with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
            for entry in archive:
                path = Path(entry.name)
                if path.is_absolute() or '..' in path.parts or path.parts[0] != 'review-lead-shadow':
                    raise ValueError('REVIEW_STATE_FOREIGN_PATH')
                target = destination/path
                if entry.isdir(): target.mkdir(parents=True, exist_ok=True)
                elif entry.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(entry) as src, target.open('xb') as out:
                        while block := src.read(1024**2): out.write(block)
                else: raise ValueError('REVIEW_STATE_FOREIGN_PATH')
        if process.wait() != 0: raise ValueError('REVIEW_STATE_ARCHIVE_FAILED')
    state = destination/'review-lead-shadow'
    if not (state/'shadow-activation.json').is_file(): raise ValueError('REVIEW_STATE_ACTIVATION_MISSING')
    return state


def replay_copied_state(bundle, state, workspace):
    before = snapshot(state)
    spec = importlib.util.spec_from_file_location('frozen_review_replay', Path('.github/scripts/review_shadow_frozen.py'))
    frozen = importlib.util.module_from_spec(spec); spec.loader.exec_module(frozen)
    counts = stage_counts(frozen.execute(bundle, state))
    if counts['new_semantic_completions'] != 0: raise ValueError('UNEXPECTED_SEMANTIC_COMPLETION')
    if counts['intake_records']+counts['omitted_backfill'] != len(bundle['documents']):
        raise ValueError('REVIEW_HANDOFF_ACCOUNTING_MISMATCH')
    core = snapshot(state, core=True)
    repeated = stage_counts(frozen.execute(bundle, state))
    if repeated['new_intake_records_in_copy'] or snapshot(state, core=True) != core:
        raise ValueError('REVIEW_REPLAY_DEDUPLICATION_FAILED')
    expected = workspace/'core-hashes.json'; expected.write_text(json.dumps(core))
    subprocess.run([sys.executable, str(Path(__file__).resolve()), 'verify', '--workspace', str(state), '--output', str(expected)], check=True)
    return {'first_delivery': counts, 'repeat_delivery': repeated,
            'old_files_preserved': verify_preserved(state, before), 'new_process_copy_hash_verification': 'PASS'}


def execute(workspace, output):
    if os.environ.get('GITHUB_REF') != TARGET_REF or os.environ.get('GITHUB_REPOSITORY') != REPOSITORY:
        raise ValueError('REVIEW_VERIFICATION_BRANCH_REQUIRED')
    workspace = Path(workspace)
    workspace.mkdir()
    run = gh_json('actions/runs/'+str(UPSTREAM_RUN_ID))
    artifact = validate_inputs(run, gh_json('actions/runs/'+str(UPSTREAM_RUN_ID)+'/artifacts?per_page=100'))
    operating_review_before = gh_json('git/ref/heads/review-lead-shadow-state')['object']['sha']
    receipt = stamp_export({'task_id': 'BCT_V4_OPERATIONS_RECOVERY_20261111', 'mode': 'REPLAY',
        'status': 'STARTED', 'run_url': 'https://github.com/'+REPOSITORY+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],
        'code_sha': os.environ['GITHUB_SHA'], 'upstream_run_id': UPSTREAM_RUN_ID,
        'upstream_sha': UPSTREAM_SHA, 'upstream_conclusion': run.get('conclusion'), 'cutover': CUTOVER,
        'artifact_id': ARTIFACT_ID, 'artifact_digest': ARTIFACT_DIGEST, 'artifact_size': ARTIFACT_SIZE,
        'copied_review_state_sha': REVIEW_SHA, 'operational_state_writes': 0, 'AI_calls': 0,
        'CPU_readings': 0, 'LIVE_writes': 0, 'EARLY_success_count': 0})
    with tempfile.TemporaryDirectory(prefix='review-download-', dir=workspace) as temporary:
        archive = Path(temporary)/'cache.zip'
        size = download(REPOSITORY, ARTIFACT_ID, artifact['size_in_bytes'], archive)
        if file_hash(archive) != ARTIFACT_DIGEST.removeprefix('sha256:'):
            raise ValueError('REVIEW_DOWNLOADED_ARTIFACT_HASH_MISMATCH')
        with zipfile.ZipFile(archive) as saved:
            groups = Counter(); expanded = Counter()
            for member in saved.infolist():
                kind = member.filename.split('/')[0]
                if kind not in ('captures', 'raw', 'documents', 'requests', 'evaluations'): kind = 'other'
                groups[kind] += 1; expanded[kind] += member.file_size
            receipt['archive_inventory'] = {'member_counts': dict(groups), 'expanded_bytes_by_group': dict(expanded)}
            try: receipt['historical_fixed230'] = historical_source_inventory(saved)
            except (ValueError, KeyError, TypeError) as exc:
                receipt['historical_fixed230'] = {'status': 'BLOCKED', 'reason': type(exc).__name__,
                                                  'source_originals_reverified': False, 'Gates_revalidated': False}
        receipt['transport'] = extract_archive(archive, workspace/'selected-cache', CUTOVER)
        receipt['transport'].update(compressed_bytes=size, downloaded_digest_verified=True)
    receipt['transport']['compressed_archive_removed'] = True
    delta = workspace/'window.json'
    delta.write_text(json.dumps({'collection_started_at': CUTOVER, 'documents': []}))
    bundle = review_shadow.handoff(delta, workspace/'selected-cache', workspace/'handoff')
    if not bundle['documents']: raise ValueError('REVIEW_NO_VERIFIED_SAVED_DOCUMENTS')
    state = copy_review_state(workspace/'review-copy')
    current_replay = replay_copied_state(bundle, state, workspace/'review-copy')
    pre_state = copy_review_state(workspace/'pre-intake-copy', PRE_INTAKE_REVIEW_SHA)
    pre_replay = replay_copied_state(bundle, pre_state, workspace/'pre-intake-copy')
    if not pre_replay['first_delivery']['new_HOLD_records_in_copy']:
        raise ValueError('REVIEW_PRE_INTAKE_INPUT_ALREADY_PROCESSED')
    receipt.update(status='PASS_BOUNDED_REVIEW_TRANSPORT_REPLAY', source_verified_handoff_documents=len(bundle['documents']),
                   provenance_skips=len(bundle['skipped']), provenance_skip_reasons=dict(Counter(s['reason'] for s in bundle['skipped'])),
                   **current_replay,
                   semantic_review_complete=False)
    receipt['pre_intake_replay'] = {'mode': 'PRE_INTAKE_REPLAY', 'copied_review_state_sha': PRE_INTAKE_REVIEW_SHA,
                                    **pre_replay, 'operational_state_writes': 0, 'semantic_review_complete': False}
    operating_review_after = gh_json('git/ref/heads/review-lead-shadow-state')['object']['sha']
    receipt.update(operating_review_ref_before=operating_review_before, operating_review_ref_after=operating_review_after,
                   historical_review_ref_unchanged=operating_review_before == operating_review_after)
    Path(output).write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'verify'])
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'verify':
        if snapshot(args.workspace, core=True) != json.loads(args.output.read_text()):
            raise ValueError('REVIEW_FRESH_PROCESS_COPY_HASH_MISMATCH')
        print('Fresh-process copied REVIEW core hashes match')
        return
    try:
        receipt = execute(args.workspace, args.output)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        args.output.write_text(json.dumps(stamp_export({'status': 'BLOCKED', 'mode': 'REPLAY', 'reason': reason,
            'task_id': 'BCT_V4_OPERATIONS_RECOVERY_20261111', 'operational_state_writes': 0,
            'semantic_review_complete': False, 'AI_calls': 0, 'CPU_readings': 0, 'LIVE_writes': 0}), indent=2)+'\n')
        raise
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__': main()
