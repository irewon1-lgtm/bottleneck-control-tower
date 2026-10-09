"""Restore checked source observations without repeating an unchanged denial."""
from pathlib import Path
import json
import time
from datetime import datetime
from collections import defaultdict, deque
from urllib.parse import urlsplit

from .future_body import read_cached_body, cache_body, is_control_only_body


def restore_observations(root, cache, *, now=None, retry_errors=False):
    """An artifact is evidence, never a new HTTP execution or read completion.

    Retain prior denied/unavailable results. Retry only requests not executed,
    a due host cooldown, or technical errors after an explicit code change.
    Hash-check every referenced body before trusting a preserved observation.
    """
    root, cache = Path(root), Path(cache)
    journal = root / 'source-recovery-attempts.jsonl'
    if not journal.exists():
        return {}, {}
    previous = {}
    for line in journal.read_text().splitlines():
        record = json.loads(line)
        if not isinstance(record.get('url'), str) or not isinstance(record.get('attempted'), bool):
            raise ValueError('invalid preserved source observation')
        previous[record['url']] = record
    observed, pending = {}, {}
    at = time.time() if now is None else now
    for url, record in previous.items():
        if record.get('access_diagnostic', {}).get('category') == 'HTTP_429' and not record.get('resume_after'):
            stamp = datetime.fromisoformat(record['attempted_at'].replace('Z', '+00:00')).timestamp()
            record['resume_after'] = stamp + (record['access_diagnostic'].get('retry_after_seconds') or 3600)
        digest = record.get('body_sha256')
        if digest:
            body = read_cached_body(root / 'private-source-cache', digest)
            if body is None:
                raise ValueError('preserved source cache hash mismatch')
            if cache_body(cache, body) != digest:
                raise ValueError('restored source cache hash mismatch')
            if record.get('body_status') == 'FULL' and is_control_only_body(body):
                # Preserve the original observation and cache, but correct its
                # classification without requesting an unchanged denied URL.
                record['prior_observation_classification'] = {
                    key: record.get(key) for key in ('status', 'body_status', 'body_sha256', 'completeness', 'reasons')}
                record.update(status='UNAVAILABLE', body_status='UNAVAILABLE',
                              reclassification_rule='ARTICLE_CONTROL_ONLY_V1')
                record['reasons'] = list(dict.fromkeys([*record.get('reasons', []), 'ARTICLE_CONTROL_ONLY']))
                record['completeness'] = {**record.get('completeness', {}), 'assessment': 'UI_CONTROL_ONLY'}
        reason = record.get('reason')
        category = record.get('access_diagnostic', {}).get('category')
        due = record.get('resume_after', float('inf')) <= at
        if (not record['attempted'] and reason == 'RUNNER_DEADLINE'
                or (reason == 'HOST_RATE_LIMIT' or category == 'HTTP_429') and due
                or record.get('status') == 'ERROR' and retry_errors):
            pending[url] = record
        elif not record['attempted']:
            pending[url] = record
        else:
            observed[url] = {**record, 'preserved_from_prior_execution': True}
    return observed, pending


def host_cooldowns(records, *, now=None):
    """Retain actual Retry-After across runner changes; never erase a limit."""
    from urllib.parse import urlsplit
    at = time.time() if now is None else now
    result = {}
    for record in records.values():
        until = record.get('resume_after', 0)
        if until > at:
            host = urlsplit(record['url']).hostname
            result[host] = max(result.get(host, 0), until)
    return result


def source_attempt_order(urls, previous):
    """Attempt untouched URLs before due retries; rotate hosts fairly.

    A repeatedly rate-limited old URL must not starve every untouched URL on
    its host. This does not shorten a cooldown or authorize parallel requests.
    """
    groups = defaultdict(deque)
    for url in sorted(urls, key=lambda u: (previous.get(u, {}).get('attempted', False), u)):
        groups[urlsplit(url).hostname].append(url)
    ordered = []
    while any(groups.values()):
        for queue in groups.values():
            if queue:
                ordered.append(queue.popleft())
    return ordered
