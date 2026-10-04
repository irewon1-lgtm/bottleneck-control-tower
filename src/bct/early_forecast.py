"""Evidence-backed early tracking, separate from quantitative discovery/S gates."""
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import math
import re
import uuid

from . import forecast_discovery as strict
from .objective_lock import require_objective, stamp_export

CLASS = 'EARLY_FORECAST_CANDIDATE'
DEMAND = strict.DEMAND_TYPES
PENDING = {'UNDER_CONSTRUCTION', 'PENDING_QUALIFICATION', 'PRE_RAMP', 'EXPANSION_INCOMPLETE',
           'PRODUCTION_CONSTRAINT', 'LONG_LEAD_TIME', 'LIMITED_QUALIFIED_SUPPLIERS'}
REFUTATION = ['Sufficient same-scope qualified supply before the demand window',
              'Earlier completed qualification or expansion covers the requirement',
              'Order cancellation, demand delay or material demand reduction',
              'Sufficient qualified substitute supply becomes available']


def _quote(doc, loc):
    a, b = loc['start'], loc['end']
    if type(a) is not int or type(b) is not int or not 0 <= a < b <= len(doc['body']):
        raise ValueError('invalid evidence locator')
    return doc['body'][a:b]


def _window(doc, field):
    """Calendar bounds describe literal coarse periods, never exact need dates."""
    text = _quote(doc, field['locator'])
    if field['text'] not in text:
        raise ValueError('window text missing from locator')
    value = field['text'].strip()
    prefix = re.fullmatch(r'(H[12]|Q[1-4])\s*(20\d{2})', value)
    match_value = (prefix[2] + ' ' + prefix[1]) if prefix else value
    m = re.fullmatch(r'(20\d{2})(?:\s*[-~–]\s*(20\d{2})|\s*(H[12]|Q[1-4]))?', match_value)
    if m:
        y, last, part = int(m[1]), int(m[2] or m[1]), m[3]
        if last < y:
            raise ValueError('reversed window')
        first_month = 1 if not part else (1 if part == 'H1' else 7) if part.startswith('H') else 3 * (int(part[1]) - 1) + 1
        last_month = 12 if not part else first_month + (5 if part.startswith('H') else 2)
        import calendar
        return {'text': value, 'start': date(y, first_month, 1).isoformat(),
                'end': date(last, last_month, calendar.monthrange(last, last_month)[1]).isoformat(),
                'precision': 'SOURCE_WINDOW_NOT_EXACT_NEED_DATE', 'locator': deepcopy(field['locator'])}
    # Open-ended contractual ordering windows retain UNKNOWN start.
    if field.get('kind') == 'ORDERING_WINDOW_END':
        end = datetime.strptime(value, '%B %d, %Y').date().isoformat()
        return {'text': value, 'start': None, 'end': end, 'precision': 'ORDERING_WINDOW_END',
                'locator': deepcopy(field['locator'])}
    raise ValueError('unsupported explicit source window')


