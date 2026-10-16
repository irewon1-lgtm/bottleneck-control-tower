#!/usr/bin/env python3
"""One research batch over already captured official versions; no target input.

The collector's normal page cursors remain authoritative. Native captures are
ephemeral/local, and only typed facts and own processing state enter Releases.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.parse import urlsplit, urlunsplit, urljoin

from bct.objective_lock import stamp_export
from bct.target_acquisition import fetch, Metadata
from bct import future_body
from bct.v4 import official_discovery as engine, official_sources as fmt
from bct.v4.quantitative_counterpart import RelationRound, relation_url, relation_links
from bct.v4.store import Ledger, sha, now, file_sha


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
