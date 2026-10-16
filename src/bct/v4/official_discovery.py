"""Research bridge: native official formats -> events -> existing Q2/Q3.

No TARGET list, model, collection service, score, S upgrade or LIVE writer.
The protected prose reader remains the baseline. Typed procurement context can
bind a purchase object without pretending the prose reader discovered it.
"""
from collections import Counter
from datetime import datetime
import json
import re

from bct import precursor_collection as pc, precursor_scope_reader as sr
from bct import forecast_discovery as forecast, precursor_evidence_graph as graph
from bct.objective_lock import stamp_export, require_objective
from . import official_sources as f, quantitative_counterpart as counterpart
from . import quantitative_targets as q3
from .evidence_path import TARGET
from .procurement_review import quantity, project_changes
from .store import sha

VERSION = 'bct-official-discovery-4'
PREFIX = 'OFFICIAL_AUTOMATIC_RESEARCH:'
COUNT = r'(?:[1-9][0-9]*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)'
PURCHASE = re.compile(r'\b(?:supply(?: and installation)? of|purchase of|requirement comprises|procurement of|provision of|supplier to provide|brief description of requirement:)\s+(?:(?P<count>'+COUNT+r')\s+(?:x\s+)?)?(?P<object>[^.;\n]{3,250})', re.I)
NONPHYSICAL = re.compile(r'\b(?:services?|software(?! defined radio)|case management system|licen[cs]es?|subscriptions?|consultancy|journals?|advice|insurance|recruitment|training|funding|shares?|securities)\b', re.I)
NO_VOLUME = re.compile(r'no (?:minimum|maximum|obligation|commitment)|no obligation.{0,40}purchase|establish.{0,70}framework|framework for the hire', re.I)
NEGATED = re.compile(r'\b(?:not ordered|did not order|cancelled order|canceled order|no purchase)\b', re.I)


def demand_status(context, *, previous=None, quantity_now=None):
    """A new identifier/signature is not proof of additional physical demand.

    Comparisons require the caller's same-contract/item lineage, never amounts
    or contract end dates. Replacement and mixed/negated claims stay explicit.
    """
    if re.search(r'\b(?:replacement|replace(?:ment|s|d)?|renewal|renewed|retender|re-tender)\b', context, re.I):
        return 'REPLACEMENT_OR_RENEWAL_NOT_PROVEN_INCREMENT'
    if re.search(r'\b(?:cancelled|canceled|terminated|did not order|not ordered|no additional|not increased)\b', context, re.I):
        return 'CANCELLED_OR_NEGATED_NOT_INCREMENT'
    if previous is not None and quantity_now is not None:
        from decimal import Decimal
        if Decimal(quantity_now) > Decimal(previous): return 'SAME_ITEM_COMMITTED_QUANTITY_INCREASE'
        if Decimal(quantity_now) < Decimal(previous): return 'SAME_ITEM_COMMITTED_QUANTITY_DECREASE'
        return 'UNCHANGED_COMMITTED_QUANTITY'
    # Explicit source wording is a research claim, not a historical comparison.
    if re.search(r'\b(?:additional|incremental|increased)\s+(?:orders?|demand|quantity|units)\b', context, re.I):
        return 'REPORTED_INCREMENT_PRIOR_BASELINE_UNKNOWN'
    return 'UNKNOWN_ORDINARY_ORDER_NOT_PROVEN_INCREMENT'


def located_object(text):
    """Conservative grammar for a native goods contract's object, not a model list.

    Several distinct objects are held; no convenient first substring is picked.
    Model digits, monetary values, options and amounts are not item counts.
    """
    found = []
    for m in PURCHASE.finditer(text):
        a, b = m.start('object'), m.end('object')
        tail = re.search(r',|\b(?:including|incorporating|with|for|to support|to securely|and associated|and software licences)\b', text[a:b], re.I)
        if tail: b = a + tail.start()
        article = re.match(r'(?:a|an|the)\s+', text[a:b], re.I)
        if article: a += article.end()
        while b > a and text[b-1].isspace(): b -= 1
        obj = text[a:b]
        if (not 3 <= len(obj) <= 140 or NONPHYSICAL.search(obj)
                or re.search(r'\b(?:and|or)\b', obj, re.I)
                or obj.casefold() in sr.GENERIC | {'equipment', 'goods', 'items', 'products', 'system'}): continue
        found.append({'product': obj, 'start': a, 'end': b, 'sentence_end': m.end('object'),
                      'count': m['count'], 'count_start': m.start('count') if m['count'] else None})
    # A repeated reference can be grounded to its paragraph, but differing
    # purchase objects in one unitemized field must never be merged.
    if len(found) != 1: return None
    return found[0]


def semantic_object(product, context):
    """A goods code and an exact substring aren't sufficient semantic proof.

    Process-only objects and explicitly cloud/software systems stay proposals;
    underspecified equipment classes stay useful family research signals.
    This is independent of model names, issuers and industry lists.
    """
    name = product.casefold()
    if re.fullmatch(r'(?:calibration|maintenance|repair|inspection|testing)', name):
        return 'UNVERIFIED', ['PROCESS_NOT_PHYSICAL_PURCHASE_OBJECT']
    if (re.search(r'\b(?:platform|system)\b', name) and
            re.search(r'\b(?:cloud services|cloud-based|software licensing|software licences|software licenses|SaaS)\b', context, re.I)):
        return 'UNVERIFIED', ['SOFTWARE_OR_SERVICE_OBJECT_UNPROVEN_PHYSICAL_GOODS']
    if re.fullmatch(r'(?:[a-z-]+\s+){0,2}(?:goods|equipment|machinery|supplies)', name):
        return 'PRODUCT_FAMILY', []
    return 'LOCATED_CONTRACT_OBJECT', []


