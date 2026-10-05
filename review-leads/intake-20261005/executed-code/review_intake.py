"""Offline, semi-automatic new-document REVIEW_LEAD intake.

No fetching, V2 pair evaluation, EARLY execution or operational writes. Frozen V2
extract() supplies source-addressed suggestions, never semantic truth labels.
Unreviewed suggestions remain HOLD; bound attributed annotations use the existing
REVIEW_LEAD assessor. This is research triage, not detection performance.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from . import precursor_v2 as extraction, review_leads as review
from .objective_lock import require_objective, stamp_export

VERSION = 'BCT_REVIEW_INTAKE_1'


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:raise ValueError('TIMEZONE_REQUIRED')
    return parsed.astimezone(timezone.utc)


def source_key(doc):
    # Do not silently infer a real origin from the publisher/domain.
    return review.digest([doc.get('origin_id'), doc['body_sha256']])


def scope_key(annotation):
    # Only literal, verified scope fields. No name similarity, UNKNOWN or aliases.
    fields = annotation['scope_fields']
    return review.digest([sorted((k, ' '.join(v['value'].casefold().split()))
        for k,v in fields.items()), annotation['hypothesis_key']])


def prepare(doc):
    events = extraction.extract(doc)
    # These are machine suggestions, including false positives; not confirmed facts.
    return {'document_id':doc['document_id'],'body_sha256':doc['body_sha256'],
        'origin_id':doc.get('origin_id'), 'origin_url':doc.get('origin_url'),
        'provenance_verified':doc.get('provenance_verified'),
        'automatic_extraction':{'version':extraction.VERSION,
            'implementation_sha256':review.digest(Path(extraction.__file__).read_bytes()),
            'events':events, 'facts_verified_semantically':False},
        'semantic_review':{'status':'PENDING','annotation_method':None,'annotator':None},
        'final_status':'HOLD','reason':'SEMANTIC_REVIEW_REQUIRED' if events else 'NO_EXTRACTED_CHANGE_SEMANTICS_UNREVIEWED',
        'formal_TARGET_id':None,'EARLY_success':False}


def screen(doc, packet, docs):
    item = prepare(doc)
    if packet is None:return item, None
    require_objective(packet)
    if packet['document_id'] != doc['document_id'] or packet['body_sha256'] != doc['body_sha256']:
        raise ValueError('SEMANTIC_DOCUMENT_BINDING_MISMATCH')
    a = deepcopy(packet['annotation'])
    if not a.get('annotation_method') or not a.get('annotator'):
        raise ValueError('SEMANTIC_ATTRIBUTION_REQUIRED')
    # A normal intake packet cannot join facts from other documents silently.
    # Explicit cross-document source review remains the existing append workflow.
    refs = [f['reference'] for f in a['facts']] + [f['reference'] for f in a['scope_fields'].values()]
    refs += a.get('relation_references',[]) + [x['reference'] for x in a.get('counter_evidence',[])]
    refs += a.get('confirmation',{}).get('references',[]) + [p['reference'] for p in a.get('period_expressions',[])]
    if any(r['document_id'] != doc['document_id'] for r in refs):
        raise ValueError('SEMANTIC_CROSS_DOCUMENT_REQUIRES_EXPLICIT_REVIEW')
    state, reasons, _ = review.assess(a, docs)
    # A human/AI must supply the specific mechanism, concrete question and source
    # assessment; machine keywords never imply a signed contract or confirmation.
    generic = {'additional research needed','추가 조사 필요','추가조사 필요'}
    if state=='REVIEW_LEAD' and any(q.strip().casefold() in generic for q in a['questions']):
        state,reasons='HOLD',['NON_FALSIFIABLE_GENERIC_QUESTION']
    item.update(final_status=state, reason=';'.join(reasons),
        semantic_review={'status':'COMPLETED','annotation_method':a['annotation_method'],
            'annotator':a['annotator'],'annotated_at':a['annotated_at'],
            'manual_or_ai_semantic_review':True,'annotation_sha256':review.digest(a)},
        target=a['target'], hypothesis=a['hypothesis'], UNKNOWN=a['unknowns'],
        refutation_conditions=a['refutation_conditions'], next_questions=a['questions'],
        confirmation=a['confirmation'], source_supported_scope=a['scope_fields'])
    return item, a


def process(bundle, contract, root, *, semantic_packets=(), prospective=False):
    """Small source-bound intake; safe replay and immutable first/history.

    Source packets contain the existing review annotation schema. The caller
    explicitly chooses prospective delivery; old documents always BACKFILL.
    No queues are scanned implicitly. max100 is a guard, not an auto-loop.
    """
    require_objective(bundle); docs=review.documents(bundle)
    if len(docs)>100:raise ValueError('REVIEW_INTAKE_BATCH_TOO_LARGE')
    packets={}
    for packet in semantic_packets:
        require_objective(packet)
        did=packet['document_id']
        if did not in docs or did in packets:raise ValueError('SEMANTIC_PACKET_SET_INVALID')
        packets[did]=packet
    root=Path(root); results=[]
    with review.locked(root):
        review.activate(root,contract)
        policy=root/'intake-activation.json'
        binding={'intake_version':VERSION,'implementation_sha256':review.digest(Path(__file__).read_bytes()),
                 'extractor_sha256':review.digest(Path(extraction.__file__).read_bytes())}
        if policy.exists():
            old=review.sealed_read(policy)
            if any(old[k]!=v for k,v in binding.items()):raise ValueError('INTAKE_VERSION_BINDING_CHANGED')
        else:review.write_first(policy,{**review.binding(contract),**binding,'activated_at':review.now()})
        activated=review.sealed_read(policy)['activated_at']
        for doc in docs.values():
            item,a=screen(doc,packets.get(doc['document_id']),docs)
            fingerprint=source_key(doc)
            # Exact source/body dedup including changed document IDs/reposts.
            processed=root/'intake'/(fingerprint+'.json')
            annotation_sha=review.digest(a) if a else None
            if processed.exists():
                old=review.sealed_read(processed)
                if old['annotation_sha256']==annotation_sha:
                    results.append({**old,'delivery':'DUPLICATE'});continue
                if old['annotation_sha256'] is not None:
                    raise ValueError('PROCESSED_SOURCE_REQUIRES_APPEND_REVIEW_NOT_OVERWRITE')
                # Complete a pending semantic review in a new immutable receipt.
                processed=root/'intake'/(fingerprint+'-'+annotation_sha+'.json')
                if processed.exists():
                    results.append({**review.sealed_read(processed),'delivery':'DUPLICATE'});continue
            existing=list((root/'first').glob('*.json'))
            duplicate_body=next((review.sealed_read(p) for p in existing
                if any(s['body_sha256']==doc['body_sha256'] for s in review.sealed_read(p)['sources'])),None)
            if duplicate_body:
                results.append({**item,'delivery':'DUPLICATE_BODY','review_id':duplicate_body['review_id']});continue
            recorded=review.now();mode='BACKFILL'
            if prospective:
                try:
                    acquired=timestamp(doc['acquired_at']);published=timestamp(doc['published_at'])
                    if timestamp(activated)<=acquired<=timestamp(recorded) and published<=acquired:
                        mode='PROSPECTIVE_REVIEW'
                except (KeyError,ValueError,TypeError):pass
            # Unreviewed inputs have no invented scope or hypothesis. Hold records
            # are separately sealed intake items, not fictitious strict TARGETs.
            rid=None;match=None
            if a:
                key=scope_key(a)
                for p in existing:
                    c=review.sealed_read(p)
                    if c.get('intake_scope_key')==key and c.get('source_supported_scope'):
                        match=c;break
                if match and item['final_status'] in ('REVIEW_LEAD','CONFIRMATION'):
                    rid=match['review_id']
                    # Avoid recursive lock: append after this context exits.
                    item['append_to_existing']=rid
                else:
                    card=review.make_card(a,docs,contract)
                    card.update(status=item['final_status'],reasons=[item['reason']],mode=mode,
                        intake_version=VERSION,intake_scope_key=key,
                        processing_method={'automatic_extraction':extraction.VERSION,
                            'manual_or_ai_semantic_review':True},first_review_recorded_at=recorded)
                    rid=card['review_id'];path=root/'first'/(rid+'.json')
                    if not path.exists():review.write_first(path,card)
            receipt={**review.binding(contract),**item,'review_id':rid,'intake_version':VERSION,
                'annotation_sha256':annotation_sha,'mode':mode,'recorded_at':recorded,
                'source_document':doc,'T':'UNKNOWN','T_scope':'UNKNOWN',
                'strict_candidate_first_met_at':'UNKNOWN','leading_detection_success':False}
            review.write_first(processed,receipt);results.append(receipt)
    for item in results:
        if item.get('append_to_existing'):
            a=packets[item['document_id']]['annotation']
            event=stamp_export({'kind':'REVIEW','annotator':a['annotator'],
                'summary':a['hypothesis']['mechanism'],'references':[f['reference'] for f in a['facts']],
                'source_note':'Semi-automatic intake; same literal scope and hypothesis; no EARLY success.',
                **({'same_TARGET':'YES','status_after':'CONFIRMATION'} if item['final_status']=='CONFIRMATION' else {})})
            review.append_event(root,contract,bundle,item['append_to_existing'],event)
    return stamp_export({'intake_version':VERSION,'records':results,
        'counts':{s:sum(i['final_status']==s and i.get('delivery') not in ('DUPLICATE','DUPLICATE_BODY') for i in results)
                  for s in ('REVIEW_LEAD','HOLD','EXCLUDED','CONFIRMATION')},
        'EARLY_success_count':0,'LIVE_writes':0})


def render(output):
    lines=['# REVIEW_LEAD intake', '', '半자동 source-bound triage; not EARLY performance.', '']
    for r in output['records']:
        lines += [f"## {r.get('target',r['document_id'])} — {r['final_status']}",
            r['reason'], 'Semantic review: '+r['semantic_review']['status'],
            'Hypothesis: '+r.get('hypothesis',{}).get('mechanism','UNKNOWN — semantic review pending'),
            'Questions: '+ '; '.join(r.get('next_questions',[])), '']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--contract',type=Path,required=True)
    p.add_argument('--semantic',type=Path);p.add_argument('--store',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--prospective',action='store_true')
    a=p.parse_args();bundle=json.loads(a.input.read_text());contract=json.loads(a.contract.read_text())
    packets=json.loads(a.semantic.read_text()) if a.semantic else stamp_export({'packets':[]})
    require_objective(packets)
    result=process(bundle,contract,a.store,semantic_packets=packets['packets'],prospective=a.prospective)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    a.output.with_suffix('.md').write_text(render(result))

if __name__=='__main__':main()
