"""Read exact-attempt public inputs for the existing isolated REVIEW writer."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

REPOSITORY = 'irewon1-lgtm/bottleneck-control-tower'
SOURCE_WORKFLOW = '.github/workflows/precursor-acquisition.yml'
CPU_WORKFLOW = '.github/workflows/v4-cpu-private-research.yml'
MAX_ARCHIVE = 6 * 1024**3


def select_source_artifact(run, artifacts, run_id, attempt, head):
    if (run.get('id') != run_id or run.get('run_attempt') != attempt or run.get('head_sha') != head
            or run.get('path') != SOURCE_WORKFLOW or run.get('event') != 'workflow_run'
            or run.get('head_branch') != 'main'
            or run.get('head_repository', {}).get('full_name') != REPOSITORY):
        raise ValueError('REVIEW_SOURCE_PRODUCER_MISMATCH')
    wanted = 'precursor-private-cache-' + str(attempt)
    matches = [a for a in artifacts if a.get('name') == wanted]
    # Only the proven original run may use the historical unsuffixed artifact.
    if not matches and attempt == 1:
        matches = [a for a in artifacts if a.get('name') == 'precursor-private-cache']
    if len(matches) > 1:
        raise ValueError('REVIEW_SOURCE_ARTIFACT_AMBIGUOUS')
    if not matches:
        return None
    item = matches[0]
    if (item.get('expired') is not False or type(item.get('id')) is not int or item['id'] < 1
            or type(item.get('size_in_bytes')) is not int or not 0 < item['size_in_bytes'] <= MAX_ARCHIVE
            or not re.fullmatch(r'sha256:[0-9a-f]{64}', item.get('digest') or '')
            or item.get('workflow_run', {}).get('id') != run_id
            or item['workflow_run'].get('head_sha') != head
            or item['workflow_run'].get('head_branch') != 'main'):
        raise ValueError('REVIEW_SOURCE_ARTIFACT_METADATA')
    return item


def api(path):
    result = subprocess.run(['gh', 'api', 'repos/' + REPOSITORY + '/' + path],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('REVIEW_PUBLIC_METADATA_UNAVAILABLE')
    return json.loads(result.stdout)


def source_input(run_id, attempt, head):
    from bct import review_artifact, review_shadow
    run = api(f'actions/runs/{run_id}')
    artifacts = []
    for page in range(1, 6):
        entries = api(f'actions/runs/{run_id}/artifacts?per_page=100&page={page}')['artifacts']
        artifacts.extend(entries)
        if len(entries) < 100:
            break
    else:
        raise ValueError('REVIEW_SOURCE_ARTIFACT_INVENTORY_BOUND')
    artifact = select_source_artifact(run, artifacts, run_id, attempt, head)
    if artifact is None:
        return {'source_handoff': 'ARTIFACT_MISSING', 'available': False}
    destination = Path('var/review-source-cache')
    with tempfile.TemporaryDirectory(prefix='review-source-') as directory:
        archive = Path(directory) / 'cache.zip'
        review_artifact.download(REPOSITORY, artifact['id'], artifact['size_in_bytes'], archive,
                                 expected_digest=artifact['digest'])
        review_artifact.extract_archive(archive, destination, run['created_at'])
    window = Path('var/review-window.json')
    window.write_text(json.dumps({'collection_started_at': run['created_at'], 'documents': [],
                                 'source': 'actual upstream workflow_run.created_at'}))
    review_shadow.handoff(window, destination, Path('var/review-handoff'))
    return {'source_handoff': 'AVAILABLE', 'available': True}


def public_transport(processor_root):
    path = Path(processor_root) / 'tools/v4_pages_research_input.py'
    spec = importlib.util.spec_from_file_location('_review_public_transport', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def public_inputs(processor_root, run_id=None):
    """Every event catches up trusted public evidence; no private credentials."""
    transport = public_transport(processor_root)
    current = transport.read_current(transport.git_client())
    snapshots = []
    if current['research']:
        snapshots.append(current['research'])
    research = current['research']
    if run_id:
        run = transport.api('actions/runs/' + str(run_id))
        if run.get('path') == CPU_WORKFLOW:
            candidate, _ = transport.receive_run(run)
            if candidate:
                if research and candidate['generation']['ack_sequence'] < research['generation']['ack_sequence']:
                    transport.require_not_older(research['generation'], candidate['generation'])
                else:
                    if research:
                        transport.require_not_older(candidate['generation'], research['generation'])
                        if candidate['generation'] == research['generation'] and candidate != research:
                            raise ValueError('REVIEW_PUBLIC_GENERATION_EQUIVOCATION')
                    research = candidate
    try:
        research, _, _, pending = transport.catch_up(current.get('cursor'), research)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        unavailable = isinstance(error, (OSError, subprocess.TimeoutExpired)) or str(error) in {
            'PAGES_PUBLIC_METADATA_UNAVAILABLE', 'PAGES_PUBLIC_ARTIFACT_DOWNLOAD'}
        pending = 'TRANSPORT_UNAVAILABLE' if unavailable else 'TRANSPORT_INVALID'
    if pending not in ('NONE', 'PRODUCER_IN_PROGRESS', 'SCAN_BOUND', 'TRANSPORT_UNAVAILABLE', 'TRANSPORT_INVALID'):
        raise ValueError('REVIEW_PUBLIC_CATCHUP_STATUS')
    if research and all(research['snapshot_sha256'] != value['snapshot_sha256'] for value in snapshots):
        snapshots.append(research)
    output = Path('var/review-public-inputs'); output.mkdir(parents=True, exist_ok=True)
    for public in snapshots:
        (output / (public['snapshot_sha256'] + '.json')).write_text(json.dumps(public))
    return {'public_snapshots': len(snapshots), 'public_input_status': 'AVAILABLE' if snapshots else 'NO_ACK_SNAPSHOT',
            'catchup_pending_reason': pending}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('source', 'public'))
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--attempt', type=int)
    parser.add_argument('--head')
    parser.add_argument('--processor-root', type=Path, default=Path('processor'))
    args = parser.parse_args()
    if args.action == 'source':
        result = source_input(args.run_id, args.attempt, args.head)
        with open(os.environ['GITHUB_ENV'], 'a') as stream:
            stream.write('BCT_REVIEW_HANDOFF_AVAILABLE=' + str(result['available']).lower() + '\n')
    else:
        result = public_inputs(args.processor_root, args.run_id)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
