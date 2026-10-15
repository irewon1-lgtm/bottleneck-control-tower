"""Bounded, BACKFILL-only source review handoff to existing located evidence.

No fetcher, model, LIVE first observation, scheduler or operating write path.
Source adjudication is explicitly attributed; it is not independent AI quality.
"""
from copy import deepcopy
from datetime import date

from bct.objective_lock import stamp_export
from . import evidence_path
from .store import sha

VERSION = 'bct-source-linkage-3'


def prepare(documents, cases, *, as_of):
    day = date.fromisoformat(as_of)
    docs = {d['document_id']: d for d in documents}
    if len(docs) != len(documents): raise ValueError('DUPLICATE_DOCUMENT_ID')
    proposals, reviews, dispositions = {}, {}, []
    for case in cases:
        row = deepcopy(case)
        row.update(s_stage='UNKNOWN', mode='BACKFILL', live_discovery=False)
        try:
            doc = docs[case['document_id']]
            if sha(doc['body'].encode()) != doc['body_sha256']: raise ValueError('BODY_HASH_MISMATCH')
            review = case['review']
            review = deepcopy(review)
            # An issuer/manufacturer name is not a verified customer-qualified
            # supplier pool. Preserve the original review and literal as a
            # reported supplier field without filling that TARGET dimension.
            if case.get('qualified_supplier_pool_status') != 'VERIFIED' and 'supply_pool' in review.get('fields', {}):
                review['fields']['reported_supplier'] = review['fields'].pop('supply_pool')
            refs = review['references'] + [review['product_reference']]
            for ref in refs: evidence_path.reference(doc, ref)
            row['exact_source_status'] = 'PASS_NOT_SEMANTIC_PROOF'
            if doc.get('provenance') != 'PASS' or not doc.get('primary_source_verified'):
                raise ValueError('PRIMARY_SOURCE_OR_PROVENANCE_HELD')
            publication = date.fromisoformat(doc['published_at'][:10])
            acquired = date.fromisoformat(doc['acquired_at'][:10])
            if publication > day or publication > acquired: raise ValueError('FUTURE_SOURCE_NOT_ALLOWED')
            if case.get('excluded_reason'): raise ValueError(case['excluded_reason'])
            # A single continuous context preserves intervening qualification,
            # negation and counterevidence, rather than concatenating fragments.
            a, b = min(r['start'] for r in refs), max(r['end'] for r in refs)
            context = {'start': a, 'end': b, 'quote': doc['body'][a:b]}
            p = {'reference': context,
                 'product': {'value': review['product_reference']['quote'], 'reference': review['product_reference']},
                 'role': review['role'], 'actuality': review['actuality'],
                 'fields': {k: {'value': v['surface'], 'reference': v['reference']} for k, v in review.get('fields', {}).items()},
                 'review_fields': deepcopy(review.get('fields', {}))}
            if case.get('origin_event_id'): p['origin_event_id'] = case['origin_event_id']
            checked = evidence_path.accept(doc, p, source_review=review)
            index = len(proposals.setdefault(doc['document_id'], []))
            proposals[doc['document_id']].append(p)
            reviews.setdefault(doc['document_id'], {})[index] = review
            row.update(status='SOURCE_REVIEW_LINKED', record_id=checked['id'], s_stage=checked['s_stage'],
                       relation_attribution=checked['meaning_status'], target=checked['target'],
                       missing=[k for k, v in checked['target'].items() if v is None])
            # An old order remains an old order. S1 is a signal, not evidence
            # of a current 12–36 month supply gap or a new LIVE detection.
            row['forecast_status'] = 'UNKNOWN_NEED_PERIOD_AND_QUALIFIED_SUPPLY'
        except (ValueError, KeyError, TypeError) as exc:
            row.update(status='HELD', reason=str(exc))
        dispositions.append(row)
    return proposals, reviews, dispositions


def analyze(documents, cases, *, as_of):
    proposals, reviews, dispositions = prepare(documents, cases, as_of=as_of)
    engine = evidence_path.analyze(documents, proposals, enabled=True, source_reviews=reviews)
    return stamp_export({'version': VERSION, 'as_of': as_of, 'mode': 'BACKFILL',
        'operational_integration_enabled': False, 'cases': dispositions, 'engine': engine,
        'candidates': [], 'AI_adoption': 'FAIL_UNCHANGED', 'independent_evaluation': 'BLOCKED_UNCHANGED',
        'forecast_performance': 'NOT_RUN', 'new_LIVE_S1_S2_S3': [0, 0, 0]})


def save(ledger, documents, cases, *, as_of):
    run_id = 'supply-linkage-' + sha([VERSION, documents, cases, as_of])
    old = ledger.db.execute('SELECT payload FROM runs WHERE id=?', (run_id,)).fetchone()
    if old:
        import json
        return json.loads(old[0])
    result = analyze(documents, cases, as_of=as_of)
    for doc in documents: ledger.capture(doc)
    from .cross_industry import common_evidence
    by_doc = {d['document_id']: d for d in documents}
    import json
    previous = {}
    for text, in ledger.db.execute("SELECT payload FROM events WHERE kind IN ('CROSS_COMMON_EVIDENCE','CROSS_COMMON_EVIDENCE_REVISION') ORDER BY seq"):
        item = json.loads(text)
        if item.get('origin_kind') == 'EXPLICIT_PRIMARY_SOURCE_REVIEW_NOT_AUTOMATIC_DISCOVERY':
            key = (item['sources'][0]['document_id'], item['source_surface_target']['product'], item['role'], item['actuality'])
            previous[key] = item['event_id']
    with ledger.db:
        for record in result['engine']['records']:
            item = common_evidence(record, by_doc[record['context']['document_id']],
                                   'EXPLICIT_PRIMARY_SOURCE_REVIEW_NOT_AUTOMATIC_DISCOVERY')
            key = (record['context']['document_id'], record['product']['surface'], record['role'], record['actuality'])
            kind = 'CROSS_COMMON_EVIDENCE'
            if key in previous:
                item['event_id'] = previous[key]
                kind = 'CROSS_COMMON_EVIDENCE_REVISION'
            ledger.event(kind, item)
            ledger.event('POST_UI_EVENT_REVIEW', {
                'source_event_id': item['event_id'],
                'reason_ko': record['source_review']['original_review']['reason_ko'],
                'reviewer': 'Same-session Codex; not independent or human verification'})
        return ledger.save_run(run_id, result, 'BACKFILL')
