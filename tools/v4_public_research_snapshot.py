"""Project fetched private ACK objects in a separate credential-free interpreter."""
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile

from bct.objective_lock import stamp_export
from bct.v4.public_research import build_snapshot, encoded, validate_snapshot
from bct.v4.private_state import PRIVATE_URL
from bct.v4.store import file_sha


def private_reader(repository):
    repository = Path(repository).resolve()
    def git(*args):
        process = subprocess.run(['git', '-C', str(repository), *args], capture_output=True, timeout=25)
        if process.returncode:
            raise ValueError('PUBLIC_RESEARCH_PRIVATE_ACK_READ_FAILED')
        return process.stdout
    if git('config', '--get', 'remote.origin.url').decode().strip() != PRIVATE_URL:
        raise ValueError('PUBLIC_RESEARCH_REPOSITORY_MISMATCH')
    return git


def read_ack(repository, expected_commit=None):
    git = private_reader(repository)
    commit = git('rev-parse', 'FETCH_HEAD').decode().strip()
    if not re.fullmatch('[0-9a-f]{40}', commit) or (expected_commit and expected_commit != commit):
        raise ValueError('PUBLIC_RESEARCH_FETCHED_GENERATION_CHANGED')
    receipt = json.loads(git('show', commit + ':private-persistence.json'))
    if git('rev-list', '--parents', '-n', '1', commit).decode().split() != [commit, receipt.get('checkpoint_commit')]:
        raise ValueError('PUBLIC_RESEARCH_ACK_PARENT_MISMATCH')
    if git('rev-parse', '--is-shallow-repository').decode().strip() != 'false':
        raise ValueError('PUBLIC_RESEARCH_INCOMPLETE_PRIVATE_HISTORY')
    roots = git('rev-list', '--max-parents=0', '--first-parent', commit).decode().split()
    if len(roots) != 1:
        raise ValueError('PUBLIC_RESEARCH_PRIVATE_LINEAGE_AMBIGUOUS')
    return {'commit': commit, 'remote_restore_verified': True, 'persistence_receipt': receipt}, {
        'lineage_root': roots[0], 'ack_sequence': int(git('rev-list', '--first-parent', '--count', commit))}


def project_git(repository, expected, output):
    """Executed by the child; independently read immutable durable Git objects."""
    if any(os.environ.get(key) for key in ('BCT_V4_PRIVATE_STATE_TOKEN', 'BCT_V4_STATE_PASSPHRASE', 'GH_TOKEN', 'GITHUB_TOKEN')):
        raise ValueError('PUBLIC_RESEARCH_CREDENTIAL_REACHED_CHILD')
    from bct.v4.cpu_operations import restore
    result, lineage = read_ack(repository, expected['commit'])
    if result['persistence_receipt'] != expected['persistence_receipt']:
        raise ValueError('PUBLIC_RESEARCH_ACK_RECEIPT_MISMATCH')
    git = private_reader(repository)
    with tempfile.TemporaryDirectory(prefix='bct-public-git-restore-') as temporary:
        root = Path(temporary); checkpoint = root / 'checkpoint'; checkpoint.mkdir()
        for name in ('checkpoint.json', 'checkpoint.sqlite3.gz'):
            (checkpoint / name).write_bytes(git('show', result['commit'] + ':' + name))
        proof = restore(checkpoint, root / 'restored')
        with sqlite3.connect((root / 'restored/v4.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
            public = build_snapshot(db, result, proof, lineage)
        with Path(output).open('xb') as out:
            out.write(encoded(public) + b'\n')


def emit(private_git, published, output, transport):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('PUBLIC_RESEARCH_OUTPUT_EXISTS')
    published = json.loads(Path(published).read_text()) if published is not None else None
    expected, _ = read_ack(private_git, published.get('commit') if published else None)
    if published is not None:
        if (published.get('remote_restore_verified') is not True or published.get('commit') != expected['commit']):
            raise ValueError('PUBLIC_RESEARCH_FETCHED_GENERATION_CHANGED')
        if published.get('persistence_receipt') != expected['persistence_receipt']:
            raise ValueError('PUBLIC_RESEARCH_ACK_RECEIPT_MISMATCH')
    with tempfile.TemporaryDirectory(prefix='bct-public-restart-') as temporary:
        root = Path(temporary); expected_path = root / 'expected.json'
        expected_path.write_bytes(encoded(expected))
        removed = {'BCT_V4_PRIVATE_STATE_TOKEN', 'BCT_V4_STATE_PASSPHRASE', 'GH_TOKEN', 'GITHUB_TOKEN'}
        environment = {key: value for key, value in os.environ.items() if key not in removed}
        child = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--child-project',
            '--private-git', str(Path(private_git).resolve()), '--expected', str(expected_path),
            '--output', str(root / 'snapshot.json')], env=environment, capture_output=True, timeout=120)
        if child.returncode:
            raise ValueError('PUBLIC_RESEARCH_NEW_PROCESS_PROJECTION_FAILED')
        raw = (root / 'snapshot.json').read_bytes()
        if len(raw) > 192 * 1024:
            raise ValueError('PUBLIC_RESEARCH_SNAPSHOT_SIZE')
        public = validate_snapshot(json.loads(raw))
        output.mkdir(parents=True, exist_ok=False)
        with (output / 'snapshot.json').open('xb') as out:
            out.write(raw)
    manifest = stamp_export({'format': 'bct-public-research-artifact-1',
        'file_sha256': file_sha(output / 'snapshot.json'), 'snapshot_sha256': public['snapshot_sha256'],
        'generation': public['generation'], 'transport_run_id': transport['run_id'],
        'transport_attempt': transport['run_attempt'], 'transport_workflow_sha': transport['workflow_sha']})
    with (output / 'manifest.json').open('xb') as out:
        out.write(encoded(manifest) + b'\n')
    return {'status': 'PASS_PUBLIC_GENERATION_AFTER_REMOTE_ACK_NEW_PROCESS',
            'generation': public['generation'], 'snapshot_sha256': public['snapshot_sha256'],
            'file_sha256': manifest['file_sha256'], 'source_originals_exported': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-git', type=Path, required=True)
    parser.add_argument('--published', type=Path)
    parser.add_argument('--recover', action='store_true')
    parser.add_argument('--child-project', action='store_true')
    parser.add_argument('--expected', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workflow-sha')
    parser.add_argument('--execution-sha')
    args = parser.parse_args()
    if args.child_project:
        project_git(args.private_git, json.loads(args.expected.read_text()), args.output)
    else:
        if not args.workflow_sha or (args.published is None) != args.recover:
            raise ValueError('PUBLIC_RESEARCH_EXPLICIT_PUBLICATION_OR_RECOVERY_REQUIRED')
        transport = {'run_id': int(os.environ['GITHUB_RUN_ID']), 'run_attempt': int(os.environ['GITHUB_RUN_ATTEMPT']),
                     'workflow_sha': args.workflow_sha}
        print('BCT_PUBLIC_RESEARCH_JSON=' + json.dumps(emit(args.private_git, args.published, args.output, transport)))