def prose_document(text, meta, identity):
    return {'document_id': sha([meta['sha256'], identity]), 'body': text,
            'body_sha256': sha(text.encode()), 'raw_sha256': meta['sha256'],
            'origin_url': meta['url'], 'origin_id': meta['source_id'],
            'origin_publisher': meta['source_id'], 'published_at': meta.get('published_at', 'UNKNOWN'),
            'publication_precision': 'UNKNOWN' if meta.get('published_at', 'UNKNOWN') == 'UNKNOWN' else 'TIME',
            'available_at': meta['acquired_at'], 'acquired_at': meta['acquired_at'],
            'provenance': 'PASS', 'primary_source_verified': True, 'body_status': 'PARTIAL',
            'provenance_verified': True}


def extract_ocds(native, meta):
    """Typed contract/award/item identities prevent cross-contract prose mixing.

    Input is the unchanged native package already captured by the common
    collector. Contact/address fields are neither read as objects nor exported.
    """
    events, facts, baseline, failures, documents, sites = [], [], [], [], [], []
    for ri, rel in enumerate(native['releases']):
        base = f'/releases/{ri}'
        awards = {}
        for ai, award in enumerate(rel.get('awards', [])):
            awards.setdefault(award.get('id'), []).append((ai, award))
        for ci, contract in enumerate(rel.get('contracts', [])):
            if not isinstance(contract.get('id'), str) or not contract['id']:
                failures.append({'key': [meta['source_id'], rel['ocid'], rel['id'], ci],
                                 'stage': 'ENTITY', 'reason': 'CONTRACT_ID_ABSENT_NOT_INVENTED'}); continue
            key = [meta['source_id'], rel['ocid'], contract['id']]
            matches = awards.get(contract.get('awardID'), [])
            if len(matches) != 1:
                failures.append({'key': key, 'stage': 'LINKAGE', 'reason': 'AWARD_ID_NOT_UNIQUE'}); continue
            ai, award = matches[0]; tender = rel.get('tender', {})
            category = award.get('mainProcurementCategory', tender.get('mainProcurementCategory'))
            if category != 'goods':
                failures.append({'key': key, 'stage': 'EXTRACTION', 'reason': 'NON_GOODS_OR_UNKNOWN_NATIVE_CATEGORY'}); continue
            items = award.get('items', [])
            # Each explicitly described item is separate. A whole-contract
            # description cannot be assigned to several unidentified items.
            sources = [(f'{base}/awards/{ai}/items/{ii}/description', item['description'], str(item.get('id', ii)), item)
                       for ii, item in enumerate(items) if isinstance(item.get('description'), str)]
            if not sources:
                if len(items) > 1:
                    failures.append({'key': key, 'stage': 'SCOPE', 'reason': 'MULTIPLE_ITEMS_WITHOUT_LOCATED_OBJECTS'}); continue
                sources = [(base+'/tender/description', tender.get('description') or '', 'contract-object', items[0] if items else {})]
            for ptr, text, item_id, item in sources:
                doc = prose_document(text, {**meta, 'published_at': rel.get('date', 'UNKNOWN')}, [*key, rel['id'], item_id])
                # Reuse, do not replace the existing prose extraction path.
                old = pc.structure(doc)
                documents.append(old)
                baseline.extend({'key': key, 'document_id': doc['document_id'], 'role': e['role'],
                                 'product': e.get('scope', {}).get('product', {}).get('value'),
                                 'locator': e['locator']} for e in old['precursor_events'])
                obj = located_object(text)
                if not obj:
                    failures.append({'key': key, 'item_id': item_id, 'stage': 'EXTRACTION', 'reason': 'PHYSICAL_OBJECT_GRAMMAR_UNRESOLVED'}); continue
                reasons = []
                scope_level, semantic_reasons = semantic_object(obj['product'], text)
                reasons += semantic_reasons
                if contract.get('status') != 'active' or award.get('status') != 'active': reasons.append('CONTRACT_OR_AWARD_NOT_ACTIVE')
                if not contract.get('dateSigned'): reasons.append('NO_SIGNED_CONTRACT')
                if NO_VOLUME.search(text) or NO_VOLUME.search(tender.get('title', '')): reasons.append('FRAMEWORK_NO_COMMITTED_VOLUME')
                if NEGATED.search(text): reasons.append('NEGATED_PURCHASE')
                if re.search(r'\b(?:plans?|expects?|intends?) to (?:purchase|order|procure)|proposed purchase|may purchase', text, re.I): reasons.append('PLANNED_NOT_CONFIRMED_PURCHASE')
                codes = [str(c.get('id', '')) for c in [tender.get('classification', {})] + item.get('additionalClassifications', [])]
                if any(code.startswith(('48', '72')) for code in codes): reasons.append('SOFTWARE_OR_IT_SERVICE_CLASSIFICATION')
                related = award.get('relatedLots', [])
                lots = [lot for lot in tender.get('lots', []) if lot['id'] in related]
                if any(lot.get('status') in {'cancelled', 'unsuccessful'} for lot in lots): reasons.append('PARENT_LOT_CONFLICT')
                if not related or not lots: reasons.append('LOT_RELATION_UNKNOWN')
                selectors = {'ocid': base+'/ocid', 'notice_id': base+'/id', 'buyer_id': base+'/buyer/id',
                             'buyer_name': base+'/buyer/name', 'contract_id': base+f'/contracts/{ci}/id',
                             'award_id': base+f'/contracts/{ci}/awardID', 'status': base+f'/contracts/{ci}/status',
                             'signed_date': base+f'/contracts/{ci}/dateSigned', 'supplier_id': base+f'/awards/{ai}/suppliers/0/id',
                             'supplier_name': base+f'/awards/{ai}/suppliers/0/name',
                             'product_label': {'pointer': ptr, 'start': obj['start'], 'end': obj['end']}}
                if obj['count']:
                    selectors['reported_item_quantity_literal'] = {'pointer': ptr, 'start': obj['count_start'], 'end': obj['count_start']+len(obj['count'])}
                specs = list(sr.SPEC.finditer(text[obj['start']:obj['sentence_end']]))
                if len(specs) == 1:
                    sp = specs[0]; selectors['material_specification_literal'] = {
                        'pointer': ptr, 'start': obj['start']+sp.start(), 'end': obj['start']+sp.end()}
                addresses = item.get('deliveryAddresses', [])
                regions = {a['region'] for a in addresses if a.get('region')}
                if len(regions) == 1 and len(items) == 1 and addresses[0].get('region'):
                    selectors['geography'] = base+f'/awards/{ai}/items/0/deliveryAddresses/0/region'
                # Store source values first. Derived count is kept separately.
                fact = f.record(meta, rel['ocid']+':automatic-object:'+contract['id']+':'+item_id,
                                'PROCUREMENT_AUTOMATIC_OBJECT', native, selectors,
                                published=rel.get('date'), publication_basis='RELEASE_DATE_NOT_FIRST_EVENT_PUBLICATION',
                                lineage='OCDS:'+rel['ocid'])
                f.recheck(fact, native); facts.append(fact)
                target = {k: None for k in TARGET}
                target['product'] = {'normalized': sr.product_key(obj['product'])}
                if 'buyer_id' in fact['claims']: target['customer_group'] = {'normalized': fact['claims']['buyer_id']['value']}
                if 'geography' in fact['claims']: target['region'] = {'normalized': fact['claims']['geography']['value']}
                if 'material_specification_literal' in fact['claims']:
                    target['specification'] = {'normalized': fact['claims']['material_specification_literal']['value'].casefold()}
                count = quantity(obj['count'])[0] if obj['count'] else None
                # Contract end is intentionally absent; only a located explicit
                # delivery condition may populate customer_need_date in future.
                event = {'version': VERSION, 'logical_id': sha(['OCDS', rel['ocid'], contract['id'], item_id]), 'source_fact_id': fact['id'],
                         'source_hash': meta['sha256'], 'lineage': fact['source_lineage'],
                         'role': 'DEMAND', 'kind': 'SIGNED_PROCUREMENT', 'actuality': 'ACTUAL' if not reasons else 'UNKNOWN',
                         'state': ('SOURCE_BOUND_PRODUCT_FAMILY' if scope_level == 'PRODUCT_FAMILY' else 'SOURCE_BOUND_EVENT') if not reasons else 'DISCOVERY_PROPOSAL',
                         'scope_level': scope_level,
                         'product': obj['product'], 'target': target, 'quantity': count,
                         'unit': 'ITEMS_OF_LOCATED_PRODUCT' if count else 'UNKNOWN',
                         'period': None, 'customer_need_date': None, 'qualified_capacity': None, 'supply_ready_date': None,
                         'qualified': False, 'coverage_complete': False, 'basis': 'UNKNOWN',
                         'supplier': award.get('suppliers', [{}])[0].get('name'),
                         'published_at': rel.get('date', 'UNKNOWN'), 'first_publication_verified': False,
                         'blockers': reasons, 'demand_increase_vs_prior_period': 'UNKNOWN',
                         'demand_change_class': demand_status(text),
                         'research_only': True, 's_stage': 'UNKNOWN',
                         'extraction_path': 'NATIVE_GOODS_CONTRACT_PLUS_LOCATED_PURCHASE_OBJECT_NOT_LEGACY_PROSE_EVENT'}
                event['id'] = sha(event); events.append(event)
                sid = fact['claims'].get('supplier_id', {}).get('value')
                parties = [(pi, p) for pi, p in enumerate(rel.get('parties', [])) if p.get('id') == sid]
                if len(parties) == 1 and parties[0][1].get('details', {}).get('url'):
                    pi, party = parties[0]
                    sites.append({'event_id': event['id'], 'supplier_id': sid, 'supplier': party['name'],
                                  'reported_site': party['details']['url'], 'source_hash': meta['sha256'],
                                  'locator': base+f'/parties/{pi}/details/url',
                                  'relationship': 'CONTRACT_REPORTED_SUPPLIER_SITE_NOT_MANUFACTURER_OR_QUALIFICATION'})
    return {'events': events, 'facts': facts, 'baseline': baseline, 'failures': failures,
            'documents': documents, 'supplier_sites': sites}


