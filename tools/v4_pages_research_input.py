"""Receive only allowlisted public receipts; never access a private repository."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import zipfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from bct.objective_lock import require_objective, stamp_export
from bct.v4.public_research import encoded, validate_snapshot, digest
from bct.v4.public_data import read_current, persist, require_not_older, validate_acquisition, validate_health, _collection_order

REPOSITORY = 'irewon1-lgtm/bottleneck-control-tower'
SITE = 'https://irewon1-lgtm.github.io/bottleneck-control-tower/'
CPU_WORKFLOW = '.github/workflows/v4-cpu-private-research.yml'
MAX_ARTIFACT = 512 * 1024
# This receipt namespace was introduced by the approved November 11 recovery.
# Earlier artifacts cannot contain this public format. Later scans use the
# durable cursor, so normal operation does not reread the historical inventory.
PUBLIC_FORMAT_CUTOVER = datetime(2026, 11, 11, tzinfo=timezone.utc)


def unpack(raw):
    if len(raw) > MAX_ARTIFACT:
        raise ValueError('PAGES_PUBLIC_ARTIFACT_SIZE')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) != 2 or {p.filename for p in entries} != {'snapshot.json', 'manifest.json'}:
            raise ValueError('PAGES_PUBLIC_ARTIFACT_FILES')
        if any(p.flag_bits & 1 or stat.S_ISLNK(p.external_attr >> 16)
               or p.file_size > MAX_ARTIFACT for p in entries):
            raise ValueError('PAGES_PUBLIC_ARTIFACT_ENTRY')
        snapshot = archive.read('snapshot.json')
        manifest = json.loads(archive.read('manifest.json'))
    return snapshot, manifest


def validate_cpu_artifact(run, jobs, raw):
    if (run.get('head_branch') != 'main' or run.get('event') not in ('workflow_run', 'workflow_dispatch')
            or run.get('conclusion') != 'success' or run.get('path') != CPU_WORKFLOW
            or run.get('head_repository', {}).get('full_name') != REPOSITORY):
        raise ValueError('PAGES_PUBLIC_PRODUCER')
    if not any(job.get('name') == 'publish' and job.get('conclusion') == 'success' for job in jobs):
        raise ValueError('PAGES_PUBLIC_PUBLISHER_NOT_SUCCESSFUL')
    content, manifest = unpack(raw); public = json.loads(content)
    if hashlib.sha256(content).hexdigest() != manifest.get('file_sha256'):
        raise ValueError('PAGES_PUBLIC_FILE_HASH')
    validate_snapshot(public); require_objective(manifest)
    if (set(manifest) != {'format', 'objective_version', 'objective_sha256', 'file_sha256', 'snapshot_sha256', 'generation',
                          'transport_run_id', 'transport_attempt', 'transport_workflow_sha'}
            or manifest['format'] != 'bct-public-research-artifact-1'
            or manifest['snapshot_sha256'] != public['snapshot_sha256']
            or manifest['generation'] != public['generation']):
        raise ValueError('PAGES_PUBLIC_MANIFEST')
    # Recovery may transport an older immutable ACK. Bind the artifact to the
    # current successful attempt without rebranding that ACK's original writer.
    if (type(manifest['transport_run_id']) is not int or type(manifest['transport_attempt']) is not int
            or manifest['transport_run_id'] != run['id'] or manifest['transport_attempt'] != run['run_attempt']
            or manifest['transport_workflow_sha'] != run['head_sha']):
        raise ValueError('PAGES_PUBLIC_PRODUCER_GENERATION')
    return public


def api(path):
    result = subprocess.run(['gh', 'api', 'repos/' + REPOSITORY + '/' + path],
                            capture_output=True, text=True, timeout=25)
    if result.returncode:
        raise ValueError('PAGES_PUBLIC_METADATA_UNAVAILABLE')
    return json.loads(result.stdout)


def artifact_bytes(artifact):
    if (artifact.get('expired') is not False or type(artifact.get('size_in_bytes')) is not int
            or not 0 < artifact['size_in_bytes'] <= MAX_ARTIFACT
            or not re.fullmatch('sha256:[0-9a-f]{64}', artifact.get('digest') or '')):
        raise ValueError('PAGES_PUBLIC_ARTIFACT_METADATA')
    result = subprocess.run(['gh', 'api', f'repos/{REPOSITORY}/actions/artifacts/{artifact["id"]}/zip'],
                            capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError('PAGES_PUBLIC_ARTIFACT_DOWNLOAD')
    if (len(result.stdout) != artifact['size_in_bytes']
            or hashlib.sha256(result.stdout).hexdigest() != artifact['digest'].split(':')[1]):
        raise ValueError('PAGES_PUBLIC_ARTIFACT_TRANSPORT_HASH')
    return result.stdout


def published_manifest():
    try:
        with urlopen(Request(SITE + 'build-manifest.json', headers={'Cache-Control': 'no-cache'}), timeout=20) as response:
            raw = response.read(MAX_ARTIFACT + 1)
    except HTTPError as error:
        if error.code == 404:
            return {}
        raise ValueError('PAGES_PREVIOUS_MANIFEST_UNAVAILABLE') from None
    if len(raw) > MAX_ARTIFACT:
        raise ValueError('PAGES_PREVIOUS_MANIFEST_SIZE')
    return json.loads(raw)


def validate_acquisition_artifact(run, raw):
    content, manifest = unpack(raw); receipt = validate_acquisition(json.loads(content))
    if (set(manifest) != {'format', 'file', 'bytes', 'sha256'}
            or manifest['format'] != 'bct-public-acquisition-manifest-1' or manifest['file'] != 'snapshot.json'
            or manifest['bytes'] != len(content) or manifest['sha256'] != hashlib.sha256(content).hexdigest()):
        raise ValueError('PAGES_PUBLIC_ACQUISITION_MANIFEST')
    if (run.get('path') != '.github/workflows/precursor-acquisition.yml' or run.get('event') != 'workflow_run'
            or run.get('head_branch') != 'main' or run.get('head_repository', {}).get('full_name') != REPOSITORY
            or receipt['run_id'] != run['id'] or receipt['run_attempt'] != run['run_attempt']
            or receipt['head_sha'] != run['head_sha']):
        raise ValueError('PAGES_PUBLIC_ACQUISITION_PRODUCER')
    return receipt


def artifact_for(run, prefix):
    wanted = prefix + '-' + str(run['run_attempt'])
    matches = [a for a in api(f'actions/runs/{run["id"]}/artifacts?per_page=100')['artifacts']
               if a['name'] == wanted and a.get('expired') is False]
    if len(matches) > 1:
        raise ValueError('PAGES_PUBLIC_ARTIFACT_AMBIGUOUS')
    return matches[0] if matches else None


def git_client():
    check = subprocess.run(['git', 'config', '--get', 'remote.origin.url'], capture_output=True, text=True, check=True)
    if check.stdout.strip().removesuffix('.git') != 'https://github.com/' + REPOSITORY:
        raise ValueError('PUBLIC_DATA_REPOSITORY_MISMATCH')
    if os.environ.get('BCT_V4_PRIVATE_STATE_TOKEN') or os.environ.get('BCT_V4_STATE_PASSPHRASE'):
        raise ValueError('PUBLIC_DATA_PRIVATE_CREDENTIAL_FORBIDDEN')
    token = os.environ.get('GH_TOKEN', '')
    environment = dict(os.environ)
    if token:
        auth = base64.b64encode(('x-access-token:' + token).encode()).decode()
        environment.update(GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
                           GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + auth,
                           GIT_CONFIG_KEY_1='credential.helper', GIT_CONFIG_VALUE_1='')
    def git(*args, input=None, env=None):
        result = subprocess.run(['git', *args], input=input, capture_output=True,
                                env={**environment, **(env or {})}, timeout=60)
        if result.returncode:
            raise ValueError('PUBLIC_DATA_GIT_FAILED')
        return result.stdout.decode().strip()
    return git


def receive_run(run, artifact=None):
    path = run.get('path'); research = collection = None
    if run.get('status') != 'completed':
        return research, collection
    if path == CPU_WORKFLOW and run.get('conclusion') == 'success':
        artifact = artifact or artifact_for(run, 'bct-public-research')
        if artifact:
            jobs = api(f'actions/runs/{run["id"]}/attempts/{run["run_attempt"]}/jobs?per_page=100')['jobs']
            research = validate_cpu_artifact(run, jobs, artifact_bytes(artifact))
    elif path == '.github/workflows/precursor-acquisition.yml':
        artifact = artifact or artifact_for(run, 'bct-public-acquisition')
        if artifact:
            collection = validate_acquisition_artifact(run, artifact_bytes(artifact))
    return research, collection


def catch_up(cursor, research=None, collection=None):
    newest = previous_id = None; complete = False; pending_producer = False
    error_reason = None
    try:
        for page in range(1, 6):
            entries = api(f'actions/artifacts?per_page=100&page={page}')['artifacts']
            for artifact in entries:
                artifact_id = artifact.get('id')
                if type(artifact_id) is not int or artifact_id < 1 or (previous_id and artifact_id >= previous_id):
                    raise ValueError('PUBLIC_TRANSPORT_INVENTORY_ORDER')
                previous_id = artifact_id
                created = datetime.fromisoformat(artifact['created_at'].replace('Z', '+00:00'))
                if created.tzinfo is None:
                    raise ValueError('PUBLIC_TRANSPORT_INVENTORY_TIME')
                if newest is None:
                    newest = stamp_export({'format': 'bct-public-transport-cursor-1', 'artifact_id': artifact_id,
                                           'artifact_created_at': artifact['created_at'], 'pending_reason': 'NONE'})
                if (cursor and cursor['artifact_id'] is not None and artifact_id <= cursor['artifact_id']) or (not cursor or cursor['artifact_id'] is None) and created < PUBLIC_FORMAT_CUTOVER:
                    complete = True
                    break
                match = re.fullmatch(r'(bct-public-research|bct-public-acquisition)-([1-9][0-9]*)', artifact.get('name', ''))
                if not match or artifact.get('expired') is not False:
                    continue
                run = api('actions/runs/' + str(artifact['workflow_run']['id']))
                if run.get('run_attempt') != int(match[2]):
                    continue  # A prior attempt's artifact cannot attest a rerun.
                if run.get('status') != 'completed':
                    pending_producer = True
                    continue
                wanted = CPU_WORKFLOW if match[1] == 'bct-public-research' else '.github/workflows/precursor-acquisition.yml'
                if run.get('path') != wanted:
                    raise ValueError('PUBLIC_TRANSPORT_WORKFLOW_MISMATCH')
                candidate, acquisition = receive_run(run, artifact)
                if candidate:
                    if research is None or candidate['generation']['ack_sequence'] > research['generation']['ack_sequence']:
                        if research: require_not_older(candidate['generation'], research['generation'])
                        research = candidate
                    elif candidate['generation']['ack_sequence'] == research['generation']['ack_sequence']:
                        require_not_older(candidate['generation'], research['generation'])
                        if candidate != research:
                            raise ValueError('PUBLIC_DATA_GENERATION_EQUIVOCATION')
                    elif candidate['generation']['lineage_root'] != research['generation']['lineage_root']:
                        raise ValueError('PUBLIC_DATA_GENERATION_LINEAGE_CHANGED')
                if acquisition and (collection is None or _collection_order(acquisition) > _collection_order(collection)):
                    collection = acquisition
            if complete or len(entries) < 100:
                complete = True
                break
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        error_reason = transport_error_reason(error)
    reason = error_reason or ('SCAN_BOUND' if not complete else 'PRODUCER_IN_PROGRESS' if pending_producer else 'NONE')
    if reason != 'NONE':
        # An independently verified current receipt remains useful even when
        # historical catch-up is bounded. Hold the cursor so later events retry.
        newest = stamp_export({'format': 'bct-public-transport-cursor-1',
            'artifact_id': cursor['artifact_id'] if cursor else None,
            'artifact_created_at': cursor['artifact_created_at'] if cursor else None, 'pending_reason': reason})
    elif cursor and cursor['artifact_id'] is not None and (newest is None or newest['artifact_id'] <= cursor['artifact_id']):
        newest = cursor
        newest = {**newest, 'pending_reason': 'NONE'}
    return research, collection, newest, reason


def transport_error_reason(error):
    unavailable = isinstance(error, (OSError, subprocess.TimeoutExpired)) or str(error) in {
        'PAGES_PUBLIC_METADATA_UNAVAILABLE', 'PAGES_PUBLIC_ARTIFACT_DOWNLOAD'}
    return 'TRANSPORT_UNAVAILABLE' if unavailable else 'TRANSPORT_INVALID'


def pending_cursor(cursor, reason):
    return stamp_export({'format': 'bct-public-transport-cursor-1',
        'artifact_id': cursor['artifact_id'] if cursor else None,
        'artifact_created_at': cursor['artifact_created_at'] if cursor else None, 'pending_reason': reason})


def sync(trigger_id=None):
    current = read_current(git_client())
    # Code-only builds need no Actions/artifact transport. Data events also
    # catch skipped pending events by artifact creation, never run creation.
    research = collection = cursor = None
    if trigger_id:
        research, collection = receive_run(api('actions/runs/' + str(trigger_id)))
        try:
            research, collection, cursor, pending_reason = catch_up(current.get('cursor'), research, collection)
        except (ValueError, OSError, subprocess.TimeoutExpired) as error:
            # Exact-trigger validation above remains fail closed. A separate
            # historical catch-up problem cannot discard this verified result.
            cursor = pending_cursor(current.get('cursor'), transport_error_reason(error))
    # Old artifacts are harmless once a newer receipt is durable. They must
    # never roll it back, and missing/expired artifacts never erase that state.
    if research and current['research'] and research['generation']['ack_sequence'] < current['research']['generation']['ack_sequence']:
        research = None
    if collection and current['acquisition'] and _collection_order(collection) < _collection_order(current['acquisition']):
        collection = None
    result = persist(git_client(), research=research, acquisition=collection, cursor=cursor)
    return {**result, 'catchup_pending_reason': cursor['pending_reason'] if cursor else 'NONE'}


def public_health():
    result = {'format': 'bct-public-workflow-observation-1',
              'observed_at': datetime.now(timezone.utc).isoformat(), 'workflows': {}}
    for key, filename, event in [('rss', 'rss-live-check.yml', 'schedule'),
                                  ('acquisition', 'precursor-acquisition.yml', 'workflow_run'),
                                  ('cpu', 'v4-cpu-private-research.yml', 'workflow_run'),
                                  ('review', 'review-lead-shadow.yml', 'workflow_run')]:
        runs = api(f'actions/workflows/{filename}/runs?branch=main&event={event}&per_page=1')['workflow_runs']
        if not runs:
            result['workflows'][key] = None
            continue
        run = runs[0]
        if run.get('head_repository', {}).get('full_name') != REPOSITORY:
            raise ValueError('PAGES_PUBLIC_HEALTH_REPOSITORY')
        row = {name: run.get(name) for name in ('id', 'status', 'conclusion', 'created_at', 'event')}
        if key == 'cpu':
            jobs = api(f'actions/runs/{run["id"]}/jobs?per_page=100')['jobs']
            row['processing_jobs'] = {j['name']: j.get('conclusion') or j['status']
                                      for j in jobs if j['name'] in ('research', 'publish')}
        result['workflows'][key] = row
    return validate_health(result)


def optional_public_health():
    try:
        return public_health()
    except (ValueError, OSError, subprocess.TimeoutExpired):
        # Status APIs are optional metadata. A failure must never erase a
        # successfully validated durable research generation or imply zeros.
        return validate_health({'format': 'bct-public-workflow-observation-1',
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'workflows': dict.fromkeys(('rss', 'acquisition', 'cpu', 'review'))})


def prepare(destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('PAGES_PUBLIC_INPUT_EXISTS')
    previous = published_manifest(); durable = read_current(git_client()); public = durable['research']
    require_not_older(public['generation'] if public else None, previous.get('research_generation'))
    destination.mkdir(parents=True, exist_ok=False)
    if public:
        (destination / 'research.json').write_bytes(encoded(public) + b'\n')
    if durable['acquisition']:
        (destination / 'collection.json').write_bytes(encoded(durable['acquisition']) + b'\n')
    if durable.get('cursor'):
        (destination / 'transport.json').write_bytes(encoded(durable['cursor']) + b'\n')
    health = optional_public_health()
    (destination / 'workflow.json').write_bytes(encoded(health) + b'\n')
    return {'research_generation': public['generation'] if public else None,
            'public_research_available': public is not None, 'source_originals_downloaded': 0}


def guard(candidate):
    durable = read_current(git_client()); latest = durable['research']
    generation = candidate.get('research_generation')
    require_not_older(generation, latest['generation'] if latest else None)
    require_not_older(generation, published_manifest().get('research_generation'))
    collection = candidate.get('collection_generation')
    if durable['acquisition'] and (collection is None or _collection_order(collection) < _collection_order(durable['acquisition'])):
        raise ValueError('PAGES_STALE_COLLECTION_OBSERVATION')
    if candidate.get('transport_cursor_sha256') != (digest(durable['cursor']) if durable.get('cursor') else None):
        raise ValueError('PAGES_STALE_TRANSPORT_OBSERVATION')
    return {'status': 'PASS_NO_NEWER_PUBLIC_GENERATION', 'research_generation': generation}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['sync', 'prepare', 'guard'])
    parser.add_argument('--path', type=Path)
    parser.add_argument('--trigger-id', type=int)
    parser.add_argument('--manifest-env')
    args = parser.parse_args()
    if args.action == 'sync':
        result = sync(args.trigger_id)
    elif args.action == 'prepare':
        result = prepare(args.path)
    else:
        candidate = json.loads(os.environ[args.manifest_env]) if args.manifest_env else json.loads((args.path / 'build-manifest.json').read_text())
        result = guard(candidate)
    print(json.dumps(result))
