"""Bounded counterpart discovery over existing sources, not an adoption engine.

All industries share this queue. Literal hits and role words only nominate
paragraphs for review; they never prove equivalent scope, independence or supply.
"""
import json
import re
import time
from urllib.parse import urlsplit, urljoin

from bct.objective_lock import stamp_export, require_objective
from bct.target_acquisition import plan as acquisition_plan, leads
from .store import sha
from .public_input import PUBLISHERS, valid_article_url

VERSION = 'bct-q2-counterpart-1'
KIND = 'QUANTITATIVE_COUNTERPART_REVIEW'
FIELDS = set('id version seed_id product literal_search_terms seed_role requested_role missing_fields search_request selected_sources pending_sources rejected_sources official_link_queue state s_stage research_only'.split())
REQUIRED = ('specification', 'region', 'customer', 'quantity', 'need_window',
            'supplier', 'qualified_supplier_pool', 'qualified_capacity', 'delivery')


def safe_url(url):
    if not valid_article_url(url):
        raise ValueError('COUNTERPART_PUBLIC_ARTICLE_URL')


def search_terms(product):
    """Source-literal model identifiers nominate leads; never alias equivalence."""
    models = [m.group() for m in re.finditer(r'\b[A-Za-z][A-Za-z0-9/-]{2,}\b', product)
              if re.search(r'\d', m.group()) or re.fullmatch(r'[A-Z]+(?:[/-][A-Z]+)+', m.group())]
    return list(dict.fromkeys([product] + models))


def seeds(products, events):
    """Keep reviewed physical facts and original event IDs, with no AI rerun."""
    result = []
    for r in products:
        role = 'DEMAND' if r['kind'].startswith('ACTUAL_ORDER') else 'SUPPLY_PLAN'
        result.append({'id': r['id'], 'product': r['product'], 'role': role,
                       'source': r['source'], 'fields': {k: r.get(k) for k in REQUIRED},
                       # Expected shipment is supplier intent, NOT customer need.
                       'planned_delivery': r.get('planned_delivery')})
    for r in events:
        role = {'DEMAND_INCREASE': 'DEMAND', 'SUPPLY_DECREASE': 'CONSTRAINT',
                'SUPPLY_DELAY': 'CONSTRAINT'}.get(r.get('role'))
        if not role:
            continue
        target = r['target']; fields = r.get('fields', {})
        value = lambda name: (target.get(name) or {}).get('surface')
        result.append({'id': r['id'], 'product': r['product'], 'role': role,
                       'source': r.get('context', r.get('reference')), 'fields': {
                           'specification': value('specification'), 'region': value('region'),
                           'customer': value('customer_group'), 'supplier': (fields.get('reported_supplier') or {}).get('surface'),
                           'quantity': None,  # Legacy raw amounts have not passed physical quantity review here.
                           'need_window': (fields.get('need_time') or {}).get('surface'),
                           'qualified_capacity': None, 'delivery': None}})
    return result


def paragraphs(body, product):
    """Exact product spelling; retain whole paragraph and adjacent conditions."""
    hits = list(re.finditer(r'(?<!\w)' + re.escape(product) + r'(?!\w)', body, re.I))
    lines = list(re.finditer(r'[^\n]+', body)); seen = set()
    for hit in hits:
        i = next((i for i, line in enumerate(lines) if line.start() <= hit.start() < line.end()), None)
        if i is None:
            continue
        a, b = lines[max(0, i - 1)].start(), lines[min(len(lines) - 1, i + 1)].end()
        if (a, b) in seen:
            continue
        seen.add((a, b))
        yield a, b, hit.start(), hit.end()


def request_for(seed):
    """Every reviewed signal gets an opposite-side task, including new products."""
    if seed['role'] not in {'DEMAND', 'CONSTRAINT', 'SUPPLY_PLAN'}:
        raise ValueError('COUNTERPART_SEED_ROLE')
    wanted = 'SUPPLY' if seed['role'] == 'DEMAND' else 'DEMAND'
    request = acquisition_plan([{'target': seed['product'], 'demand_signal': seed['role'] == 'DEMAND',
                                'supply_signal': seed['role'] != 'DEMAND', 'document_ids': [seed['source'].get('document_id')]}])
    request = next(r for r in request['requests'] if r['role'] == wanted)
    return {**request, 'request_id': sha([VERSION, seed['id'], wanted]),
            'missing_fields': [k for k in REQUIRED if seed['fields'].get(k) in (None, '', 'UNKNOWN')]}