def indicative_supply(raw, meta):
    """Product-page reported stock/lead time, never customer-qualified capacity.

    Reuses exact raw HTML span facts. Multiple h1s or lead-time conditions stay
    unresolved. The unknown publication date is never replaced by acquisition.
    """
    html = raw.decode('utf-8')
    headings = list(re.finditer(r'<h1\b[^>]*>\s*(?P<name>[^<>]{3,140}?)\s*</h1>', html, re.I))
    leads = list(re.finditer(r'Lead time\s+[1-9][0-9]*\s+(?:weeks?|days?)\b', html, re.I))
    if len(headings) != 1 or len(leads) != 1: return None
    h, lead = headings[0], leads[0]
    if NONPHYSICAL.search(h['name']): return None
    span = lambda m, group=0: {'raw_utf8_html': True, 'start': m.start(group), 'end': m.end(group)}
    selectors = {'product_label': span(h, 'name'), 'reported_lead_time_literal': span(lead)}
    stock = list(re.finditer(r'In stock(?=\s*[-<])', html, re.I))
    if len(stock) == 1: selectors['reported_stock_literal'] = span(stock[0])
    fact = f.record(meta, meta['url'], 'PRODUCT_SPECIFICATION_NOT_QUALIFIED_CAPACITY', html, selectors,
                    publication_basis='UNKNOWN', lineage=meta['source_id'])
    f.recheck(fact, html)
    event = {'version': VERSION, 'logical_id': sha([meta['source_id'], meta['url'], 'INDICATIVE_LEAD_TIME']),
             'source_fact_id': fact['id'], 'source_hash': meta['sha256'], 'lineage': fact['source_lineage'],
             'role': 'SUPPLY', 'kind': 'INDICATIVE_STOCK_AND_LEAD_TIME', 'actuality': 'REPORTED_INDICATIVE',
             'state': 'SOURCE_BOUND_INDICATIVE_SUPPLY', 'product': h['name'],
             'scope_level': 'MANUFACTURER_PAGE_MODEL_NOT_CUSTOMER_QUALIFIED_VARIANT',
             'target': {k: {'normalized': sr.product_key(h['name'])} if k == 'product' else None for k in TARGET},
             'quantity': None, 'unit': 'UNKNOWN', 'period': None, 'customer_need_date': None,
             'qualified_capacity': None, 'supply_ready_date': None, 'qualified': False, 'coverage_complete': False,
             'basis': 'UNKNOWN', 'supplier': meta['source_id'], 'published_at': 'UNKNOWN', 'first_publication_verified': False,
             'blockers': ['CUSTOMER_ALLOCATION_UNVERIFIED', 'PUBLICATION_UNKNOWN', 'CONDITIONAL_INDICATIVE_NOT_FIRM_DELIVERY'],
             'demand_increase_vs_prior_period': 'UNKNOWN', 'research_only': True, 's_stage': 'UNKNOWN',
             'extraction_path': 'UNIQUE_PRODUCT_H1_AND_NATIVE_LEAD_TIME_LITERAL'}
    event['id'] = sha(event)
    return fact, event


