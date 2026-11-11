"""Project the freshly fetched private ACK in a separate, credential-free process."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from bct.v4.public_research import encoded, validate_snapshot
from bct.objective_lock import stamp_export
from bct.v4.store import file_sha
from bct.v4.private_state import PRIVATE_URL


def emit(private_git, published, output, producer):
    private_git, output = Path(private_git), Path(output)
    if output.exists():
        raise ValueError('PUBLIC_RESEARCH_OUTPUT_EXISTS')
    result = json.loads(Path(published).read_text())
    commit = result.get('commit', '')
    if not re.fullmatch('[0-9a-f]{40}', commit) or result.get('remote_restore_verified') is not True:
        raise ValueError('PUBLIC_RESEARCH_ACK_REQUIRED')

    def git(*args):
        process = subprocess.run(['git', '-C', str(private_git), *args], capture_output=True, timeout=25)
        if process.returncode:
            raise ValueError('PUBLIC_RESEARCH_PRIVATE_ACK_READ_FAILED')
        return process.stdout

    if git('config', '--get', 'remote.origin.url').decode().strip() != PRIVATE_URL:
        raise ValueError('PUBLIC_RESEARCH_REPOSITORY_MISMATCH')
    if git('rev-parse', 'FETCH_HEAD').decode().strip() != commit:
        raise ValueError('PUBLIC_RESEARCH_FETCHED_GENERATION_CHANGED')
    acknowledgment = json.loads(git('show', commit + ':private-persistence.json'))
    if acknowledgment != result.get('persistence_receipt'):
        raise ValueError('PUBLIC_RESEARCH_ACK_RECEIPT_MISMATCH')
    parents = git('rev-list', '--parents', '-n', '1', commit).decode().split()
    if parents != [commit, acknowledgment.get('checkpoint_commit')]:
        raise ValueError('PUBLIC_RESEARCH_ACK_PARENT_MISMATCH')
    if git('rev-parse', '--is-shallow-repository').decode().strip() != 'false':
        raise ValueError('PUBLIC_RESEARCH_INCOMPLETE_PRIVATE_HISTORY')
    roots = git('rev-list', '--max-parents=0', '--first-parent', commit).decode().split()
    if len(roots) != 1:
        raise ValueError('PUBLIC_RESEARCH_PRIVATE_LINEAGE_AMBIGUOUS')
    producer = {**producer, 'lineage_root': roots[0],
                'ack_sequence': int(git('rev-list', '--first-parent', '--count', commit))}
    with tempfile.TemporaryDirectory(prefix='bct-public-restart-') as temporary:
        root = Path(temporary); packet = root / 'checkpoint'; packet.mkdir()
        for name in ('checkpoint.json', 'checkpoint.sqlite3.gz'):
            (packet / name).write_bytes(git('show', commit + ':' + name))
        (root / 'publisher.json').write_bytes(encoded(result))
        (root / 'producer.json').write_bytes(encoded(producer))
        code = '''import json,sqlite3,sys
from pathlib import Path
from bct.v4.cpu_operations import restore
from bct.v4.public_research import build_snapshot,encoded
r=Path(sys.argv[1]);proof=restore(r/'checkpoint',r/'restored')
with sqlite3.connect((r/'restored/v4.sqlite3').as_uri()+'?mode=ro',uri=True)as db:
 public=build_snapshot(db,json.loads((r/'publisher.json').read_text()),proof,json.loads((r/'producer.json').read_text()))
with (r/'snapshot.json').open('xb')as out:out.write(encoded(public)+b'\\n')
'''
        removed = {'BCT_V4_PRIVATE_STATE_TOKEN', 'BCT_V4_STATE_PASSPHRASE', 'GH_TOKEN', 'GITHUB_TOKEN'}
        environment = {key: value for key, value in os.environ.items() if key not in removed}
        child = subprocess.run([sys.executable, '-c', code, str(root)], env=environment,
                               capture_output=True, timeout=120)
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
        'generation': public['generation']})
    with (output / 'manifest.json').open('xb') as out:
        out.write(encoded(manifest) + b'\n')
    return {'status': 'PASS_PUBLIC_GENERATION_AFTER_REMOTE_ACK_NEW_PROCESS',
            'generation': public['generation'], 'snapshot_sha256': public['snapshot_sha256'],
            'file_sha256': manifest['file_sha256'], 'source_originals_exported': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-git', type=Path, required=True)
    parser.add_argument('--published', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workflow-sha', required=True)
    parser.add_argument('--execution-sha', required=True)
    args = parser.parse_args()
    source = {'run_id': int(os.environ['GITHUB_RUN_ID']), 'run_attempt': int(os.environ['GITHUB_RUN_ATTEMPT']),
              'workflow_sha': args.workflow_sha, 'execution_sha': args.execution_sha}
    print('BCT_PUBLIC_RESEARCH_JSON=' + json.dumps(emit(args.private_git, args.published, args.output, source)))
