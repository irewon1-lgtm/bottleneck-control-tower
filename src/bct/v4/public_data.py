"""CAS persistence for public receipts only; preserves every unowned data blob."""
import importlib.util
import json
from pathlib import Path
import tempfile
from datetime import datetime

from bct.objective_lock import stamp_export
from .public_research import encoded, validate_snapshot

REF = 'refs/heads/data'
RESEARCH = 'v4-public/research.json'
ACQUISITION = 'v4-public/acquisition.json'
CURSOR = 'v4-public/transport.json'
OWNED = {path for name in (RESEARCH, ACQUISITION, CURSOR) for path in (name, name + '.manifest.json')}


def validate_cursor(value):
    from .public_research import exact, number, timestamp
    from bct.objective_lock import require_objective
    exact(value, {'format', 'objective_version', 'objective_sha256', 'artifact_id', 'artifact_created_at', 'pending_reason'})
    require_objective(value)
    if value['format'] != 'bct-public-transport-cursor-1':
        raise ValueError('PUBLIC_TRANSPORT_CURSOR_FORMAT')
    number(value['artifact_id'], nullable=True); timestamp(value['artifact_created_at'])
    if (value['pending_reason'] not in ('NONE', 'PRODUCER_IN_PROGRESS', 'SCAN_BOUND', 'TRANSPORT_UNAVAILABLE', 'TRANSPORT_INVALID')
            or ((value['artifact_id'] is None) != (value['artifact_created_at'] is None))
            or (value['artifact_id'] is None and value['pending_reason'] == 'NONE')
            or (value['artifact_id'] is not None and value['artifact_id'] < 1)):
        raise ValueError('PUBLIC_TRANSPORT_CURSOR_ID')
    return value


def require_not_older(candidate, published):
    if published is None:
        return
    if candidate is None:
        raise ValueError('PUBLIC_DATA_STALE_MISSING_GENERATION')
    if candidate['lineage_root'] != published['lineage_root']:
        raise ValueError('PUBLIC_DATA_GENERATION_LINEAGE_CHANGED')
    if candidate['ack_sequence'] < published['ack_sequence']:
        raise ValueError('PUBLIC_DATA_STALE_GENERATION')
    if candidate['ack_sequence'] == published['ack_sequence'] and candidate != published:
        raise ValueError('PUBLIC_DATA_GENERATION_EQUIVOCATION')


