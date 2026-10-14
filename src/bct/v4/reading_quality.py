"""Opt-in step-2 research reading. No scheduling, pairing or stage promotion.

Uses the existing exact decoder, semantic guards, located evidence records and
append-only Ledger. Historical responses are never rewritten or repaired.
"""
from copy import deepcopy
import json
import re

from . import public_input
from .evidence_path import accept, reference, ROLES, ACTUALITY
from .free_ai import APIError, no_duplicate_keys, source_input
from .research_reading import decode, PROMPT
from .semantics import semantic_reading, AMOUNT, MONEY
from .store import sha
from bct.objective_lock import stamp_export

VERSION = 'bct-reading-quality-2'
RUN_ID = 'bct-reading-quality-step2-20261015'
SYSTEM = PROMPT + (
    ' Also extract physically named products even without events, using role UNKNOWN. '
    'A production win, company growth or increased consumption is not an actual purchase order. '
    'The object after an order is the bought equipment, not chips/products it tests or makes. '
    'Copy whole source sentences including punctuation, exact case, plural and written numbers; '
    'never convert four to 4 or change a plural. Keep the complete source context available '
    'for cancellation/qualification checks. Money and award recipients are not quantity/buyers. '
    'No physical evidence: omit the field rather than guessing. '
    'Use only the documented role/actuality enums; inventories easing supply are RELIEF. '
    'Each extraction needs event and event_attributes.product. No example facts.')


def coverage(body, windows):
    spans = sorted(set((w['start'], w['end']) for w in windows))
    merged = []
    for a, b in spans:
        if not 0 <= a < b <= len(body): raise ValueError('INVALID_INPUT_RANGE')
        if merged and a <= merged[-1][1]: merged[-1][1] = max(b, merged[-1][1])
        else: merged.append([a, b])
    unread, cursor = [], 0
    for a, b in merged:
        if cursor < a: unread.append({'start': cursor, 'end': a})
        cursor = b
    if cursor < len(body): unread.append({'start': cursor, 'end': len(body)})
    return {'read_ranges': [{'start': a, 'end': b} for a, b in merged],
            'read_characters': sum(b-a for a, b in merged), 'body_characters': len(body),
            'unread_ranges': unread, 'unread_characters': sum(x['end']-x['start'] for x in unread)}


def plan_pages(doc, config, env):
    """Plan all existing bounded pages, not calls. Source holds stay holds.

    Same paragraph/continuation grouping and page budgets as the established
    public excerpt planner. No signal/industry prefilter, no sentence rewrite.
    """
    if doc.get('provenance') != 'PASS': raise ValueError('SOURCE_PROVENANCE_NOT_PASS')
    if not doc.get('published_at') or doc['published_at'] == 'UNKNOWN':
        raise ValueError('PUBLICATION_UNKNOWN')
    # Existing policy verifies hash, URL, explicit restrictions and sensitive
    # text across the entire body, even if it will not be transmitted.
    source_input(doc, config, env)
    body = doc['body']; groups, current = [], []
    for paragraph in re.finditer(r'[^\n]+', body):
        dependent = re.match(r'^(?:this|these|it|its|they|their|the (?:order|contract|agreement|system|facility))\b', paragraph[0].strip(), re.I)
        if current and (public_input.LINK.search(paragraph[0].strip()) or public_input.COUNTER.search(paragraph[0]) or dependent):
            current.append(paragraph)
        else:
            if current: groups.append(current)
            current = [paragraph]
    if current: groups.append(current)
    pages = []
    for page in range(16):
        try:
            selected = public_input._context_page(doc, {**config, 'input_policy': 'sentence-context-v3', 'input_page': page},
                                                  {'scope': 'VERIFIED_DOCUMENT'}, env, groups)
        except ValueError as e:
            if str(e) == 'NO_FURTHER_SAFE_CONTEXT_PAGE': break
            raise
        pages.append(selected)
    prepared = coverage(body, [w for p in pages for w in p['windows']])
    return {'version': VERSION, 'document_id': doc['document_id'], 'body_sha256': doc['body_sha256'],
            'pages': pages, 'prepared': prepared, 'actually_read': coverage(body, []),
            'state': 'PREPARED_NOT_AI_READ', 'additional_pages_require_remaining_task_budget': True}


