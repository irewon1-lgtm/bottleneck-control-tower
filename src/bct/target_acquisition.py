"""Bounded missing-evidence acquisition, separate from RSS and frozen engines.

A lead is not a verified signal. Unknown scope, attribution and calendar bounds
remain unknown. Existing screening exports are consumed without screening again.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import xml.etree.ElementTree as ET

from .future_body import extract_document, discovery_document
from .future_hypothesis import extract_facts

UNKNOWN = 'UNKNOWN'
ROLES = ('DEMAND', 'SUPPLY')
WORDS = {
    'DEMAND': r'\b(?:orders?|backlog|offtake|purchase|reservations?|customer.{0,20}capex|deliveries|delivery|procurement)\b',
    'SUPPLY': r'\b(?:capacity|commissioning|ramp|utilization|qualified|qualification|production|allocation|inventory|manufacturing)\b',
}
PERIOD = re.compile(r'\b(?:20\d{2}(?:-\d{2}-\d{2})?|Q[1-4]\s*20\d{2}|(?:first|second) half of 20\d{2}|next \d+ months|through 20\d{2})\b', re.I)
AMOUNT = re.compile(r'(?<![\w$€£])\d+(?:,\d{3})*(?:\.\d+)?\s*(?:million\s+)?(?:(?:all-electric|electric|SAR)\s+)?(?:mtpa|Bcf/d|kg/day|MW|GW|tonnes|tons|units|satellites|vehicles|trucks|wafers|slots|pieces)(?:\s*(?:per year|annually|per month))?\b', re.I)
FIELDS = ('specification', 'region', 'supply_pool', 'quantity', 'unit', 'period', 'basis')


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def put(path, value):
    """Immutable operation results: never replace an earlier attempt."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def public_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise ValueError('public HTTPS source required')
    if p.hostname.lower() in ('localhost', 'localhost.localdomain'):
        raise ValueError('private source rejected')
    try:
        if not ipaddress.ip_address(p.hostname).is_global:
            raise ValueError('private source rejected')
    except ValueError as exc:
        if str(exc) == 'private source rejected':
            raise
    return url


