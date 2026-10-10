"""Isolated post-save REVIEW_LEAD SHADOW transport, queue and audit.

Uses 83aaf61 intake/assessor unchanged. No source acquisition, AI inference,
EARLY/V2 evaluator, DB writer or operational store is called.
"""
import argparse
import importlib.util
import json
import re
from pathlib import Path

from . import review_intake as intake, review_leads as review
from .objective_lock import stamp_export, require_objective

VERSION='BCT_REVIEW_SHADOW_TRANSPORT_1'


def safe_root(path):
    root=Path(path)
    # Fixed namespace, no user-selected live/store subdirectory or symlink escape.
    if root.name!='review-lead-shadow' or root.is_symlink():raise ValueError('SHADOW_NAMESPACE_REQUIRED')
    if any('live' in p.casefold() or 'v2' in p.casefold() or 'early' in p.casefold() for p in root.resolve().parts):
        raise ValueError('OPERATIONAL_STORE_FORBIDDEN')
    for ancestor in root.resolve().parents:
        if any((ancestor/name).exists() for name in ('session.json','frozen-policy.json','activation.json')):
            raise ValueError('OPERATIONAL_STORE_ANCESTOR_FORBIDDEN')
    if root.exists():
        if any(p.is_symlink() for p in root.rglob('*')):raise ValueError('SHADOW_SYMLINK_FORBIDDEN')
        # An unrelated nonempty directory cannot be adopted as a new shadow store.
        if any(root.iterdir()) and not (root/'shadow-activation.json').exists():raise ValueError('FOREIGN_STORE_FORBIDDEN')
    return root


def initialize(root):
    root=safe_root(root);root.mkdir(parents=True,exist_ok=True)
    contract=json.loads(Path('review-leads/contract.json').read_text())
    binding={**review.binding(contract),'shadow_transport_version':VERSION,
             'intake_sha256':review.digest(Path(intake.__file__).read_bytes()),
             'transport_sha256':review.digest(Path(__file__).read_bytes()),
             'source_loader_sha256':review.digest((Path(__file__).resolve().parents[2]/'.github/scripts/review_lead_intake.py').read_bytes())}
    path=root/'shadow-activation.json'
    if path.exists():
        current=review.sealed_read(path)
        if any(current[k]!=v for k,v in binding.items()):raise ValueError('SHADOW_FROZEN_BINDING_CHANGED')
    else:
        current=review.write_first(path,{**binding,'activated_at':review.now(),'EARLY_success':False,'LIVE_writes':0})
    # Initialize unchanged intake before any eligible future document arrives.
    intake.process(stamp_export({'documents':[]}),contract,root/'store')
    return root,contract,current


def original_hook():
    path=Path(__file__).resolve().parents[2]/'.github/scripts/review_lead_intake.py'
    spec=importlib.util.spec_from_file_location('_frozen_review_hook',path)
    hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook);return hook