def identity_hold(name, context):
    # Structural page/organization/policy heads, never an industry/product list.
    if re.search(r'\b(?:inc\.?|corporation|ltd\.?|plc|company)$', name, re.I): return 'ORGANIZATION_IDENTITY'
    if re.search(r'\b(?:business|win|partnership|agreement|funding|grant|project|program|policy)$', name, re.I): return 'NON_PRODUCT_HEAD'
    if re.search(r'\b(?:business|agreement|grant|funding)\s+(?:for|of|to)\b', name, re.I): return 'NON_PRODUCT_RELATIONAL_HEAD'
    if re.fullmatch(r'(?:sign in|read more|privacy policy|cookie settings|subscribe|lock|padlock)', name, re.I): return 'PAGE_DECORATION'
    if re.search(re.escape(name)+r'\s*\((?:NASDAQ|NYSE|LSE)\s*:', context): return 'ISSUER_NOT_PRODUCT'
    return None


def validate_packet(text, doc, windows):
    if sha(doc['body'].encode()) != doc['body_sha256']: raise ValueError('BODY_HASH_MISMATCH')
    for w in windows:
        reference(doc, {'start': w['start'], 'end': w['end'], 'quote': w['text']})
    try:
        data = json.loads(text, object_pairs_hook=no_duplicate_keys,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NON_FINITE_JSON')))
    except (ValueError, APIError) as e: raise ValueError('INVALID_JSON_PACKET') from e
    if not isinstance(data, dict) or set(data) != {'extractions'} or not isinstance(data['extractions'], list) or len(data['extractions']) > 8:
        raise ValueError('INVALID_EXTRACTION_PACKET')
    records, held = [], []
    for index, raw in enumerate(data['extractions']):
        try:
            if not isinstance(raw, dict) or not isinstance(raw.get('event'), str) or not isinstance(raw.get('event_attributes'), dict) or not isinstance(raw['event_attributes'].get('product'), str):
                raise ValueError('INVALID_EXTRACTION_ITEM')
            ps, rejects = decode(json.dumps({'extractions': [raw]}), doc, windows)
            held.extend({**h, 'index': index} for h in rejects)
            if not ps: continue
            p = ps[0]; name = p['product']['value']; reason = identity_hold(name, p['reference']['quote'])
            if reason: raise ValueError(reason)
            if not re.search(r'(?<![\w-])'+re.escape(name)+r'(?![\w-])', p['extraction_reference']['quote']):
                raise ValueError('PRODUCT_TOKEN_BOUNDARY')
            unsupported = p['role'] not in ROLES | {'UNKNOWN'} or p['actuality'] not in ACTUALITY
            item = {'kind': 'PHYSICAL_PRODUCT', 'entity': {'value': name, **p['product']['reference']},
                    'context': deepcopy(p['reference']), 'role': p['role'] if not unsupported else 'UNKNOWN',
                    'actuality': p['actuality'] if p['actuality'] in ACTUALITY else 'UNKNOWN',
                    'facts': [{'field': k, 'value': v['value'], **v['reference']} for k, v in p['fields'].items()],
                    'source_reference_protocol': True}
            semantic = semantic_reading(item)
            checked = deepcopy(p)
            # A miss in the advisory verb grammar is not itself a rejection of
            # an order proved by the existing ordered-object relation checker.
            checked['role'] = (semantic['role'] if semantic['role'] != 'UNKNOWN' else p['role']) if not unsupported else 'UNKNOWN'
            if semantic['actuality'] == 'NEGATED': checked['role'] = 'UNKNOWN'
            checked['actuality'] = semantic['actuality'] if semantic['actuality'] != 'UNKNOWN' else p['actuality']
            checked['fields'] = {f['field']: {'value': f['value'], 'reference': {k: f[k] for k in ('start', 'end', 'quote')}}
                                 for f in semantic['facts'] if f['value'] is not None}
            r = accept(doc, checked)
            # A literal value elsewhere in the same sentence is insufficient:
            # each party/count must be tied to this ordered object. Unsupported
            # relationships remain in the original proposal, not usable fields.
            relation_holds = []
            qtext = p['extraction_reference']['quote']
            for field in ('quantity', 'customer_group', 'supply_pool'):
                fact = r['fields'].get(field)
                if not fact: continue
                claim = re.escape(fact['surface']); product = re.escape(name)
                if field == 'quantity':
                    supported = bool(re.search(claim+r'\s+'+product+r'(?![\w-])', qtext, re.I))
                elif field == 'customer_group':
                    prefix = claim+r'\s+(?:(?:has|have)\s+)?(?:ordered|purchased|bought)\s+'
                    count = r'(?:(?:'+AMOUNT+r'|a|an|the|new|additional)\s+)*'
                    supported = bool(re.search(r'(?<!\w)'+prefix+count+product+r'(?![\w-])', qtext, re.I))
                else:
                    supported = bool(re.search(claim+r'\s+(?:is|are)\s+(?:a |an |the )?(?:qualified|certified|eligible)\s+(?:supplier|manufacturer|producer)\s+of\s+'+product+r'(?![\w-])', qtext, re.I))
                if not supported:
                    relation_holds.append({'field':field,'reason':'EXACT_FIELD_TO_PRODUCT_RELATION_UNPROVEN','source_fact':r['fields'].pop(field)})
                    for decision in semantic['semantic_checks']['field_decisions']:
                        if decision['field'] == field:
                            decision.update(status='UNKNOWN', reason='EXACT_FIELD_TO_PRODUCT_RELATION_UNPROVEN')
                    if field in r['target']: r['target'][field] = None
                    if field == 'quantity': r.pop('quantity_conversion', None)
            semantic['semantic_review'].extend(relation_holds)
            related = [c for c in re.split(r'[.;\n]', p['reference']['quote'])
                       if name in c or re.match(r'^\s*(?:however,?\s+)?(?:this|the) order\b', c, re.I)]
            if any(re.search(r'\b(?:cancelled|canceled|not confirmed|not ordered|did not|has not|no longer)\b', c, re.I) for c in related):
                r.update(event_status='DISCOVERY_ONLY', relation_check='RELATED_NEGATION_OR_CANCELLATION')
            # Open product vocabulary: an exact direct ordered-object count
            # needs no fixed industry noun list. Never recover a nonliteral
            # field held by decode, nor infer a count from a financial value.
            quantity = p['fields'].get('quantity'); unit = p['fields'].get('unit')
            if quantity and r['event_status'] == 'ADOPTED_RESEARCH_EVENT' and r['role'] == 'DEMAND_INCREASE':
                pattern = r'(?<![\w$€£¥])(?P<count>'+AMOUNT+r')\s+'+re.escape(name)+r'(?![\w-])'
                matches = [m for m in re.finditer(pattern, p['extraction_reference']['quote'], re.I)
                           if not MONEY.search(m[0]) and m['count'] == quantity['value']
                           and not re.search(r'(?:[$€£¥]|\b(?:USD|EUR|GBP|JPY|KRW))\s*$', p['extraction_reference']['quote'][:m.start()], re.I)]
                if len(matches) == 1:
                    from .evidence_path import value, normalize_quantity
                    r['fields']['quantity'] = value(doc, quantity, p['reference'])
                    r['quantity_conversion'] = normalize_quantity(quantity['value'])
                    if unit and unit['value'] == name.split()[-1]:
                        r['fields']['unit'] = value(doc, unit, p['reference'])
                    recovered = set(r['fields']) & {'quantity', 'unit'}
                    semantic['semantic_review'] = [f for f in semantic['semantic_review'] if f['field'] not in recovered]
                    for decision in semantic['semantic_checks']['field_decisions']:
                        if decision['field'] in recovered:
                            decision.update(status='ADOPTED', reason='LITERAL_COUNT_PLUS_ORDERED_PRODUCT_NO_FIXED_NOUN_LIST')
                    semantic['semantic_checks']['exact_ordered_object_count'] = 'LITERAL_COUNT_PLUS_ORDERED_PRODUCT_NO_FIXED_NOUN_LIST'
            # This phase exports facts, not TARGET pairing or stage decisions.
            r.update(original_proposal=deepcopy(p), original_model_item=deepcopy(raw),
                     semantic_audit=semantic['semantic_checks'], rejected_fields=semantic['semantic_review'],
                     s_stage='UNKNOWN', source_verified=True, semantic_accuracy='UNVERIFIED_LIMITED_RULES',
                     reading_quality_version=VERSION)
            if unsupported: held.append({'index': index, 'reason': 'UNSUPPORTED_ROLE_OR_ACTUALITY_EVENT_HELD_PRODUCT_ONLY'})
            records.append(r)
        except (ValueError, KeyError, TypeError, APIError) as e:
            held.append({'index': index, 'reason': str(e)})
    records = list({r['id']: r for r in records}.values())
    return stamp_export({'version': VERSION, 'document_id': doc['document_id'], 'original_response': text,
                         'records': records, 'held': held, 'coverage': coverage(doc['body'], windows),
                         'S1_S2_S3': [0, 0, 0], 'operational_integration_enabled': False,
                         'semantic_accuracy': 'NOT_MEASURED_BY_SOURCE_MATCH'})


def save_result(ledger, doc, text, windows, *, raw=None):
    key = 'reading-quality-' + sha([VERSION, doc['document_id'], doc['body_sha256'], text, windows])
    previous = ledger.db.execute('SELECT payload FROM runs WHERE id=?', (key,)).fetchone()
    if previous: return json.loads(previous[0])
    result = validate_packet(text, doc, windows)
    ledger.capture(doc, raw, reading={'original_model_output': text, 'validation': result})
    return ledger.save_run(key, result, 'BACKFILL')