def norm(url):
    p = urlsplit(url or '')
    return (p.hostname or '').lower(), p.path.rstrip('/'), p.query


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta, self.canonical, self.ld, self.links = {}, None, [], []
        self.script, self.parts, self.anchor = False, [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta':
            self.meta[a.get('property') or a.get('name')] = a.get('content')
        if tag == 'link' and a.get('rel') == 'canonical':
            self.canonical = a.get('href')
        if tag == 'script' and a.get('type') == 'application/ld+json':
            self.script, self.parts = True, []
        if tag == 'a' and a.get('href'):
            self.anchor = [a['href'], []]

    def handle_data(self, data):
        if self.script:
            self.parts.append(data)
        if self.anchor is not None:
            self.anchor[1].append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.script:
            try:
                self.ld.append(json.loads(''.join(self.parts)))
            except ValueError:
                pass
            self.script = False
        if tag == 'a' and self.anchor is not None:
            self.links.append((self.anchor[0], ' '.join(self.anchor[1])))
            self.anchor = None


def nodes(v):
    if isinstance(v, dict):
        yield v
        for x in v.values():
            yield from nodes(x)
    elif isinstance(v, list):
        for x in v:
            yield from nodes(x)


def verify(raw, url, final_url, acquired_at, status=200, content_type='text/html'):
    """Evidence-based identity/date/body checks; no hostname-based promotion."""
    html = raw.decode('utf-8', errors='replace')
    extracted = extract_document(html, http_status=status, content_type=content_type)
    m = Metadata(); m.feed(html)
    ns = list(nodes(m.ld))
    refs = {n['@id']: n for n in ns if '@id' in n and len(n) > 1}
    articles = [n for n in ns if any(x in str(n.get('@type')) for x in ('Article', 'Posting'))
                and norm((n.get('url') or n.get('@id') or '').split('#')[0]) == norm(m.canonical or final_url)]
    a = articles[0] if len(articles) == 1 else {}
    publisher = a.get('publisher', {})
    if isinstance(publisher, dict):
        publisher = refs.get(publisher.get('@id'), publisher).get('name')
    else:
        publisher = None
    publisher = publisher or m.meta.get('og:site_name')
    raw_pub = a.get('datePublished') or m.meta.get('article:published_time')
    published, precision = None, UNKNOWN
    if isinstance(raw_pub, str):
        try:
            dt = datetime.fromisoformat(raw_pub.replace('Z', '+00:00'))
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw_pub):
                published, precision = raw_pub, 'DATE'
            elif dt.tzinfo is not None:
                published, precision = dt.isoformat(), 'TIMESTAMP'
        except ValueError:
            pass
    body = extracted['body']
    checks = {
        'http_success': status == 200,
        'original_identity': bool(m.canonical and norm(url) == norm(final_url) == norm(m.canonical)),
        'publisher_observed': bool(publisher),
        'attribution_consistent': bool(publisher and m.meta.get('og:site_name') and publisher.casefold() == m.meta['og:site_name'].casefold()),
        'original_publication': bool(published),
        'available_at_recorded': bool(acquired_at),
        'full_accessible_body': extracted['body_status'] == 'FULL',
        'not_republication': not bool(re.search(r'\b(?:reprinted (?:from|with)|originally (?:published|appeared)|provided by Reuters|Reuters reporting|copyright.{0,20}Reuters)\b', extracted['body'], re.I)),
        'body_hash_matches': bool(body and digest(body) == extracted['body_sha256']),
    }
    if published:
        checks['publication_before_acquisition'] = published[:10] <= acquired_at[:10] if precision == 'DATE' else datetime.fromisoformat(published) <= datetime.fromisoformat(acquired_at)
    return {'origin_id': a.get('@id') or m.canonical or UNKNOWN, 'origin_url': url,
            'canonical_url': m.canonical, 'origin_publisher': publisher or UNKNOWN,
            'published_at': published, 'published_at_raw': raw_pub, 'publication_precision': precision,
            'acquired_at': acquired_at, 'available_at': acquired_at,
            'body': body, 'body_sha256': digest(body), 'version': digest(body),
            'raw_sha256': digest(raw), 'checks': checks,
            'provenance': 'PASS' if all(checks.values()) else 'BLOCKED',
            'provenance_verified': all(checks.values()),
            'provenance_blockers': [k for k, v in checks.items() if not v],
            'body_status': extracted['body_status']}


def plan(targets):
    """Consume existing evidence; do not rescan or reclassify the seed corpus."""
    requests, state = [], []
    for t in targets:
        target = t['target']
        sides = {}
        for role in ROLES:
            signal = t['demand_signal' if role == 'DEMAND' else 'supply_signal']
            # Screening presence is a lead, not validated field completeness.
            known = t.get('existing_verified_facts', {}).get(role, [])
            missing = [k for k in FIELDS if not any(f.get(k) not in (None, '', UNKNOWN) for f in known)]
            if not known:
                missing.append('independent_original_provenance')
            sides[role] = {'signal_present': signal, 'facts': known, 'missing_fields': missing}
            if not missing:
                continue
            kind = 'MISSING_FIELDS' if signal else 'MISSING_SIDE'
            hints = 'firm orders backlog offtake delivery quantity delivery start end' if role == 'DEMAND' else 'qualified production capacity commissioning ramp available allocation'
            query = f'"{target}" {hints} official'
            requests.append({'request_id': digest(target + ':' + role), 'target': target,
                             'role': role, 'kind': kind, 'missing_fields': sides[role]['missing_fields'],
                             'query': query, 'seed_document_ids': t['document_ids']})
        state.append({'target': target, 'sides': sides, 'common_future_period': UNKNOWN})
    return {'format': 'bct-target-evidence-plan-v1', 'targets': state, 'requests': requests}