def context_role(context):
    """Deterministic change semantics, separate from exact-source verification.

    No issuer/product allowlist. A reported plan is not completed supply;
    backlog currency is not physical volume, nor a machine's processing rate
    its manufacturer's capacity. Mixed relations are retained for review.
    """
    q = context
    if re.search(r'\b(?:can process|capable of processing|processes up to|can test)\b', q, re.I):
        return 'CONTEXT', 'PROCESSING_SPECIFICATION_NOT_MANUFACTURER_CAPACITY', 'SPECIFICATION'
    if re.search(r'\b(?:not|never|no longer)\b.{0,25}\b(?:increas|decreas|delay|expand|qualif|cancel)', q, re.I):
        return 'CONTEXT', 'NEGATED_CHANGE', 'NEGATED'
    plan = bool(re.search(r'\b(?:plans?|expects?|targets?|propos\w*|will|would|could|may|aims?|scheduled|anticipated)\b', q, re.I))
    actuality = 'PLANNED_OR_EXPECTED' if plan else 'REPORTED_ACTUAL'
    if re.search(r'\b(?:backlog|bookings|orders?|demand)\b', q, re.I):
        if re.search(r'\b(?:cancel\w*|decreas\w*|declin\w*|fell|reduc\w*)\b', q, re.I):
            return 'RELIEF', 'DEMAND_REDUCTION', actuality
        if re.search(r'\b(?:backlog|bookings)\b', q, re.I):
            return 'DEMAND', 'BACKLOG_OR_BOOKINGS', actuality
        if re.search(r'\b(?:reserv\w*|prepayment|long.term)\b', q, re.I):
            return 'DEMAND', 'RESERVATION', actuality
        if re.search(r'\b(?:orders?|demand)\b', q, re.I):
            return 'DEMAND', 'ORDER_OR_DEMAND_CLAIM', actuality
    if re.search(r'\b(?:plant|factory|facility|production line|commission\w*|permit|certif\w*|qualif\w*)\b', q, re.I):
        if re.search(r'\b(?:delay\w*|postpon\w*|await\w*|pending|closed?|closure|suspend\w*|restrict\w*)\b', q, re.I):
            return 'CONSTRAINT', 'FACILITY_OR_QUALIFICATION_CONSTRAINT', actuality
        if re.search(r'\b(?:completed|opened|operational|commissioned|certified|qualified|approved)\b', q, re.I):
            return 'RELIEF' if not plan else 'SUPPLY_PLAN', 'FACILITY_OR_QUALIFICATION_READY', actuality
    if re.search(r'\b(?:production|output|capacity|utilization|yield|inventory|inventories|lead.times?|export|import|supply)\b', q, re.I):
        if re.search(r'\b(?:can|capable of|up to|process\w*|test\w*|measurement|bandwidth)\b', q, re.I) and not re.search(r'\b(?:increased|decreased|expanded|delayed|reduced)\b', q, re.I):
            return 'CONTEXT', 'PROCESSING_SPECIFICATION_NOT_MANUFACTURER_CAPACITY', 'SPECIFICATION'
        down = bool(re.search(r'\b(?:decreas\w*|declin\w*|reduc\w*|fell|delay\w*|restrict\w*|ban\w*|shortage|limited|unavailable|suspend\w*)\b', q, re.I))
        up = bool(re.search(r'\b(?:increas\w*|rose|expand\w*|doubl\w*|recover\w*|restor\w*|resum\w*)\b', q, re.I))
        lead = bool(re.search(r'\blead.times?\b', q, re.I))
        if up and down: return 'CONTEXT', 'MIXED_CHANGE_REQUIRES_ATTRIBUTION', 'UNKNOWN'
        if down or up:
            constraint = up if lead else down
            return ('CONSTRAINT' if constraint else 'SUPPLY_PLAN' if plan else 'RELIEF'), 'REPORTED_SUPPLY_CHANGE', actuality
    if re.search(r'\b(?:CAPEX|capital expenditure|capacity expansion|investment|new factory|new plant)\b', q, re.I):
        return 'SUPPLY_PLAN', 'INVESTMENT_NOT_AVAILABLE_CAPACITY', 'PLANNED_OR_EXPECTED'
    return 'CONTEXT', 'NO_DIRECTIONAL_CHANGE_PROVEN', 'UNKNOWN'


