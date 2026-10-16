"""Private, append-only transport for backups and monthly quantitative research.

Reuses the audited Q1 capsule, page delta and authenticated GPG components.
Monthly primary selection is explicit; this module never activates a schedule.
Releases are not an unlimited database service.
"""
import gzip
import hashlib
from itertools import zip_longest
import json
import re
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from bct.objective_lock import stamp_export, require_objective
from . import private_state as transport, quantitative_private as typed, quantitative_delta as delta
from .store import file_sha

FORMAT = 'bct-release-archive-1'
PILOT_BYTES = 64 * 1024**2  # Separate finite pilot budget; old Git cap is unchanged.
MAX_ASSETS = 400  # Safely below the documented 1000/release, including orphan uploads.
MAX_MANIFEST = 1024**2
MAX_DELTAS = 32
MAX_AGE_DAYS = 7
MONTHLY_TOTAL_BYTES = 6 * 1024**3
MONTHLY_BYTES = 256 * 1024**2


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Releases:
    """Fixed private destination; auth is never forwarded to a signed download host."""
    def __init__(self, token, tag, parent):
        monthly = re.fullmatch(r'bct-v4-archive-monthly-(?:trial-[0-9]+-)?([0-9]{4}-[0-9]{2})', tag)
        if not monthly and not re.fullmatch(r'bct-v4-archive-(?:test|shadow)-[0-9]+', tag):
            raise ValueError('ARCHIVE_TAG_NAMESPACE')
        if monthly:
            datetime.strptime(monthly[1], '%Y-%m')
        if not token or not re.fullmatch('[0-9a-f]{40}', parent):
            raise ValueError('ARCHIVE_CREDENTIAL_OR_PARENT_MISSING')
        self.token, self.tag, self.parent = token, tag, parent
        self.base = 'repos/' + transport.PRIVATE_REPO
        self.release_id = None
        self.monthly = bool(monthly)
        self.metrics = {'HTTP_requests':0, 'upload_bytes':0, 'download_bytes':0,
                        'rate_remaining':None, 'rate_limit':None, 'HTTP_seconds':0.0}

    def _request(self, method, path, value=None, *, binary=False, upload=False):
        host = 'uploads.github.com' if upload else 'api.github.com'
        url = 'https://' + host + '/' + path
        headers = {'Authorization': 'Bearer ' + self.token, 'User-Agent': 'BCT-archive',
                   'Accept': 'application/octet-stream' if binary else 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28'}
        data = value if upload else canonical(value) if value is not None else None
        if data is not None:
            headers['Content-Type'] = 'application/octet-stream' if upload else 'application/json'
        self.metrics['HTTP_requests'] += 1
        if upload:
            self.metrics['upload_bytes'] += len(data)
        started = time.monotonic()
        try:
            response = build_opener(NoRedirect).open(Request(url, data=data, method=method, headers=headers), timeout=25)
        except HTTPError as exc:
            if binary and method == 'GET' and exc.code == 302:
                location = exc.headers.get('Location', '')
                u = urlsplit(location)
                if u.scheme != 'https' or u.hostname not in {'release-assets.githubusercontent.com', 'objects.githubusercontent.com'} or u.username or u.password or u.port not in (None, 443):
                    raise ValueError('ARCHIVE_DOWNLOAD_REDIRECT_REJECTED') from None
                # New request without Authorization, cookies or signed URL logging.
                self.metrics['HTTP_requests'] += 1
                response = build_opener(NoRedirect).open(Request(location, headers={'User-Agent': 'BCT-archive'}), timeout=25)
            else:
                return exc.code, None
        with response:
            raw = response.read(transport.MAX_TRANSPORT + 1)
            self.metrics['download_bytes'] += len(raw)
            self.metrics['HTTP_seconds'] += time.monotonic() - started
            for header, key in [('X-RateLimit-Remaining','rate_remaining'),('X-RateLimit-Limit','rate_limit')]:
                value = getattr(response, 'headers', {}).get(header)
                if value is not None and str(value).isdigit():
                    self.metrics[key] = int(value)
            if len(raw) > transport.MAX_TRANSPORT:
                raise ValueError('ARCHIVE_RESPONSE_LIMIT')
            return response.status, raw if binary else json.loads(raw)

    def ensure(self, *, create=True):
        code, repo = self._request('GET', self.base)
        if code != 200 or repo.get('private') is not True or repo.get('full_name') != transport.PRIVATE_REPO:
            raise ValueError('ARCHIVE_PRIVATE_REPOSITORY_NOT_VERIFIED_' + str(code))
        code, value = self._request('GET', self.base + '/releases/tags/' + self.tag)
        if code == 404 and create:
            code, value = self._request('POST', self.base + '/releases', {
                'tag_name': self.tag, 'target_commitish': self.parent,
                'name': self.tag, 'body': 'Encrypted BCT research state; no public source originals.',
                'draft': False, 'prerelease': True, 'make_latest': 'false'})
        if code not in (200, 201) or value.get('tag_name') != self.tag or value.get('draft') is not False:
            raise ValueError('ARCHIVE_RELEASE_FAILED_' + str(code))
        self.release_id = value['id']
        return self

    def assets(self):
        output = []
        for page in range(1, 12):
            code, rows = self._request('GET', f'{self.base}/releases/{self.release_id}/assets?per_page=100&page={page}')
            if code != 200 or not isinstance(rows, list):
                raise ValueError('ARCHIVE_ASSET_LIST_FAILED_' + str(code))
            output += rows
            if len(rows) < 100:
                return output
        raise ValueError('ARCHIVE_LIST_BOUND')

    def read(self, asset):
        code, raw = self._request('GET', f'{self.base}/releases/assets/{asset["id"]}', binary=True)
        if code != 200:
            raise ValueError('ARCHIVE_DOWNLOAD_FAILED_' + str(code))
        return raw

    def put(self, name, raw):
        assets = self.assets()
        # Count all archive pilot releases, not a fresh allowance for every run ID.
        total = 0
        for page in range(1, 12):
            code, releases = self._request('GET', f'{self.base}/releases?per_page=100&page={page}')
            if code != 200 or not isinstance(releases, list):
                raise ValueError('ARCHIVE_TOTAL_BUDGET_NOT_OBSERVABLE')
            for release in releases:
                if not release['tag_name'].startswith('bct-v4-archive-'):
                    continue
                for ap in range(1, 12):
                    code, rows = self._request('GET', f'{self.base}/releases/{release["id"]}/assets?per_page=100&page={ap}')
                    if code != 200 or not isinstance(rows, list):
                        raise ValueError('ARCHIVE_TOTAL_BUDGET_NOT_OBSERVABLE')
                    total += sum(x['size'] for x in rows)
                    if len(rows) < 100:
                        break
                else:
                    raise ValueError('ARCHIVE_LIST_BOUND')
            if len(releases) < 100:
                break
        else:
            raise ValueError('ARCHIVE_LIST_BOUND')
        total_limit = MONTHLY_TOTAL_BYTES if self.monthly else PILOT_BYTES
        own_bytes = sum(x['size'] for x in assets)
        slots = 2 if name.startswith('blob-') else 1  # Reserve the final commit slot.
        if (len(raw) > transport.MAX_TRANSPORT or len(assets) + slots > MAX_ASSETS
                or total + len(raw) > total_limit
                or self.monthly and own_bytes + len(raw) > MONTHLY_BYTES):
            raise ValueError('ARCHIVE_PILOT_BUDGET_STOP_BEFORE_UPLOAD')
        if any(x['name'] == name for x in assets):
            raise ValueError('ARCHIVE_IMMUTABLE_NAME_ALREADY_EXISTS')
        code, value = self._request('POST', f'{self.base}/releases/{self.release_id}/assets?' + urlencode({'name': name}), raw, upload=True)
        if code != 201:
            raise ValueError('ARCHIVE_UPLOAD_FAILED_' + str(code))
        return value


def commit_name(generation):
    if type(generation) is not int or not 0 <= generation < 10000:
        raise ValueError('ARCHIVE_GENERATION_BOUND')
    return f'commit-{generation:08d}.gpg'


def generations(store):
    return sorted(int(m.group(1)) for a in store.assets()
                  if (m := re.fullmatch(r'commit-([0-9]{8})\.gpg', a['name'])))


def load_commit(store, generation, password):
    name = commit_name(generation)
    matches = [a for a in store.assets() if a['name'] == name]
    if len(matches) != 1:
        raise ValueError('ARCHIVE_COMMIT_MISSING_OR_AMBIGUOUS')
    plain = transport._gpg(store.read(matches[0]), password, decrypt=True)
    if len(plain) > MAX_MANIFEST:
        raise ValueError('ARCHIVE_MANIFEST_SIZE')
    m = json.loads(plain); require_objective(m)
    if m.get('format') != FORMAT or m.get('generation') != generation or not isinstance(m.get('patches'), list) or len(m['patches']) > MAX_DELTAS:
        raise ValueError('ARCHIVE_MANIFEST_CONTRACT')
    if m['tag'] != store.tag or m['legacy_parent'] != store.parent:
        raise ValueError('ARCHIVE_NAMESPACE_OR_LEGACY_PARENT')
    if generation:
        # Bind to the immediately preceding immutable commit; not a floating latest pointer.
        prior = [a for a in store.assets() if a['name'] == commit_name(generation - 1)]
        if len(prior) != 1 or digest(transport._gpg(store.read(prior[0]), password, decrypt=True)) != m['previous_manifest_sha256']:
            raise ValueError('ARCHIVE_PARENT_MANIFEST_HASH')
    return m, digest(plain)


def read_blob(store, record, password):
    if not re.fullmatch(r'blob-[0-9a-f]{64}\.gpg', record['name']) or record['name'] != 'blob-' + record['plaintext_sha256'] + '.gpg':
        raise ValueError('ARCHIVE_OBJECT_NAME')
    matches = [a for a in store.assets() if a['name'] == record['name']]
    if len(matches) != 1 or matches[0]['id'] != record['id']:
        raise ValueError('ARCHIVE_OBJECT_MISSING_OR_REPLACED')
    raw = store.read(matches[0])
    if len(raw) != record['bytes'] or digest(raw) != record['ciphertext_sha256']:
        raise ValueError('ARCHIVE_CIPHERTEXT_HASH')
    plain = transport._gpg(raw, password, decrypt=True)
    if digest(plain) != record['plaintext_sha256']:
        raise ValueError('ARCHIVE_PLAINTEXT_HASH')
    return plain


def put_blob(store, plain, password):
    key = digest(plain); name = 'blob-' + key + '.gpg'
    existing = [a for a in store.assets() if a['name'] == name]
    if existing:
        if len(existing) != 1:
            raise ValueError('ARCHIVE_DUPLICATE_OBJECT')
        # An interrupted prior upload may be reused only after full authentication.
        asset = existing[0]; raw = store.read(asset)
        if digest(transport._gpg(raw, password, decrypt=True)) != key:
            raise ValueError('ARCHIVE_EXISTING_OBJECT_HASH')
    else:
        raw = transport._gpg(plain, password); asset = store.put(name, raw)
        if store.read(asset) != raw:
            raise ValueError('ARCHIVE_UPLOAD_READBACK_HASH')
    return {'name': name, 'id': asset['id'], 'bytes': len(raw), 'plaintext_sha256': key,
            'ciphertext_sha256': digest(raw)}


def materialize_verified(checkpoint, destination):
    proof = json.loads((Path(checkpoint)/'checkpoint.json').read_text())
    if file_sha(Path(checkpoint)/'checkpoint.sqlite3.gz') != proof['archive_sha256']:
        raise ValueError('ARCHIVE_PRIOR_CHECKPOINT_HASH')
    count = 0
    with gzip.open(Path(checkpoint)/'checkpoint.sqlite3.gz', 'rb') as src, Path(destination).open('xb') as out:
        while block := src.read(1048576):
            count += len(block)
            if count > delta.MAX_SQLITE:
                raise ValueError('ARCHIVE_EXPANDED_SIZE')
            out.write(block)
    if file_sha(destination) != proof['sqlite_sha256']:
        raise ValueError('ARCHIVE_PREVIOUS_SQLITE_HASH')


def require_append_only(previous, target):
    with sqlite3.connect(Path(target).resolve().as_uri()+'?mode=ro', uri=True) as db:
        db.execute('ATTACH DATABASE ? AS prior', (Path(previous).resolve().as_uri()+'?mode=ro',))
        if list(db.execute('SELECT * FROM metadata ORDER BY key')) != list(db.execute('SELECT * FROM prior.metadata ORDER BY key')):
            raise ValueError('ARCHIVE_PRIMARY_METADATA_CHANGED')
        last = db.execute('SELECT coalesce(max(seq),0) FROM prior.events').fetchone()[0]
        before = db.execute('SELECT seq,at,kind,payload FROM prior.events ORDER BY seq')
        after = db.execute('SELECT seq,at,kind,payload FROM events WHERE seq<=? ORDER BY seq',(last,))
        # Stream exact rows by the primary key: no huge temporary EXCEPT b-tree.
        if any(a != b for a,b in zip_longest(before,after)):
            raise ValueError('ARCHIVE_PRIMARY_EXISTING_HISTORY_LOST')


def restore(store, generation, password, destination, *, expected_sqlite_sha256):
    """Never overwrite a valid destination or silently downgrade a corrupt generation."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError('ARCHIVE_RESTORE_REFUSES_OVERWRITE')
    m, _ = load_commit(store, generation, password)
    if m['proof']['sqlite_sha256'] != expected_sqlite_sha256:
        raise ValueError('ARCHIVE_EXPECTED_TARGET_HASH')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bct-archive-restore-', dir=destination.parent) as temp:
        root = Path(temp); db = root / 'v4.sqlite3'; cp = root / 'checkpoint'; cp.mkdir()
        raw = read_blob(store, m['base'], password)
        from io import BytesIO
        with gzip.GzipFile(fileobj=BytesIO(raw)) as src, db.open('xb') as out:
            size = 0
            while block := src.read(1048576):
                size += len(block)
                if size > delta.MAX_SQLITE:
                    raise ValueError('ARCHIVE_EXPANDED_SIZE')
                out.write(block)
        for patch in m['patches']:
            delta.apply_delta(db, read_blob(store, patch, password))
        if file_sha(db) != expected_sqlite_sha256:
            raise ValueError('ARCHIVE_RESTORED_SQLITE_HASH')
        with db.open('rb') as src, (cp / 'checkpoint.sqlite3.gz').open('xb') as dst:
            with gzip.GzipFile(fileobj=dst, mode='wb', mtime=0) as out:
                shutil.copyfileobj(src, out)
        (cp / 'checkpoint.json').write_bytes(canonical(m['proof']))
        proof = typed.restore(cp, root / 'verified')  # Exact hash, 8 tables and rights audit.
        cp.rename(destination)
    return {**proof, 'generation': generation, 'original_evidence_restore': False}


def publish(store, checkpoint, password, *, expected_generation, max_deltas=MAX_DELTAS,
            at=None, interrupt_before_commit=False, context=None, prior_checkpoint=None):
    if not 1 <= max_deltas <= MAX_DELTAS:
        raise ValueError('ARCHIVE_DELTA_CHAIN_BOUND')
    seen = generations(store); latest = seen[-1] if seen else -1
    if seen and seen != list(range(latest + 1)):
        raise ValueError('ARCHIVE_GENERATION_GAP')
    if latest != expected_generation:
        raise ValueError('ARCHIVE_PARENT_CHANGED_NO_OVERWRITE')
    checkpoint = Path(checkpoint); proof = json.loads((checkpoint / 'checkpoint.json').read_text())
    now = at or datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix='bct-archive-publish-') as tmp:
        root = Path(tmp); typed.restore(checkpoint, root / 'target')
        previous, previous_sha = load_commit(store, latest, password) if latest >= 0 else (None, None)
        if previous and previous['proof']['sqlite_sha256'] == proof['sqlite_sha256']:
            # Read back the committed generation; don't trust only its manifest hash.
            restore(store, latest, password, root / 'unchanged', expected_sqlite_sha256=proof['sqlite_sha256'])
            return {'generation': latest, 'unchanged': True, 'uploaded_objects': 0}
        checkpoint_due = previous is None or len(previous['patches']) >= max_deltas or now >= datetime.fromisoformat(previous['checkpoint_at']) + timedelta(days=MAX_AGE_DAYS)
        primary = bool(context and context.get('purpose') == 'QUANTITATIVE_RESEARCH_PRIMARY')
        if previous and (not checkpoint_due or primary):
            restore(store, latest, password, root/'previous', expected_sqlite_sha256=previous['proof']['sqlite_sha256'])
            materialize_verified(root/'previous', root/'old.sqlite3')
            if primary:
                require_append_only(root/'old.sqlite3', root/'target/v4.sqlite3')
        elif primary and prior_checkpoint:
            materialize_verified(prior_checkpoint, root/'previous-month.sqlite3')
            require_append_only(root/'previous-month.sqlite3', root/'target/v4.sqlite3')
        if checkpoint_due:
            base = put_blob(store, (checkpoint / 'checkpoint.sqlite3.gz').read_bytes(), password)
            patches = []; checkpoint_at = now.isoformat(); kind = 'CHECKPOINT'
        else:
            raw, _ = delta.make_delta(root/'old.sqlite3', root/'target/v4.sqlite3')
            base = previous['base']; patches = previous['patches'] + [put_blob(store, raw, password)]
            checkpoint_at = previous['checkpoint_at']; kind = 'PAGE_DELTA'
        m = stamp_export({'format': FORMAT, 'tag': store.tag, 'legacy_parent': store.parent,
                          'generation': latest + 1, 'previous_manifest_sha256': previous_sha,
                          'created_at': now.isoformat(), 'checkpoint_at': checkpoint_at, 'kind': kind,
                          'base': base, 'patches': patches, 'proof': proof,
                          'research_only': True,
                          'primary_backend_enabled': bool(context and context.get('purpose') == 'QUANTITATIVE_RESEARCH_PRIMARY'),
                          **({'monthly_context': context} if context else {})})
        raw = canonical(m)
        if len(raw) > MAX_MANIFEST:
            raise ValueError('ARCHIVE_MANIFEST_SIZE')
        if interrupt_before_commit:
            raise ValueError('ARCHIVE_TEST_INTERRUPTED_BEFORE_COMMIT')
        # Unique sequence name is the final atomic commit point. Concurrent writers
        # conflict rather than replacing a complete generation. Orphan blobs remain.
        store.put(commit_name(latest + 1), transport._gpg(raw, password))
        loaded, got_sha = load_commit(store, latest + 1, password)
        if got_sha != digest(raw):
            raise ValueError('ARCHIVE_COMMIT_READBACK_HASH')
        return {'generation': latest + 1, 'unchanged': False, 'kind': loaded['kind'],
                'patches': len(patches), 'manifest_sha256': got_sha,
                'sqlite_sha256': proof['sqlite_sha256'], 'legacy_parent': store.parent}