def leads(body, target, requested_roles):
    """Keep exact raw amounts/periods. Never convert dollars/MW into output."""
    result = []
    structured = extract_facts(body, {'targets': [{'name': target}], 'discovery_paths': []})['scope_facts']
    for mt in re.finditer(r'[^\n]+', body):
        quote = mt.group()
        # No pronoun/document-wide attribution to an unrelated product.
        if target.casefold() not in quote.casefold():
            continue
        roles = [role for role in requested_roles if re.search(WORDS[role], quote, re.I)]
        if len(roles) != 1:
            # Ambiguous dual-role sentence is preserved as a lead, never two signals.
            if roles:
                result.append({'target': target, 'role': 'AMBIGUOUS', 'source_quote': quote,
                               'locator': {'start': mt.start(), 'end': mt.end()}, 'status': 'REQUIRES_ROLE_REVIEW'})
            continue
        fact = next((f for f in structured if f['role'] == roles[0] and f['target'].casefold() == target.casefold()
                     and f['locator']['start'] == mt.start() and not f.get('scope_ambiguous')), {})
        result.append({'target': target, 'role': roles[0], 'source_quote': quote,
                       'locator': {'start': mt.start(), 'end': mt.end()},
                       'raw_quantities': AMOUNT.findall(quote) + [m.group() for m in re.finditer(r'\b\d+(?:,\d{3})*(?:\.\d+)?\s+(?:all-electric\s+)?' + re.escape(target) + r's?\b', quote, re.I)], 'raw_period_expressions': PERIOD.findall(quote),
                       **{k: fact.get(k, UNKNOWN) for k in FIELDS},
                       'need_date': fact.get('need_date'), 'available_date': fact.get('available_date'),
                       'qualified': bool(roles[0] == 'SUPPLY' and re.search(r'\bqualified (?:supply|capacity|production)\b', quote, re.I)),
                       'actual_statement': fact.get('actual_statement', False),
                       'claim_attribution': 'INDEPENDENT_ORIGIN_UNVERIFIED' if re.search(r'\b(?:according to|announced|said|says|syndicated|told)\b', quote, re.I) else 'SOURCE_STATEMENT',
                       'status': 'EXPLICIT_SCOPE_FACT' if fact else 'LEAD_UNKNOWN_SCOPE'})
    return result


def error_status(exc):
    if isinstance(exc, HTTPError):
        return 'SITE_HTTP_BLOCKED' if exc.code in (401, 403, 429) else 'HTTP_FAILED'
    return 'CONNECT_BLOCKED' if 'Tunnel connection failed: 403' in str(exc) else 'NETWORK_FAILED'


def fetch(url):
    public_url(url)
    r = urlopen(Request(url, headers={'User-Agent': 'BCT-target-evidence/1.0'}), timeout=20)
    public_url(r.url)
    raw = r.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('response exceeds bounded 4MB capture')
    return raw, r.url, r.status, r.headers.get('Content-Type', '')


def search(request, endpoint):
    url = endpoint + ('&' if '?' in endpoint else '?') + urlencode({'q': request['query'], 'format': 'rss'})
    raw, final, status, content_type = fetch(url)
    if 'xml' in content_type or raw.lstrip().startswith(b'<?xml'):
        root = ET.fromstring(raw)
        return [i.findtext('link') for i in root.findall('.//item') if i.findtext('link')][:3]
    value = json.loads(raw)
    return [r['url'] for r in value['results']][:3]