def handoff(delta_path,cache,output):
    """Package only newly acquired cache entries, reusing existing proof loader.

    Scan capture metadata, not old corpus bodies. Include opposite-side documents
    obtained in this acquisition window as well as the RSS seed delta. No fetch.
    """
    delta=json.loads(Path(delta_path).read_text());cutover=intake.timestamp(delta['collection_started_at'])
    rows=[];skipped=[];cache=Path(cache);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for path in sorted((cache/'captures').glob('*.json')):
        try:
            d=json.loads(path.read_text())
            if intake.timestamp(d.get('acquired_at',d.get('collected_at',''))) < cutover:continue
            rows.append({'document_id':d['document_id'],'url':d['origin_url']})
        except Exception as exc:skipped.append({'capture_file':path.name,'reason':str(exc)})
    docs=[];hook=original_hook()
    for start in range(0,len(rows),100):
        # This is temporary handoff metadata; neither captures nor source bytes change.
        batch=output/'selected-delta.json';batch.write_text(json.dumps({'documents':rows[start:start+100]}))
        prepared,failed=hook.load_saved_delta(batch,cache);docs.extend(prepared['documents']);skipped.extend(failed)
    unique={d['document_id']:d for d in docs}
    bundle=stamp_export({'documents':list(unique.values()),'handoff_at':review.now(),
        'upstream_collection_started_at':delta['collection_started_at'],'skipped':skipped,
        'source':'read-only new acquisition captures; original provenance/body loader'})
    (output/'input.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2))
    return bundle


def snapshot(root):
    return {str(p.relative_to(root)):review.digest(p.read_bytes()) for p in root.rglob('*') if p.is_file() and p.name!='.review-lock'}


def queue_entry(item,started):
    d=item['source_document'];events=item['automatic_extraction']['events']
    return {**review.binding(json.loads(Path('review-leads/contract.json').read_text())),
        'document_id':d['document_id'],'body_sha256':d['body_sha256'],
        'published_at':d.get('published_at','UNKNOWN'),'acquired_at':d.get('acquired_at','UNKNOWN'),
        'available_at':d.get('available_at','UNKNOWN'),'intake_started_at':started,
        'intake_recorded_at':item['recorded_at'],
        'first_review_recorded_at':'UNKNOWN' if not item.get('review_id') else item['recorded_at'],
        'mode':item['mode'],'status':item['final_status'],
        'automatic_extraction':item['automatic_extraction'],
        'candidate_TARGET':'UNKNOWN — deterministic scope suggestions only',
        'candidate_scope_suggestions':[{'event_id':e['event_id'],'fields':e['fields'],
            'reference':e['reference'],'verified_same_TARGET':False} for e in events],
        'review_reason':item['reason'],'semantic_review_method':'PENDING_AI_OR_MANUAL',
        'annotation_method':None,'annotator':None,'annotated_at':None,
        'source_document':d,'EARLY_success':False}


def run(bundle,root,*,packets=(),allow_backfill=False):
    require_objective(bundle);root,contract,activation=initialize(root)
    before=snapshot(root);started=review.now();docs=review.documents(bundle);packet_ids={p['document_id'] for p in packets}
    # Semantic completion may address a queued original without re-fetching it.
    for did in packet_ids-set(docs):
        candidates=[]
        for path in (root/'queue').glob('*.json'):
            q=review.sealed_read(path)
            if q['document_id']==did:candidates.append(q)
        if len(candidates)!=1:raise ValueError('SEMANTIC_QUEUE_DOCUMENT_NOT_UNIQUE')
        docs[did]=candidates[0]['source_document']
    selected=[];omitted=[]
    for d in docs.values():
        try:new=intake.timestamp(d['acquired_at'])>=intake.timestamp(activation['activated_at'])
        except (ValueError,KeyError,TypeError):new=False
        if new or allow_backfill or d['document_id'] in packet_ids:selected.append(d)
        else:omitted.append({'document_id':d['document_id'],'body_sha256':d['body_sha256'],
            'mode':'BACKFILL','reason':'BEFORE_ACTUAL_SHADOW_ACTIVATION','published_at':d.get('published_at'),
            'acquired_at':d.get('acquired_at'),'available_at':d.get('available_at')})
    records=[];pending=[]
    for d in selected:
        prior=root/'store'/'intake'/(intake.source_key(d)+'.json')
        if d['document_id'] not in packet_ids and prior.exists():
            records.append({**review.sealed_read(prior),'delivery':'DUPLICATE'})
        else:pending.append(d)
    selected=pending
    for start in range(0,len(selected),100):
        chunk=selected[start:start+100];ids={d['document_id'] for d in chunk}
        result=intake.process(stamp_export({'documents':chunk}),contract,root/'store',
            semantic_packets=[p for p in packets if p['document_id'] in ids],prospective=True)
        records.extend(result['records'])
    # Verify old files before emitting any new append-only transport receipts.
    for path,h in before.items():
        if review.digest((root/path).read_bytes())!=h:raise ValueError('SHADOW_EXISTING_FILE_CHANGED')
    alerts=[]
    for item in records:
        duplicate=item.get('delivery') in ('DUPLICATE','DUPLICATE_BODY')
        if duplicate:
            if item['semantic_review']['status']=='PENDING':
                key=review.digest([item['document_id'],item['body_sha256']]);path=root/'queue'/(key+'.json')
                if not path.exists():review.write_first(path,queue_entry(item,'UNKNOWN'))
            continue
        if item['semantic_review']['status']=='PENDING':
            q=queue_entry(item,started);key=review.digest([q['document_id'],q['body_sha256']])
            path=root/'queue'/(key+'.json')
            if not path.exists():review.write_first(path,q)
        else:
            # Keep attribution with this completion rather than rewriting its queue.
            packet=next(p for p in packets if p['document_id']==item['document_id'])
            a=packet['annotation'];value={**review.binding(contract),'document_id':item['document_id'],
                'body_sha256':item['body_sha256'],'annotation_method':a['annotation_method'],
                'annotator':a['annotator'],'annotated_at':a['annotated_at'],
                'automatic_extraction':item['automatic_extraction'],
                'semantic_review_method':a['annotation_method'],'packet':packet,'recorded_at':review.now()}
            path=root/'semantic'/(review.digest(packet)+'.json')
            if not path.exists():review.write_first(path,value)
        if item.get('review_id'):
            first=review.sealed_read(root/'store'/'first'/(item['review_id']+'.json'))
            time_path=root/'review-times'/(item['review_id']+'.json')
            if not time_path.exists():
                earlier=[review.sealed_read(p) for p in (root/'queue').glob('*.json')
                         if review.sealed_read(p)['document_id']==item['document_id']]
                source=first['sources'][0]
                review.write_first(time_path,{**review.binding(contract),'review_id':item['review_id'],
                    'first_record_sha256':first['record_sha256'],'published_at':source['published_at'],
                    'acquired_at':source['acquired_at'],'available_at':source['available_at'],
                    'intake_started_at':earlier[0]['intake_started_at'] if earlier else started,
                    'first_review_recorded_at':first['first_review_recorded_at'],
                    'strict_candidate_first_met_at':'UNKNOWN','mode':first['mode'],
                    'T':'UNKNOWN','T_scope':'UNKNOWN','EARLY_success':False})
        if item['final_status']=='REVIEW_LEAD':
            # Subsequent genuine source facts are a research update; no EARLY claim.
            alerts.append({'kind':'REVIEW_LEAD_UPDATE' if item.get('append_to_existing') else 'NEW_REVIEW_LEAD',
                'review_id':item['review_id'],'target':item['target'],'mode':item['mode'],
                'source_origin_id':item['source_document'].get('origin_id'),
                'independent_origin_verification':'UNKNOWN','fact_references':item.get('source_observations',[]),
                'hypothesis':item['hypothesis'],'questions':item['next_questions'],'EARLY_success':False})
        elif item['final_status']=='CONFIRMATION' and item.get('append_to_existing'):
            alerts.append({'kind':'REVIEW_LEAD_UPDATE','review_id':item['review_id'],
                'confirmation':True,'EARLY_success':False})
    receipt={**review.binding(contract),'shadow_transport_version':VERSION,'started_at':started,
        'completed_at':review.now(),'input_sha256':review.digest(bundle),'records':records,
        'omitted_backfill':omitted,'handoff_skipped':bundle.get('skipped',[]),'alerts':alerts,
        'EARLY_success_count':0,'LIVE_writes':0}
    path=root/'runs'/(review.digest(receipt)+'.json');review.write_first(path,receipt)
    # Summary is a derived view, not immutable first/history; no external messaging.
    lines=['# REVIEW_LEAD SHADOW important updates','',f'New/important records: {len(alerts)}','']
    for a in alerts:lines.extend([f"- {a['kind']}: {a.get('target',a['review_id'])}", '  '+str(a.get('questions',[]))])
    (root/'summary.md').write_text('\n'.join(lines)+'\n')
    return receipt


def followup(bundle,root,review_id,event):
    """Explicit attributed evidence/refutation; no automatic state promotion."""
    require_objective(bundle);require_objective(event)
    if not re.fullmatch(r'review-[0-9a-f]{24}',review_id):raise ValueError('INVALID_REVIEW_ID')
    root,contract,_=initialize(root)
    if not event.get('annotation_method'):raise ValueError('FOLLOWUP_SEMANTIC_METHOD_REQUIRED')
    saved=review.append_event(root/'store',contract,bundle,review_id,event)
    audit={**review.binding(contract),'review_id':review_id,'event':event,
           'semantic_review_method':event['annotation_method'],
           'annotation_method':event['annotation_method'],'annotator':event['annotator'],
           'annotated_at':event.get('annotated_at','UNKNOWN'),
           'saved_record_sha256':saved['record_sha256'],'EARLY_success':False}
    path=root/'updates'/(review.digest(event)+'.json')
    if not path.exists():review.write_first(path,audit)
    (root/'summary.md').write_text('# REVIEW_LEAD SHADOW important updates\n\n'
        +event['kind']+': '+review_id+'\n'+event['summary']+'\n')
    return saved


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['handoff','run','initialize','append'])
    p.add_argument('--delta',type=Path);p.add_argument('--cache',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--input',type=Path);p.add_argument('--state',type=Path);p.add_argument('--semantic',type=Path)
    p.add_argument('--review-id');p.add_argument('--event',type=Path)
    a=p.parse_args()
    if a.action=='handoff':handoff(a.delta,a.cache,a.output)
    elif a.action=='initialize':initialize(a.state)
    elif a.action=='append':followup(json.loads(a.input.read_text()),a.state,a.review_id,json.loads(a.event.read_text()))
    else:
        packets=json.loads(a.semantic.read_text()) if a.semantic else stamp_export({'packets':[]});require_objective(packets)
        run(json.loads(a.input.read_text()),a.state,packets=packets['packets'])

if __name__=='__main__':main()
