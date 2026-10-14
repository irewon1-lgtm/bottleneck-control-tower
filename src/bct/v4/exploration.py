"""Research discovery retention, separate from verified event adoption.

An empty/invalid AI reply cannot veto CPU proposals. All originals are retained;
literal position, physical identity and event meaning are separate decisions.
No provider calls, new model, TARGET pairing or S-stage judgement.
"""
from copy import deepcopy
from .evidence_path import reference
from .store import sha
from .cross_industry import reading_result
from bct.objective_lock import stamp_export

VERSION = 'bct-cpu-exploration-recovery-1'


def retain(doc, cpu_readings, ai_proposals=()):
    if sha(doc['body'].encode()) != doc['body_sha256']: raise ValueError('BODY_HASH_MISMATCH')
    discoveries = []
    valid, windows, held = [], [], []
    for reading in cpu_readings:
        selected = reading.get('selected_windows', [])
        for w in selected:
            reference(doc, {'start':w['start'],'end':w['end'],'quote':doc['body'][w['start']:w['end']]})
            if 'text' in w and w['text'] != doc['body'][w['start']:w['end']]: raise ValueError('CPU_INPUT_MISMATCH')
        windows.extend(selected)
        for span in reading.get('spans', []):
            row = {'id':sha(['CPU',doc['document_id'],reading.get('input_sha256'),span]),
                   'origin':'CPU','original_proposal':deepcopy(span),'proposed_name':span.get('text'),
                   'product_candidate':span.get('label')=='product','discovery_status':'RETAINED',
                   'event_adoption':'NOT_DECIDED_BY_DISCOVERY','s_stage':'UNKNOWN'}
            try:
                if span.get('document_id') != doc['document_id'] or span.get('body_sha256') != doc['body_sha256']:
                    raise ValueError('CPU_DOCUMENT_OR_HASH_MISMATCH')
                a,b=span['locator']['start'],span['locator']['end']
                row['reference']=reference(doc,{'start':a,'end':b,'quote':span['text']})
                if not any(w['start']<=a<b<=w['end']for w in selected): raise ValueError('CPU_OUTSIDE_READ_SCOPE')
                row['source_status']='EXACT_LOCATION_PASS_NOT_MEANING_PROOF';valid.append(deepcopy(span))
            except (ValueError,KeyError,TypeError)as e:
                row.update(source_status='HELD',reason=str(e));held.append({'id':row['id'],'reason':str(e)})
            discoveries.append(row)
        # Invalid source positions are retained as proposals, not converted
        # into source facts or counted as successful product extraction.
        for bad in reading.get('rejected_spans', []):
            discoveries.append({'id':sha(['CPU_RAW_HELD',doc['document_id'],bad]),'origin':'CPU',
                'original_proposal':deepcopy(bad),'proposed_name':bad['original_proposal'].get('text'),
                'product_candidate':bad.get('label')=='product','discovery_status':'RETAINED_SOURCE_HELD',
                'source_status':'HELD','reason':bad['reason'],'event_adoption':'NOT_ADOPTED','s_stage':'UNKNOWN'})
    for index, proposal in enumerate(ai_proposals):
        attrs = proposal.get('event_attributes', {}) if isinstance(proposal,dict) else {}
        discoveries.append({'id':sha(['SAVED_AI',doc['document_id'],index,proposal]),'origin':'SAVED_AI',
            'original_proposal':deepcopy(proposal),'proposed_name':attrs.get('product'),
            'product_candidate':bool(attrs.get('product')),'discovery_status':'RETAINED_PENDING_VALIDATION',
            'source_status':'UNVERIFIED_MODEL_PROPOSAL','event_adoption':'NOT_ADOPTED','s_stage':'UNKNOWN'})
    discoveries = list({d['id']:d for d in discoveries}.values())
    reading={'status':'PASS','spans':valid,'selected_windows':list({(w['start'],w['end']):w for w in windows}.values())}
    # Reuse existing CPU→located evidence diagnostics, including its primary
    # source gate and discovery-only default. No copied AI answer as CPU truth.
    checked=reading_result(doc,reading)
    return stamp_export({'version':VERSION,'document_id':doc['document_id'],'discoveries':discoveries,
        'source_held':held,'CPU_validation':checked,'candidates':[],
        'validated_event_count':0,'S1_S2_S3':[0,0,0],'AI_adoption':'FAIL_PRESERVED',
        'independent_evaluation':'BLOCKED_PRESERVED','operating_integration_enabled':False})