def collect(plan_value, output, *, direct_urls=None, search_endpoint=None, workers=6):
    """100 request batches; completed request files make resumption idempotent."""
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    direct_urls = direct_urls or {}
    searches, failures, url_jobs = [], [], {}
    provider_blocked = None
    for offset in range(0, len(plan_value['requests']), 100):
        batch = plan_value['requests'][offset:offset + 100]
        for req in batch:
            p = output / 'requests' / (req['request_id'] + '.json')
            if p.exists():
                record = json.loads(p.read_text())
            else:
                urls = list(direct_urls.get(req['request_id'], [])); record = {**req, 'created_at': now(), 'urls': urls}
                if search_endpoint and not provider_blocked:
                    try:
                        discovered = search(req, search_endpoint)
                        urls.extend(discovered); record['urls'] = list(dict.fromkeys(urls)); record['search_status'] = 'FINISHED'
                    except Exception as exc:
                        record['search_status'] = error_status(exc); record['error'] = str(exc)
                        if record['search_status'] in ('CONNECT_BLOCKED', 'SITE_HTTP_BLOCKED'):
                            provider_blocked = record['search_status']
                else:
                    record['search_status'] = provider_blocked or 'SEARCH_PROVIDER_NOT_CONFIGURED'
                put(p, record)
            searches.append(record)
            for url in record['urls']:
                try:
                    public_url(url)
                except ValueError:
                    continue
                url_jobs.setdefault(url, []).append(req)
        put_if_new = output / f'batch-{offset // 100 + 1:03d}-requests.json'
        if not put_if_new.exists():
            put(put_if_new, {'requests': len(batch), 'request_ids': [r['request_id'] for r in batch], 'next_batch_allowed': True})
    def capture(item):
        url, reqs = item; key = digest(url); path = output / 'documents' / (key + '.json')
        if path.exists():
            return json.loads(path.read_text())
        record = {'document_id': 'target-' + key, 'url': url, 'requests': [r['request_id'] for r in reqs], 'targets': sorted({r['target'] for r in reqs}), 'acquired_at': now()}
        try:
            raw, final, status, content_type = fetch(url)
            record['acquired_at'] = now()
            put_raw = output / 'raw' / (digest(raw) + '.html'); put_raw.parent.mkdir(exist_ok=True)
            if not put_raw.exists():
                with put_raw.open('xb') as f:
                    f.write(raw)
            record.update(verify(raw, url, final, record['acquired_at'], status, content_type))
            record.update(status='BODY_CAPTURED' if record['body'] else 'NO_BODY', final_url=final, raw_path=str(put_raw))
            record['evidence'] = []
            for target in record['targets']:
                role_set = sorted({r['role'] for r in reqs if r['target'] == target})
                for lead in leads(record['body'], target, role_set):
                    record['evidence'].append({**lead, 'document_id': record['document_id'], 'publisher': record['origin_publisher'], 'origin_url': url, 'published_at': record['published_at'], 'acquired_at': record['acquired_at'], 'body_sha256': record['body_sha256'], 'version': record['version'], 'provenance': record['provenance']})
        except Exception as exc:
            record.update(status=error_status(exc), error=str(exc), provenance='BLOCKED', evidence=[])
        put(path, record)
        return record
    documents = []
    items = list(url_jobs.items())
    for offset in range(0, len(items), 100):
        with ThreadPoolExecutor(max_workers=workers) as executor:
            documents.extend(executor.map(capture, items[offset:offset + 100]))
    return searches, documents


def reference_plan(plan_value, documents, *, completed_urls=(), blocked_domains=()):
    """One hop to cited source documents, never a site crawl or domain promotion."""
    requests, direct, used = [], {}, set(completed_urls)
    blocked = set(blocked_domains)
    for d in documents:
        if d.get('provenance') != 'PASS' or not d.get('raw_path'):
            continue
        m = Metadata(); m.feed(Path(d['raw_path']).read_text(errors='replace'))
        for req in plan_value['requests']:
            if req['target'] not in d['targets']:
                continue
            count = 0
            for href, label in m.links:
                url = urljoin(d['url'], href)
                p = urlsplit(url)
                if p.hostname in blocked or url in used or p.hostname == urlsplit(d['url']).hostname:
                    continue
                # A cited contract/production statement must actually identify
                # this product in its URL or anchor. No unrelated homepage crawl.
                context = (url + ' ' + label).casefold()
                if req['target'] not in context or not re.search(WORDS[req['role']], context, re.I):
                    continue
                try:
                    public_url(url)
                except ValueError:
                    continue
                item = {**req, 'request_id': digest(req['request_id'] + ':' + url),
                        'reference_parent': d['url'], 'reference_label': label}
                requests.append(item); direct[item['request_id']] = [url]
                used.add(url); count += 1
                if count == 2:
                    break
    return {'requests': requests, 'targets': plan_value['targets']}, direct