def html_source(raw):
    """Decode only an explicit gzip signature; cap expansion before parsing."""
    import gzip
    from io import BytesIO
    if raw.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=BytesIO(raw)) as stream: decoded = stream.read(4_000_001)
    else: decoded = raw
    if len(decoded) > 4_000_000: raise ValueError('CONTEXT_DECODED_SIZE_LIMIT')
    decoded.decode('utf-8', errors='strict')  # unknown encodings remain held
    return decoded


def read_context(raw, meta):
    """Reuse the source/scope/temporal readers on an actual official HTML body.

    A complete sentence must map exactly once into the unchanged raw document.
    Its product position is then resolved *inside that sentence*, never by a
    convenient first global product hit. Markup/ambiguous quotations are held.
    Only short factual scalars, positions and hashes leave this function.
    """
    from bct import future_body
    counterpart.relation_url(meta['url'])
    if sha(raw) != meta['sha256']: raise ValueError('CONTEXT_NATIVE_HASH')
    decoded = html_source(raw)
    html = decoded.decode('utf-8', errors='strict')
    extraction = future_body.extract_document(html, content_type='text/html')
    body = extraction.get('body', '')
    doc = prose_document(body, meta, ['OFFICIAL_CONTEXT', meta['url']])
    doc['body_status'] = extraction['body_status']
    structured = pc.structure(doc)
    events, holds = [], []
    statements = list(structured['precursor_events'])
    # The old trigger list misses output/yield changes without the phrase
    # 'production capacity'. Reuse its sentence and physical-object binding,
    # extending only trigger coverage in this research path.
    positions = {(e['locator']['start'], e['locator']['end']) for e in statements}
    for line in sr.sentences(doc, sr.allowed_lines(doc, decoded)[0]):
        if (line['start'], line['end']) in positions or context_role(line['quote'])[0] == 'CONTEXT': continue
        p = sr.bound_product(line, sr._products(doc, line))
        statements.append({'source_quote': line['quote'], 'locator': {'start': line['start'], 'end': line['end']},
                           'scope': {'product': p} if p else {}, 'quantity': 'UNKNOWN', 'unit': 'UNKNOWN'})
    for old in statements:
        context = old['source_quote']; start = old['locator']['start']; end = old['locator']['end']
        role, kind, actuality = context_role(context)
        locations = [m.start() for m in re.finditer(re.escape(context), html)]
        if len(locations) != 1:
            holds.append({'stage': 'EXTRACTION', 'reason': 'RAW_CONTEXT_AMBIGUOUS' if locations else 'RAW_CONTEXT_MARKUP_ALIGNMENT_UNSUPPORTED',
                          'body_position': old['locator'], 'context_sha256': sha(context.encode())}); continue
        field = old['scope'].get('product')
        # Incomplete scope is preserved; it is not a verified physical event.
        product = field['value'] if field else None
        if field and not start <= field['locator']['start'] < field['locator']['end'] <= end:
            # Cross-sentence scope references need separate relation proof.
            holds.append({'stage': 'ENTITY', 'reason': 'PRODUCT_OUTSIDE_EVENT_NEEDS_RELATION_PROOF', 'body_position': old['locator']})
            product = None; field = None
        at = locations[0]
        position = ({'start': at + field['locator']['start']-start, 'end': at + field['locator']['end']-start} if field else None)
        if position and html[position['start']:position['end']] != product: raise ValueError('CONTEXT_PRODUCT_POSITION')
        amount = old.get('quantity')
        target = {k: None for k in TARGET}
        if product: target['product'] = {'normalized': sr.product_key(product)}
        scope_positions = {}
        for key in ('specification', 'region', 'customer_group'):
            attr = old['scope'].get(key)
            if attr and start <= attr['locator']['start'] < attr['locator']['end'] <= end:
                loc = {k: at+v-start for k,v in attr['locator'].items()}
                if html[loc['start']:loc['end']] != attr['value']: raise ValueError('CONTEXT_SCOPE_POSITION')
                target[key] = {'normalized': attr['value'].casefold()}; scope_positions[key] = loc
        e = {'logical_id': sha([meta['url'], kind, product, sha(context.encode())]), 'source_hash': meta['sha256'],
             'source_url': meta['url'], 'lineage': meta['source_id'], 'published_at': meta.get('published_at') or 'UNKNOWN',
             'acquired_at': meta['acquired_at'], 'body_sha256': doc['body_sha256'], 'body_position': old['locator'],
             'raw_position': {'start': at, 'end': at+len(context)}, 'context_sha256': sha(context.encode()),
             'product': product, 'product_position': position, 'role': role, 'kind': kind, 'actuality': actuality,
             'state': 'SOURCE_BOUND_REPORTED_CHANGE' if product and role != 'CONTEXT' else 'CONTEXT_REVIEW_PENDING',
             'quantity': None if amount in (None, 'UNKNOWN') else amount, 'unit': old.get('unit', 'UNKNOWN'),
             'quantity_meaning': 'REPORTED_LITERAL_NOT_QUALIFIED_AVAILABLE_SUPPLY',
             'target': target, 'scope_positions': scope_positions,
             'temporal_references': [{'start': x['locator']['start'], 'end': x['locator']['end']} for x in old.get('raw_period_references', [])],
             'demand_change_class': demand_status(context) if role in {'DEMAND','RELIEF'} else None,
             'qualified': False, 'coverage_complete': False, 'customer_need_date': None, 'supply_ready_date': None,
             'qualified_capacity': None, 'first_publication_verified': False, 'research_only': True, 's_stage': 'UNKNOWN'}
        e['id'] = sha(e); events.append(e)
    return {'source': {**{k: meta[k] for k in ['source_id', 'url', 'sha256', 'acquired_at']},
                       'body_sha256': doc['body_sha256'], 'body_status': extraction['body_status'],
                       'read_characters': len(body), 'scope': 'EXTRACTED_BODY_NOT_WHOLE_NATIVE_DOCUMENT',
                       'position_space': 'GZIP_DECODED_UTF8_HTML_CHARACTERS' if decoded is not raw else 'UTF8_HTML_CHARACTERS',
                       'published_at': meta.get('published_at') or 'UNKNOWN'}, 'events': events, 'holds': holds}