def discover(seed, documents, *, as_of, limit=3, blocked_urls=()):
    if not 1 <= limit <= 3:
        raise ValueError('COUNTERPART_SOURCE_CAP_3')
    request = request_for(seed); wanted = request['role']; missing = request['missing_fields']
    matches, rejected, seen = [], [], set()
    for doc in sorted(documents, key=lambda d: d['document_id']):
        if doc['body_sha256'] in seen:
            continue
        seen.add(doc['body_sha256'])
        if doc['body_sha256'] == seed['source'].get('body_sha256'):
            continue
        positions = sorted(set(p for term in search_terms(seed['product']) for p in paragraphs(doc['body'], term)))
        if not positions:
            continue
        reason = None
        if sha(doc['body'].encode()) != doc['body_sha256']:
            reason = 'SOURCE_HASH_MISMATCH'
        elif doc.get('provenance') != 'PASS' or doc.get('body_status') != 'FULL':
            reason = 'SOURCE_OR_FULLNESS_UNVERIFIED'
        elif not (doc.get('primary_source_verified') is True or urlsplit(doc['origin_url']).hostname in PUBLISHERS):
            reason = 'PRIMARY_SOURCE_UNVERIFIED'
        elif not doc.get('published_at') or doc['published_at'] == 'UNKNOWN':
            reason = 'PUBLICATION_UNKNOWN'
        elif doc['published_at'][:10] > as_of:
            reason = 'FUTURE_PUBLICATION'
        if reason:
            rejected.append({'document_id': doc['document_id'], 'reason': reason})
            continue
        contexts = []
        for a, b, c, d in positions:
            # Reuse the existing proposal extractor on identical source scope.
            proposals = [p for term in search_terms(seed['product']) for p in leads(doc['body'][a:b], term, [wanted])]
            if not proposals:
                continue
            contexts.append({'start': a, 'end': b, 'context_sha256': sha(doc['body'][a:b].encode()),
                             'product_start': c, 'product_end': d,
                             'status': 'ROLE_LITERAL_LEAD_NOT_ADOPTED',
                             'conditions': 'NEGATION_PLAN_AND_RELIEF_REQUIRE_REVIEW'})
        if not contexts:
            continue
        matches.append({'document_id': doc['document_id'], 'url': doc['origin_url'],
                        'body_sha256': doc['body_sha256'], 'raw_sha256': doc.get('raw_sha256'),
                        'published_at': doc['published_at'], 'acquired_at': doc.get('acquired_at'),
                        'origin_publisher': doc.get('origin_publisher'), 'contexts': contexts,
                        'scope_equivalence': 'UNKNOWN', 'independence': 'UNKNOWN',
                        'adoption': 'REVIEW_PENDING'})
    # Same publisher is useful for supply discovery, never an independent pair.
    matches.sort(key=lambda x: x['url'])
    matches.sort(key=lambda x: x['published_at'], reverse=True)
    row = {'version': VERSION, 'seed_id': seed['id'], 'product': seed['product'], 'literal_search_terms': search_terms(seed['product']),
           'seed_role': seed['role'], 'requested_role': wanted, 'missing_fields': missing,
           'search_request': request, 'selected_sources': matches[:limit],
           'pending_sources': len(matches[limit:]), 'rejected_sources': rejected,
           'official_link_queue': [], 'state': 'REVIEW_PENDING' if matches else 'OFFICIAL_COUNTERPART_NOT_FOUND_IN_STORED_SCOPE',
           's_stage': 'UNKNOWN', 'research_only': True}
    row['id'] = sha([VERSION, row])
    return row