def signal_batch(documents):
    """Only fully explicit, proven facts reach frozen engine validation."""
    from .objective_lock import stamp_export
    docs, signals = [], []
    for d in documents:
        if d.get('provenance') != 'PASS':
            continue
        for e in d.get('evidence', []):
            if e.get('claim_attribution') == 'INDEPENDENT_ORIGIN_UNVERIFIED':
                continue
            if e['role'] not in ROLES or not e.get('actual_statement') or any(e.get(k) in (None, '', UNKNOWN) for k in ('specification', 'region', 'supply_pool', 'period', 'basis')):
                continue
            if not isinstance(e['period'], dict) or e['status'] != 'EXPLICIT_SCOPE_FACT':
                continue
            signals.append({**{k: e[k] for k in FIELDS}, 'target_id': e['target'], 'target': e['target'],
                            'document_id': d['document_id'], 'locator': e['locator'], 'role': e['role'],
                            'signal_type': 'committed_order' if e['role'] == 'DEMAND' else 'qualified_capacity',
                            'need_date': e['need_date'], 'available_date': e['available_date'],
                            'qualified': e['qualified'], 'source_quote': e['source_quote']})
        if any(s['document_id'] == d['document_id'] for s in signals):
            record = {**d, 'id': d['document_id'], 'publication_verified': True,
                      'provenance_evidence': {'body_sha256': d['body_sha256'], 'verified_source_url': d['origin_url'], 'source_identity': d['origin_id']},
                      'publication_evidence': {'body_sha256': d['body_sha256'], 'source_quote': d.get('published_at_raw') or d['published_at']}}
            docs.append(discovery_document(record, d['body']))
    return stamp_export({'documents': docs, 'signals': signals, 'confirmations': []})


def align_periods(batch):
    """Intersect literal explicit bounds only within identical physical scope."""
    from copy import deepcopy
    from .objective_lock import stamp_export
    signals, seen, overlaps = [], set(), []
    for demand in batch['signals']:
        if demand['role'] != 'DEMAND':
            continue
        for supply in batch['signals']:
            if supply['role'] != 'SUPPLY' or any(demand[k] != supply[k] for k in ('target_id', 'target', 'specification', 'region', 'supply_pool')):
                continue
            dp, sp = demand['period'], supply['period']
            try:
                for date in [dp['start'], dp['end'], sp['start'], sp['end']]:
                    datetime.strptime(date, '%Y-%m-%d')
            except (ValueError, KeyError, TypeError):
                continue
            start, end = max(dp['start'], sp['start']), min(dp['end'], sp['end'])
            if start > end or start <= now()[:10]:
                continue
            overlaps.append({'target': demand['target_id'], 'period': {'start': start, 'end': end},
                             'demand_document_id': demand['document_id'], 'supply_document_id': supply['document_id']})
            for original in (demand, supply):
                item = deepcopy(original)
                item['source_period'] = original['period']
                item['period'] = {'start': start, 'end': end}
                key = json.dumps(item, sort_keys=True)
                if key not in seen:
                    seen.add(key); signals.append(item)
    # Keep unmatched facts for DATA_WAIT diagnostics; never discard an old state.
    paired = {(s['document_id'], s['locator']['start']) for s in signals}
    signals += [s for s in batch['signals'] if (s['document_id'], s['locator']['start']) not in paired]
    return stamp_export({**batch, 'signals': signals}), overlaps


def evaluate(documents, *, engine=None):
    if engine is None:
        from . import forecast_discovery as engine
    unique, seen = [], set()
    for d in documents:
        key = d.get('body_sha256')
        if not key or key in seen:
            continue
        seen.add(key); unique.append(d)
    batch, overlaps = align_periods(signal_batch(unique))
    # Exact frozen engine validation, no writes/session creation/backdating.
    result = engine.discover(batch, mode='LIVE')
    ready = sorted({c['target_id'] for c in result['candidates']})
    return {'strict_ready': ready, 'batch': batch, 'preflight': result, 'unique_body_documents': len(unique), 'explicit_scope_period_overlaps': overlaps}


