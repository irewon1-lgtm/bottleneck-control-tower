"""Conservative source-backed hypotheses in the existing candidate JSON.

No model, network, score or database is introduced. Explicit text rules cover
only readable claims; missing scope and ambiguous relationships remain UNKNOWN.
Automatic projections never replace request-driven reviewer records.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any
import re
import uuid

CRITERIA_VERSION = 'bct-v33-light-prd-1'
UNKNOWN = 'UNKNOWN'
POLICY = {'collection_documents': 300, 'collection_workers': 6,
          'review_documents': 10, 'review_characters': 12000,
          'fifo_slots': 1, 'new_target_slots': 1, 'old_wait_days': 7}
SCOPE_FIELDS = ('target', 'specification', 'region', 'supply_pool', 'period', 'basis')
NAME = re.compile(
    r'\b(?:total demand for|additional demand for|remaining demand for|demand for|orders? for|'
    r'total qualified supply for|unallocated qualified supply for|qualified supply for|'
    r'production of|certification of|qualification of|capacity for)\s+'
    r'(?P<name>[^.;:\n()]{2,100}?)'
    r'(?=\s+(?:is|are|was|were|has|have|will|must|increased|decreased|grew|rose|fell|'
    r'doubled|surged|remains?|reached|needs?|requires?)\b|[.(;\n]|$)', re.I)
CONDITIONAL = re.compile(r'\b(?:may|might|could|would|if|unless|forecast\w*|expect\w*|plan\w*|'
                         r'propos\w*|not|never|denied|rumou?rs?)\b', re.I)
PUBLIC_LIMIT = re.compile(r'\b(?:no (?:new )?(?:order|production|delivery) slots|'
                          r'unable to (?:meet|supply|deliver)|cannot (?:meet|supply|deliver)|'
                          r'supply (?:is |will be )?insufficient|shortage|sold out)\b', re.I)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _clock(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    value = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('observation timestamps require timezone')
    return value.astimezone(timezone.utc)


def _name(value):
    value = re.sub(r'^(?:the|a|an)\s+', '', value.strip(), flags=re.I)
    if (not 1 <= len(value.split()) <= 8 or not re.fullmatch(r'[A-Za-z][A-Za-z0-9 /+-]*', value)
            or re.search(r'\b(?:more|less|to|by|may|could|up|down)\b', value, re.I)):
        return None
    return ' '.join(value.split())


def extract_facts(body, screening):
    """Read explicit claims and offsets, never infer a quantity from CAPEX.

    Scope labels are deliberately conservative. Arbitrary prose still creates
    an unclassified or partially scoped draft for the existing human reviewer.
    A fully scoped statement can be compared only to the same supply pool.
    """
    from .future_bottleneck import TARGET, CHANGE, SUPPLY_LOSS
    facts, relationships = [], []
    for row in re.finditer(r'[^\n]+', body):
        text, start, end = row.group(), row.start(), row.end()
        names = []
        for match in NAME.finditer(text):
            name = _name(match['name'])
            if name and name not in names:
                names.append(name)
        for target in screening.get('targets', []):
            if target['name'].lower() in text.lower() and target['name'] not in names:
                names.append(target['name'])
        if not names:
            names = list(dict.fromkeys(m.group() for m in TARGET.finditer(text)))
        relation = re.fullmatch(r'\s*(.{2,80}?)\s+(?:is|are) used in\s+(.{2,80}?)\.?\s*', text, re.I)
        if relation:
            component, product = _name(relation[1]), _name(relation[2].rstrip('.'))
            if component and product:
                relationships.append({'component': component, 'product': product,
                                      'locator': {'start': start, 'end': end}, 'confirmed': True})
        names = list(dict.fromkeys(names))
        if not names:
            continue
        scope = {}
        for field, label in [('specification', r'spec(?:ification)?'), ('region', 'region'),
                             ('supply_pool', 'supply pool')]:
            scope_match = re.search(r'\b' + label + r'\s*[:=]\s*([^;().\n]+)', text, re.I)
            scope[field] = scope_match[1].strip() if scope_match else UNKNOWN
        period = re.search(r'\bperiod\s*[:=]\s*(\d{4}-\d{2}-\d{2})\s+(?:to|through)\s+(\d{4}-\d{2}-\d{2})', text, re.I)
        scope['period'] = {'start': period[1], 'end': period[2], 'precision': 'DAY'} if period else UNKNOWN
        basis = re.search(r'\bbasis\s*[:=]\s*(total|additional|unallocated)\b', text, re.I)
        scope['basis'] = basis[1].lower() if basis else UNKNOWN
        roles = []
        if re.search(r'\b(?:demand for|orders? for)\b', text, re.I):
            roles.append('DEMAND')
        if re.search(r'\b(?:qualified supply for|capacity for|production of|certification of|qualification of)\b', text, re.I):
            roles.append('SUPPLY')
        if 'RELIEF' in screening.get('discovery_paths', []) and re.search(r'\b(?:alternative|inventory|expan\w*|new supplier|cancel\w*|recover\w*)\b', text, re.I):
            roles.append('RELIEF')
        # Do not attach one quantity or a scope to several possible targets.
        ambiguous = len(names) != 1
        number = re.search(r'\b(?:increased to|decreased to|is|are|equals|reached)\s+(\d+(?:,\d{3})*(?:\.\d+)?)\s+(units|tonnes|tons|slots|wafers|pieces)\b', text, re.I)
        needed = re.search(r'\b(?:needed|required|delivery) by\s+(\d{4}-\d{2}-\d{2})', text, re.I)
        available = re.search(r'\b(?:available|certified|qualified|shipments start) (?:on|from)\s+(\d{4}-\d{2}-\d{2})', text, re.I)
        actual = not CONDITIONAL.search(text)
        for name in names:
            for role in roles or ['CHANGE']:
                fact = {**deepcopy(scope), 'target': name, 'role': role,
                        'locator': {'start': start, 'end': end},
                        'actual_statement': bool(actual), 'scope_ambiguous': ambiguous,
                        'change_confirmed': bool(actual and (role == 'DEMAND' and CHANGE.search(text)
                            or role == 'SUPPLY' and SUPPLY_LOSS.search(text))),
                        'quantity': float(number[1].replace(',', '')) if number and not ambiguous and actual else None,
                        'unit': number[2].lower() if number and not ambiguous and actual else UNKNOWN,
                        'need_date': needed[1] if needed and not ambiguous and actual else None,
                        'available_date': available[1] if available and not ambiguous and actual else None,
                        'coverage_complete': bool(re.search(r'\bincluding all qualified suppliers,\s*usable inventory and alternative suppliers\b', text, re.I)),
                        'explicit_public_constraint': bool(PUBLIC_LIMIT.search(text) and actual)}
                order = re.search(r'\b(?:order|contract) (?:ID\s*[:=]\s*)?([A-Z][A-Z0-9-]*\d[A-Z0-9-]*)\b', text)
                fact['transaction_id'] = order[1] if order else None
                facts.append(fact)
    return {'scope_facts': facts, 'supply_relationships': relationships}


def _canonical_target(value, tracking):
    """Only reviewer-confirmed aliases with documentary locators may connect."""
    for target in tracking.get('targets', []):
        for alias in target.get('confirmed_aliases', []):
            if (isinstance(alias, dict) and alias.get('name', '').casefold() == value.casefold()
                    and alias.get('evidence')):
                return target.get('target', value).casefold()
    return value.casefold()


def _scope_key(fact, tracking):
    values = {key: fact.get(key, UNKNOWN) for key in SCOPE_FIELDS}
    values['target'] = _canonical_target(values['target'], tracking)
    for key in ('specification', 'region', 'supply_pool'):
        values[key] = values[key].casefold()
    # Demand increments and unallocated supply intentionally share a basis.
    if values['basis'] == 'unallocated':
        values['basis'] = 'additional'
    complete = all(value != UNKNOWN for value in values.values()) and not fact.get('scope_ambiguous')
    if not complete:
        values['unresolved_document'] = fact['document_id']
    return _hash(values), values


def compare_gap(facts, *, now=None, change_confirmed=False):
    """Earn S3 only from explicit matched total or increment/free-supply bounds."""
    gates = {key: UNKNOWN for key in ('change', 'remaining_demand', 'matched_scope', 'future_period',
                                      'qualified_supply', 'relief_reviewed', 'supply_gap')}
    if change_confirmed or any(f.get('change_confirmed') for f in facts):
        gates['change'] = 'TRUE'
    demands = [f for f in facts if f['role'] == 'DEMAND' and f.get('actual_statement')]
    supplies = [f for f in facts if f['role'] == 'SUPPLY' and f.get('actual_statement')]
    if demands:
        gates['remaining_demand'] = 'TRUE'
    if not demands or not supplies:
        return {'stage': 'S2', 'gates': gates, 'reason': '수요 또는 적격 공급 비교 근거 부족'}
    period = demands[0].get('period')
    if not isinstance(period, dict):
        return {'stage': 'S2', 'gates': gates, 'reason': '필요기간 미확인'}
    try:
        future = _clock(now).date().isoformat() < period['start'] <= period['end']
        datetime.fromisoformat(period['start']); datetime.fromisoformat(period['end'])
    except (KeyError, TypeError, ValueError):
        future = False
    gates['future_period'] = 'TRUE' if future else 'FALSE'
    complete = all(all(f.get(key, UNKNOWN) != UNKNOWN for key in SCOPE_FIELDS)
                   and not f.get('scope_ambiguous') for f in demands + supplies)
    scopes = {(f['target'].casefold(), f['specification'].casefold(), f['region'].casefold(),
               f['supply_pool'].casefold(), _hash(f['period'])) for f in demands + supplies}
    bases_ok = all(d.get('basis') == s.get('basis') == 'total' or
                   d.get('basis') == 'additional' and s.get('basis') == 'unallocated'
                   for d in demands for s in supplies)
    gates['matched_scope'] = 'TRUE' if complete and len(scopes) == 1 and bases_ok else UNKNOWN
    covered = [s for s in supplies if s.get('coverage_complete')]
    if covered:
        gates['qualified_supply'] = gates['relief_reviewed'] = 'TRUE'
    # Different total figures are conflicts, not figures to sum or cherry-pick.
    dq = {(d.get('quantity'), d.get('unit')) for d in demands if d.get('quantity') is not None}
    sq = {(s.get('quantity'), s.get('unit')) for s in covered if s.get('quantity') is not None}
    gap = UNKNOWN
    if len(dq) == len(sq) == 1:
        (d, du), (s, su) = next(iter(dq)), next(iter(sq))
        if du == su:
            gap = 'TRUE' if d > s else 'FALSE'
    elif not dq and not sq:
        nd = {d.get('need_date') for d in demands}
        ad = {s.get('available_date') for s in covered}
        if len(nd) == len(ad) == 1 and None not in nd | ad:
            need, available = next(iter(nd)), next(iter(ad))
            if period['start'] <= need <= period['end']:
                gap = 'TRUE' if need < available else 'FALSE'
    gates['supply_gap'] = gap
    stage = 'S3' if all(v == 'TRUE' for v in gates.values()) else 'S2'
    return {'stage': stage, 'gates': gates, 'reason': '동일 범위의 수요와 적격 공급이 불일치' if stage == 'S3'
            else '공급 충족 근거' if gap == 'FALSE' else '비교 범위·대체 공급 또는 시점 미확인'}


def _evidence_rows(candidates):
    for document_id, doc in candidates.get('results', {}).items():
        for raw in doc.get('scope_facts', []):
            fact = deepcopy(raw)
            fact.update(document_id=document_id, body_sha256=doc.get('current_body_sha256') or doc.get('body_sha256'),
                        body_status=doc.get('body_status', 'UNAVAILABLE'), published_at=doc.get('published_at'),
                        publication_precision=doc.get('publication_precision', UNKNOWN),
                        publication_verified=doc.get('publication_verified', False), url=doc.get('url'))
            # PARTIAL provides a lead, but not complete evidence for automatic S3.
            if fact['body_status'] != 'FULL':
                fact['coverage_complete'] = False
            fact['anchor'] = _hash([document_id, fact['locator'], fact['role']])
            fact['id'] = _hash([fact['anchor'], fact['body_sha256']])
            yield fact


def hypothesis_patch(candidates, tracking, *, now=None, mode='LIVE'):
    if mode not in ('LIVE', 'BACKFILL', 'SYNTHETIC'):
        raise ValueError('invalid detection mode')
    clock = _clock(now).isoformat()
    groups: dict[str,Any] = {}
    for fact in _evidence_rows(candidates):
        key, scope = _scope_key(fact, tracking)
        group = groups.setdefault(key, {'scope': scope, 'facts': []})
        # Exact reprints and identical explicit transactions never add quantities.
        identity = (fact.get('transaction_id') or fact['body_sha256'], fact['role'],
                    fact['target'].casefold(), _hash(fact['locator']))
        if not any(f.get('dedup_key') == list(identity) for f in group['facts']):
            group['facts'].append({**fact, 'dedup_key': list(identity)})
    previous = candidates.get('hypotheses', {})
    by_key: dict[str,set] = {}
    by_anchor: dict[str,set] = {}
    relations: dict[str,list] = {}
    for eid, h in previous.items():
        by_key.setdefault(h.get('candidate_key'), set()).add(eid)
        for anchor in h.get('anchors', []): by_anchor.setdefault(anchor, set()).add(eid)
    for document_id, doc in candidates.get('results', {}).items():
        for rel in doc.get('supply_relationships', []):
            if not rel.get('confirmed'): continue
            ref = {**rel, 'document_id': document_id, 'body_sha256': doc.get('body_sha256')}
            for name in (rel['component'], rel['product']): relations.setdefault(name.casefold(), []).append(ref)
    changed_products = {f['target'].casefold() for g in groups.values() for f in g['facts']
                        if f['role'] == 'DEMAND' and candidates['results'][f['document_id']].get('candidate')}
    patch: dict[str,Any] = {}
    assigned: set[str] = set()
    for key, group in groups.items():
        facts, scope = group['facts'], group['scope']
        has_change = any(candidates['results'][f['document_id']].get('candidate') for f in facts)
        # One documented product/component edge can discover a component even
        # when its own capacity statement is static. No use ratio is invented.
        if not has_change:
            has_change = any(rel.get('confirmed') and rel['component'].casefold() == scope['target']
                             and rel['product'].casefold() in changed_products
                             for rel in relations.get(scope['target'], []))
        if not has_change:
            continue
        anchors = {f['anchor'] for f in facts}
        matched_ids = set(by_key.get(key, set()))
        for anchor in anchors: matched_ids.update(by_anchor.get(anchor, set()))
        matching = [(eid, previous[eid]) for eid in sorted(matched_ids - assigned)
                    if _canonical_target(previous[eid].get('current', {}).get('scope', {}).get('target', UNKNOWN), tracking) == scope['target']]
        ambiguous_merge = len(matching) > 1
        if ambiguous_merge:
            matching = []  # Preserve a separate draft and pending relation.
        eid, old = matching[0] if matching else ('hypothesis-' + str(uuid.uuid4()), {})
        assigned.add(eid)
        verdict = compare_gap(facts, now=clock)
        if ambiguous_merge:
            verdict.update(stage='S2', reason='여러 기존 사건의 연결 관계 검토 필요')
            verdict['gates']['matched_scope'] = UNKNOWN
        if any(scope.get(k) == UNKNOWN for k in ('target', 'specification', 'region', 'period')):
            verdict['stage'] = 'S1'
        # Relations expand related evidence one hop, without deriving quantities.
        related = []
        names = {f['target'].casefold() for f in facts}
        for name in names:
            for rel in relations.get(name, []):
                if rel not in related: related.append(rel)
        by_role = {role: [f['id'] for f in facts if f['role'] == role] for role in ('DEMAND', 'SUPPLY', 'RELIEF')}
        missing = [k for k in SCOPE_FIELDS if scope.get(k) == UNKNOWN]
        if not by_role['DEMAND']: missing.append('수요 근거')
        if not by_role['SUPPLY']: missing.append('적격 공급 근거')
        if verdict['stage'] != 'S3': missing.append(verdict['reason'])
        draft = {'kind': 'INFERENCE', 'text': f"{scope['target']}의 필요기간 {scope['period']}에서 수요와 적격 공급의 불일치 가능성을 검토한다.",
                 'facts': by_role, 'refutation': '동일 기간·규격·공급 풀의 적격 공급이 수요를 충족하거나 수요가 취소되면 반박한다.',
                 'unconfirmed': missing, 'next_material': missing,
                 'comparison_missing': not by_role['DEMAND'] or not by_role['SUPPLY']}
        ledger = tracking.get('prediction_ledger', {}).get(eid, {})
        entries = ledger.get('entries', [])
        first_s3 = old.get('first_s3') or ledger.get('first_s3')
        if not first_s3 and verdict['stage'] == 'S3':
            first_s3 = {'at': clock, 'hypothesis': draft, 'period': scope['period'],
                        'documents': [{'document_id': f['document_id'], 'body_sha256': f['body_sha256']} for f in facts],
                        'criteria_version': CRITERIA_VERSION, 'detection_mode': mode}
        confirmations = [source for entry in entries for source in entry.get('public_confirmations', [])]
        scans = [entry['public_scan'] for entry in entries if entry.get('public_scan')]
        classification = classify_public(first_s3, confirmations, scans[-1] if scans else {})
        current = {'scope': scope, 'stage': verdict['stage'], 'gates': verdict['gates'],
                   'draft': draft, 'evidence': facts, 'related_evidence': related,
                   'review_required': verdict['stage'] != 'S3', 'criteria_version': CRITERIA_VERSION,
                   'public_classification': classification, 'outcome': ledger.get('outcome', {'status': 'OPEN', 'actual_occurred': UNKNOWN})}
        if current == old.get('current'):
            continue
        refs = [{'document_id': f['document_id'], 'body_sha256': f['body_sha256']} for f in facts]
        detected = min((candidates['results'][f['document_id']].get('first_candidate_at', clock) for f in facts), default=clock)
        record = {'id': eid, 'candidate_key': key, 'anchors': sorted(anchors), 'current': current,
                  'first_detected_at': old.get('first_detected_at', detected),
                  'first_hypothesis_at': old.get('first_hypothesis_at', clock),
                  'detection_mode': old.get('detection_mode', mode),
                  'history': [{'id': 'generation-' + _hash([eid, current])[:24], 'at': clock,
                               'criteria_version': CRITERIA_VERSION, 'documents': refs,
                               'old': old.get('current'), 'new': current}]}
        if verdict['stage'] == 'S3' and not old.get('first_s3'):
            record['first_s3'] = first_s3
        patch[eid] = record
    # Unnamed uncertain documents also remain visible, without invented TARGETs.
    for document_id, doc in candidates.get('results', {}).items():
        if not doc.get('candidate') or doc.get('scope_facts'):
            continue
        key = 'unclassified-' + document_id
        if key not in previous:
            patch[key] = {'id': key, 'candidate_key': key, 'anchors': [], 'first_detected_at': clock,
                          'first_hypothesis_at': clock, 'detection_mode': mode,
                          'current': {'stage': 'S1', 'scope': {'target': UNKNOWN}, 'review_required': True,
                                      'draft': {'kind': 'INFERENCE', 'text': '미분류 변화 후보. TARGET·기간·공급 비교 근거 확인 필요.',
                                                'unconfirmed': ['TARGET', '규격', '지역', '필요기간', '수요·공급 비교']},
                                      'evidence': [{'document_id': document_id, 'body_sha256': doc.get('body_sha256')} ]}}
    return {'hypotheses': patch}


def classify_public(first_s3, confirmations, scan):
    """A search miss is UNKNOWN; same day without time is unordered."""
    if not first_s3 or first_s3.get('detection_mode') in ('BACKFILL', 'SYNTHETIC'):
        return UNKNOWN
    at = _clock(first_s3['at'])
    incomplete = False
    for source in confirmations:
        if not source.get('same_event') or not source.get('explicit_constraint'):
            continue
        if not source.get('publication_verified') or not source.get('locator'):
            incomplete = True
            continue
        value, precision = source.get('published_at'), source.get('precision')
        try:
            if precision == 'DAY':
                # Unknown publisher timezone: use the whole possible UTC day
                # interval, not a fictitious midnight publication timestamp.
                day = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
                earliest, latest = day - timedelta(hours=14), day + timedelta(days=1, hours=12)
                if earliest <= at < latest:
                    incomplete = True
                    continue
                if latest <= at:
                    return 'PUBLIC_AT_DETECTION'
            elif precision == 'TIMESTAMP':
                if _clock(value) <= at:
                    return 'PUBLIC_AT_DETECTION'
            else:
                incomplete = True
        except (TypeError, ValueError):
            incomplete = True
    try:
        covered = (scan.get('frozen_scope') and scan.get('complete') is True and scan.get('evidence')
                   and scan.get('checked_through') and _clock(scan['checked_through']) >= at)
    except (TypeError, ValueError):
        covered = False
    return 'PRE_PUBLIC' if covered and not incomplete else UNKNOWN


def outcome_update(previous, update, period):
    """Preserve occurrence after relief; absence of news never proves FALSE."""
    result = deepcopy(previous or {'status': 'OPEN', 'actual_occurred': UNKNOWN})
    if update in result.get('history', []):
        return result
    status = update.get('status')
    if status not in ('OPEN', 'CONFIRMED', 'RELIEVED', 'DISCONFIRMED'):
        raise ValueError('invalid outcome status')
    if status != 'OPEN' and not update.get('evidence'):
        raise ValueError('outcomes need documentary evidence')
    if status != 'OPEN' and not update.get('at'):
        raise ValueError('outcomes need the observation timestamp')
    actual = update.get('actual_occurred', UNKNOWN)
    if actual not in ('TRUE', 'FALSE', UNKNOWN):
        raise ValueError('invalid occurrence value')
    if actual == 'TRUE' and status != 'CONFIRMED' and result.get('actual_occurred') != 'TRUE':
        raise ValueError('occurrence TRUE needs an in-period confirmation')
    if status == 'CONFIRMED':
        start = update.get('actual_started_at')
        if not update.get('same_scope') or not start or not period['start'] <= start[:10] <= period['end']:
            raise ValueError('confirmation must be within original scope and period')
        actual = 'TRUE'
        result.setdefault('actual_started_at', start)
    if actual == 'FALSE' and not (update.get('full_period_supply_fulfilled') is True and update.get('evidence')
                                  and update.get('at', '')[:10] > period['end']):
        raise ValueError('FALSE requires actual supply fulfilment evidence for the entire period')
    if result.get('actual_occurred') == 'TRUE':
        actual = 'TRUE'
    result.update(status=status, actual_occurred=actual if actual != UNKNOWN else result.get('actual_occurred', UNKNOWN))
    if status == 'RELIEVED': result['relieved_at'] = update.get('at')
    result.setdefault('history', []).append(deepcopy(update))
    return result


def operation_report(samples, *, now=None):
    """Reuse elapsed-day checks, but require actual PRD burden evidence too."""
    from .future_quality import observation_status
    rows = [s for s in samples if s.get('criteria_version') == CRITERIA_VERSION]
    base = observation_status(rows, now=now)
    missing, failures = [], []
    checks = ('collection_budget_verified', 'candidate_retention_verified', 'source_wide_scan',
              'review_bundle_budget_verified', 'selection_reservations_verified')
    for row in rows:
        stamp = row.get('recorded_at')
        if row.get('fixed_policy') != POLICY:
            missing.append({'at': stamp, 'field': 'fixed_policy'})
        for key in checks:
            if row.get(key) is False:
                failures.append({'at': stamp, 'field': key})
            elif row.get(key) is not True:
                missing.append({'at': stamp, 'field': key})
        reviewed, seconds = row.get('review_documents_total'), row.get('review_seconds_total')
        if (not isinstance(reviewed, int) or isinstance(reviewed, bool) or reviewed < 0
                or reviewed > 0 and (not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds < 0)):
            missing.append({'at': stamp, 'field': 'actual_review_count_and_time'})
        if row.get('user_wait', 0) > 0 and reviewed == 0:
            missing.append({'at': stamp, 'field': 'request_driven_review_execution'})
    return {**base, 'status': 'FAIL' if failures else 'BLOCKED' if missing or base['status'] != 'PASS' else 'PASS',
            'criteria_version': CRITERIA_VERSION, 'fixed_policy': POLICY,
            'missing_evidence': missing, 'budget_failures': failures, 'forecast_pass': None}


def performance_report(hypotheses, *, now=None, cohort=None, reference=None):
    """Event-level measurements only; missing denominators remain unmeasured."""
    report: dict[str,Any] = {'status': 'BLOCKED', 'accuracy': None, 'recall': None,
              'confirmed_results': 0, 'unresolved_results': None,
              'forecast_pass': None, 'reason': '고정 전향 후보군·독립 사건군·사전 성능 기준 필요'}
    if not cohort or cohort.get('frozen_before_evaluation') is not True:
        return report
    ids = cohort.get('event_ids', [])
    if len(ids) != len(set(ids)) or not all(i in hypotheses for i in ids):
        return report
    selected = [hypotheses[i] for i in ids if hypotheses[i].get('first_s3')
                and hypotheses[i]['first_s3'].get('detection_mode') == 'LIVE'
                and hypotheses[i]['current'].get('public_classification') == 'PRE_PUBLIC'
                and hypotheses[i]['first_s3']['period']['end'] < _clock(now).date().isoformat()]
    known = [h['current']['outcome']['actual_occurred'] for h in selected
             if h['current'].get('outcome', {}).get('actual_occurred') in ('TRUE', 'FALSE')]
    report.update(accuracy=known.count('TRUE') / len(known) if known else None,
                  confirmed_results=len(known), unresolved_results=len(selected) - len(known),
                  unresolved_ratio=(len(selected) - len(known)) / len(selected) if selected else None)
    if reference and reference.get('independent') is True and reference.get('frozen_before_evaluation') is True:
        cases = reference.get('cases', [])
        if cases and len({c['id'] for c in cases}) == len(cases) and all(c.get('result_verified') is True
                and c.get('actual_started_at') and c.get('public_confirmed_at') for c in cases):
            caught = 0
            for case in cases:
                h = hypotheses.get(case.get('hypothesis_id'), {})
                s3 = h.get('first_s3', {})
                if s3.get('detection_mode') == 'LIVE' and s3.get('at'):
                    caught += (_clock(s3['at']) < min(_clock(case['actual_started_at']), _clock(case['public_confirmed_at'])))
            report['recall'] = caught / len(cases)
    return report
