"""Source-backed discovery only. Never assign S stages or write v3.3 sidecars."""
import argparse
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import uuid
from urllib.parse import urlsplit

from .objective_lock import ObjectiveBlocked, objective_binding, require_objective, stamp_export

PUBLIC_CONFIRMATION = re.compile(r'\b(?:shortages?|bottlenecks?|scarcity|tight[- ]supply|supply (?:is |remains? )?tight)\b|병목|공급\s*부족|품귀|공급난', re.I)
DEMAND_TYPES = {'customer_roadmap', 'committed_order', 'reservation', 'capex', 'deployment', 'product_transition'}
SUPPLY_TYPES = {'qualified_capacity', 'utilization', 'yield', 'lead_time', 'fab_tool_installation',
                'qualification', 'production_ramp', 'inventory', 'substitute', 'dual_source', 'redesign'}
SCOPE = ('target_id', 'specification', 'region', 'supply_pool', 'period')


def clock(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result.astimezone(timezone.utc)


def publication_cutoff(doc, as_of, *, allow_unknown=False):
    """Validate real precision without converting a calendar date to a time."""
    if not isinstance(doc.get('available_at'), str):
        raise ValueError('BLOCKED: availability UNKNOWN')
    available = clock(doc['available_at'])
    if available > as_of:
        raise ValueError('not available at discovery cutoff')
    precision = doc.get('publication_precision')
    if precision == 'DATE':
        published = date.fromisoformat(doc['published_at'])
        if published >= as_of.date():
            raise ValueError('BLOCKED: DATE publication not strictly before discovery date')
        if available.date() < published:
            raise ValueError('availability precedes publication date')
        return
    if allow_unknown and doc.get('published_at') is None and precision == 'UNKNOWN':
        if not isinstance(doc.get('public_snapshot_observed_at'), str):
            raise ValueError('BLOCKED: snapshot observation UNKNOWN')
        published = clock(doc['public_snapshot_observed_at'])
    else:
        if doc.get('published_at') is None:
            raise ValueError('BLOCKED: original publication UNKNOWN')
        published = clock(doc['published_at'])
    if published > as_of:
        raise ValueError('not available at discovery cutoff')
    if available < published:
        raise ValueError('availability precedes publication')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def url(value):
    p = urlsplit(value)
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password:
        raise ValueError('source URL required')
    return p.hostname.lower() + p.path.rstrip('/') + ('?' + p.query if p.query else '')


def scope(signal):
    return digest({k: signal[k] for k in SCOPE})


def independent(a, b):
    # Unknown attribution is never filled with the republishing website's identity.
    return (a['origin_id'] != b['origin_id'] and url(a['origin_url']) != url(b['origin_url'])
            and a['origin_publisher'].casefold() != b['origin_publisher'].casefold()
            and a['body_sha256'] != b['body_sha256'] and a['excerpt_sha256'] != b['excerpt_sha256'])


def lead_time(candidate, confirmation_at):
    if not candidate or not confirmation_at:
        return {'lead_time_days': None, 'early_detection_success': False, 'status': 'UNMEASURED'}
    days = (clock(confirmation_at) - clock(candidate['candidate_first_detected_at'])).total_seconds() / 86400
    return {'lead_time_days': days, 'early_detection_success': days > 0,
            'status': 'EARLY_DETECTION' if days > 0 else 'MISSED_EARLY_DETECTION'}


def comparison(d, s):
    """Only compare explicit comparable quantities/dates; no imputation or summing."""
    basis_ok = (d.get('basis'), s.get('basis')) in (('total', 'total'), ('additional', 'unallocated'))
    if not basis_ok or s.get('qualified') is not True:
        return None, None
    need, available = d.get('need_date'), s.get('available_date')
    timing = None
    if need and available:
        datetime.fromisoformat(need); datetime.fromisoformat(available)
        if not d['period']['start'] <= need <= d['period']['end']:
            return None, None
        timing = need < available
    dq, sq = d.get('quantity'), s.get('quantity')
    numeric = all(type(q) in (int, float) and math.isfinite(q) and q >= 0 for q in (dq, sq))
    quantitative = numeric and d.get('unit') not in (None, '', 'UNKNOWN') and d.get('unit') == s.get('unit')
    sufficient = quantitative and sq >= dq and s.get('coverage_complete') is True and timing is False
    if sufficient:
        return 'SUFFICIENT_BEFORE_NEED', None
    if quantitative and dq > sq:
        return 'POSSIBLE_QUANTITY_GAP', {'demand': dq, 'qualified_supply': sq, 'unit': d['unit'],
                                         'supply_coverage': 'COMPLETE' if s.get('coverage_complete') is True else 'UNKNOWN'}
    if timing:
        return 'POSSIBLE_TIMING_GAP', {'need_date': need, 'available_date': available,
                                      'demand_quantity': dq if numeric else 'UNKNOWN',
                                      'supply_quantity': sq if numeric else 'UNKNOWN'}
    return None, None


def discover(batch, *, now=None, mode='LIVE', previous=None):
    require_objective(batch)
    if mode not in ('LIVE', 'BACKFILL', 'SYNTHETIC'):
        raise ValueError('invalid discovery mode')
    if mode == 'LIVE' and now is not None:
        raise ValueError('LIVE discovery cannot backdate detection; use BACKFILL')
    as_of = clock(now) if now is not None else datetime.now(timezone.utc)
    prior = {}
    if previous is not None:
        require_objective(previous)
        if previous.get('mode') != mode:
            raise ValueError('cannot mix live and replay discovery history')
        if clock(previous['computed_at']) > as_of:
            raise ValueError('previous history is from the future')
        prior = {x['scope_id']: x for x in previous.get('candidates', [])}
        for candidate in prior.values():
            first = clock(candidate['candidate_first_detected_at'])
            if first > clock(previous['computed_at']) or any(
                    clock(e['available_at']) > first for e in candidate['evidence']):
                raise ValueError('invalid first-detection history; cannot backdate source availability')
    docs = {}; rejected = []
    for doc in batch.get('documents', []):
        try:
            if doc['document_id'] in docs:
                raise ValueError('duplicate document ID')
            if hashlib.sha256(doc['body'].encode()).hexdigest() != doc['body_sha256']:
                raise ValueError('snapshot hash mismatch')
            publication_cutoff(doc, as_of)
            if doc.get('provenance_verified') is not True or not all(doc.get(k) for k in ('origin_id', 'origin_url', 'origin_publisher')):
                raise ValueError('UNVERIFIED_ORIGINAL_SOURCE')
            url(doc['origin_url'])
            if doc.get('public_bottleneck_confirmation') is True or PUBLIC_CONFIRMATION.search(doc['body']):
                raise ValueError('PUBLIC_CONFIRMATION_NOT_PRECURSOR')
            docs[doc['document_id']] = doc
        except (KeyError, ValueError, TypeError) as exc:
            rejected.append({'document_id': doc.get('document_id'), 'reason': str(exc)})
    groups = {}
    for signal in batch.get('signals', []):
        try:
            doc = docs[signal['document_id']]
            start, end = signal['locator']['start'], signal['locator']['end']
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(doc['body']):
                raise ValueError('invalid locator')
            role = signal['role']
            if signal['signal_type'] not in (DEMAND_TYPES if role == 'DEMAND' else SUPPLY_TYPES if role == 'SUPPLY' else set()):
                raise ValueError('invalid precursor type/role')
            if not signal.get('target') or any(signal.get(k) in (None, '', 'UNKNOWN') for k in SCOPE):
                raise ValueError('scope UNKNOWN; cannot fuse unrelated targets')
            period = signal['period']
            if not as_of.date().isoformat() < period['start'] <= period['end']:
                raise ValueError('period must be future')
            datetime.fromisoformat(period['start']); datetime.fromisoformat(period['end'])
            quantity = signal.get('quantity', 'UNKNOWN')
            if quantity != 'UNKNOWN' and quantity is not None and (
                    type(quantity) not in (int, float) or not math.isfinite(quantity) or quantity < 0):
                raise ValueError('invalid quantity; do not impute UNKNOWN')
            x = {**deepcopy(signal), 'origin_id': doc['origin_id'], 'origin_url': doc['origin_url'],
                 'origin_publisher': doc['origin_publisher'], 'body_sha256': doc['body_sha256'],
                 'published_at': doc['published_at'], 'available_at': doc['available_at'],
                 'excerpt_sha256': hashlib.sha256(doc['body'][start:end].encode()).hexdigest()}
            if 'publication_precision' in doc:
                x['publication_precision'] = doc['publication_precision']
            groups.setdefault(scope(signal), []).append(x)
        except (KeyError, TypeError, ValueError) as exc:
            rejected.append({'document_id': signal.get('document_id'), 'reason': str(exc)})
    confirmations = {}
    for item in batch.get('confirmations', []):
        if item.get('explicit') is not True or item.get('frozen') is not True or not item.get('evidence', {}).get('locator'):
            raise ValueError('public confirmation requires frozen explicit source evidence')
        url(item['evidence']['url']); at = clock(item['first_public_bottleneck_confirmation_at'])
        key = item['target_id'];old = confirmations.get(key)
        if old is None or at < clock(old): confirmations[key] = at.isoformat()
    candidates = []; outcomes = []
    for key, signals in sorted(groups.items()):
        demands = [x for x in signals if x['role'] == 'DEMAND']; supplies = [x for x in signals if x['role'] == 'SUPPLY']
        pairs = [(d, s) for d in demands for s in supplies if d['target'] == s['target'] and independent(d, s)]
        evaluated = [(d, s, *comparison(d, s)) for d, s in pairs]
        enough = any(reason == 'SUFFICIENT_BEFORE_NEED' for _, _, reason, _ in evaluated)
        gaps = [(d, s, reason, evidence) for d, s, reason, evidence in evaluated if reason and reason.startswith('POSSIBLE_')]
        state = 'CONTRADICTED' if enough else 'FORECAST_CANDIDATE' if gaps else 'DATA_WAIT'
        candidate = prior.get(key)
        if state == 'FORECAST_CANDIDATE':
            d, s, reason, evidence = gaps[0]
            candidate = {'scope_id': key, 'target_id': d['target_id'], 'target': d['target'],
                         'scope': {k: d[k] for k in SCOPE}, 'layer': 'DISCOVERY',
                         'candidate_first_detected_at': candidate['candidate_first_detected_at'] if candidate else as_of.isoformat(),
                         'reason': reason, 'comparison': evidence, 'evidence': [d, s]}
            candidates.append(candidate)
        elif candidate:
            # Preserve first-detection history even when new relief refutes it.
            candidate = {**candidate, 'current_state': state}; candidates.append(candidate)
        metric = lead_time(candidate, confirmations.get(signals[0]['target_id']))
        if metric['status'] == 'MISSED_EARLY_DETECTION': state = metric['status']
        outcomes.append({'scope_id': key, 'target_id': signals[0]['target_id'], 'state': state, **metric})
    # Prior candidates outside today's input must not disappear or be backdated.
    seen = {x['scope_id'] for x in candidates}
    candidates.extend(deepcopy(x) for k,x in prior.items() if k not in seen)
    return stamp_export({'format': 'bct-forecast-discovery-v1', 'batch_id': 'forecast-'+uuid.uuid4().hex,
                         'state': 'FINISHED' if groups else 'BLOCKED',
                         'mode': mode, 'computed_at': as_of.isoformat(), 'layer': 'DISCOVERY',
                         'candidates': candidates, 'outcomes': outcomes, 'rejected_inputs': rejected,
                         'input_sha256': digest(batch), 'confirmation_layer': 'existing quick/deep/S1/S2/S3 unchanged',
                         'forecast_performance': {'status': 'BLOCKED', 'reason': 'No independent real pre-public holdout evaluation; functional fixtures are not performance evidence.'}})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--mode', choices=['LIVE', 'BACKFILL', 'SYNTHETIC'], default='LIVE')
    parser.add_argument('--as-of')
    args = parser.parse_args()
    try:
        result = discover(json.loads(args.input.read_text()), now=args.as_of, mode=args.mode,
                          previous=json.loads(args.previous.read_text()) if args.previous else None)
    except (ObjectiveBlocked, ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({'state': 'BLOCKED', 'reason': str(exc)})); raise SystemExit(1)
    from .future_manual_review import _private_write
    _private_write(args.output, result)


if __name__ == '__main__':
    main()