def context_seeds(results):
    """Both directions feed the same existing four-facet relation queue."""
    out = []
    for r in results:
        for e in r['events']:
            if e['state'] != 'SOURCE_BOUND_REPORTED_CHANGE': continue
            role = 'DEMAND' if e['role'] == 'DEMAND' else 'CONSTRAINT' if e['role'] == 'CONSTRAINT' else 'SUPPLY_PLAN'
            out.append({'id': e['id'], 'event_key': e['logical_id'], 'product': e['product'], 'role': role,
                        'source': {'document_id': e['logical_id'], 'body_sha256': e['body_sha256'],
                                   'origin_url': e['source_url'], 'published_at': e['published_at']},
                        'fields': {'specification': None, 'region': None, 'customer': None, 'supplier': None,
                                   'quantity': e['quantity'], 'need_window': None, 'qualified_capacity': None, 'delivery': None}})
    return out


def save_context(ledger, result, *, raw=None, meta=None):
    """Verify with the captured native before retaining non-body research state.

    A restored receipt is evidence of prior acquisition, not a claim that its
    unavailable original has just been verified again.
    """
    if raw is None or meta is None or read_context(raw, meta) != result:
        raise ValueError('CONTEXT_REPLAY_REQUIRED')
    reason = 'OFFICIAL_BIDIRECTIONAL_CONTEXT:'+sha(result)
    with ledger.db:
        old = ledger.db.execute("SELECT 1 FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.reason')=?", (reason,)).fetchone()
        if not old: ledger.event('QUANTITATIVE_VALIDATION', {'reason': reason, 'originals_modified': False, 'policy': result})
    return {'added': int(not old), 'events': len(result['events'])}


def structured_supply_changes(ledger):
    """Reuse verified Q1 EIA rows; compare present-present facility identities.

    Missing rows are not retirements. Date/nameplate edits are reported edits,
    not proved production delays or qualified customer-allocated capacity.
    This reads facts, never reruns a model or downloads a completed workbook.
    """
    from collections import defaultdict
    from .quantitative import research_export
    groups = defaultdict(lambda: defaultdict(list))
    for obs in research_export(ledger)['observations']:
        r = obs['record']
        if r['source_id'] != 'eia' or r['metric'] != 'nameplate_capacity': continue
        groups[(r['entity_or_facility_id'], r['product_or_classification'], r['geography'], r['unit_original'])][r['period_start']].append(obs)
    changes = []; holds = []
    for key, periods in sorted(groups.items()):
        for first, second in zip(sorted(periods), sorted(periods)[1:]):
            if len(periods[first]) != 1 or len(periods[second]) != 1:
                holds.append({'facility_id': key[0], 'periods': [first, second], 'reason': 'AMBIGUOUS_FACILITY_ROWS'}); continue
            a, b = periods[first][0], periods[second][0]; x, y = a['record'], b['record']
            if x['unit_original'] != y['unit_original']: continue
            before, after = x['attributes']['sheet'], y['attributes']['sheet']
            role = 'RELIEF' if before == 'Planned' and after == 'Operating' else 'CONSTRAINT' if before == 'Operating' and after == 'Retired' else 'CONTEXT'
            dates = lambda r: [r['attributes'].get('Planned Operation Year'), r['attributes'].get('Planned Operation Month')]
            capacity_changed = x['value_decimal_or_null'] != y['value_decimal_or_null']
            dates_changed = dates(x) != dates(y)
            if before == after and not dates_changed and not capacity_changed: continue
            e = {'facility_id': key[0], 'technology': key[1], 'region': key[2], 'unit': key[3],
                 'periods': [first, second], 'before_status': before, 'after_status': after,
                 'before_nameplate': x['value_decimal_or_null'], 'after_nameplate': y['value_decimal_or_null'],
                 'before_planned_date': dates(x), 'after_planned_date': dates(y),
                 'role': role, 'kind': 'REPORTED_FACILITY_STATUS_CHANGE' if role != 'CONTEXT' else 'RECORD_REVISION_NOT_PROVEN_SUPPLY_CHANGE',
                 'actuality': 'REPORTED_STATUS_NOT_DELIVERY', 'product': 'electricity',
                 'source_ids': [a['id'], b['id']], 'source_hashes': [x['raw_or_safe_payload_hash'], y['raw_or_safe_payload_hash']],
                 'positions': [x['source_locator'], y['source_locator']], 'source_urls': [x['source_url'], y['source_url']],
                 'published_at': [x['published_at'], y['published_at']], 'lineage': 'eia',
                 'customer_need_date': None, 'qualified_capacity': None, 'qualified': False,
                 'coverage_complete': False, 's_stage': 'UNKNOWN', 'research_only': True}
            e['id'] = sha(e); changes.append(e)
    return {'changes': changes, 'holds': holds, 'source_HTTP': 0, 'CPU_windows': 0,
            'originals_rechecked_here': False, 'basis': 'PREVIOUSLY_LOCATED_Q1_NATIVE_ROWS_NOT_COMPLETE_QUALIFIED_SUPPLY'}