def linked_sources(row, doc, raw, *, blocked_urls=(), attempted_urls=()):
    """Nominate only same-official-host cited links, no arbitrary URL invention.

    Reuse Metadata parsing. Link labels/URLs are discovery, never source proof.
    The round's three-document cap includes existing selected sources.
    """
    from bct.target_acquisition import Metadata
    if doc.get('provenance') != 'PASS' or sha(raw) != doc['raw_sha256']:
        return []
    parser = Metadata(); parser.feed(raw.decode('utf-8', errors='replace'))
    host = urlsplit(doc['origin_url']).hostname
    used = set(blocked_urls) | set(attempted_urls) | {x['url'] for x in row['selected_sources']}
    out = []
    for href, label in parser.links:
        url = urljoin(doc['origin_url'], href)
        try:
            safe_url(url)
        except ValueError:
            continue
        if url in used or urlsplit(url).hostname != host:
            continue
        if not any(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', label + ' ' + url, re.I) for term in row['literal_search_terms']):
            continue
        # Product pages often have no capacity word in the anchor; they are
        # valid discovery destinations, still NOT opposite-role evidence.
        used.add(url); out.append({'url': url, 'parent_document_id': doc['document_id'],
                                 'status': 'UNFETCHED_OFFICIAL_LINK_NOT_EVIDENCE'})
        if len(out) >= 3 - len(row['selected_sources']):
            break
    return out if len(row['selected_sources']) < 3 else []


def packet(seed_records, documents, *, as_of):
    records = [discover(s, documents, as_of=as_of) for s in seed_records]
    return stamp_export({'plan_id': 'BCT-V4-Q-1.0', 'version': VERSION, 'as_of': as_of,
                         'records': records, 'scope': 'Stored-source counterpart discovery; not independent evaluation or shortage prediction',
                         'new_AI_calls': 0, 'new_S2': 0, 'new_S3': 0})


def save(ledger, value):
    require_objective(value); added = 0
    with ledger.db:
        for row in value['records']:
            validate(row)
            if ledger.db.execute("SELECT 1 FROM events WHERE kind=? AND json_extract(payload,'$.id')=?", (KIND, row['id'])).fetchone():
                continue
            ledger.event(KIND, row); added += 1
    return {'added': added, 'records': len(value['records']), 'new_S2': 0, 'new_S3': 0}


def acquire(value, ledger, client, *, max_calls=32, seconds=90):
    """One-hop, journaled official-link acquisition using the existing client.

    Public site failure is isolated, never retried under a new run ID. Raw
    originals are local only; retained private queue records exclude prose.
    """
    require_objective(value)
    if not 1 <= max_calls <= 32 or not 0 < seconds <= 90:
        raise ValueError('COUNTERPART_BATCH_BUDGET')
    started = time.monotonic(); calls = 0
    attempts = {json.loads(p)['url'] for p, in ledger.db.execute(
        "SELECT payload FROM events WHERE kind='Q2_COUNTERPART_FETCH_ATTEMPT'")}
    blocked_hosts = {json.loads(p)['host'] for p, in ledger.db.execute(
        "SELECT payload FROM events WHERE kind='Q2_COUNTERPART_FETCH_FAILURE' AND json_extract(payload,'$.http_status') IN (401,403,429,451)")}
    results = []
    for row in value['records']:
        validate(row)
        for item in row['official_link_queue']:
            url = item['url']; host = urlsplit(url).hostname
            if url in attempts or host in blocked_hosts:
                continue
            if calls >= max_calls or time.monotonic() - started >= seconds:
                return results  # Unattempted links remain pending, not failed/read.
            safe_url(url); attempts.add(url)
            with ledger.db:
                ledger.event('Q2_COUNTERPART_FETCH_ATTEMPT', {'url': url, 'seed_id': row['seed_id']})
            try:
                calls += 1
                from bct.target_acquisition import verify, now
                raw, final, status, content_type = client.fetch(url)
                # Keep raw before parsing so a local parser failure can be
                # repaired offline rather than fetching the URL again.
                with ledger.db:
                    ledger.db.execute('INSERT OR IGNORE INTO blobs VALUES(?,?)', (sha(raw), raw))
                    ledger.event('Q2_COUNTERPART_RAW_CAPTURED', {'url': url, 'raw_sha256': sha(raw), 'status': status})
                doc = verify(raw, url, final, now(), status, content_type)
                bind_publication(doc, raw)
                doc['document_id'] = 'q2-source-' + sha([url, sha(raw)])
                ledger.capture(doc, raw, {'purpose': VERSION, 'AI': 'DISABLED'})
                results.append({'url': url, 'status': 'CAPTURED', 'document_id': doc['document_id'],
                                'body_sha256': doc['body_sha256'], 'provenance': doc['provenance'],
                                'published_at': doc.get('published_at'), 'body_status': doc['body_status'],
                                'adoption': 'NOT_ADOPTED_REVIEW_REQUIRED'})
            except Exception as exc:
                code = getattr(exc, 'code', None)
                result = {'url': url, 'host': host, 'status': 'FAILED_ISOLATED',
                          'http_status': code, 'error_type': type(exc).__name__, 'retry': False}
                with ledger.db:
                    ledger.event('Q2_COUNTERPART_FETCH_FAILURE', result)
                if code in (401, 403, 429, 451):
                    blocked_hosts.add(host)
                results.append(result)
    return results


def bind_publication(doc, raw):
    """Product/sidebar dates cannot be used as event publication evidence."""
    from bct.target_acquisition import Metadata, nodes, norm
    m = Metadata(); m.feed(raw.decode('utf-8', errors='replace'))
    articles = [n for n in nodes(m.ld) if any(t in str(n.get('@type')) for t in ('Article', 'Posting'))]
    bound = []
    for article in articles:
        identity = article.get('mainEntityOfPage') or article.get('url') or article.get('@id')
        if isinstance(identity, dict):
            identity = identity.get('@id')
        if isinstance(identity, str) and norm(identity.split('#')[0]) == norm(doc['origin_url']):
            bound.append(article.get('datePublished'))
    if len(bound) != 1 or not isinstance(bound[0], str) or bound[0][:10] != str(doc.get('published_at'))[:10]:
        doc['unbound_metadata_publication'] = doc.get('published_at')
        doc.update(published_at=None, provenance='BLOCKED', provenance_verified=False)
        doc.setdefault('provenance_blockers', []).append('ARTICLE_PUBLICATION_NOT_BOUND_TO_THIS_PAGE')
    return doc


def validate(row):
    if set(row) != FIELDS or row['s_stage'] != 'UNKNOWN' or row['research_only'] is not True:
        raise ValueError('COUNTERPART_PROMOTION_OR_UNKNOWN_FIELD')
    if len(row['selected_sources']) + len(row['official_link_queue']) > 3:
        raise ValueError('COUNTERPART_SOURCE_CAP_3')
    if row['requested_role'] not in {'DEMAND', 'SUPPLY'}:
        raise ValueError('COUNTERPART_ROLE')
    if row['literal_search_terms'] != search_terms(row['product']):
        raise ValueError('COUNTERPART_UNPROVEN_ALIAS')
    if row['id'] != sha([VERSION, {k: v for k, v in row.items() if k != 'id'}]):
        raise ValueError('COUNTERPART_RECORD_HASH')
    if set(row['search_request']) != set('request_id target role kind missing_fields query seed_document_ids'.split()):
        raise ValueError('COUNTERPART_REQUEST_FIELDS')
    for link in row['official_link_queue']:
        if set(link) != {'url', 'parent_document_id', 'status'} or link['status'] not in {
                'UNFETCHED_OFFICIAL_LINK_NOT_EVIDENCE', 'CAPTURED_SOURCE_REVIEW_HELD', 'FAILED_LOCAL_EXTRACTION_NO_RETRY'}:
            raise ValueError('COUNTERPART_LINK_FIELDS')
        safe_url(link['url'])
    for source in row['selected_sources']:
        safe_url(source['url'])
        if source['adoption'] != 'REVIEW_PENDING' or source['scope_equivalence'] != 'UNKNOWN' or source['independence'] != 'UNKNOWN':
            raise ValueError('COUNTERPART_UNVERIFIED_LINK')
        if set(source) != set('document_id url body_sha256 raw_sha256 published_at acquired_at origin_publisher contexts scope_equivalence independence adoption'.split()):
            raise ValueError('COUNTERPART_SOURCE_FIELDS')
        for context in source['contexts']:
            if set(context) != set('start end context_sha256 product_start product_end status conditions'.split()):
                raise ValueError('COUNTERPART_CONTEXT_FIELDS')
            if not 0 <= context['start'] <= context['product_start'] < context['product_end'] <= context['end']:
                raise ValueError('COUNTERPART_POSITION')
    # No source prose in retained state, only own queue state and positions.
    if re.search(r'"(?:body|quote|text|excerpt|response)"\s*:', json.dumps(row)):
        raise ValueError('COUNTERPART_SOURCE_TEXT_FORBIDDEN')