def discover(batch, *, mode='LIVE', now=None):
    require_objective(batch)
    if mode not in ('LIVE', 'SYNTHETIC', 'BACKFILL') or (mode == 'LIVE' and now is not None):
        raise ValueError('LIVE detection cannot backdate')
    at = strict.clock(now) if now is not None else strict.clock(datetime.now(timezone.utc).isoformat())
    docs, rejected = {}, []
    for d in batch.get('documents', []):
        try:
            if d['document_id'] in docs or not d['body'] or hashlib.sha256(d['body'].encode()).hexdigest() != d['body_sha256']:
                raise ValueError('duplicate document or body hash mismatch')
            available = strict.clock(d['available_at'])
            if d.get('published_at') is None and d.get('publication_precision') == 'UNKNOWN':
                publication_bound = strict.clock(d['public_snapshot_observed_at'])
            else:
                publication_bound = strict.clock(d['published_at'])
            if not publication_bound <= available <= at:
                raise ValueError('source not available at cutoff')
            if d.get('provenance_verified') is not True or not all(d.get(k) for k in ('origin_id', 'origin_url', 'origin_publisher')):
                raise ValueError('unverified original source')
            strict.url(d['origin_url'])
            if strict.PUBLIC_CONFIRMATION.search(d['body']) or d.get('public_bottleneck_confirmation') is True:
                raise ValueError('PUBLIC_CONFIRMATION_NOT_PRECURSOR')
            docs[d['document_id']] = d
        except (KeyError, ValueError, TypeError) as e:
            rejected.append({'document_id': d.get('document_id'), 'reason': str(e)})
    groups = {}
    for s in batch.get('signals', []):
        try:
            d = docs[s['document_id']]; quote = _quote(d, s['locator'])
            quantity = s.get('quantity', 'UNKNOWN')
            if quantity not in (None, 'UNKNOWN') and (type(quantity) not in (int, float) or not math.isfinite(quantity) or quantity < 0):
                raise ValueError('invalid quantity; preserve UNKNOWN')
            if s.get('source_quote') != quote:
                raise ValueError('source quote mismatch')
            keys = ('target_id', 'target', 'specification', 'region', 'supply_pool')
            if any(s.get(k) in (None, '', 'UNKNOWN') for k in keys) or s.get('target_relation_verified') is not True:
                raise ValueError('target/scope relation unverified')
            relation = s['target_relation_reference']
            relation_doc = docs[relation['document_id']]
            if (relation.get('relationship') not in ('SAME_TARGET', 'VERIFIED_SUPPLY_CHAIN')
                    or relation['source_quote'] != _quote(relation_doc, relation['locator'])):
                raise ValueError('target relation evidence missing or altered')
            if s['role'] == 'DEMAND':
                if s['signal_type'] not in DEMAND or s.get('demand_status') not in ('COMMITTED', 'CONFIRMED_PLAN'):
                    raise ValueError('general forecast is not committed demand')
                window = _window(d, s['future_demand_window'])
                if window['end'] <= at.date().isoformat():
                    raise ValueError('no future demand window')
                if s.get('increase_kind') not in ('NEW_ORDER', 'NEW_DEPLOYMENT', 'EXPANSION', 'ADDITIONAL_RESERVATION', 'TRANSITION'):
                    raise ValueError('source-backed incremental demand required')
                _quote(d, s['increase_locator'])
            elif s['role'] == 'SUPPLY':
                if s['signal_type'] not in strict.SUPPLY_TYPES:
                    raise ValueError('invalid supply type')
                window = _window(d, s['known_supply_window']) if s.get('known_supply_window') else 'UNKNOWN'
            else:
                raise ValueError('invalid role')
            x = {**deepcopy(s), 'origin_id': d['origin_id'], 'origin_url': d['origin_url'],
                 'origin_publisher': d['origin_publisher'], 'body_sha256': d['body_sha256'],
                 'published_at': d['published_at'], 'available_at': d['available_at'],
                 'excerpt_sha256': hashlib.sha256(quote.encode()).hexdigest(), 'source_window': window, 'relation_evidence': {**deepcopy(relation), 'role': 'RELATION',
                 'body_sha256': relation_doc['body_sha256'], 'published_at': relation_doc.get('published_at'),
                 'available_at': relation_doc['available_at']}}
            if s['role'] == 'SUPPLY' and s.get('supply_status') in PENDING:
                _quote(d, s['status_locator'])
                if isinstance(window, dict) and window['end'] < at.date().isoformat():
                    raise ValueError('old pending supply window needs current verification')
            groups.setdefault(strict.digest({k: s[k] for k in keys}), []).append(x)
        except (KeyError, ValueError, TypeError) as e:
            rejected.append({'document_id': s.get('document_id'), 'reason': str(e)})
    # Prior confirmation needs an actual hashed, matching source locator, not a date label.
    confirmed = {}
    for c in batch.get('confirmations', []):
        d = c['document']; q = _quote(d, c['locator'])
        if (hashlib.sha256(d['body'].encode()).hexdigest() != d['body_sha256']
                or c.get('explicit') is not True or c.get('target_match_verified') is not True
                or d.get('provenance_verified') is not True or not strict.PUBLIC_CONFIRMATION.search(q)
                or not strict.clock(d['published_at']) <= strict.clock(d['available_at']) <= at):
            raise ValueError('unverified same-target explicit confirmation')
        strict.url(d['url'])
        if c['target_id'] not in confirmed or strict.clock(d['published_at']) < strict.clock(confirmed[c['target_id']]):
            confirmed[c['target_id']] = d['published_at']
    candidates, outcomes = [], []
    for key, signals in groups.items():
        tid = signals[0]['target_id']; pairs = [(d, s) for d in signals if d['role'] == 'DEMAND'
                                               for s in signals if s['role'] == 'SUPPLY' and strict.independent(d, s)]
        chosen = None; refuted = False
        # Confirmed complete supply wins even when the relief shares demand's origin.
        for d in (x for x in signals if x['role'] == 'DEMAND'):
            for s in (x for x in signals if x['role'] == 'SUPPLY'):
                # Strict same-scope sufficiency is not relaxed for early discovery.
                comparable = d.get('period') == s.get('period') and d.get('period')
                if comparable and strict.comparison(d, s)[0] == 'SUFFICIENT_BEFORE_NEED':
                    refuted = True
                if (s.get('sufficiency_verified') is True and s.get('qualified') is True
                        and s.get('coverage_complete') is True and s.get('supply_status') == 'AVAILABLE'
                        and isinstance(s['source_window'], dict) and d['source_window']['start']
                        and s['source_window']['end'] < d['source_window']['start']):
                    try:
                        _quote(docs[s['document_id']], s['sufficiency_locator'])
                    except (KeyError, ValueError, TypeError):
                        continue
                    refuted = True
        for d, s in pairs:
            if s.get('supply_status') not in PENDING:
                continue
            # F2/F3: expansion/qualification still pending or qualified suppliers limited.
            if s['supply_status'] in ('LONG_LEAD_TIME', 'PRODUCTION_CONSTRAINT'):
                sw = s['source_window']; dw = d['source_window']
                if not isinstance(sw, dict) or not sw['start'] or not sw['start'] > dw['end']:
                    continue  # F1/F4 require an actual source-window lag, not a generic constraint.
            chosen = (d, s); break
        state = 'MISSED_EARLY_DETECTION' if tid in confirmed else 'REFUTED' if refuted else CLASS if chosen else 'DATA_WAIT'
        origins = list(chosen) if chosen else []
        for s in signals:
            if all(strict.independent(s, old) for old in origins): origins.append(s)
        if state == CLASS:
            d, s = chosen
            evidence = [d, s]
            for e in (d['relation_evidence'], s['relation_evidence']):
                if not any(old['document_id'] == e['document_id'] for old in evidence): evidence.append(e)
            candidate = {'scope_id': key, 'target_id': tid, 'target': d['target'], 'candidate_class': CLASS,
                         'layer': 'DISCOVERY', 'candidate_first_detected_at': at.isoformat(),
                         'independent_origin_count': len(origins), 'evidence': evidence,
                         'future_demand_window': d['source_window'], 'known_supply_window': s['source_window'],
                         'reason': 'SOURCE_BACKED_INCREASING_DEMAND_WITH_PENDING_OR_CONSTRAINED_SUPPLY',
                         'refutation_conditions': deepcopy(REFUTATION),
                         'decisive_UNKNOWN': deepcopy(batch.get('candidate_annotations', {}).get(tid, {}).get('decisive_UNKNOWN', [])),
                         'quantitative_comparison': 'UNKNOWN', 's_stage_unchanged': True}
            candidates.append(candidate)
        outcomes.append({'target_id': tid, 'target': signals[0]['target'], 'scope_id': key, 'state': state,
                         'independent_origin_count': len(origins), 'early_detection_success': False,
                         'confirmation_at': confirmed.get(tid)})
    for tid, when in confirmed.items():
        if not any(x['target_id'] == tid for x in outcomes):
            outcomes.append({'target_id': tid, 'state': 'MISSED_EARLY_DETECTION', 'confirmation_at': when,
                             'early_detection_success': False, 'independent_origin_count': 0})
    return stamp_export({'format': 'bct-early-forecast-v1', 'mode': mode, 'layer': 'DISCOVERY',
                         'batch_id': 'early-'+uuid.uuid4().hex, 'computed_at': at.isoformat(),
                         'state': 'FINISHED', 'candidates': candidates, 'outcomes': outcomes,
                         'rejected_inputs': rejected, 'input_sha256': strict.digest(batch),
                         'performance_PASS': None})
