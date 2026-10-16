#!/usr/bin/env python3
"""One research batch over already captured official versions; no target input.

The collector's normal page cursors remain authoritative. Native captures are
ephemeral/local, and only typed facts and own processing state enter Releases.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import re
from pathlib import Path
import time
from urllib.parse import urlsplit, urlunsplit, urljoin

from bct.objective_lock import stamp_export
from bct.target_acquisition import fetch, Metadata
from bct import future_body
from bct.v4 import official_discovery as engine, official_sources as fmt
from bct.v4.quantitative_counterpart import RelationRound, relation_url, relation_links
from bct.v4.store import Ledger, sha, now, file_sha

BIDIRECTIONAL = 'bct-official-bidirectional-1'


def relation_index_links(raw, url):
    """Publisher navigation nominates indices; it is never supply evidence.

    Unlike article citations, an IR/news navigation link may live in a header.
    Cross-domain leads need separate ownership proof; issuer subdomains are
    only discovery leads and never evidence of a qualified manufacturer.
    """
    parser = Metadata(); parser.feed(raw.decode('utf-8', errors='strict'))
    host = urlsplit(url).hostname.removeprefix('www.')
    out = {}; html = raw.decode('utf-8')
    for href, label in parser.links:
        dest = urljoin(url, href).split('#')[0]
        h = urlsplit(dest).hostname or ''
        if h.removeprefix('www.') != host and not h.endswith('.'+host): continue
        try: relation_url(dest)
        except ValueError: continue
        value = href+' '+' '.join(label.split())
        if not re.search(r'capacit|manufactur|facilit|production|annual.report|investor|financial|press.release|news', value, re.I): continue
        if re.search(r'contact|calendar|funding|the.share|share.price', value, re.I): continue
        # Raw href is a precise discovery position, not a semantic assertion.
        locs = [m.start() for m in re.finditer(re.escape(href), html)]
        if not locs: continue
        rank = 0 if re.search(r'capacit|manufactur|facilit|production', value, re.I) else 1 if re.search(r'press.release|annual.report|reports.presentation', value, re.I) else 2
        out.setdefault(dest, {'url': dest, 'via_url': url, 'via_hash': sha(raw),
                             'href_positions': [{'start': i, 'end': i+len(href)} for i in locs],
                             'rank': rank, 'relation': 'PUBLISHER_INDEX_LEAD_NOT_TARGET_EQUIVALENCE'})
    return sorted(out.values(), key=lambda x: (x['rank'], x['url']))


def structured_demand_queries(changes, root, *, network=False, as_of=None, max_calls=32):
    """Supply -> customer-contract discovery using the existing official API.

    One keyword/region query is shared by all relevant facilities, not one
    request per plant. Awards/amounts are leads, not electricity quantities,
    growth, future customer need dates or independent qualified supply pairs.
    """
    from bct.collectors.usaspending.collector import request_body,request_bytes,parse_response,USAspendingTransport,ENDPOINT
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    from datetime import date
    end = date.fromisoformat(as_of or now()[:10])
    start = end.replace(year=end.year-3, day=min(end.day,28))
    budget = RelationRound(root/'request-rounds.json'); out = []
    # Only an actually reported status transition triggers a reverse query.
    scopes = sorted({(e['product'],e['region']) for e in changes if e['role'] != 'CONTEXT'})
    held = any(json.loads(p.read_text()).get('http_status') in {401,403,429} for p in root.glob('query-*.json'))
    for product, region in scopes:
        if not re.fullmatch('[A-Z]{2}',region): continue
        body=request_body(product,'keyword',20)
        body['filters']['place_of_performance_locations']=[{'country':'USA','state':region}]
        body['filters']['time_period']=[{'start_date':start.isoformat(),'end_date':end.isoformat()}]
        ident=sha(request_bytes(body));p=root/('query-'+ident+'.json')
        if p.exists():out.append(json.loads(p.read_text()));continue
        if not network or held or len(budget.current['charges']) >= max_calls or not budget.allow(ident,'api.usaspending.gov'):
            out.append({'query_id':ident,'product':product,'region':region,'status':'PENDING_OFFICIAL_QUERY','Q3_eligible':False});continue
        budget.charge(ident,ENDPOINT)
        result={'query_id':ident,'url':ENDPOINT,'product':product,'region':region,'request':body,
                'status':'INTERRUPTED_NO_RETRY','Q3_eligible':False,'physical_quantity':None,'customer_need_date':None}
        p.write_text(json.dumps(result))
        try:
            raw=USAspendingTransport(timeout_seconds=20).post(body)
            p.with_suffix('.raw').write_bytes(raw)
            awards=parse_response(raw,20);native=json.loads(raw)
            result.update(status='OFFICIAL_AWARD_SEARCH_PARSED',http_status=200,source_hash=sha(raw),
                          acquired_at=now(),records=len(awards),award_ids=[a.external_id for a in awards],
                          has_next=native.get('page_metadata',{}).get('hasNext'),
                          interpretation='AWARD_IDENTITY_ONLY_NOT_PRODUCT_QUANTITY_OR_FUTURE_CUSTOMER_NEED')
        except Exception as exc:
            result.update(status='OFFICIAL_QUERY_FAILED_NO_RETRY',http_status=getattr(exc,'code',None),reason=type(exc).__name__)
            held=result['http_status'] in {401,403,429}
        p.write_text(json.dumps(result));out.append(result)
    return {'queries':out,'budget':budget.state,'requests_this_round':len(budget.current['charges']),
            'successful_queries':sum(q['status']=='OFFICIAL_AWARD_SEARCH_PARSED'for q in out),
            'award_identity_leads':sum(q.get('records',0)for q in out),'independent_pairs':0}


def award_detail_leads(queries, root, *, network=False):
    """Resolve one returned award identifier per query through the official API.

    The bounded first-page search is not exhausted; keywords and award amounts
    cannot establish a physical purchase. No full descriptions are archived.
    """
    from urllib.parse import quote
    root=Path(root);budget=RelationRound(root/'request-rounds.json');out=[]
    for query in queries:
        if not query.get('award_ids'): continue
        award=query['award_ids'][0];url='https://api.usaspending.gov/api/v2/awards/'+quote(award,safe='_-')+'/'
        p=root/('detail-'+sha(url.encode())+'.json')
        if p.exists():out.append(json.loads(p.read_text()));continue
        if not network or not budget.allow(query['query_id'],'api.usaspending.gov'):continue
        budget.charge(query['query_id'],url)
        result={'url':url,'query_id':query['query_id'],'award_id':award,'status':'INTERRUPTED_NO_RETRY','Q3_eligible':False}
        p.write_text(json.dumps(result))
        try:
            raw,final,status,ct=fetch(url);p.with_suffix('.raw').write_bytes(raw)
            if final!=url or status!=200:raise ValueError('AWARD_DETAIL_IDENTITY')
            data=json.loads(raw)
            if data.get('generated_unique_award_id')!=award:raise ValueError('AWARD_DETAIL_ID_MISMATCH')
            desc=data.get('description')or''
            match=bool(re.search(r'\b(?:electric power|purchase of electricity|supply of electricity|electricity supply)\b',desc,re.I))
            result.update(status='OFFICIAL_CONTRACT_DETAIL_PARSED',http_status=200,source_hash=sha(raw),acquired_at=now(),
                          product_scope='LITERAL_POWER_CONTRACT_REVIEW_PENDING'if match else'KEYWORD_AWARD_NOT_VERIFIED_PRODUCT_DEMAND',
                          source_positions={'identity':'/generated_unique_award_id','scope_description_sha256':sha(desc.encode())},
                          category=data.get('category'),physical_quantity=None,customer_need_date=None,
                          interpretation='CONTRACT_PERIOD_IS_NOT_CUSTOMER_DELIVERY_REQUIREMENT_NO_PHYSICAL_ALLOCATION')
        except Exception as exc:
            result.update(status='OFFICIAL_CONTRACT_DETAIL_FAILED_NO_RETRY',http_status=getattr(exc,'code',None),reason=type(exc).__name__)
        p.write_text(json.dumps(result));out.append(result)
    return out


def bidirectional(ledger, root, *, network=False, seed_links=(), documents=()):
    """Resume the restored common queue, with one durable bounded I/O round.

    The source collector is not run here. Prior successful or failed URLs are
    never fetched again merely because ephemeral originals are unavailable.
    New index/article links and receipts survive in the existing research DB.
    """
    from bct.v4 import quantitative_counterpart as q
    from bct.target_acquisition import verify
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    previous = ledger.db.execute("SELECT payload FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.policy.format')=? ORDER BY seq DESC LIMIT 1", (BIDIRECTIONAL,)).fetchone()
    prior = json.loads(previous[0])['policy'] if previous else None
    roundfile = root/'request-rounds.json'
    if prior and not roundfile.exists(): roundfile.write_text(json.dumps(prior['budget']))
    budget = RelationRound(roundfile)
    tasks = q.latest_relations(ledger)['tasks']
    tasks = [t for t in tasks if 'automatic_stored_search' in t['scope']]
    receipts = dict(prior['receipts']) if prior else {}
    # Interrupted before a batch manifest? The per-URL write-ahead receipt is
    # still authoritative, so a new process does not repeat that request.
    for p in root.glob('*.json'):
        if p.name in {'request-rounds.json', 'bidirectional-report.json'}: continue
        m = json.loads(p.read_text())
        if 'url' in m and 'status' in m: receipts.setdefault(m['url'], m)
    for t in tasks:
        for r in t['checked_sources']:
            receipts.setdefault(r['url'], {**r, 'native_available': False, 'source': 'PRIOR_COMMON_QUEUE_RECEIPT'})
    # Reuse the official automatic source report to associate native supplier
    # identities. No handpicked company/product list or manual gold is input.
    old_packets = [json.loads(p)['policy'] for p, in ledger.db.execute("SELECT payload FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.policy.format')=?", (engine.VERSION,))]
    seed_events = {e['id']: e for p in old_packets for e in p.get('events', [])}
    pending = list(prior['pending']) if prior else []
    seen_links = {(p['seed_id'], p['url']) for p in pending}
    for link in seed_links:
        matching = [t for t in tasks if t['seed_id'] == link['seed_id']]
        # Offline discovered href proof must bind to a previously captured
        # page hash present in this restored source-driven task history.
        if not matching or not any(r.get('source_hash') == link['via_hash'] and r['url'] == link['via_url'] for t in matching for r in t['checked_sources']):
            raise ValueError('RELATION_SEED_NOT_BOUND_TO_RESTORED_QUEUE')
        if (link['seed_id'], link['url']) not in seen_links:
            pending.append(link); seen_links.add((link['seed_id'], link['url']))
    results = list(prior['context_results']) if prior else []
    calls = 0; readbacks = 0; started = time.monotonic(); remaining = []; attempted = []; held_hosts = {}
    for r in receipts.values():
        if r.get('status') in {401, 403, 429}: held_hosts[urlsplit(r['url']).hostname] = r['status']
    # Round-robin tasks: new links are appended behind already pending work.
    pending.sort(key=lambda p: (p.get('depth', 0), p.get('rank', 2), p['seed_id'], p['url']))
    done = set()
    while pending:
        link = pending.pop(0); url = link['url']; sid = link['seed_id']; relation_url(url)
        if (sid, url) in done: continue
        done.add((sid, url)); host = urlsplit(url).hostname
        task = next((t for t in tasks if t['seed_id'] == sid), None)
        if not task: continue
        if url in receipts:
            # A prior native is not silently fetched to reconstruct links.
            readbacks += 1; continue
        if host in held_hosts:
            receipts[url] = {'url': url, 'status': 'HOST_QUARANTINED', 'http_status': held_hosts[host], 'retry': False}; continue
        if not network or time.monotonic()-started >= 90 or not budget.allow(task['event_key'], host):
            remaining.append(link); continue
        if q.relation_url(url) != 'PUBLIC_DOCUMENT':
            remaining.append({**link, 'hold': 'SEC_TRANSPORT_PRIOR_QUARANTINE'}); continue
        budget.charge(task['event_key'], url); calls += 1
        rp = root/(sha(url.encode())+'.json')
        receipt = {'url': url, 'status': 'INTERRUPTED_NO_RETRY', 'acquired_at': now(), 'seed_id': sid}
        rp.write_text(json.dumps(receipt))
        try:
            raw, final, status, ct = fetch(url); relation_url(final)
            # Keep native before parsing: parser failures can be repaired
            # offline, without repeating a successful HTTP request.
            rp.with_suffix('.raw').write_bytes(raw)
            receipt.update(source_hash=sha(raw), final_url=final, content_type=ct)
            h = host.removeprefix('www.'); fh = urlsplit(final).hostname.removeprefix('www.')
            if fh != h and not fh.endswith('.'+h) and not h.endswith('.'+fh): raise ValueError('UNVERIFIED_ISSUER_REDIRECT')
            if raw.lstrip().startswith(b'%PDF'):
                receipt.update(status='PDF_EXTRACTION_PENDING', source_hash=sha(raw))
            else:
                d = verify(raw, url, final, receipt['acquired_at'], status, ct)
                q.bind_publication(d, raw)
                meta = {'source_id': 'ISSUER:'+fh, 'url': final, 'sha256': sha(raw),
                        'acquired_at': receipt['acquired_at'], 'published_at': d.get('published_at') or 'UNKNOWN'}
                context = engine.read_context(raw, meta)
                engine.save_context(ledger, context, raw=raw, meta=meta)
                results.append(context)
                receipt.update(status=status, source_hash=sha(raw), final_url=final,
                               read_characters=context['source']['read_characters'], body_status=context['source']['body_status'],
                               published_at=meta['published_at'], source_events=len(context['events']))
                newlinks = relation_index_links(raw, final)
                # Reuse existing facet-specific article citations too.
                doc = {**d, 'document_id': sha([final, sha(raw)])}
                for facet in [t for t in tasks if t['seed_id'] == sid]:
                    for p in relation_links(facet, doc, raw):
                        if p['status'] == 'UNFETCHED_RELATION_LEAD' and (urlsplit(p['url']).hostname or '').removeprefix('www.') == fh:
                            newlinks.append({'url': p['url'], 'via_url': final, 'via_hash': sha(raw), 'rank': 0})
                for p in newlinks:
                    key = (sid, p['url'])
                    if p['url'] not in receipts and key not in done and key not in seen_links:
                        pending.append({**p, 'seed_id': sid, 'depth': link.get('depth', 0)+1}); seen_links.add(key)
                rp.with_suffix('.raw').write_bytes(raw)  # ephemeral only, not archive
        except Exception as exc:
            receipt.update(status=getattr(exc, 'code', type(exc).__name__), reason=type(exc).__name__, retry=False)
            if receipt['status'] in {401,403,429}: held_hosts[host] = receipt['status']
        rp.write_text(json.dumps(receipt)); receipts[url] = receipt; attempted.append(receipt)
    # Retain every source-driven task, including sources with no locator. A
    # failed source never aborts another issuer or removes an old task.
    for t in tasks:
        applicable = [r for r in receipts.values() if r.get('seed_id') == t['seed_id']]
        by_url = {r['url']: r for r in t['checked_sources']}
        by_url.update({r['url']: r for r in applicable})
        t['checked_sources'] = list(by_url.values())
        existing = {u['url'] for u in t['urls']}
        t['urls'] += [{'url': p['url'], 'via_document_id': t['source_identity']['document_id'],
                       'status': 'UNFETCHED_RELATION_LEAD', 'relation': 'UNKNOWN_REVIEW_REQUIRED'}
                      for p in remaining if p['seed_id'] == t['seed_id'] and p['url'] not in existing and not existing.add(p['url'])]
        t['search_state'] = 'OFFICIAL_RELATION_EXECUTED_SCOPE_UNVERIFIED' if applicable else t['search_state']
        t['id'] = sha(['q2-relation-state-1', {k:v for k,v in t.items() if k != 'id'}])
    new_seeds = engine.context_seeds(results)
    structured = engine.structured_supply_changes(ledger)
    reverse = (prior or {}).get('reverse_queries')
    if reverse is None:
        reverse = structured_demand_queries(structured['changes'],root/'reverse-queries',network=network,
                                            max_calls=max(0,32-len(budget.current['charges'])))
    for e in structured['changes']:
        if e['role'] == 'CONTEXT': continue
        new_seeds.append({'id': e['id'], 'event_key': e['id'], 'product': e['product'],
                          'role': 'CONSTRAINT' if e['role']=='CONSTRAINT' else 'SUPPLY_PLAN',
                          'source': {'document_id': e['source_ids'][1], 'body_sha256': e['source_hashes'][1],
                                     'origin_url': e['source_urls'][1], 'published_at': e['published_at'][1]},
                          'fields': {'specification': e['technology'], 'region': e['region'], 'customer': None,
                                     'supplier': None, 'quantity': None, 'need_window': None,
                                     'qualified_capacity': None, 'delivery': None}})
    new_tasks = q.relation_tasks(new_seeds)
    for t in new_tasks:
        pointers = q.local_relation_pointers(t, list(documents), as_of=now()[:10], limit=3)
        t['scope']['automatic_stored_search'] = pointers
        t['scope']['counterevidence_not_shortage'] = t['known_side'] == 'SUPPLY_PLAN'
        t['id'] = sha(['q2-relation-state-1', {k:v for k,v in t.items() if k != 'id'}])
        # Every new supply constraint searches for DEMAND with the existing
        # source reader. Relief is retained as counterevidence, not a shortage.
    stored = [q.discover(s, list(documents), as_of=now()[:10]) for s in new_seeds]
    q.save_relations(ledger, stamp_export({'tasks': tasks+new_tasks}))
    # Existing strict engine sees its own source-verified signals only. A
    # reported output change cannot invent the absent qualified supply pool.
    old_facts = [json.loads(p) for p, in ledger.db.execute('SELECT payload FROM events WHERE kind=?', (fmt.KIND,))]
    native_opposites = []
    for seed in new_seeds:
        matches = [r['id'] for r in old_facts if r['record_kind'] in {'PROCUREMENT_CONTRACT', 'PROCUREMENT_AUTOMATIC_OBJECT'}
                   and re.search(r'(?<!\w)'+re.escape(seed['product'])+r'(?!\w)',
                                 str(r['claims'].get('product_label', {}).get('value', '')), re.I)]
        native_opposites.append({'seed_id': seed['id'], 'requested_role': 'SUPPLY' if seed['role']=='DEMAND' else 'DEMAND',
                                 'scanned_official_rows': len(old_facts), 'literal_matches': matches,
                                 'state': 'STRUCTURED_LITERAL_LEADS_SCOPE_AND_INDEPENDENCE_UNVERIFIED' if matches else 'NO_MATCH_IN_STORED_TYPED_SCOPE_NOT_GLOBAL_ABSENCE'})
    comparison = engine.q3_input(list(seed_events.values()), old_facts, as_of=now(), documents=())
    comparison['context_and_facility_inputs_held'] = len(new_seeds)
    comparison['context_hold_reason'] = 'CUSTOMER_NEED_QUALIFIED_POOL_SPECIFICATION_PERIOD_AND_INDEPENDENCE_NOT_PROVEN'
    e = [e for r in results for e in r['events']]
    report = stamp_export({'format': BIDIRECTIONAL, 'plan_id': 'BCT-V4-Q-1.0', 'receipts': receipts,
                          'pending': remaining, 'budget': budget.state, 'context_results': results,
                          'stored_counterparts': stored, 'Q3': comparison,
                          'structured_supply': structured,
                          'reverse_queries': reverse,
                          'structured_counterparts': native_opposites,
                          'stored_documents_searched': len(documents),
                          'summary': {'source_queue_tasks': len(tasks), 'new_context_tasks': len(new_tasks),
                                      'new_HTTP_this_batch': calls, 'unique_native_documents_read': len(results),
                                      'actual_characters': sum(r['source']['read_characters'] for r in results),
                                      'actual_demand_change': sum(x['role']=='DEMAND' and x['actuality']=='REPORTED_ACTUAL' and x.get('demand_change_class')=='REPORTED_INCREMENT_PRIOR_BASELINE_UNKNOWN' for x in e),
                                      'reported_supply_constraints': sum(x['role']=='CONSTRAINT' and x['actuality']=='REPORTED_ACTUAL' and x['product'] is not None for x in e),
                                      'reported_relief': sum(x['role']=='RELIEF' and x['actuality']=='REPORTED_ACTUAL' and x['product'] is not None for x in e),
                                      'supply_plans': sum(x['role']=='SUPPLY_PLAN' and x['product'] is not None for x in e),
                                      'reported_facility_relief': sum(x['role']=='RELIEF' for x in structured['changes']),
                                      'reported_facility_constraints': sum(x['role']=='CONSTRAINT' for x in structured['changes']),
                                      'facility_record_revisions_not_physical_delay': sum(x['role']=='CONTEXT' for x in structured['changes']),
                                      'context_proposals': len(e), 'independent_pairs': 0, 'Q3_eligible': 0, 'future_candidates': 0},
                          'AI_calls': 0, 'CPU_windows': 0, 'paid_cost': 0, 'operating_changes': False})
    reason = 'OFFICIAL_BIDIRECTIONAL_BATCH:'+sha(report)
    with ledger.db:
        if not ledger.db.execute("SELECT 1 FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.reason')=?", (reason,)).fetchone():
            ledger.event('QUANTITATIVE_VALIDATION', {'reason': reason, 'originals_modified': False, 'policy': report})
    (root/'bidirectional-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    return report


def import_bidirectional(ledger, packet):
    """Transport capture-verified own research state, never native originals.

    Acquisition/semantic diagnostics were executed on the developer runner.
    This remote append checks integrity and stale queue parents; it does NOT
    pretend to revalidate missing originals or grant qualified supply status.
    """
    from bct.objective_lock import require_objective
    from bct.v4 import quantitative_counterpart as q
    require_objective(packet)
    reason = 'OFFICIAL_BIDIRECTIONAL_BATCH:'+sha(packet)
    if ledger.db.execute("SELECT 1 FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.reason')=?", (reason,)).fetchone():
        return {'added': 0, 'captured_documents': len(packet['context_results']), 'native_recheck_here': False}
    if packet['format'] != BIDIRECTIONAL or packet['plan_id'] != 'BCT-V4-Q-1.0': raise ValueError('BIDIRECTIONAL_FORMAT')
    if any(packet['Q3'][k] for k in ['eligible_pairs','strict_engine_candidates','S2','S3']): raise ValueError('BIDIRECTIONAL_PROMOTION')
    if packet['AI_calls'] or packet['CPU_windows'] or packet['paid_cost'] or packet['operating_changes']: raise ValueError('BIDIRECTIONAL_SCOPE')
    if re.search(r'"(?:body|quote|source_quote|excerpt|response)"\s*:',json.dumps(packet)): raise ValueError('BIDIRECTIONAL_SOURCE_BODY')
    for r in packet['receipts'].values(): relation_url(r['url'])
    for c in packet['context_results']:
        source = c['source']; relation_url(source['url'])
        receipt = next((r for r in packet['receipts'].values() if r.get('source_hash') == source['sha256'] and source['url'] in {r['url'], r.get('final_url')}),None)
        if not receipt or receipt['status'] != 200: raise ValueError('BIDIRECTIONAL_CAPTURE_RECEIPT')
        for e in c['events']:
            if e['id'] != sha({k:v for k,v in e.items() if k!='id'}): raise ValueError('BIDIRECTIONAL_EVENT_ID')
            if e['source_hash'] != source['sha256'] or e['source_url'] != source['url']: raise ValueError('BIDIRECTIONAL_EVENT_SOURCE')
            if e['s_stage'] != 'UNKNOWN' or e['qualified'] or e['coverage_complete'] or e['qualified_capacity'] is not None: raise ValueError('BIDIRECTIONAL_UNPROVEN_CAPACITY')
            p = e.get('product_position'); loc = e['raw_position']
            if p and not loc['start'] <= p['start'] < p['end'] <= loc['end']: raise ValueError('BIDIRECTIONAL_POSITION')
    for rnd in packet['budget']['rounds']:
        if len(rnd['charges']) > 32: raise ValueError('BIDIRECTIONAL_BUDGET')
        if any(v > 3 for v in Counter(x['event'] for x in rnd['charges']).values()): raise ValueError('BIDIRECTIONAL_EVENT_BUDGET')
        if any(v > 6 for v in Counter(x['host'] for x in rnd['charges']).values()): raise ValueError('BIDIRECTIONAL_HOST_BUDGET')
    current = {t['task_id']:t for t in q.latest_relations(ledger)['tasks']}
    for t, parent in packet['resume_parent_ids'].items():
        if t not in current or current[t]['id'] != parent: raise ValueError('BIDIRECTIONAL_REMOTE_CURSOR_ADVANCED')
    with ledger.db:
        exists = ledger.db.execute("SELECT 1 FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.reason')=?", (reason,)).fetchone()
        if not exists: ledger.event('QUANTITATIVE_VALIDATION', {'reason': reason, 'originals_modified': False, 'policy': packet})
    return {'added': int(not exists), 'captured_documents': len(packet['context_results']), 'native_recheck_here': False}


def supplier_discovery(result, root, caches, *, network=False):
    """Follow government-reported supplier URLs and their own product citations.

    This is NOT an open crawler or a manufacturer/qualification assertion.
    Existing URL receipts, including failures, are reused without retries.
    """
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    budget = RelationRound(root/'round.json'); known = {}
    for folder in [*map(Path, caches), root]:
        for p in folder.glob('*.json'):
            try: m = json.loads(p.read_text())
            except (ValueError, UnicodeError): continue
            if 'url' in m and 'status' in m: known[m['url']] = (p, m)
            if m.get('status') == 200 and m.get('final_url'):
                # Reuse a previously observed safe canonical redirect, rather
                # than requesting www/non-www aliases as different documents.
                try: relation_url(m['final_url'])
                except ValueError: continue
                if urlsplit(m['url']).hostname.removeprefix('www.') == urlsplit(m['final_url']).hostname.removeprefix('www.'):
                    known[m['final_url']] = (p, m)
    events = {e['id']: e for e in result['events']}; reports = []; started = time.monotonic(); supply_facts = {}; supply_events = {}
    for site in result['supplier_sites']:
        event = events[site['event_id']]
        if event['state'] not in {'SOURCE_BOUND_EVENT', 'SOURCE_BOUND_PRODUCT_FAMILY'}: continue
        u = urlsplit(site['reported_site'])
        url = urlunsplit(('https', u.netloc, u.path or '/', u.query, ''))
        try: relation_url(url)
        except ValueError:
            reports.append({'event_id': event['id'], 'state': 'SUPPLIER_URL_NOT_SAFE', 'stage': 'SOURCE'}); continue
        queue = [url]; visited = []; pending = []; leads = []
        for depth in range(3):
            if not queue: break
            dest = queue.pop(0)
            if dest in visited: continue
            if dest not in known:
                if not network or time.monotonic()-started >= 90 or not budget.allow(event['logical_id'], urlsplit(dest).hostname):
                    pending.append(dest); break
                budget.charge(event['logical_id'], dest)
                p = root/(sha(dest.encode())+'.json')
                m = {'url': dest, 'status': 'INTERRUPTED_NO_RETRY', 'acquired_at': now()}; p.write_text(json.dumps(m))
                try:
                    raw, final, status, ct = fetch(dest)
                    relation_url(final)
                    if urlsplit(final).hostname.removeprefix('www.') != u.hostname.removeprefix('www.'):
                        raise ValueError('SUPPLIER_REDIRECT_IDENTITY')
                    p.with_suffix('.raw').write_bytes(raw)
                    m.update(status=status, final_url=final, raw_sha256=sha(raw), content_type=ct)
                except Exception as exc:
                    m.update(status=getattr(exc, 'code', type(exc).__name__), retry=False)
                p.write_text(json.dumps(m)); known[dest] = (p, m)
            p, m = known[dest]; visited.append(dest)
            if m['status'] != 200 or not p.with_suffix('.raw').exists():
                leads.append({'url': dest, 'status': m['status'], 'stage': 'SOURCE', 'retry': False}); continue
            raw = p.with_suffix('.raw').read_bytes()
            if sha(raw) != m['raw_sha256']: raise ValueError('SUPPLIER_CAPTURE_HASH_MISMATCH')
            if raw.startswith(b'%PDF'):
                leads.append({'url': dest, 'status': 'PDF_IN_EXISTING_EXTRACTION_QUEUE', 'source_hash': sha(raw)}); continue
            parser = Metadata(); parser.feed(raw.decode('utf-8', errors='replace'))
            dom = future_body._Document(); dom.feed(raw.decode('utf-8', errors='replace')); dom.close()
            bases = [n.attrs['href'] for n in future_body._nodes(dom.root) if n.tag == 'base' and n.attrs.get('href')]
            link_base = m.get('final_url', dest)
            if len(bases) == 1:
                candidate_base = urljoin(link_base, bases[0])
                if urlsplit(candidate_base).hostname.removeprefix('www.') == u.hostname.removeprefix('www.'): link_base = candidate_base
            provider = next((sid for sid, hosts in fmt.HOSTS.items() if sid.startswith('issuer_') and urlsplit(dest).hostname in hosts), None)
            if provider:
                indicative = engine.indicative_supply(raw, {'source_id': provider, 'url': dest, 'sha256': sha(raw),
                    'acquired_at': m['acquired_at']})
                if indicative:
                    fact, signal = indicative; supply_facts[fact['id']] = fact; supply_events[signal['id']] = signal
            candidates = []
            for href, label in parser.links:
                child = urljoin(link_base, href).split('#')[0]
                try: relation_url(child)
                except ValueError: continue
                # A literal prefix only nominates a product page. It does not
                # prove a model/variant match or a qualified supply pool.
                label = ' '.join(label.split())
                if (len(label.split()) >= 3 and event['product'].casefold().startswith(label.casefold())
                        and urlsplit(child).hostname.removeprefix('www.') == u.hostname.removeprefix('www.')
                        and child not in visited and child not in candidates): candidates.append(child)
            queue.extend(candidates)
            body = future_body.extract_document(raw.decode('utf-8', errors='replace'), content_type=m.get('content_type', 'text/html'))
            # The existing parser reports extraction scope; a menu isn't a
            # source-backed supply fact even when its HTTP response is200.
            leads.append({'url': dest, 'status': 'SUPPLIER_PAGE_INSPECTED_NOT_SUPPLY_PROOF',
                          'source_hash': sha(raw), 'body_status': body.get('body_status', body.get('status', 'UNKNOWN')),
                          'product_links': candidates, 'published_at': parser.meta.get('article:published_time') or 'UNKNOWN',
                          'qualified_supply': 'UNKNOWN', 'independence': 'UNKNOWN'})
        reports.append({'event_id': event['id'], 'supplier_id': site['supplier_id'], 'reported_site': site['reported_site'],
                        'visited': visited, 'pending_urls': list(dict.fromkeys(pending+queue)), 'results': leads,
                        'state': 'REVIEW_PENDING_NO_QUALIFIED_SUPPLY', 'Q3_eligible': False})
    # Leave an open traversal's charges intact across restarts; never reset by
    # run ID or silently declare exhausted sources globally absent.
    return {'requests_charged_this_round': len(budget.current['charges']), 'suppliers': reports,
            'supply_facts': list(supply_facts.values()), 'supply_events': list(supply_events.values())}


def bind_supplier_receipts(opposites, external):
    """Keep actual attempted ranges in the existing common relation queue."""
    by_event = {s['event_id']: s for s in external['suppliers']}
    for task in opposites['relation_tasks']:
        source = by_event.get(task['seed_id'])
        if source and task['facet'] in {'MANUFACTURER_FACILITY', 'FACILITY_CAPACITY_READY', 'QUALIFICATION_RELIEF'}:
            task['checked_sources'] = [{k: r[k] for k in ['url', 'status', 'source_hash'] if k in r} for r in source.get('results', [])]
            task['urls'] = [{'url': u, 'via_document_id': task['source_identity']['document_id'],
                             'status': 'AUTOMATIC_SUPPLIER_RELATION_PENDING', 'relation': 'UNKNOWN_REVIEW_REQUIRED'}
                            for u in source.get('pending_urls', [])]
            task['search_state'] = 'SUPPLIER_SITE_INSPECTED_QUALIFIED_CAPACITY_PENDING'
            task['reason'] = 'CHECKED_PUBLISHER_RANGE_NOT_GLOBAL_ABSENCE_OR_QUALIFIED_SUPPLY'
        elif not source:
            task['scope']['supplier_site_missing'] = True
        task['id'] = sha(['q2-relation-state-1', {k: v for k, v in task.items() if k != 'id'}])


def resume_counterparts(ledger, root, caches, *, network=False):
    """Resume the saved opposite-side phase without re-reading source inputs."""
    path = Path(root)/'automatic-report.json'; packet = json.loads(path.read_text())
    external = supplier_discovery(packet, Path(root)/'supplier-captures', caches, network=network)
    if sha(external) == sha(packet['supplier_discovery']): return {'state': 'COUNTERPART_RECEIPTS_UNCHANGED_NO_REPEAT', 'source_inputs_reread': 0}
    prior = sha(packet); path.with_name('automatic-report-'+prior+'.json').write_bytes(path.read_bytes())
    packet['supplier_discovery'] = external
    bind_supplier_receipts(packet['counterparts'], external)
    facts = json.loads((Path(root)/'automatic-facts.json').read_text())
    all_facts = {f['id']: f for f in facts['facts']+external['supply_facts']}
    fmt.save(ledger, list(all_facts.values()))
    all_events = {e['id']: e for e in packet['events']+external['supply_events']}; packet['events'] = list(all_events.values())
    packet['summary']['indicative_supply_events'] = sum(e['role'] == 'SUPPLY' for e in packet['events'])
    packet['summary']['automatic_events'] = len(packet['events'])
    packet.setdefault('resume_history', []).append({'previous_report_sha256': prior, 'source_inputs_reread': 0,
        'condition_change': 'PREVIOUSLY_UNEXECUTED_COUNTERPART_PHASE_NOW_ENABLED_WITH_SAME_DURABLE_BUDGET'})
    engine.save(ledger, packet)
    from bct.v4.quantitative_counterpart import save_relations
    save_relations(ledger, stamp_export({'tasks': packet['counterparts']['relation_tasks']}))
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2)+'\n')
    facts['facts'] = list(all_facts.values()); (Path(root)/'automatic-facts.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2)+'\n')
    return {'state': 'COUNTERPART_PHASE_RESUMED', 'summary': packet['summary'], 'source_inputs_reread': 0,
            'requests_charged_same_round': external['requests_charged_this_round'], 'Q3': packet['Q3']}


def run(ledger, cache, root, *, documents=(), network=False, auxiliary_caches=(), as_of=None):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    at = as_of or now(); combined = {k: [] for k in ['events', 'facts', 'baseline', 'failures', 'documents', 'supplier_sites']}
    processed_hashes = set()
    for text, in ledger.db.execute("SELECT payload FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.policy.format')=?", (engine.VERSION,)):
        processed_hashes.update(i['source_hash'] for i in json.loads(text)['policy'].get('inputs', []))
    inputs = []; releases = set(); pending_native = []
    for p in sorted(Path(cache).glob('*.json')):
        try: m = json.loads(p.read_text())
        except (ValueError, UnicodeError): continue
        u = urlsplit(m.get('url', ''))
        source = ('find_tender' if u.hostname == 'www.find-tender.service.gov.uk' else
                  'contracts_finder' if u.hostname == 'www.contractsfinder.service.gov.uk' else None)
        endpoint = (u.path.startswith('/api/1.0/ocdsReleasePackages') if source == 'find_tender'
                    else u.path == '/Published/Notices/OCDS/Search')
        if not source or not endpoint or m.get('status') != 200 or not p.with_suffix('.raw').exists(): continue
        if m.get('raw_sha256') in processed_hashes: continue
        raw = p.with_suffix('.raw').read_bytes()
        if sha(raw) != m['raw_sha256']:
            combined['failures'].append({'stage': 'SOURCE', 'reason': 'DISCOVERY_INPUT_HASH_MISMATCH', 'url': m['url']}); continue
        try: native = json.loads(raw)
        except ValueError:
            combined['failures'].append({'stage': 'EXTRACTION', 'reason': 'NATIVE_JSON_INVALID', 'url': m['url']}); continue
        if not isinstance(native.get('releases'), list): continue
        fmt.safe_url(source, m['url'])
        acquired = m.get('acquired_at') or datetime.fromtimestamp(m['at'], timezone.utc).isoformat()
        inputs.append({'source_id': source, 'url': m['url'], 'source_hash': sha(raw), 'acquired_at': acquired})
        releases.update((source, r['ocid'], r['id']) for r in native['releases'])
        pending_native.append((native, {'source_id': source, 'url': m['url'], 'sha256': sha(raw), 'acquired_at': acquired}))
    if not inputs:
        if network and (root/'automatic-report.json').exists(): return resume_counterparts(ledger, root, auxiliary_caches, network=True)
        return {'state': 'NO_NEW_NATIVE_INPUT_MODEL_NOT_LOADED', 'new_inputs': 0}
    marker = 'OFFICIAL_AUTO_INPUTS:'+sha([engine.VERSION, sorted(i['source_hash'] for i in inputs)])
    prior = ledger.db.execute("SELECT payload FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.reason')=? ORDER BY seq DESC LIMIT 1", (marker,)).fetchone()
    if prior: return {'state': 'ALREADY_PROCESSED_NATIVE_VERSIONS', 'new_inputs': 0, 'previous': json.loads(prior[0])['policy']}
    for native, meta in pending_native:
        result = engine.extract_ocds(native, meta)
        for k in combined: combined[k] += result[k]
    facts_saved = fmt.save(ledger, combined['facts'])
    # Latest publication per logical event, never count an amended release as
    # another order. Original versions remain in official facts and receipts.
    latest = {}
    for e in combined['events']:
        if e['logical_id'] not in latest or e['published_at'] > latest[e['logical_id']]['published_at']: latest[e['logical_id']] = e
    combined['events'] = list(latest.values())
    opposites = engine.counterparts(combined['events'], combined['facts'], list(documents), as_of=at[:10])
    external = supplier_discovery(combined, root/'supplier-captures', auxiliary_caches, network=network)
    bind_supplier_receipts(opposites, external)
    fmt.save(ledger, external['supply_facts'])
    combined['facts'] += external['supply_facts']; combined['events'] += external['supply_events']
    q3 = engine.q3_input(combined['events'], combined['facts'], as_of=at, documents=combined['documents'])
    current = [json.loads(p) for p, in ledger.db.execute('SELECT payload FROM events WHERE kind=?', (fmt.KIND,))]
    changes = engine.project_changes(current)
    report = {'format': engine.VERSION, 'plan_id': 'BCT-V4-Q-1.0', 'inputs': inputs,
              'release_versions': len(releases), 'events': combined['events'], 'failures': combined['failures'],
              'supplier_sites': combined['supplier_sites'], 'baseline': combined['baseline'],
              'counterparts': opposites, 'supplier_discovery': external, 'project_changes': changes, 'Q3': q3,
              'typed_routes': engine.typed_routes(current),
              'summary': {'automatic_events': len(combined['events']), 'source_bound_demand': sum(e['state'] == 'SOURCE_BOUND_EVENT' for e in combined['events']),
                          'discovery_proposals': sum(e['state'] == 'DISCOVERY_PROPOSAL' for e in combined['events']),
                          'product_family_signals': sum(e['state'] == 'SOURCE_BOUND_PRODUCT_FAMILY' for e in combined['events']),
                          'indicative_supply_events': len(external['supply_events']),
                          'new_fact_versions': facts_saved['added'], 'native_documents': len(releases),
                          'failure_stages': dict(Counter(e['stage'] for e in combined['failures'])),
                          'project_revision_fields': len(changes), 'project_revision_targets': len({c['project_lineage'] for c in changes})},
              'operating_changes': False, 'AI_calls': 0, 'CPU_windows': 0, 'paid_cost': 0,
              'scope': 'DEVELOPMENT_AUTOMATIC_DISCOVERY_NOT_INDEPENDENT_ACCURACY_OR_LIVE_FORECAST'}
    report = stamp_export(report)
    engine.save(ledger, report)
    from bct.v4.quantitative_counterpart import save_relations
    save_relations(ledger, stamp_export({'tasks': opposites['relation_tasks']}))
    with ledger.db: ledger.event('QUANTITATIVE_VALIDATION', {'reason': marker, 'originals_modified': False, 'policy': {'summary': report['summary'], 'report_sha256': sha(report)}})
    (root/'automatic-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    (root/'automatic-facts.json').write_text(json.dumps(stamp_export({'plan_id': 'BCT-V4-Q-1.0', 'facts': combined['facts']}), ensure_ascii=False, indent=2)+'\n')
    return {'state': 'AUTOMATIC_RESEARCH_EXECUTED', **report['summary'], 'Q3': q3}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--ledger', required=True); p.add_argument('--cache', required=True); p.add_argument('--root', required=True); p.add_argument('--network-counterparts', action='store_true'); p.add_argument('--auxiliary-cache', action='append', default=[])
    a = p.parse_args()
    from v4_quantitative_relations import inventory
    _, _, docs, *_ = inventory()
    ledger = Ledger(a.ledger)
    try:
        with ledger.worker():
            print(json.dumps(run(ledger, a.cache, a.root, documents=list(docs.values()), network=a.network_counterparts, auxiliary_caches=a.auxiliary_cache), ensure_ascii=False))
    finally: ledger.close()
