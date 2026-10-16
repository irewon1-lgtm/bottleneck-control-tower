"""Bounded source review downstream of OCDS; no model, forecast or scheduler.

Classification is routing, not product verification. Short reviewed literals
retain native positions in official facts; all missing customer/supply facts
remain missing. Uses the existing Ledger validation-event storage.
"""
from collections import Counter
from datetime import datetime
import json
import re

from bct.objective_lock import require_objective
from . import official_sources as f
from .store import sha

PREFIX = 'OFFICIAL_CONTRACT_REVIEW:'
CATEGORIES = {'PHYSICAL_PRODUCT', 'FACILITY_INSTALLATION', 'SUPPLY_CHAIN',
              'GENERAL_SERVICE_OR_CIVIL_WORK', 'UNRESOLVED'}
WORDS = dict(zip('one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(), range(1, 21)))


def quantity(literal):
    """Only an explicitly reviewed count literal; never scan arbitrary numbers."""
    if literal in WORDS: return str(WORDS[literal]), 'ENGLISH_CARDINAL_1_TO_20'
    if re.fullmatch(r'[1-9][0-9]*', literal): return literal, 'EXACT_POSITIVE_INTEGER'
    raise ValueError('REVIEW_QUANTITY_NOT_EXPLICIT_COUNT')


def review(contract, award, category, product=None, *, framework=False):
    for row in [contract, award] + ([product] if product else []): f.validate(row)
    c, a = contract['claims'], award['claims']
    if (category not in CATEGORIES or contract['source_lineage'] != award['source_lineage']
            or c['notice_id']['value'] != a['notice_id']['value']
            or c['award_id']['value'] != a['award_id']['value']):
        raise ValueError('CONTRACT_AWARD_SCOPE_MISMATCH')
    if product and (product['source_lineage'] != contract['source_lineage']
                    or product['claims']['contract_id']['value'] != c['contract_id']['value']
                    or product['claims']['notice_id']['value'] != c['notice_id']['value']):
        raise ValueError('PRODUCT_CONTRACT_SCOPE_MISMATCH')
    pc = product['claims'] if product else {}
    reasons = []
    if c.get('status', {}).get('value') != 'active': reasons.append('CONTRACT_NOT_ACTIVE')
    if 'signed_date' not in c: reasons.append('UNSIGNED')
    if a.get('status', {}).get('value') != 'active': reasons.append('AWARD_NOT_ACTIVE')
    if pc.get('lot_status', {}).get('value') in {'cancelled', 'unsuccessful'}: reasons.append('PARENT_LOT_CONFLICT')
    if framework: reasons.append('FRAMEWORK_NO_COMMITTED_VOLUME')
    if not product: reasons.append('PHYSICAL_OBJECT_NOT_SOURCE_REVIEWED')
    qty = quantity(pc['reported_item_quantity_literal']['value']) if 'reported_item_quantity_literal' in pc else (None, None)
    adopted = product is not None and category == 'PHYSICAL_PRODUCT' and not reasons
    row = {'contract_fact_id': contract['id'], 'award_fact_id': award['id'],
           'category': category, 'product_fact_id': product['id'] if product else None,
           'state': 'CONFIRMED_PHYSICAL_CONTRACT' if adopted else 'HELD_OR_OUT_OF_PHYSICAL_SCOPE',
           'quantity': qty[0], 'quantity_rule': qty[1],
           'quantity_unit': 'ITEMS_OF_REVIEWED_PRODUCT' if qty[0] else 'UNKNOWN',
           'customer_need_date': 'UNKNOWN', 'qualified_capacity': 'UNKNOWN',
           'supply_ready_date': 'UNKNOWN', 'hold_reasons': reasons,
           'demand_increase_vs_prior_period': 'UNKNOWN',
           'first_publication': 'UNKNOWN', 'Q3_eligible': False, 's_stage': 'UNKNOWN',
           'review_method': 'CODEX_DIRECT_SOURCE_REVIEW_NOT_HUMAN_OR_INDEPENDENT_ACCURACY'}
    row['id'] = sha(row)
    return row


def project_changes(rows):
    """Compare actual ERCOT snapshots by sheet+INR, not filename or row order.

    Absence is not withdrawal. Explicit cancellation/commissioning remains a
    project status record, not equipment demand or allocable product capacity.
    """
    versions = {}
    for r in rows:
        if r['source_id'] != 'ercot': continue
        f.validate(r)
        if r['published_at'] == 'UNKNOWN': continue
        versions.setdefault(r['logical_id'], {})[r['published_at']] = r
    changes = []
    fields = ('reported_project_MW', 'planned_service_date', 'commissioning_status', 'approval_date', 'cancellation_date')
    for group in versions.values():
        if len(group) < 2: continue
        ordered = sorted(group.values(), key=lambda r: datetime.fromisoformat(r['published_at']))
        old, new = ordered[-2:]
        for name in fields:
            before, after = old['claims'].get(name), new['claims'].get(name)
            # Missing data isn't a proved change of physical state.
            if not before or not after or type(before['value']) is not type(after['value']): continue
            if before['value'] == after['value']: continue
            value = {'project_lineage': new['source_lineage'], 'native_id': new['native_id'],
                     'field': name, 'before_fact_id': old['id'], 'after_fact_id': new['id'],
                     'before': before['value'], 'after': after['value'],
                     'interpretation': 'REPORTED_PROJECT_REVISION_NOT_PROVEN_PHYSICAL_CHANGE',
                     'Q3_eligible': False}
            value['id'] = sha(value); changes.append(value)
    return changes


def validate_packet(packet, records):
    require_objective(packet)
    if packet['plan_id'] != 'BCT-V4-Q-1.0' or packet['Q3_pairs'] != 0 or packet['S2'] != 0 or packet['S3'] != 0:
        raise ValueError('CONTRACT_REVIEW_PROMOTION_FORBIDDEN')
    index = {r['id']: r for r in records}
    upstream = {r['id'] for r in records if r['record_kind'] == 'PROCUREMENT_CONTRACT'}
    if not {r['contract_fact_id'] for r in packet['reviews']} <= upstream:
        raise ValueError('CONTRACT_REVIEW_COVERAGE_CHANGED')
    if len({r['contract_fact_id'] for r in packet['reviews']}) != len(packet['reviews']):
        raise ValueError('DUPLICATE_CONTRACT_REVIEW')
    for row in packet['reviews']:
        expected = review(index[row['contract_fact_id']], index[row['award_fact_id']], row['category'],
                          index[row['product_fact_id']] if row['product_fact_id'] else None,
                          framework='FRAMEWORK_NO_COMMITTED_VOLUME' in row['hold_reasons'])
        if row != expected: raise ValueError('CONTRACT_REVIEW_DERIVATION_CHANGED')
    expected_changes = {c['id']: c for c in project_changes(records)}
    for change in packet['project_changes']:
        if expected_changes.get(change['id']) != change: raise ValueError('PROJECT_CHANGE_NOT_IN_SNAPSHOTS')
    return {'contracts': len(packet['reviews']), 'categories': dict(Counter(r['category'] for r in packet['reviews'])),
            'confirmed_physical_contracts': sum(r['state'] == 'CONFIRMED_PHYSICAL_CONTRACT' for r in packet['reviews']),
            'confirmed_with_count': sum(r['state'] == 'CONFIRMED_PHYSICAL_CONTRACT' and r['quantity'] is not None for r in packet['reviews']),
            'project_revision_fields': len(packet['project_changes']),
            'project_revision_targets': len({r['project_lineage'] for r in packet['project_changes']}),
            'Q3_pairs': 0, 'S2': 0, 'S3': 0}


def save(ledger, packet):
    # Verify every upstream reference before any append; stale/missing originals
    # are not silently replaced with a local older DB.
    records = [json.loads(p) for p, in ledger.db.execute('SELECT payload FROM events WHERE kind=?', (f.KIND,))]
    summary = validate_packet(packet, records)
    reason = PREFIX + sha(packet)
    with ledger.db:
        prior = ledger.db.execute("SELECT 1 FROM events WHERE kind='QUANTITATIVE_VALIDATION' AND json_extract(payload,'$.reason')=?", (reason,)).fetchone()
        if not prior: ledger.event('QUANTITATIVE_VALIDATION', {'reason': reason, 'originals_modified': False, 'policy': packet})
    return {**summary, 'added_review_batches': 0 if prior else 1}
