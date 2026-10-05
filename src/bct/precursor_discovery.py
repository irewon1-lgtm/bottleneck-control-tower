"""Source-addressed events -> new scoped TARGETs -> conservative EARLY inputs.

No TARGET dictionary, scores, S upgrades, collection, or retrospective writes.
The legacy EARLY/strict engines and Objective Lock are reused unchanged.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import re

from . import early_forecast as early, forecast_discovery as strict
from .objective_lock import require_objective, stamp_export

VERSION = 'PRECURSOR_SYNTHESIS_V1'
UNKNOWN = 'UNKNOWN'
SCOPE = ('product', 'specification', 'region', 'customer_group', 'supply_pool')
PATTERNS = {
    'ORDER': r'\b(?:orders?|procurement|purchases?|backlog|offtake)\b',
    'RESERVATION': r'\b(?:capacity reservation|reserved capacity|prepayments?|long[- ]term (?:purchase|contract))\b',
    'CUSTOMER_CAPEX': r'\b(?:customer|buyer).{0,50}\b(?:CAPEX|capital expenditure|investment)\b',
    'DEPLOYMENT': r'\b(?:deploy\w*|mass production|customer product launch)\b',
    'REGULATION': r'\b(?:FEOC|origin restrictions?|import restrictions?|export controls?|export bans?|regulation|origin requirements?)\b',
    'CAPACITY': r'\b(?:production capacity|qualified capacity|qualified supply|production output)\b',
    'CAPACITY_INVESTMENT': r'\b(?:DPA|DoD|government funding|subsid\w*|grants?|invest\w*|new (?:factory|line|plant)|capacity expansion)\b',
    'RAMP': r'\b(?:ramp|commission\w*|qualification|certification|permits?|licen[cs]ing)\b',
    'INVENTORY': r'\b(?:inventory|inventories|stockpiles?)\b',
    'LEAD_TIME': r'\blead[- ]times?\b',
    'CONCENTRATION': r'\b(?:sole supplier|supplier concentration|dependen\w*|single[- ]source|concentrated suppliers)\b',
    'RELIEF': r'\b(?:substitute|alternative supplier|qualified inventory|sufficient qualified supply)\b',
    'DEMAND_CHANGE': r'\b(?:cancel\w*|postpon\w*|demand delay|deferred demand)\b',
}
WINDOW = re.compile(r'\b(?:H[12]\s+20\d{2}|Q[1-4]\s+20\d{2}|20\d{2}\s+(?:H[12]|Q[1-4])|20\d{2}(?:\s*[–~-]\s*20\d{2})?)\b')
INCREMENT = re.compile(r'\b(?:new|expand\w*|increas\w*|additional|doubl\w*|surge|raised|signed|committed|awarded)\b', re.I)
PENDING = re.compile(r'\b(?:pending|under construction|not yet|delay\w*|not ready|pre[- ]ramp|incomplete|await\w*|commission\w*|qualification completes|ready (?:in|on))\b', re.I)


def _reference(doc, loc):
    quote = early._quote(doc, loc)
    return {'document_id': doc['document_id'], 'locator': deepcopy(loc), 'source_quote': quote}


def _scope_refs(doc):
    """Only unique explicit labels. Unlabelled prose stays an unresolved lead.

    A source reader may supply per-event field references instead, but every
    field must match original bytes. Document-level labels are not inferred
    across multiple distinct specifications in a single article.
    """
    out = {}
    for key in SCOPE:
        label = key.replace('_', r'[ _-]')
        matches = list(re.finditer(r'(?im)(?:^|[;\n])\s*' + label + r'\s*:\s*([^;\n]+)', doc['body']))
        if len(matches) == 1:
            m = matches[0]; value = m[1].strip()
            start = m.start(1) + len(m[1]) - len(m[1].lstrip())
            if value and value != UNKNOWN:
                out[key] = {'value': value, 'locator': {'start': start, 'end': start + len(value)}}
    return out


def extract_events(doc):
    """Retain pre-public events even with incomplete scope or missing totals."""
    events = []
    scope = _scope_refs(doc)
    for match in re.finditer(r'[^\n]+', doc['body']):
        quote = match.group(); loc = {'start': match.start(), 'end': match.end()}
        kinds = [kind for kind, pattern in PATTERNS.items() if re.search(pattern, quote, re.I)]
        if strict.PUBLIC_CONFIRMATION.search(quote):
            kinds = ['CONFIRMATION']
        if not kinds:
            continue
        windows = list(WINDOW.finditer(quote))
        # Several periods in a prose sentence require explicit field attribution.
        # Never select a convenient last date from a historical comparison.
        window = None
        if len(windows) == 1:
            w = windows[0]
            window = {'text': w.group(), 'locator': {'start': match.start() + w.start(), 'end': match.start() + w.end()}}
        role = 'DEMAND' if any(k in kinds for k in ('ORDER', 'RESERVATION', 'CUSTOMER_CAPEX', 'DEPLOYMENT', 'DEMAND_CHANGE')) else 'SUPPLY'
        # Single-clause demand/capacity ambiguity is retained but not promoted.
        if role == 'DEMAND' and any(k in kinds for k in ('RAMP', 'RELIEF', 'LEAD_TIME', 'CAPACITY')):
            role = 'CONTEXT'
        if 'RELIEF' in kinds and re.search(r'\b(?:sufficient qualified|covers all|qualified inventory)\b', quote, re.I):
            role = 'SUPPLY'
        kind = 'DEMAND_CHANGE' if 'DEMAND_CHANGE' in kinds else 'RELIEF' if 'RELIEF' in kinds else kinds[0]
        event = {'event_id': strict.digest([doc['document_id'], loc, kinds]), 'document_id': doc['document_id'],
                 'kind': kind, 'event_types': kinds, 'role': role, 'locator': loc, 'source_quote': quote,
                 'scope': deepcopy(scope), 'window': window, 'quantity': UNKNOWN, 'unit': UNKNOWN,
                 'basis': UNKNOWN, 'qualified': False, 'coverage_complete': False,
                 'incremental': bool(INCREMENT.search(quote)), 'pending': bool(PENDING.search(quote)),
                 'demand_status': 'COMMITTED' if re.search(r'\b(?:committed|signed|awarded|binding|firm|confirmed)\b', quote, re.I) and not re.search(r'\b(?:forecast|rumou?r|hypothetical)\b', quote, re.I) else UNKNOWN}
        if re.search(r'\b(?:not ready by|later than demand|after the need window|may miss the demand window)\b', quote, re.I):
            event['misses_need_window'] = True
            event['field_references'] = {'misses_need_window': _reference(doc, loc)}
        numeric = list(re.finditer(r'(?<![\w.,-])(\d+(?:[ ,]\d{3})*(?:\.\d+)?)\s+((?:units|cells|tonnes|tons|kg|wafers|slots|pieces|satellites|vehicles)(?:\s*(?:(?:/\s*[A-Za-z0-9²³]+)+|per\s+(?:(?:calendar|operating|working)\s+)?(?:second|minute|hour|day|week|month|quarter|year)|annually))?)\b(?!\s*(?:/|per\b|annually\b))', quote, re.I))
        if len(numeric) == 1 and role in ('DEMAND', 'SUPPLY'):
            amount = numeric[0]
            value = float(amount[1].replace(',', '').replace(' ', '')) if '.' in amount[1] else int(amount[1].replace(',', '').replace(' ', ''))
            reference = _reference(doc, {'start': match.start() + amount.start(), 'end': match.start() + amount.end()})
            event.update(quantity=value, unit=amount[2])
            event.setdefault('field_references', {}).update(quantity=reference, unit=reference)
        basis = list(re.finditer(r'\b(total|additional|unallocated)\b', quote, re.I))
        if len(basis) == 1:
            event['basis'] = basis[0].group().lower()
            event.setdefault('field_references', {})['basis'] = _reference(doc, loc)
        if re.search(r'\bqualified (?:capacity|supply|production|inventory)\b', quote, re.I) and not re.search(r'\b(?:not|not yet|never) qualified\b', quote, re.I):
            event['qualified'] = True
            event.setdefault('field_references', {})['qualified'] = _reference(doc, loc)
        if (re.search(r'\bqualified\b', quote, re.I) and re.search(r'\b(?:covers all (?:contracted|committed|confirmed|future) demand|sufficient qualified (?:supply|inventory).{0,60}for all (?:orders|demand))\b', quote, re.I)
                and not re.search(r'\b(?:insufficient|cannot cover|not cover|not sufficient|not qualified)\b', quote, re.I)):
            event.update(coverage_complete=True, sufficiency_verified=True)
            event.setdefault('field_references', {}).update(coverage_complete=_reference(doc, loc), sufficiency_verified=_reference(doc, loc))
        for key, pattern in [('need_date', r'\b(?:needed|required|delivery) (?:on|by) (\d{4}-\d{2}-\d{2})'), ('available_date', r'\b(?:available|qualified|ready) (?:on|from) (\d{4}-\d{2}-\d{2})')]:
            dates = list(re.finditer(pattern, quote, re.I))
            if len(dates) == 1:
                event[key] = dates[0][1]
                event.setdefault('field_references', {})[key] = _reference(doc, loc)
        events.append(event)
    return events


def _validate(doc, event):
    if event['document_id'] != doc['document_id'] or early._quote(doc, event['locator']) != event['source_quote']:
        raise ValueError('event source reference mismatch')
    kind = event['kind']
    if kind == 'CONFIRMATION':
        if not strict.PUBLIC_CONFIRMATION.search(event['source_quote']):
            raise ValueError('no explicit confirmation in event')
    elif kind not in PATTERNS or not re.search(PATTERNS[kind], event['source_quote'], re.I):
        raise ValueError('event type not supported by source')
    if event.get('role') == 'DEMAND':
        if kind not in ('ORDER', 'RESERVATION', 'CUSTOMER_CAPEX', 'DEPLOYMENT', 'DEMAND_CHANGE'):
            raise ValueError('source event is not demand')
        if event.get('incremental') and not INCREMENT.search(event['source_quote']):
            raise ValueError('incremental demand not in original source')
        if event.get('demand_status') in ('COMMITTED', 'CONFIRMED_PLAN') and (not re.search(r'\b(?:committed|signed|awarded|binding|firm|confirmed)\b', event['source_quote'], re.I) or re.search(r'\b(?:forecast|rumou?r|hypothetical)\b', event['source_quote'], re.I)):
            raise ValueError('source does not establish committed demand')
    if event.get('pending') and not PENDING.search(event['source_quote']):
        raise ValueError('source does not establish pending supply')
    values = {}
    for key in SCOPE:
        field = event.get('scope', {}).get(key)
        if not field:
            values[key] = UNKNOWN
            continue
        value = field['value']
        if not isinstance(value, str) or value.strip() in ('', UNKNOWN) or early._quote(doc, field['locator']) != value:
            raise ValueError('scope field not supported by original source: ' + key)
        values[key] = ' '.join(value.casefold().split())
    if event.get('window'):
        early._window(doc, event['window'])
        loc = event['window']['locator']
        if not event['locator']['start'] <= loc['start'] < loc['end'] <= event['locator']['end']:
            raise ValueError('future window not attributed to source event')
    # Optional reader-supplied quantitative/dated/sufficiency facts require
    # their own exact references. Flags alone are never verification.
    for key in ('quantity', 'unit', 'basis', 'need_date', 'available_date', 'qualified', 'coverage_complete', 'sufficiency_verified', 'misses_need_window'):
        value = event.get(key)
        if value is None or value is False or value == '' or value == UNKNOWN:
            continue
        ref = event.get('field_references', {}).get(key)
        if not ref or ref['source_quote'] != early._quote(doc, ref['locator']):
            raise ValueError('unreferenced event field: ' + key)
        if not event['locator']['start'] <= ref['locator']['start'] < ref['locator']['end'] <= event['locator']['end']:
            raise ValueError('event field reference belongs to a different statement')
        quote = ref['source_quote']
        value = event[key]
        if key == 'unit' and str(value).casefold() in ('usd', 'eur', 'krw', 'gbp', 'jpy', 'cny', 'chf', 'dollars', 'dollar', 'won', '$', '€', '£'):
            raise ValueError('financial value is not physical demand/supply quantity')
        if key == 'quantity':
            tokens = re.findall(r'(?<![\w.,-])\d+(?:[ ,]\d{3})*(?:\.\d+)?(?![\w.,])', quote)
            if type(value) not in (int, float) or value not in [float(t.replace(',', '').replace(' ', '')) for t in tokens]:
                raise ValueError('quantity not supported by a complete source number')
        if key in ('unit', 'basis', 'need_date', 'available_date') and str(value) not in (quote.casefold() if key == 'basis' else quote):
            raise ValueError('event value missing from source: ' + key)
        semantic = {'qualified': r'\bqualified\b', 'coverage_complete': r'\b(?:all|complete)\b',
                    'sufficiency_verified': r'\b(?:sufficient|covers all|cover all)\b',
                    'misses_need_window': r'\b(?:not ready by|later than demand|after the need window|may miss the demand window)\b'}
        if key == 'qualified' and re.search(r'\b(?:not|not yet|never) qualified\b', quote, re.I):
            raise ValueError('source says supply is not qualified')
        if key in semantic and not re.search(semantic[key], quote, re.I):
            raise ValueError('event assertion missing from source: ' + key)
    return values


def _target(scope):
    # Identity is physical scope, never source count, stock symbol or dictionary.
    return 'precursor-' + strict.digest({k: scope[k] for k in SCOPE}), ' / '.join(scope[k] for k in ('region', 'customer_group', 'supply_pool', 'specification', 'product'))


def _origins(events, docs):
    independent = []
    for event in events:
        doc = docs[event['document_id']]
        origin = {**doc, 'excerpt_sha256': hashlib.sha256(event['source_quote'].encode()).hexdigest()}
        if all(strict.independent(origin, other) for other in independent):
            independent.append(origin)
    return independent


def _clock(mode, now):
    if mode not in ('LIVE', 'SYNTHETIC', 'BACKFILL') or (mode == 'LIVE' and now is not None):
        raise ValueError('LIVE synthesis cannot backdate')
    return strict.clock(now) if now is not None else datetime.now(timezone.utc)


def synthesize(batch, *, mode='LIVE', now=None):
    require_objective(batch)
    at = _clock(mode, now)
    docs, rejected, retained, groups = {}, [], [], {}
    for raw in batch.get('documents', []):
        try:
            if raw['document_id'] in docs or not raw['body'] or hashlib.sha256(raw['body'].encode()).hexdigest() != raw['body_sha256']:
                raise ValueError('duplicate document or body hash mismatch')
            strict.publication_cutoff(raw, at, allow_unknown=True)
            if raw.get('provenance_verified') is not True or any(raw.get(k) in (None, '', UNKNOWN) for k in ('origin_id', 'origin_url', 'origin_publisher')):
                raise ValueError('UNVERIFIED_ORIGINAL_SOURCE')
            strict.url(raw['origin_url']); docs[raw['document_id']] = raw
        except (ValueError, KeyError, TypeError) as exc:
            rejected.append({'document_id': raw.get('document_id'), 'reason': str(exc)})
            if raw.get('body') and hashlib.sha256(raw['body'].encode()).hexdigest() == raw.get('body_sha256'):
                for lead in extract_events(raw):
                    retained.append({**lead, 'extraction_status': 'PROVENANCE_OR_PUBLICATION_UNVERIFIED', 'blocking_reason': str(exc)})
    relations = []
    for relation in batch.get('relationships', []):
        try:
            source = docs[relation['document_id']]
            quote = early._quote(source, relation['locator'])
            if relation.get('source_quote') != quote or relation.get('relationship') != 'VERIFIED_SUPPLY_CHAIN':
                raise ValueError('supply-chain reference mismatch')
            component, product = relation['component_product'], relation['target_product']
            if component not in quote or product not in quote or not re.search(r'\b(?:used in|required for|component of)\b', quote, re.I):
                raise ValueError('supply-chain relationship not in source')
            refs = _scope_refs(source)
            if any(k not in refs for k in SCOPE if k != 'product'):
                raise ValueError('supply-chain physical scope UNKNOWN')
            relations.append({**relation, 'source_scope': {k:' '.join(v['value'].casefold().split()) for k,v in refs.items()}})
        except (KeyError, ValueError, TypeError) as exc:
            rejected.append({'document_id': relation.get('document_id'), 'reason': str(exc)})
    for doc in docs.values():
        supplied = doc.get('precursor_events')
        events = supplied if supplied is not None else extract_events(doc)
        for raw in events:
            try:
                event = deepcopy(raw); scope = _validate(doc, event)
                for relation in relations:
                    if (scope['product'] == relation['target_product'].casefold()
                            and all(scope[k] == relation['source_scope'][k] for k in SCOPE if k != 'product')):
                        # Cross-product association needs the component's actual
                        # required period, not a guessed engineering lead time.
                        if not relation.get('required_component_window'):
                            continue
                        component_window = early._window(docs[relation['document_id']], relation['required_component_window'])
                        event_window = early._window(doc, event['window']) if event.get('window') else None
                        if not event_window or (event_window['start'], event_window['end']) != (component_window['start'], component_window['end']):
                            continue
                        scope['product'] = relation['component_product'].casefold()
                        event['verified_supply_chain_reference'] = relation
                        event['quantity'], event['unit'] = UNKNOWN, UNKNOWN
                event['resolved_scope'] = scope
                event['extraction_status'] = 'SCOPED_EVENT' if UNKNOWN not in scope.values() else 'UNRESOLVED_SCOPE'
                retained.append(event)
                if UNKNOWN in scope.values():
                    continue
                tid, title = _target(scope)
                group = groups.setdefault(tid, {'target_id': tid, 'target': title, 'scope': scope, 'events': []})
                group['events'].append(event)
            except (ValueError, KeyError, TypeError) as exc:
                rejected.append({'document_id': doc['document_id'], 'reason': str(exc)})
    signals, annotations, targets = [], {}, []
    for tid, group in groups.items():
        events = group['events']; ds, ss = [], []
        for event in events:
            kind = event['kind']; doc = docs[event['document_id']]
            if kind == 'CONFIRMATION' or strict.PUBLIC_CONFIRMATION.search(doc['body']):
                continue  # Every explicit public bottleneck document is confirmation only.
            role = event['role']
            if role not in ('DEMAND', 'SUPPLY') or not event.get('window'):
                continue
            window = early._window(doc, event['window'])
            if not window.get('start') or window['end'] <= at.date().isoformat():
                continue
            if role == 'DEMAND' and (kind == 'DEMAND_CHANGE' or not event.get('incremental') or event.get('demand_status') not in ('COMMITTED', 'CONFIRMED_PLAN')):
                continue
            signal = {'document_id': doc['document_id'], 'target_id': tid, 'target': group['target'],
                      'specification': group['scope']['specification'], 'region': group['scope']['region'],
                      # Customer/product dimensions remain part of the pool identity,
                      # so legacy grouping cannot erase synthesized distinctions.
                      'supply_pool': strict.digest(group['scope']), 'role': role,
                      'locator': event['locator'], 'source_quote': event['source_quote'],
                      'quantity': event.get('quantity', UNKNOWN), 'unit': event.get('unit', UNKNOWN),
                      'basis': event.get('basis', UNKNOWN), 'qualified': event.get('qualified', False),
                      'coverage_complete': event.get('coverage_complete', False),
                      'need_date': event.get('need_date'), 'available_date': event.get('available_date'),
                      'target_relation_verified': True, 'target_relation_reference': {**_reference(doc, event['locator']), 'relationship': 'SAME_TARGET'},
                      'source_window': window, 'event_id': event['event_id'], 'source_event': event}
            if role == 'DEMAND':
                signal.update(signal_type={'RESERVATION':'reservation', 'CUSTOMER_CAPEX':'capex', 'DEPLOYMENT':'deployment'}.get(kind, 'committed_order'),
                              demand_status=event['demand_status'], increase_kind='NEW_ORDER', increase_locator=event['locator'], future_demand_window=event['window'])
                ds.append(signal)
            else:
                status = 'AVAILABLE' if event.get('qualified') and not event.get('pending') else 'PENDING_QUALIFICATION' if 'qualification' in event['source_quote'].lower() else 'UNDER_CONSTRUCTION'
                signal.update(signal_type='inventory' if kind == 'RELIEF' else 'qualification' if status == 'PENDING_QUALIFICATION' else 'production_ramp',
                              supply_status=status, status_locator=event['locator'], known_supply_window=event['window'])
                if event.get('sufficiency_verified'):
                    signal.update(sufficiency_verified=True, sufficiency_locator=event['field_references']['sufficiency_verified']['locator'])
                ss.append(signal)
        origins = _origins(events, docs)
        missing = []
        if not ds: missing.append('DEMAND_WITH_FUTURE_WINDOW')
        if not ss: missing.append('SUPPLY_RAMP_WITH_FUTURE_WINDOW')
        if len(origins) < 2: missing.append('INDEPENDENT_ORIGINS')
        pairs = []
        for demand in ds:
            for supply in ss:
                ddoc, sdoc = docs[demand['document_id']], docs[supply['document_id']]
                do = {**ddoc, 'excerpt_sha256': hashlib.sha256(demand['source_quote'].encode()).hexdigest()}
                so = {**sdoc, 'excerpt_sha256': hashlib.sha256(supply['source_quote'].encode()).hexdigest()}
                if not strict.independent(do, so):
                    continue
                dw, sw = demand['source_window'], supply['source_window']
                dates = demand.get('need_date'), supply.get('available_date')
                dated_lag = False
                if all(dates):
                    try:
                        for date in dates: datetime.strptime(date, '%Y-%m-%d')
                    except ValueError:
                        continue
                    dated_lag = dw['start'] <= dates[0] <= dw['end'] and sw['start'] <= dates[1] <= sw['end'] and dates[0] < dates[1]
                # Annual quantities from different source periods cannot be compared.
                same_window = (dw['start'], dw['end']) == (sw['start'], sw['end'])
                numerical = strict.comparison({**demand, 'period': dw}, {**supply, 'period': dw})[0] if same_window else None
                source_lag = sw['start'] > dw['end']
                # A stated readiness interval crossing the demand deadline is
                # a possible lag, not an invented exact completion date.
                readiness_range = (sw['end'] > dw['end']
                    and re.search(r'20\d{2}\s*[–~-]\s*20\d{2}', supply['source_event']['window']['text'])
                    and re.search(r'\b(?:qualification completes|completion|ready)\b', supply['source_quote'], re.I))
                source_lag = source_lag or bool(readiness_range)
                timing = supply['source_event'].get('pending') and (source_lag or dated_lag or supply['source_event'].get('misses_need_window') is True)
                if timing or numerical == 'POSSIBLE_QUANTITY_GAP':
                    supply['tension_reason'] = 'POSSIBLE_QUANTITY_GAP' if numerical == 'POSSIBLE_QUANTITY_GAP' else 'POSSIBLE_TIMING_GAP'
                    pairs.append((demand, supply))
        if not pairs: missing.append('EXPLICIT_FUTURE_TIMING_OR_QUANTITY_TENSION')
        # Explicit same-scope cancellation is adverse evidence, never a positive precursor.
        if any(e['kind'] == 'DEMAND_CHANGE' for e in events):
            missing.append('DEMAND_CANCELLATION_OR_DELAY_REQUIRES_RECONCILIATION'); pairs = []
        chosen_signals = {strict.digest(s): s for pair in pairs for s in pair}
        # Include complete relief before comparison even if it shares a source.
        for s in ss:
            if s['source_event'].get('sufficiency_verified'):
                chosen_signals[strict.digest(s)] = s
        signals.extend(chosen_signals.values())
        annotations[tid] = {'decisive_UNKNOWN': [{'field': key, 'value': UNKNOWN} for key in ('total_demand', 'total_qualified_supply', 'alternative_supply_coverage') if any(e.get('quantity', UNKNOWN) == UNKNOWN for e in events)], 'synthesis_scope': group['scope']}
        targets.append({**group, 'independent_origin_count': len(origins), 'missing_core_conditions': missing, 'state': 'ELIGIBLE_FOR_EARLY_VALIDATION' if pairs else 'DATA_WAIT', 'eligible_pair_event_ids': [[d['event_id'], s['event_id']] for d,s in pairs]})
    return stamp_export({'mode': mode, 'format': 'bct-precursor-synthesis-input-v1', 'discovery_strategy': VERSION,
                         'documents': list(docs.values()), 'signals': signals, 'confirmations': [],
                         'candidate_annotations': annotations, 'synthesized_targets': targets,
                         'retained_precursor_events': retained, 'synthesis_rejected_inputs': rejected})


def discover(batch, *, mode='LIVE', now=None, previous_first=None, confirmation_domains=None):
    prepared = synthesize(batch, mode=mode, now=now)
    result = early.discover(prepared, mode=mode, now=now)
    result['discovery_strategy'] = VERSION
    result['synthesized_targets'] = prepared['synthesized_targets']
    result['retained_precursor_events'] = prepared['retained_precursor_events']
    result['rejected_inputs'] += prepared['synthesis_rejected_inputs']
    previous_first = previous_first or {}
    targets = {t['target_id']: t for t in prepared['synthesized_targets']}
    docs = {d['document_id']: d for d in prepared['documents']}
    for tid, target in targets.items():
        outcome = next((o for o in result['outcomes'] if o['target_id'] == tid), None)
        if outcome is None:
            outcome = {'target_id': tid, 'target': target['target'], 'state': 'DATA_WAIT', 'independent_origin_count': target['independent_origin_count'], 'early_detection_success': False}
            result['outcomes'].append(outcome)
        numerical_signals = [s for s in prepared['signals'] if s['target_id'] == tid]
        if outcome['state'] not in ('REFUTED', 'MISSED_EARLY_DETECTION') and not any(c['target_id'] == tid for c in result['candidates']):
            for demand in (s for s in numerical_signals if s['role'] == 'DEMAND'):
                for supply in (s for s in numerical_signals if s.get('tension_reason') == 'POSSIBLE_QUANTITY_GAP'):
                    if [demand['event_id'], supply['event_id']] not in target['eligible_pair_event_ids']:
                        continue
                    # Pair was independently provenance/scope/window/physical-unit
                    # validated above. No strict/S gate is changed by this class.
                    evidence = []
                    for s in (demand, supply):
                        d = docs[s['document_id']]
                        evidence.append({**s, 'body_sha256': d['body_sha256'], 'published_at': d['published_at'], 'available_at': d['available_at'], 'origin_id': d['origin_id'], 'origin_url': d['origin_url'], 'origin_publisher': d['origin_publisher']})
                    result['candidates'].append({'target_id': tid, 'target': target['target'], 'scope_id': strict.digest(target['scope']),
                        'candidate_class': early.CLASS, 'layer': 'DISCOVERY', 'candidate_first_detected_at': result['computed_at'],
                        'independent_origin_count': target['independent_origin_count'], 'evidence': evidence,
                        'future_demand_window': demand['source_window'], 'known_supply_window': supply['source_window'],
                        'quantitative_comparison': 'SOURCE_BACKED_POSSIBLE_QUANTITY_GAP', 'reason': 'POSSIBLE_QUANTITY_GAP',
                        'refutation_conditions': deepcopy(early.REFUTATION), 's_stage_unchanged': True})
                    outcome.update(state=early.CLASS, independent_origin_count=target['independent_origin_count'])
                    break
                if any(c['target_id'] == tid for c in result['candidates']):
                    break
        outcome['missing_core_conditions'] = target['missing_core_conditions']
        public = [docs[e['document_id']] for e in target['events'] if e['kind'] == 'CONFIRMATION']
        if public and confirmation_domains is not None:
            from urllib.parse import urlsplit
            allowed = [d for d in public if urlsplit(d['origin_url']).hostname in confirmation_domains]
            if len(allowed) != len(public):
                result['rejected_inputs'].append({'target_id': tid, 'reason': 'CONFIRMATION_OUTSIDE_FROZEN_SCOPE'})
            public = allowed
        if public:
            first = previous_first.get(tid)
            if any(d.get('publication_precision') == 'DATE' or d.get('published_at') is None for d in public):
                state, when = 'DATA_WAIT', None
                outcome['missing_core_conditions'].append('EXACT_CONFIRMATION_TIME_UNKNOWN')
            else:
                when = min(public, key=lambda d: strict.clock(d['published_at']))['published_at']
                state = 'CONFIRMED' if first and strict.clock(when) > strict.clock(first) else 'MISSED_EARLY_DETECTION'
            result['candidates'] = [c for c in result['candidates'] if c['target_id'] != tid]
            outcome.update(state=state, confirmation_at=when, early_detection_success=state == 'CONFIRMED')
    for candidate in result['candidates']:
        tid = candidate['target_id']; target = targets[tid]
        candidate['discovery_strategy'] = VERSION
        candidate['synthesis_scope'] = target['scope']
        candidate['synthesis_event_ids'] = [e['event_id'] for e in target['events']]
        candidate['decisive_UNKNOWN'] = prepared['candidate_annotations'][tid]['decisive_UNKNOWN']
        present = {e['document_id'] for e in candidate['evidence']}
        for event in target['events']:
            if event['document_id'] not in present:
                d = docs[event['document_id']]
                candidate['evidence'].append({**_reference(d, event['locator']), 'role': 'CONTEXT', 'body_sha256': d['body_sha256'], 'published_at': d['published_at'], 'available_at': d['available_at'], 'event_id': event['event_id']})
                present.add(event['document_id'])
            relation = event.get('verified_supply_chain_reference')
            if relation and relation['document_id'] not in present:
                d = docs[relation['document_id']]
                candidate['evidence'].append({**_reference(d, relation['locator']), 'role': 'CONTEXT', 'body_sha256': d['body_sha256'], 'published_at': d['published_at'], 'available_at': d['available_at']})
                present.add(relation['document_id'])
    result['precursor_source_input_sha256'] = strict.digest(batch)
    result['input_sha256'] = strict.digest(prepared)
    return result, prepared


def snapshot_batch(snapshot, root):
    """Use existing snapshot/cache provenance guards, never RSS publication dates."""
    from pathlib import Path
    from .future_body import discovery_document
    require_objective(snapshot)
    root = Path(root).resolve()
    documents = []
    for item in snapshot['documents']:
        if not item.get('body_path'):
            continue
        path = (root / item['body_path']).resolve()
        if not path.is_relative_to(root) or path.is_symlink():
            raise ValueError('snapshot body outside artifact root')
        record = deepcopy(item['snapshot_metadata'])
        if record.get('id', item['document_id']) != item['document_id']:
            raise ValueError('snapshot document ID mismatch')
        record['id'] = item['document_id']
        document = discovery_document(record, path.read_text())
        document['precursor_events'] = item.get('precursor_events', extract_events(document))
        documents.append(document)
    return stamp_export({'mode': 'LIVE', 'precursor_discovery': True, 'documents': documents, 'signals': []})


def main():
    import argparse
    import json
    from pathlib import Path
    from .future_manual_review import _private_write
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--artifact-root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--store', type=Path, help='Optional existing LIVE store; omission is read-only')
    args = parser.parse_args()
    batch = json.loads(args.input.read_text())
    if args.artifact_root:
        batch = snapshot_batch(batch, args.artifact_root)
    if args.store:
        if not (args.store / 'session.json').is_file():
            raise ValueError('existing LIVE session required; never create one')
        from .prospective import run
        result = run(args.store, {**batch, 'precursor_discovery': True}, early=True)
    else:
        result, prepared = discover(batch, mode='LIVE')
        result['read_only'] = True
    _private_write(args.output, result)
    print(json.dumps({'state': result.get('state', result.get('engine_state')), 'new_early_candidates': len(result.get('candidates', [])), 'read_only': args.store is None}))


if __name__ == '__main__':
    main()
