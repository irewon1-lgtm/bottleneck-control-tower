"""24-month quantitative research primary state; CPU/RSS/UI paths are untouched.

Reuses the archive format, exact table audit, secret handoff and old Git reader.
There is deliberately no fallback to stale Git after a Releases error.
"""
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from bct.objective_lock import require_objective
from . import release_archive as archive, quantitative_private as legacy

POLICY = Path('docs/v4/quantitative/storage-policy.json')
PREFIX = 'bct-v4-archive-monthly-'


def policy(path=POLICY):
    p = json.loads(Path(path).read_text()); require_objective(p)
    if (p['format'] != 'bct-monthly-storage-policy-1' or p['backend'] not in {'git', 'monthly-releases'}
            or p['months'] != 24 or p['all_archive_bytes_budget'] != archive.MONTHLY_TOTAL_BYTES
            or p['monthly_bytes_budget'] != archive.MONTHLY_BYTES or p['monthly_assets_budget'] != archive.MAX_ASSETS
            or p['checkpoint_deltas'] != archive.MAX_DELTAS or p['checkpoint_age_days'] != archive.MAX_AGE_DAYS):
        raise ValueError('MONTHLY_POLICY_CONTRACT')
    datetime.strptime(p['monthly_start'], '%Y-%m')
    return p


def month_number(value):
    d = datetime.strptime(value, '%Y-%m')
    return d.year * 12 + d.month - 1


