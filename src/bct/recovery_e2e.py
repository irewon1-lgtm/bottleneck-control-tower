"""Trace actual retained source bytes through the unchanged conservative engine.

This verifies execution and source bindings, not predictive accuracy. It does
not write hypothetical TARGETs, overwrite decisions or manufacture labels.
"""
from collections import Counter
from hashlib import sha256
import gzip
import json

from .future_bottleneck import screen
from .future_hypothesis import extract_facts, hypothesis_patch, SCOPE_FIELDS, UNKNOWN
from .future_ui import display_blob


def trace_source(item, body, tracking):
    digest=sha256(body.encode()).hexdigest()
    if digest!=item['body_sha256'] or len(body)!=item['body_chars'] or item['body_status']!='FULL':
        raise ValueError('real E2E source binding or completeness differs')
    screened=screen(body);extracted=extract_facts(body,screened)
    references=[]
    for fact in extracted['scope_facts']:
        start,end=fact['locator']['start'],fact['locator']['end']
        if type(start) is not int or type(end) is not int or not 0<=start<end<=len(body):
            raise ValueError('extracted source locator outside original body')
        text=' '.join(body[start:end].casefold().split())
        if ' '.join(fact['target'].casefold().split()) not in text:
            raise ValueError('extracted TARGET absent from its original evidence locator')
        references.append({'target':fact['target'],'role':fact['role'],'locator':fact['locator'],
            'body_sha256':digest,'excerpt_sha256':sha256(body[start:end].encode()).hexdigest(),
            'missing_scope':[k for k in SCOPE_FIELDS if fact.get(k,UNKNOWN)==UNKNOWN]})
    # Source metadata stays as observed. Accessible FULL structure cannot
    # become verified provenance, publication, qualification or supply cover.
    record={**item,**screened,**extracted}
    cases={'results':{item['document_id']:record}}
    projected=hypothesis_patch(cases,tracking,mode='BACKFILL')['hypotheses']
    verdicts=[]
    for hypothesis in projected.values():
        current=hypothesis['current'];scope=current.get('scope',{})
        evidence=current.get('evidence',[])
        if any(ref.get('document_id')!=item['document_id'] or ref.get('body_sha256')!=digest for ref in evidence):
            raise ValueError('hypothesis uses a different source version')
        if current['stage']=='S3':
            if any(value!='TRUE' for value in current['gates'].values()):
                raise ValueError('supply gap advanced without all existing gates')
            scopes={(f['target'].casefold(),f['specification'].casefold(),f['region'].casefold(),
                f['supply_pool'].casefold(),json.dumps(f['period'],sort_keys=True))
                for f in evidence if f['role'] in ('DEMAND','SUPPLY')}
            if len(scopes)!=1:raise ValueError('different TARGET supply pools were combined')
        verdicts.append({'stage':current['stage'],'scope':scope,'gates':current.get('gates',{}),
            'review_required':current.get('review_required'),
            'public_classification':current.get('public_classification'),
            'missing_evidence':current.get('draft',{}).get('unconfirmed',[])})
    return {'document_id':item['document_id'],'body_sha256':digest,'body_chars':len(body),
        'source_extent_verified':True,'actual_parser_execution':True,'facts':references,
        'relationships':extracted['supply_relationships'],'verdicts':verdicts,
        'stage_counts':dict(Counter(v['stage'] for v in verdicts)),
        'production_decisions_written':0,'prediction_performance':'UNVERIFIED'}


def verify_display_generation(path,document,source_document_sha256):
    envelope=json.loads(gzip.decompress(display_blob(path,document,source_document_sha256)))
    payload=envelope['payload'].encode()
    if (envelope['source_document_sha256']!=source_document_sha256
            or envelope['payload_sha256']!=sha256(payload).hexdigest()):
        raise ValueError('display source/payload hash differs')
    projected=json.loads(payload)
    if path=='future-candidates.json':
        if set(projected['results'])!=set(document['results']):
            raise ValueError('display candidate identities differ')
        for field in ('review_queue','recovery_queue'):
            # The current display bounds the legacy preview only; all counts
            # and authoritative seven-state recovery metrics remain exact.
            actual=projected.get('summary',{}).get(field,{})
            expected=document.get('summary',{}).get(field,{})
            if {k:v for k,v in actual.items() if k!='preview'}!={k:v for k,v in expected.items() if k!='preview'}:
                raise ValueError('display queue aggregates differ')
    elif projected.get('targets')!=document.get('targets'):
        raise ValueError('display confirmed TARGETs differ')
    return {'status':'PASS','source_document_sha256':source_document_sha256,
            'payload_sha256':envelope['payload_sha256']}