def execute_ready(evaluation, store, engine_hashes, output):
    """Run only existing session, and only preflight candidate subsets."""
    from . import prospective, forecast_discovery, early_forecast
    modules = {'prospective.py': prospective, 'forecast_discovery.py': forecast_discovery, 'early_forecast.py': early_forecast}
    for name, module in modules.items():
        if digest(Path(module.__file__).read_bytes()) != engine_hashes[name]:
            raise ValueError('frozen engine mismatch: ' + name)
    store = Path(store)
    if not (store / 'session.json').is_file():
        raise ValueError('existing session required; never create a session')
    session_hash = digest((store / 'session.json').read_bytes())
    originals = {str(p): digest(p.read_bytes()) for p in store.rglob('*.json')}
    from .objective_lock import stamp_export
    executions = []
    for target in evaluation['strict_ready']:
        batch = evaluation['batch']
        signals = [s for s in batch['signals'] if s['target_id'] == target]
        ids = {s['document_id'] for s in signals}
        subset = stamp_export({'documents': [d for d in batch['documents'] if d['document_id'] in ids], 'signals': signals, 'confirmations': []})
        # The unchanged EARLY engine must accept the same genuine input first.
        early_check = early_forecast.discover(subset, mode='LIVE')
        if early_check['state'] == 'BLOCKED' or early_check.get('rejected_inputs'):
            executions.append({'target': target, 'run_early': 'BLOCKED', 'reason': early_check})
            continue
        early = prospective.run(store, subset, early=True)
        if early['engine_state'] == 'BLOCKED':
            executions.append({'target': target, 'run_early': early, 'strict': 'NOT_RUN'})
            continue
        strict = prospective.run(store, subset)
        executions.append({'target': target, 'run_early': early, 'strict': strict})
        for path, h in originals.items():
            if digest(Path(path).read_bytes()) != h:
                raise ValueError('existing append-only record changed')
        if digest((store / 'session.json').read_bytes()) != session_hash:
            raise ValueError('session changed')
        if strict['engine_state'] != 'BLOCKED' and strict.get('first_frozen', 0) + strict.get('history_appended', 0):
            break
    put(Path(output) / 'live-executions.json', executions)
    return executions


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed-targets', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--direct-urls', type=Path)
    p.add_argument('--search-endpoint')
    p.add_argument('--seed-documents', type=Path)
    p.add_argument('--live-store', type=Path)
    p.add_argument('--engine-manifest', type=Path)
    p.add_argument('--attempted-urls', type=Path, help='JSON list of previously attempted original URLs')
    p.add_argument('--blocked-domains', type=Path, help='JSON list of known blocked domains; never retry')
    args = p.parse_args()
    value = plan(json.loads(args.seed_targets.read_text()))
    if not (args.output / 'plan.json').exists():
        put(args.output / 'plan.json', value)
    elif json.loads((args.output / 'plan.json').read_text()) != value:
        raise ValueError('resume seed differs')
    searches, documents = collect(value, args.output, direct_urls=json.loads(args.direct_urls.read_text()) if args.direct_urls else {}, search_endpoint=args.search_endpoint)
    excluded = json.loads(args.attempted_urls.read_text()) if args.attempted_urls else []
    blocked = json.loads(args.blocked_domains.read_text()) if args.blocked_domains else []
    references, reference_urls = reference_plan(value, documents, completed_urls=excluded + [d['url'] for d in documents], blocked_domains=blocked)
    if references['requests']:
        _, reference_documents = collect(references, args.output / 'references', direct_urls=reference_urls)
        documents += reference_documents
    seed_documents = json.loads(args.seed_documents.read_text()) if args.seed_documents else []
    if args.engine_manifest:
        from . import prospective, forecast_discovery, early_forecast
        expected = json.loads(args.engine_manifest.read_text())
        for name, module in [('prospective.py', prospective), ('forecast_discovery.py', forecast_discovery), ('early_forecast.py', early_forecast)]:
            if digest(Path(module.__file__).read_bytes()) != expected[name]:
                raise ValueError('frozen engine mismatch: ' + name)
    result = evaluate(seed_documents + documents)
    if result['strict_ready']:
        if not args.live_store or not args.engine_manifest:
            raise ValueError('strict-ready batch pending: existing LIVE store and frozen engine manifest required')
        execute_ready(result, args.live_store, json.loads(args.engine_manifest.read_text()), args.output)
    for name, data in [('documents.json', documents), ('evaluation.json', result)]:
        if not (args.output / name).exists():
            put(args.output / name, data)
    print(json.dumps({'targets': len(value['targets']), 'requests': len(searches), 'documents': len(documents), 'provenance_pass': sum(d.get('provenance') == 'PASS' for d in documents), 'strict_ready': result['strict_ready']}))


if __name__ == '__main__':
    main()
