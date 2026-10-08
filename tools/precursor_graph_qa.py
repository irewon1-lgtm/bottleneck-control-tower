"""Read-only fixed-source and registered-original graph QA with field audits.

Raw/source/private failure audits stay in the designated private output. A
missing regex match is explicitly NOT proof that the information is unpublished.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from bct import precursor_collection as c, precursor_evidence_graph as g
from bct import precursor_official_source as official, precursor_scope_reader as scope
from bct.objective_lock import stamp_export
from precursor_backfill_qa import metrics,snapshot


def load_registered(root):
    docs=[];attempts=[]
    for p in sorted(root.glob('*.json')):
        old=json.loads(p.read_text());rawpath=p.with_suffix('.raw')
        row={k:old.get(k) for k in ('url','registries','status','bytes','acquired_at','error')}
        if not rawpath.exists():attempts.append(row);continue
        if not old.get('final_url') or not old.get('content_type'):
            row.update(body_acquired=True,provenance='BLOCKED',blockers=['CAPTURE_TRANSPORT_METADATA_INCOMPLETE'])
            attempts.append(row);continue
        raw=rawpath.read_bytes();meta=old.get('sec_filing_metadata')
        metaraw=(root/'raw'/(meta['raw_sha256']+'.json')).read_bytes() if meta and meta.get('status')=='CAPTURED' else None
        proof=official.verify(raw,old['url'],old['final_url'],old['acquired_at'],200,old['content_type'],metadata_record=meta,metadata_raw=metaraw)
        row.update(body_acquired=True,provenance=proof['provenance'],blockers=proof.get('provenance_blockers'),official_blocker=proof.get('official_blocker'),body_sha256=proof['body_sha256'])
        if proof['provenance']=='PASS':docs.append(c.structure({**proof,'document_id':old['document_id'],'registries':old['registries']},raw))
        attempts.append(row)
    unique={}
    for d in docs:unique.setdefault(d['body_sha256'],d)
    return list(unique.values()),attempts


def graph_summary(graph):
    return {k:graph[k] for k in ('version','complete_target_events','independent_pairs','comparable_period_pairs','reference_checks')} | {
        'observations':len(graph['observations']),'cross_document_edges':sum(e['references'][0]['document_id']!=e['references'][1]['document_id'] for e in graph['edges']),
        'edges':len(graph['edges']),'targets':len(graph['targets']),
        'backfill_early_candidates':len(graph['protected_result']['candidates']),
        'blocked_reasons':dict(Counter(b['reason'] for b in graph['blocked']))}


def selected_field_results(documents,gold):
    """Measure only explicitly labelled source spans, not exhaustive recall."""
    docs={d['document_id']:d for d in documents};rows=[];matched=missed=0
    for case in gold['cases']:
        d=docs[case['document_id']]
        if d['body_sha256']!=case['body_sha256']:raise ValueError('GOLD_BODY_VERSION_MISMATCH')
        observed=g.observations(d);fields=[]
        for key,label in case['fields'].items():
            candidates=[o['fields'][key] for o in observed if key in o['fields']]
            actual=label.get('source_value')
            if actual is None:
                fields.append({'field':key,'state':'UNKNOWN_EXPECTED_NO_VERIFIED_TARGET_BINDING','automatic_values':[f['value'] for f in candidates]});continue
            if d['body'][label['locator']['start']:label['locator']['end']]!=actual:raise ValueError('GOLD_SOURCE_LOCATOR_MISMATCH')
            found=any(g.norm(f['value'])==g.norm(actual) for f in candidates)
            matched+=found;missed+=not found
            fields.append({'field':key,'gold':actual,'state':'SOURCE_PRESENT_EXACT_EXTRACTION' if found else 'SOURCE_PRESENT_EXTRACTION_FAILURE','automatic_values':[f['value'] for f in candidates]})
        rows.append({'document_id':d['document_id'],'origin_url':d['origin_url'],'fields':fields})
    return {'frozen_sources':len(rows),'positive_selected_fields':matched+missed,'exact_selected_field_matches':matched,'selected_field_misses':missed,
            'selected_field_recall':matched/(matched+missed) if matched+missed else 'UNKNOWN',
            'whole_corpus_precision':'UNKNOWN_INCOMPLETE_GOLD','wrong_link_precision':'UNKNOWN_NO_REAL_COMPLETE_SCOPE_PAIRS','results':rows}


def audit(documents,graph):
    obs={}
    for o in graph['observations']:obs.setdefault(o['document_id'],[]).append(o)
    rows=[]
    for d in documents:
        events=d['retained_collection_events'];nodes=obs.get(d['document_id'],[])
        fields={}
        for k in scope.FIELDS:
            literal=[f for o in nodes for key,f in o['fields'].items() if key==k]
            automatic=[e['scope'][k] for e in events if k in e['scope']]
            linked=[o['resolved_fields'][k] for o in nodes if k in o['resolved_fields'] and o.get('event_ids')]
            actual={g.norm(f['value']) for f in literal};extracted={g.norm(f['value']) for f in automatic};resolved={g.norm(f['value']) for f in linked}
            missing=actual-extracted
            other_document_links=[o['resolved_fields'][k] for o in nodes if k in o['resolved_fields'] and o.get('event_ids')
                                  and any(r['document_id']!=d['document_id'] for r in [o['resolved_fields'][k]['reference'],*o['resolved_fields'][k].get('support_references',[])])]
            cross_linked={g.norm(f['value']) for f in other_document_links}-extracted
            fields[k]={'literal_source_values':list({g.norm(f['value']):f for f in literal}.values()),
                       'automatic_event_values':sorted(extracted),'linked_event_values':sorted(resolved),
                       'missed_literal_values':sorted(missing),
                       'failure_type':'B' if cross_linked else 'A' if missing or resolved-extracted else 'C_OR_UNDETECTED_UNKNOWN' if not actual else 'EXTRACTED',
                       'reason':'EXACT_RELATION_GRAPH_FILLS_DIFFERENT_DOCUMENT' if cross_linked else 'SOURCE_SENTENCE_PRESENT_BUT_EVENT_BINDING_ABSENT' if missing or resolved-extracted else 'NO_UNAMBIGUOUS_VALUE_DETECTED_ABSENCE_NOT_PROVEN' if not actual else 'SOURCE_BOUND_EXTRACTION',
                       'method':'Fix event/reference linkage; never fabricate missing scope.' if missing else 'Preserve UNKNOWN; field-specific official acquisition plan.' if not actual else 'Exact body/locator checked.'}
        rows.append({'document_id':d['document_id'],'origin_url':d['origin_url'],'body_sha256':d['body_sha256'],'event_count':len(events),'fields':fields})
    return rows


def run(cache,registered,baseline,targets,output,as_of,holdout=None):
    before=snapshot(cache);docs=c.stored_documents(cache)
    fixed_stats,_=metrics(docs,as_of);fixed=g.analyze(docs,mode='BACKFILL',now=as_of)
    official_docs,attempts=load_registered(registered)
    official_as_of=c.acquisition.now()
    official_stats,_=metrics(official_docs,official_as_of);official_graph=g.analyze(official_docs,mode='BACKFILL',now=official_as_of)
    field_audit=audit(docs,fixed);official_audit=audit(official_docs,official_graph)
    output.mkdir(parents=True,exist_ok=True)
    (output/'fixed-field-audit.json').write_text(json.dumps(field_audit,ensure_ascii=False,indent=2))
    (output/'official-field-audit.json').write_text(json.dumps(official_audit,ensure_ascii=False,indent=2))
    (output/'fixed-graph.json').write_text(json.dumps(fixed,ensure_ascii=False))
    (output/'official-graph.json').write_text(json.dumps(official_graph,ensure_ascii=False))
    coverage=[]
    catalog=json.loads(targets.read_text())
    # All existing 22 targets are inventoried; prior verdicts are never inputs.
    for target in catalog['targets']:
        text=json.dumps(target,ensure_ascii=False)
        matched=[d for d in official_docs if d['origin_url'] in text or any(target['id'] in p for p in d['registries'])]
        # Registration manifests link through their explicit TARGET ids.
        source_paths=[]
        repository=Path(__file__).resolve().parents[1]
        for p in (repository/'docs/registrations').glob('*.json'):
            if target['id'] in p.read_text():source_paths.append(str(p.relative_to(repository)))
        coverage.append({'target_id':target['id'],'target':target['target'],'verified_full_originals':len(matched),
                         'verified_document_ids':[d['document_id'] for d in matched],
                         'registration_paths':source_paths,
                         'unresolved':'FULL_ORIGINAL_OR_EXPLICIT_CUSTOMER_QUALIFICATION_PERIOD_COVERAGE_REQUIRED',
                         'historical_verdict_unchanged':True})
    (output/'target-coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2))
    preserved=snapshot(cache)==before
    if not preserved:raise AssertionError('original cache changed')
    value=stamp_export({'as_of':as_of,'baseline':json.loads(baseline.read_text())['after'],
          'backfill':{'metrics':fixed_stats,'graph':graph_summary(fixed)},
          'independent_official':{'as_of':official_as_of,'url_attempts':len(attempts),'body_acquisitions':sum(bool(r.get('body_acquired')) for r in attempts),
             'unique_verified_originals':len(official_docs),'status_counts':dict(Counter(r['status'] for r in attempts)),
             'metrics':official_stats,'graph':graph_summary(official_graph)},
          'failure_field_classifications':dict(Counter(f['failure_type'] for d in field_audit for f in d['fields'].values())),
          'existing_target_count':len(coverage),'cache_original_unchanged':preserved,
          'cache_file_count':len(before),'engine_hashes':c.hashes(),'new_live_early_candidates':0,
          'metrics_not_measured':{'whole_corpus_precision':'UNKNOWN_NO_COMPLETE_MANUAL_GOLD','whole_corpus_recall':'UNKNOWN_NO_COMPLETE_MANUAL_GOLD','actual_early_lead_time':'UNKNOWN_NO_INDEPENDENT_PREPUBLIC_TRIAL'}})
    if holdout:
        frozen=json.loads(holdout.read_text());ids={d['document_id'] for d in frozen};subset=[d for d in official_docs if d['document_id'] in ids]
        for frozen_doc in frozen:
            actual=next(d for d in subset if d['document_id']==frozen_doc['document_id']);assert actual['body_sha256']==frozen_doc['body_sha256']
        value['holdout']={'frozen_originals':len(frozen),'same_body_hashes_verified':len(subset),'metrics':metrics(subset,official_as_of)[0],'graph':graph_summary(g.analyze(subset,mode='BACKFILL',now=official_as_of))}
    (output/'summary.json').write_text(json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k not in ('objective','objective_binding')},ensure_ascii=False))
    return value


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--registered',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--targets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--holdout',type=Path);p.add_argument('--as-of',default='2026-10-08T17:30:00+00:00')
    a=p.parse_args();run(a.cache,a.registered,a.baseline,a.targets,a.output,a.as_of,a.holdout)