def seeds(events, facts):
    idx = {f['id']: f for f in facts}; out = []
    for e in events:
        if e['state'] not in {'SOURCE_BOUND_EVENT', 'SOURCE_BOUND_PRODUCT_FAMILY'}: continue
        row = idx[e['source_fact_id']]
        out.append({'id': e['id'], 'event_key': e['logical_id'], 'product': e['product'], 'role': 'DEMAND',
                    'source': {'document_id': e['source_fact_id'], 'body_sha256': e['source_hash'],
                               'origin_url': row['url'], 'published_at': e['published_at']},
                    'fields': {'specification': None, 'region': (e['target']['region'] or {}).get('normalized'),
                               'customer': row['claims'].get('buyer_name', {}).get('value'), 'supplier': e['supplier'],
                               'quantity': e['quantity'], 'need_window': None, 'qualified_capacity': None, 'delivery': None}})
    return out


def typed_routes(records):
    """All collected source families share routing, without upgrading context."""
    routes = {'PROCUREMENT_TENDER': 'TENDER_NOT_ORDER', 'PROCUREMENT_AWARD': 'AWARD_PHYSICAL_OBJECT_PENDING',
              'PROCUREMENT_CONTRACT': 'CONTRACT_NATIVE_OBJECT_QUEUE',
              'CONNECTION_PROJECT': 'PROJECT_PLAN_OR_STATUS_NOT_EQUIPMENT_CAPACITY',
              'TRADE_STATISTIC': 'INDUSTRY_CONTEXT_NOT_CUSTOMER_ORDER',
              'REGULATORY_DOCUMENT': 'DOCUMENT_METADATA_BODY_PENDING', 'LEGAL_ENTITY': 'ENTITY_IDENTITY_ONLY',
              'PROGRAM_CONTEXT_NOT_QUALIFIED_SUPPLY': 'PROGRAM_NOT_QUALIFIED_SUPPLY'}
    counts = Counter()
    for row in records:
        f.validate(row)
        counts[(row['source_id'], routes.get(row['record_kind'], 'LOCATED_RESEARCH_FACT'))] += 1
    return [{'source_id': source, 'route': route, 'versions': count} for (source, route), count in sorted(counts.items())]


def counterparts(events, facts, documents, *, as_of):
    """Existing opposite-side search and relation queue; no network or new crawler.

    Actual stored documents are inspected; generating queries is reported
    separately from an executed external search. Upstream IDs retain lineage.
    """
    ss = seeds(events, facts)
    found = [counterpart.discover(s, documents, as_of=as_of, limit=3) for s in ss]
    tasks = counterpart.relation_tasks(ss)
    for task in tasks:
        pointers = counterpart.local_relation_pointers(task, documents, as_of=as_of, limit=3)
        task['scope']['automatic_stored_search'] = pointers
        task['search_state'] = 'STORED_SOURCE_SEARCH_EXECUTED_EXTERNAL_INDEX_PENDING'
        task['id'] = sha(['q2-relation-state-1', {k: v for k, v in task.items() if k != 'id'}])
    return {'searches': found, 'relation_tasks': tasks, 'stored_documents_searched': len(documents),
            'external_requests': 0, 'independent_pairs': 0}


def q3_input(events, facts, *, as_of, documents=()):
    """Pass only qualified complete scope into the unchanged strict engine.

    Current source formats do not assert entire qualified supply pools. Their
    absence is a recorded COMPARISON dependency, never an S3 substitution.
    """
    reasons = Counter(); eligible = []
    demands = [e for e in events if e['role'] == 'DEMAND' and e['state'] == 'SOURCE_BOUND_EVENT']
    supplies = [e for e in events if e['role'] == 'SUPPLY' and e['state'] == 'SOURCE_BOUND_EVENT']
    for d in demands:
        if not supplies: reasons['LINKAGE_NO_VERIFIED_OPPOSITE_SIDE'] += 1
        for s in supplies:
            def item(e):
                return {**e, 'lineage': e['lineage'], 'source_verified': e['state'] == 'SOURCE_BOUND_EVENT', 'measurement_type': 'PHYSICAL'}
            ok, reason = q3.comparable(item(d), item(s))
            if not ok: reasons[reason] += 1; continue
            if not s.get('qualified') or not s.get('coverage_complete'):
                reasons['QUALIFIED_ENTIRE_SUPPLY_SCOPE_UNPROVEN'] += 1; continue
            if d['source_hash'] == s['source_hash']:
                reasons['INDEPENDENCE_COPIED_SOURCE'] += 1; continue
            eligible.append((d, s))
    # Reuse the actual evidence graph and its fully located signal projection,
    # including relief, exact scope, provenance and12-36 month checks. Structured
    # proposals aren't inserted into prose or disguised as old parser events.
    evaluated = graph.analyze(list(documents), now=as_of, mode='BACKFILL')
    strict_batch = evaluated['protected_batch']
    # Only the graph's source-backed, qualified total/unallocated supply enters
    # the unchanged strict forecast engine. EARLY != qualified supply gap.
    selected = []
    for pair in evaluated['pairs']:
        if pair.get('engine_state') != 'FORWARDED_TO_UNCHANGED_EARLY_ENGINE': continue
        members = [s for s in strict_batch['signals'] if s['event_id'] in {pair['demand_event'], pair['supply_event']}]
        demand = next((s for s in members if s['role'] == 'DEMAND'), None)
        supply = next((s for s in members if s['role'] == 'SUPPLY'), None)
        if not demand or not supply or not supply.get('qualified') or not supply.get('coverage_complete'): continue
        need, ready = pair['comparison'].get('need'), pair['comparison'].get('readiness')
        if not need or not ready or need['start'] == 'UNKNOWN' or ready['start'] == 'UNKNOWN': continue
        period = {k: need[k] for k in ('start', 'end')}
        # Timing evidence remains an interval; latest customer need versus
        # earliest supplier readiness is the conservative gap comparison.
        selected.extend([{**demand, 'period': period, 'need_date': need['end']},
                         {**supply, 'period': period, 'available_date': ready['start']}])
    strict_result = forecast.discover(stamp_export({'documents': list(documents), 'signals': selected}), now=as_of, mode='BACKFILL')
    return {'eligible_pairs': len(selected)//2, 'reasons': dict(reasons), 'strict_engine_state': strict_result['state'],
            'strict_engine_candidates': len(strict_result['candidates']), 'formal_Q3_complete': False,
            'graph_independent_pairs': evaluated['independent_pairs'], 'graph_complete_target_events': evaluated['complete_target_events'],
            'graph_forwarded_signals': len(strict_batch['signals']),
            'forecast_signal_binding': 'EXISTING_EVIDENCE_GRAPH_TO_STRICT_FORECAST_RESEARCH_ONLY', 'S2': 0, 'S3': 0}


