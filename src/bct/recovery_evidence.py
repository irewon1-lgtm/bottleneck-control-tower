"""Audit missing evidence using the unchanged source-scope/temporal reader.

These are assessment records, not saved human reviews or model completions.
Unknown TARGET attributes, quantities and dates remain explicitly unknown.
"""
import hashlib

from .precursor_collection import structure, evidence_plan
from .precursor_evidence_graph import analyze

FIELDS=('DEMAND','CONSTRAINT','CAPACITY','LEAD_TIME','QUALIFIED_SUPPLY',
        'NEED_TIMING','READY_TIMING','RELIEF','INDEPENDENT_EVIDENCE','TARGET')


def source_document(identity, observation, body):
    expected=observation.get('body_sha256')
    if not body or hashlib.sha256(body.encode()).hexdigest()!=expected:
        raise ValueError('recovery evidence body hash mismatch')
    proof=observation.get('source_proof', {})
    document={'document_id':identity,'body':body,'body_sha256':expected,
        'origin_id':proof.get('origin_id'),'origin_url':observation['url'],
        'origin_publisher':proof.get('origin_publisher'),
        'provenance':proof.get('provenance','BLOCKED'),
        'provenance_verified':proof.get('provenance_verified') is True,
        'checks':proof.get('checks',{}),'published_at':proof.get('published_at'),
        'publication_precision':proof.get('publication_precision','UNKNOWN'),
        'available_at':observation['attempted_at'],'acquired_at':observation['attempted_at'],
        'body_status':observation.get('body_status'),'version':expected}
    return structure(document,fresh=False)


def assess(document, supplemental=()):
    """A literal lead does not close a verified evidence requirement."""
    if document is None:
        return {'state':'EVIDENCE_WAIT','missing_fields':list(FIELDS),
                'scope_status':'SOURCE_UNAVAILABLE','search_plan':{'requests':[],'blocked':[]}}
    documents=[document,*supplemental]
    graph=analyze(documents,mode='BACKFILL')
    events=document.get('precursor_events',[])
    present={k:[] for k in FIELDS}
    for event in events:
        identity=event['event_id']
        facts=event.get('temporal_facts',{})
        if event['role']=='DEMAND' and event.get('demand_status') in ('COMMITTED','CONFIRMED_PLAN'):
            present['DEMAND'].append(identity)
        if event['role']=='SUPPLY':
            if event.get('pending') or 'LEAD_TIME' in event.get('event_types',[]):
                present['CONSTRAINT'].append(identity)
            if event.get('quantity') not in (None,'UNKNOWN'):present['CAPACITY'].append(identity)
            if event.get('qualified') is True:present['QUALIFIED_SUPPLY'].append(identity)
        periods=facts.get('periods',[])
        if any(p['fact_kind']=='DEMAND_NEED' for p in periods):present['NEED_TIMING'].append(identity)
        if any(p['fact_kind'] in ('SUPPLY_READY','QUALIFICATION') for p in periods):present['READY_TIMING'].append(identity)
        if 'LEAD_TIME' in event.get('event_types',[]) and any(p['precision']=='RELATIVE_DURATION' for p in periods):
            present['LEAD_TIME'].append(identity)
        if facts.get('relief'):present['RELIEF'].append(identity)
        if not event.get('missing_scope'):present['TARGET'].append(identity)
    if graph['independent_pairs']:present['INDEPENDENT_EVIDENCE']=['SOURCE_BOUND_INDEPENDENT_PAIR']
    # Genuine literal assertions are retained as leads. Only independently
    # verified original sources can close the requirements; no issuer guess.
    verified=document.get('provenance')=='PASS' and document.get('body_status')=='FULL'
    missing=[field for field in FIELDS if not present[field] or not verified]
    candidates=graph['protected_result'].get('candidates',[])
    return {'state':'EVIDENCE_WAIT' if missing or not candidates else 'REVIEW_REQUIRED',
            'body_sha256':document['body_sha256'],'missing_fields':missing,
            'literal_event_ids':present,'scope_status':'EXACT_SCOPE_IDENTIFIED' if present['TARGET'] else 'TARGET_SCOPE_INCOMPLETE',
            'source_verified':verified,'independent_pairs':graph['independent_pairs'],
            'reference_checks':graph['reference_checks'],'technical_graph_checked':True,
            'search_plan':evidence_plan(documents),'completed_review_created':False,
            'forecast_promotion_created':False,'prediction_performance':'UNVERIFIED'}