class Monthly:
    def __init__(self, token, password, *, settings=None, at=None, trial=None, factory=None):
        self.p = settings or policy(); self.token = token; self.password = password
        self.at = at or datetime.now(timezone.utc); self.month = self.at.strftime('%Y-%m')
        self.prefix = PREFIX + ('trial-' + str(trial) + '-' if trial else '')
        self.anchor = self.p['anchor_legacy_parent']; self.factory = factory or archive.Releases
        self.metrics = {'HTTP_requests':0, 'upload_bytes':0, 'download_bytes':0,
                        'rate_remaining':None, 'rate_limit':None, 'HTTP_seconds':0.0}
        # The write window expires; existing archives must remain readable afterward.
        self.write_allowed = 0 <= month_number(self.month) - month_number(self.p['monthly_start']) < self.p['months']

    def store(self, tag=None, *, create=False):
        return self.client(tag or self.prefix + self.month).ensure(create=create)

    def client(self, tag):
        value = self.factory(self.token, tag, self.anchor)
        value.metrics = self.metrics
        return value

    def head(self):
        client = self.client(self.prefix + self.month)
        code, repo = client._request('GET', client.base)
        if code != 200 or repo.get('private') is not True or repo.get('full_name') != archive.transport.PRIVATE_REPO:
            raise ValueError('MONTHLY_PRIVATE_REPOSITORY_UNVERIFIED')
        found = []
        for page in range(1, 12):
            code, rows = client._request('GET', client.base + f'/releases?per_page=100&page={page}')
            if code != 200 or not isinstance(rows, list):
                raise ValueError('MONTHLY_HEAD_LIST_FAILED_NO_GIT_FALLBACK')
            for r in rows:
                tag = r['tag_name']
                if not tag.startswith(self.prefix) or len(tag) != len(self.prefix) + 7:
                    continue
                period = tag[-7:]; month_number(period)
                if (r.get('draft') is not False or period > self.month
                        or not 0 <= month_number(period) - month_number(self.p['monthly_start']) < 24):
                    raise ValueError('MONTHLY_FUTURE_OR_UNREVIEWED_RELEASE')
                found.append(tag)
            if len(rows) < 100:
                break
        else:
            raise ValueError('MONTHLY_RELEASE_LIST_BOUND')
        tag = None
        for candidate in sorted(found, reverse=True):
            s = self.store(candidate); gens = archive.generations(s)
            if not gens:
                continue  # Incomplete month seed isn't a new completed head.
            if gens != list(range(gens[-1] + 1)):
                raise ValueError('MONTHLY_COMMIT_GAP')
            tag, generation = candidate, gens[-1]
            break
        if tag is None:
            return None
        m, h = archive.load_commit(s, generation, self.password)
        context = m.get('monthly_context')
        if not context or context['purpose'] != 'QUANTITATIVE_RESEARCH_PRIMARY':
            raise ValueError('MONTHLY_PRIMARY_CONTEXT_MISSING')
        previous = context.get('previous_month')
        if previous:
            if previous['tag'] >= tag or previous['legacy_parent'] != self.anchor:
                raise ValueError('MONTHLY_PREVIOUS_PERIOD')
            pm, ph = archive.load_commit(self.store(previous['tag']), previous['generation'], self.password)
            if ph != previous['manifest_sha256'] or pm['proof']['sqlite_sha256'] != previous['sqlite_sha256']:
                raise ValueError('MONTHLY_PREVIOUS_MONTH_HASH')
        return {'backend':'monthly-releases', 'tag':tag, 'generation':generation,
                'manifest_sha256':h, 'sqlite_sha256':m['proof']['sqlite_sha256'], 'legacy_parent':self.anchor}

    def receive(self, destination, *, git_repo=None):
        cursor = self.head()
        if cursor is None:
            if git_repo is None:
                raise ValueError('MONTHLY_INITIAL_GIT_SEED_REQUIRED')
            old = legacy.remote_checkpoint(git_repo, destination, self.token)
            if old['parent'] != self.anchor:
                raise ValueError('MONTHLY_LEGACY_ANCHOR_CHANGED')
            old['storage'] = {'backend':'git-seed', 'legacy_parent':self.anchor,
                              'sqlite_sha256':old['verified']['sqlite_sha256']}
            return old
        verified = archive.restore(self.store(cursor['tag']), cursor['generation'], self.password,
                                   destination, expected_sqlite_sha256=cursor['sqlite_sha256'])
        return {'parent':self.anchor, 'verified':verified, 'storage':cursor}

    def publish(self, checkpoint, expected, *, interrupt_before_commit=False):
        if not self.write_allowed:
            raise ValueError('MONTHLY_24_MONTH_HORIZON_ENDED')
        current = self.head()
        proof = json.loads((Path(checkpoint)/'checkpoint.json').read_text())
        if expected is None:
            raise ValueError('MONTHLY_INPUT_CURSOR_REQUIRED')
        if current != (None if expected.get('backend') == 'git-seed' else expected):
            if current and current['sqlite_sha256'] == proof['sqlite_sha256'] and expected.get('legacy_parent') == self.anchor:
                # Publication may have succeeded before its acknowledgment was lost.
                # Validate the exact candidate and committed state; do not upload again.
                with tempfile.TemporaryDirectory(prefix='bct-monthly-ack-') as tmp:
                    legacy.restore(checkpoint, Path(tmp)/'candidate')
                    archive.restore(self.store(current['tag']), current['generation'], self.password,
                                    Path(tmp)/'committed', expected_sqlite_sha256=current['sqlite_sha256'])
                return {'backend':'monthly-releases', 'storage':current, 'unchanged':True,
                        'recovered_lost_acknowledgment':True, 'Git_writes':0}
            raise ValueError('MONTHLY_PARENT_CHANGED_NO_OVERWRITE')
        if expected['legacy_parent'] != self.anchor:
            raise ValueError('MONTHLY_LEGACY_PARENT')
        tag = self.prefix + self.month
        same_month = current and current['tag'] == tag
        previous_month = None
        if same_month:
            m, _ = archive.load_commit(self.store(tag), current['generation'], self.password)
            previous_month = m['monthly_context'].get('previous_month')
        elif current:
            previous_month = current
        if current is None and proof['sqlite_sha256'] != expected['sqlite_sha256']:
            raise ValueError('MONTHLY_FIRST_SEED_MUST_EQUAL_LEGACY_STATE')
        # Equal old-month input is a no-op; no unnecessary monthly full seed.
        if current and not same_month and proof['sqlite_sha256'] == current['sqlite_sha256']:
            return {'backend':'monthly-releases', 'storage':current, 'unchanged':True, 'Git_writes':0}
        s = self.store(tag, create=True)
        with tempfile.TemporaryDirectory(prefix='bct-month-transition-') as tmp:
            prior_checkpoint = None
            if previous_month and not same_month:
                prior_checkpoint = Path(tmp)/'previous-month'
                archive.restore(self.store(previous_month['tag']), previous_month['generation'], self.password,
                                prior_checkpoint, expected_sqlite_sha256=previous_month['sqlite_sha256'])
            result = archive.publish(s, checkpoint, self.password,
                expected_generation=current['generation'] if same_month else -1, at=self.at,
                interrupt_before_commit=interrupt_before_commit, prior_checkpoint=prior_checkpoint,
                context={'purpose':'QUANTITATIVE_RESEARCH_PRIMARY', 'previous_month':previous_month,
                         'scope':'Q1 quantitative facts, page cursors and own Q2 state; CPU originals unchanged'})
        m, h = archive.load_commit(s, result['generation'], self.password)
        cursor = {'backend':'monthly-releases', 'tag':tag, 'generation':result['generation'],
                  'manifest_sha256':h, 'sqlite_sha256':m['proof']['sqlite_sha256'], 'legacy_parent':self.anchor}
        return {**result, 'backend':'monthly-releases', 'storage':cursor, 'Git_writes':0,
                'request_metrics':dict(self.metrics)}