def save(ledger, packet):
    require_objective(packet)
    if packet['format'] != VERSION or packet['plan_id'] != 'BCT-V4-Q-1.0': raise ValueError('AUTOMATIC_RESEARCH_FORMAT')
    if packet['Q3']['S2'] or packet['Q3']['S3']: raise ValueError('AUTOMATIC_PROMOTION_FORBIDDEN')
    current = {r['id']: r for p, in ledger.db.execute('SELECT payload FROM events WHERE kind=?', (f.KIND,)) for r in [json.loads(p)]}
    for e in packet['events']:
        r = current.get(e['source_fact_id'])
        if not r or r['source_hash'] != e['source_hash'] or r['claims']['product_label']['value'] != e['product']:
            raise ValueError('AUTOMATIC_SOURCE_BINDING_MISMATCH')
        if e['s_stage'] != 'UNKNOWN' or e['qualified'] or not e['research_only']: raise ValueError('AUTOMATIC_EVENT_PROMOTION')
        if e['id'] != sha({k: v for k, v in e.items() if k != 'id'}): raise ValueError('AUTOMATIC_EVENT_ID')
        if e['target']['product'] != {'normalized': sr.product_key(e['product'])} or e['target']['supply_pool'] is not None:
            raise ValueError('AUTOMATIC_TARGET_SCOPE')
        if e['customer_need_date'] is not None or e['qualified_capacity'] is not None or e['supply_ready_date'] is not None:
            raise ValueError('AUTOMATIC_UNSUPPORTED_NEED_OR_CAPACITY')
        if e['quantity'] != (quantity(r['claims']['reported_item_quantity_literal']['value'])[0] if 'reported_item_quantity_literal' in r['claims'] else None):
            raise ValueError('AUTOMATIC_QUANTITY_DERIVATION')
    reason = PREFIX+sha(packet)
    with ledger.db:
        old = ledger.db.execute("SELECT 1 FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.reason')=?", (reason,)).fetchone()
        if not old: ledger.event('QUANTITATIVE_VALIDATION', {'reason': reason, 'originals_modified': False, 'policy': packet})
    return {'added': 0 if old else 1, 'events': len(packet['events']), 'Q3_pairs': 0, 'S2': 0, 'S3': 0}


def save_cursors(ledger, packet):
    """Import executed data-page receipts, preserving failure then repair order."""
    from urllib.parse import urlsplit, parse_qsl
    require_objective(packet); added = 0
    for event in packet['records']:
        if event.get('originals_modified') is not False or set(event)-{'reason', 'originals_modified', 'policy'}:
            raise ValueError('AUTOMATIC_CURSOR_FIELDS')
        p = event['policy']; source = p['source_id']
        if source not in {'find_tender', 'contracts_finder'} or not p['job_id'].startswith('official-daily-'+source+'-'):
            raise ValueError('AUTOMATIC_CURSOR_JOB')
        day = p['job_id'][-10:]; datetime.fromisoformat(day)
        f.safe_url(source, p['url']); query = dict(parse_qsl(urlsplit(p['url']).query))
        start, end = ('updatedFrom', 'updatedTo') if source == 'find_tender' else ('publishedFrom', 'publishedTo')
        if query[start][:10] != day or query[end][:10] != day or type(p['page']) is not int or p['page'] < 1:
            raise ValueError('AUTOMATIC_CURSOR_SCOPE')
        if p['status'] not in {'FACTS_STORED', 'BLOCKED'}: raise ValueError('AUTOMATIC_CURSOR_STATUS')
        reason = 'OFFICIAL_AUTO_IMPORTED_CURSOR:'+sha(event)
        with ledger.db:
            if not ledger.db.execute("SELECT 1 FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.reason')=?", (reason,)).fetchone():
                ledger.event('QUANTITATIVE_VALIDATION', {**event, 'reason': reason}); added += 1
    return {'added': added, 'receipts': len(packet['records'])}


def enqueue(ledger, native, meta):
    """Collector hook for NEW native versions; existing page cursors stay intact."""
    result = extract_ocds(native, meta)
    f.save(ledger, result['facts'])
    packet = stamp_export({'format': VERSION, 'plan_id': 'BCT-V4-Q-1.0', 'events': result['events'],
                          'failures': result['failures'], 'supplier_sites': result['supplier_sites'],
                          'baseline_counts': {'events': len(result['baseline']), 'products': sum(bool(e['product']) for e in result['baseline'])},
                          'Q3': q3_input(result['events'], result['facts'], as_of=meta['acquired_at'], documents=result['documents']),
                          'scope': 'AUTOMATIC_NEW_NATIVE_VERSION_RESEARCH_NOT_LIVE_REGISTRATION'})
    return save(ledger, packet)