def validate_acquisition(value):
    path = Path(__file__).resolve().parents[3] / '.github/scripts/public_acquisition.py'
    spec = importlib.util.spec_from_file_location('public_acquisition_contract', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.validate_receipt(value)


def validate_health(value):
    if (not isinstance(value, dict) or set(value) != {'format', 'observed_at', 'workflows'}
            or value['format'] != 'bct-public-workflow-observation-1'
            or set(value['workflows']) != {'rss', 'acquisition', 'cpu', 'review'}):
        raise ValueError('PUBLIC_WORKFLOW_FIELDS')
    from .public_research import timestamp, number
    timestamp(value['observed_at'], nullable=False)
    states = {'queued', 'in_progress', 'completed', 'waiting', 'pending', 'requested'}
    conclusions = {None, 'success', 'failure', 'neutral', 'cancelled', 'skipped', 'timed_out',
                   'action_required', 'stale', 'startup_failure'}
    for name, row in value['workflows'].items():
        if row is None:
            continue
        fields = {'id', 'status', 'conclusion', 'created_at', 'event'} | ({'processing_jobs'} if name == 'cpu' else set())
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError('PUBLIC_WORKFLOW_FIELDS')
        number(row['id']); timestamp(row['created_at'], nullable=False)
        if (row['status'] not in states or row['conclusion'] not in conclusions
                or row['event'] != ('schedule' if name == 'rss' else 'workflow_run')):
            raise ValueError('PUBLIC_WORKFLOW_STATE')
        if name == 'cpu' and (set(row['processing_jobs']) - {'research', 'publish'}
                or any(v not in states | conclusions for v in row['processing_jobs'].values())):
            raise ValueError('PUBLIC_WORKFLOW_PROCESSING_JOBS')
    return value


def _load(git, base, path, names):
    if path not in names:
        if path + '.manifest.json' in names:
            raise ValueError('PUBLIC_DATA_INCOMPLETE_RECEIPT')
        return None
    if path + '.manifest.json' not in names:
        raise ValueError('PUBLIC_DATA_MANIFEST_MISSING')
    raw = git('show', base + ':' + path)
    value = json.loads(raw)
    manifest = json.loads(git('show', base + ':' + path + '.manifest.json'))
    import hashlib
    if manifest != stamp_export({'format': 'bct-public-data-file-1',
                                  'sha256': hashlib.sha256(encoded(value)).hexdigest()}):
        raise ValueError('PUBLIC_DATA_MANIFEST_HASH')
    return {RESEARCH: validate_snapshot, ACQUISITION: validate_acquisition, CURSOR: validate_cursor}[path](value)


def read_current(git):
    git('fetch', '--no-tags', '--depth=1', 'origin', REF)
    base = git('rev-parse', 'FETCH_HEAD')
    names = set(git('ls-tree', '-r', '--name-only', base).splitlines())
    return {'commit': base, 'research': _load(git, base, RESEARCH, names),
            'acquisition': _load(git, base, ACQUISITION, names), 'cursor': _load(git, base, CURSOR, names)}


def _collection_order(value):
    instant = lambda text: datetime.fromisoformat(text.replace('Z', '+00:00'))
    return (instant(value['collection_started_at']), value['RSS_run_id'], value['run_id'],
            value.get('run_attempt', 1), instant(value['completed_at']))


def persist(git, *, research=None, acquisition=None, cursor=None):
    if research is not None:
        validate_snapshot(research)
    if acquisition is not None:
        validate_acquisition(acquisition)
    if cursor is not None:
        validate_cursor(cursor)
    for attempt in range(1, 4):
        current = read_current(git); base = current['commit']; updates = {}
        if research is not None:
            old = current['research']
            require_not_older(research['generation'], old['generation'] if old else None)
            if old and old['generation'] == research['generation'] and old != research:
                raise ValueError('PUBLIC_DATA_GENERATION_EQUIVOCATION')
            if old != research:
                updates[RESEARCH] = research
        if acquisition is not None:
            old = current['acquisition']
            if old and _collection_order(acquisition) < _collection_order(old):
                raise ValueError('PUBLIC_DATA_STALE_COLLECTION')
            if old != acquisition:
                updates[ACQUISITION] = acquisition
        if cursor is not None:
            old = current['cursor']
            if old and old['artifact_id'] is not None and (cursor['artifact_id'] is None or cursor['artifact_id'] < old['artifact_id']):
                raise ValueError('PUBLIC_DATA_STALE_TRANSPORT_CURSOR')
            if old and cursor['artifact_id'] == old['artifact_id'] and cursor['artifact_created_at'] != old['artifact_created_at']:
                raise ValueError('PUBLIC_DATA_TRANSPORT_CURSOR_EQUIVOCATION')
            if old != cursor:
                updates[CURSOR] = cursor
        selected = research if research is not None else current['research']
        if not updates:
            return {'status': 'PASS_PUBLIC_DATA_UNCHANGED', 'commit': base, 'unchanged': True,
                    'research_generation': selected['generation'] if selected else None, 'attempts': attempt}
        with tempfile.TemporaryDirectory(prefix='bct-public-data-index-') as temporary:
            env = {'GIT_INDEX_FILE': str(Path(temporary) / 'index')}
            git('read-tree', base, env=env)
            for path, value in updates.items():
                import hashlib
                manifest = stamp_export({'format': 'bct-public-data-file-1',
                    'sha256': hashlib.sha256(encoded(value)).hexdigest()})
                for name, content in ((path, value), (path + '.manifest.json', manifest)):
                    blob = git('hash-object', '-w', '--stdin', input=encoded(content) + b'\n')
                    git('update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + name, env=env)
            tree = git('write-tree', env=env)
            # Explicitly verify canonical/state/index and all future unowned files.
            def unowned(ref):
                return {line for line in git('ls-tree', '-r', ref).splitlines()
                        if line.split('\t', 1)[1] not in OWNED}
            if unowned(base) != unowned(tree):
                raise ValueError('PUBLIC_DATA_UNOWNED_BLOB_CHANGED')
            commit = git('-c', 'user.name=BCT public receipt', '-c',
                         'user.email=bct-public@users.noreply.github.com', 'commit-tree', tree, '-p', base,
                         input=b'Preserve validated public processing receipt\n')
        remote = git('ls-remote', 'origin', REF).split()
        if not remote or remote[0] != base:
            continue  # A new canonical write is preserved by rereading its tree.
        try:
            git('push', 'origin', commit + ':' + REF)
        except ValueError:
            remote = git('ls-remote', 'origin', REF).split()
            if remote and remote[0] != base:
                continue
            raise
        return {'status': 'PASS_PUBLIC_DATA_CAS', 'commit': commit, 'unchanged': False,
                'research_generation': selected['generation'] if selected else None,
                'updated_paths': sorted(updates), 'unowned_blobs_preserved': True, 'attempts': attempt}
    raise ValueError('PUBLIC_DATA_CAS_CONFLICT_RETRY_BOUND')
