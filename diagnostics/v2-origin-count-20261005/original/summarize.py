from collections import Counter
from pathlib import Path
import hashlib,json
from bct import precursor_v2 as v
R=Path('/workspace/bct-v2-all-verified-batch-20261005')
run=json.loads((R/'run.json').read_text());p=run['prepared'];counts=run['counts']
guard=json.loads((R/'protected-before.json').read_text())
changed=[name for name,h in guard.items() if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=h]
assert not changed,changed
assert run['live_performance'] is False and run['freeze']['live_early']==0
assert counts['documents_input']==52 and not p['document_rejections']
assert all(d['provenance_verified'] is True for d in p['documents'])
es={e['event_id']:e for e in p['events']};ds={d['document_id']:d for d in p['documents']}
reasons=Counter(r for e in p['evaluations'] for r in e['reasons'])
relation_reasons=Counter(e['relation'].get('reason') for e in p['evaluations'] if e['relation']['state']!='VERIFIED')
# Compress only actually linked or partial pairs. Do not turn arbitrary UNKNOWN
# cross-products into TARGET hypotheses, or add a new score/probability.
linked=[e for e in p['evaluations'] if e['relation']['state']=='VERIFIED']
partial=[e for e in p['evaluations'] if e['state']=='PARTIAL_SCOPE_PAIR']
def rank(e):
 return (e['early_eligible'],e['relation']['state']=='VERIFIED' and e['independent'],e['scope_verified'],bool(e['comparison']),bool(e['demand_window']) and bool(e['supply_window']),e['relation']['state']=='VERIFIED')
groups={}
for e in sorted(linked+partial,key=rank,reverse=True):
 a,b=es[e['demand_event_id']],es[e['supply_event_id']]
 label=None
 for key in ('facility','model','product','contract'):
  af,bf=a['fields'].get(key),b['fields'].get(key)
  if af and bf and af['value']==bf['value']:
   label=af['value'];break
 if not label:continue
 groups.setdefault(label,e)
top=[]
for label,e in list(groups.items())[:5]:
 a,b=es[e['demand_event_id']],es[e['supply_event_id']]
 top.append({'source_identity':label,'state':e['state'],'synthetic_target_created':e['target_id'] is not None,
             'independent':e['independent'],'demand_document':a['document_id'],'supply_document':b['document_id'],
             'demand_publisher':ds[a['document_id']]['origin_publisher'],'supply_publisher':ds[b['document_id']]['origin_publisher'],
             'demand_reference':a['reference'],'supply_reference':b['reference'],
             'demand_window':e['demand_window'],'supply_window':e['supply_window'],'comparison':e['comparison'],
             'blocked_reasons':e['reasons'],'UNKNOWN':e['decisive_UNKNOWN']})
trace=0
for e in p['events']:
 refs=[e['reference']]+e['context_references']
 for field in e['fields'].values():refs += [field['reference']]+field.get('support_references',[])
 refs += [f['reference'] for f in e['facts'].values()]
 if e['period']:refs.append(e['period']['reference'])
 for ref in refs:v.verify_reference(ref,ds);trace+=1
for e in p['evaluations']:
 for ref in e['evidence']:v.verify_reference(ref,ds);trace+=1
unique_doc_edges={tuple(sorted((es[e['demand_event_id']]['document_id'],es[e['supply_event_id']]['document_id']))) for e in linked}
report={'processed_documents':counts['documents_valid'],'relation_connections_event_pairs':counts['relationship_verified'],
        'relation_connections_unique_document_pairs':len(unique_doc_edges),'independent_pairs':counts['independent_verified'],
        'PARTIAL_SCOPE_PAIR':counts['states'].get('PARTIAL_SCOPE_PAIR',0),'DATA_WAIT':counts['states'].get('DATA_WAIT',0),
        'EARLY_candidates':counts['early_targets'],'all_counts':counts,'top_candidates':top,
        'common_relation_blockers':dict(relation_reasons.most_common()),'common_blockers':dict(reasons.most_common()),
        'source_proof_missing_documents':0,'traceable_references_checked':trace,'existing_records_or_code_changed':changed,
        'network_requests':0,'live_writes':0,'shadow_only':True,'ranking_policy':'Existing gate order only; no new score or probability. Names are source identities, not promoted TARGETs.'}
(R/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['processed_documents','relation_connections_event_pairs','relation_connections_unique_document_pairs','independent_pairs','PARTIAL_SCOPE_PAIR','DATA_WAIT','EARLY_candidates','common_relation_blockers','common_blockers']},ensure_ascii=False,indent=2))
print('TOP',[(x['source_identity'],x['state'],x['independent']) for x in top])