def save(ledger, doc, cpu_readings, ai_proposals=()):
    key='exploration-'+sha([VERSION,doc['document_id'],doc['body_sha256'],cpu_readings,ai_proposals])
    old=ledger.db.execute('SELECT payload FROM runs WHERE id=?',(key,)).fetchone()
    if old:
        import json
        return json.loads(old[0])
    result=retain(doc,cpu_readings,ai_proposals)
    ledger.capture(doc,reading={'CPU_originals':cpu_readings,'saved_AI_originals':ai_proposals,'validation':result})
    return ledger.save_run(key,result,'BACKFILL')


def source_review(doc, review, read_windows):
    """Validate a clearly attributed source review, never impersonate CPU/AI.

    Exact source verification is automatic. Semantic judgements here are an
    explicit same-session Codex review, not independent truth or model quality.
    Primary-source and S-stage gates stay separate and unchanged.
    """
    from .reading_quality import coverage
    from .evidence_path import normalize_quantity
    import re
    if doc.get('provenance')!='PASS' or doc.get('published_at') in (None,'','UNKNOWN'):
        raise ValueError('SOURCE_PROVENANCE_OR_PUBLICATION_HELD')
    if sha(doc['body'].encode())!=doc['body_sha256']:raise ValueError('BODY_HASH_MISMATCH')
    if review.get('review_type')!='SAME_SESSION_CODEX_SOURCE_REVIEW' or review.get('independent')is not False or review.get('human_verified')is not False:
        raise ValueError('SOURCE_REVIEW_ATTRIBUTION_REQUIRED')
    for w in read_windows:reference(doc,{'start':w['start'],'end':w['end'],'quote':doc['body'][w['start']:w['end']]})
    cov=coverage(doc['body'],read_windows)
    refs=review['references']+[review['product_reference']]
    from .evidence_path import ROLES, ACTUALITY
    if review['role']not in ROLES or review['actuality']not in ACTUALITY:raise ValueError('UNSUPPORTED_EVENT_CLASSIFICATION')
    if not any(r['start']<=review['product_reference']['start']<review['product_reference']['end']<=r['end']for r in review['references']):
        raise ValueError('PRODUCT_NOT_IN_REVIEWED_EVENT_CONTEXT')
    for field in review.get('fields',{}).values():
        if field['surface']!=field['reference']['quote']:raise ValueError('FIELD_MUST_BE_LITERAL')
    refs += [v['reference']for v in review.get('fields',{}).values()]
    for ref in refs:
        reference(doc,ref)
        for gap in cov['unread_ranges']:
            a,b=max(gap['start'],ref['start']),min(gap['end'],ref['end'])
            if a<b and doc['body'][a:b].strip():raise ValueError('REVIEW_EVIDENCE_OUTSIDE_ACTUAL_READ')
    quantity=review.get('fields',{}).get('quantity')
    if quantity:
        ref=quantity['reference'];value=quantity['surface']
        if value!=ref['quote']:raise ValueError('QUANTITY_MUST_BE_LITERAL')
        if re.search(r'[$€£¥]|\b(?:USD|EUR|dollars?|million dollars|funding|investment)\b',value,re.I) or re.search(r'(?:[$€£¥]|\b(?:USD|EUR|GBP|JPY|KRW))\s*$',doc['body'][:ref['start']],re.I):
            raise ValueError('MONEY_NOT_PHYSICAL_QUANTITY')
    record={'id':sha([VERSION,doc['document_id'],review]),'origin':'EXPLICIT_CODEX_SOURCE_REVIEW_NOT_CPU_OR_GROQ',
        'original_review':deepcopy(review),'source_document_id':doc['document_id'],'body_sha256':doc['body_sha256'],
        'raw_sha256':doc.get('raw_sha256'),'published_at':doc['published_at'],'acquired_at':doc.get('acquired_at'),
        'origin_url':doc['origin_url'],'product':{'surface':review['product_reference']['quote'],'reference':review['product_reference']},
        'role':review['role'],'actuality':review['actuality'],'references':review['references'],'fields':review.get('fields',{}),
        'event_status':'REPORTED_FACT_REVIEWED_PRIMARY_PENDING'if not doc.get('primary_source_verified')else'SOURCE_REVIEWED_NOT_INDEPENDENT',
        'source_gate':'HELD_PRIMARY_SOURCE'if not doc.get('primary_source_verified')else'PASS',
        's_stage':'UNKNOWN','independence':'UNKNOWN','total_qualified_supply':'UNKNOWN','future_gap':'UNKNOWN',
        'research_only':True,'independent_accuracy_verified':False,'candidates':[]}
    if quantity:record['quantity_conversion']=normalize_quantity(quantity['surface'])
    return record
