"""Read-only consumed-development diagnosis. No inference or score mutation."""
import json,pathlib,collections
from bct.v4.comparison_evaluation import physical_targets,score_products
from bct.v4.event_evaluation import norm,metrics
from bct.v4.exploration import retain,save
from bct.v4.store import Ledger,sha,now
R=pathlib.Path('docs/v4/cpu-recovery');OLD=pathlib.Path('docs/v4/path-comparison/final')
rows={r['document_id']:r for r in json.load(open(OLD/'inputs.json'))['documents']};golds={d['document_id']:d for d in json.load(open(OLD/'event-gold.json'))['documents']};previous={d['document_id']:d for d in json.load(open('docs/v4/reading-quality/RESULTS.json'))['same_input_development']['documents_detail']}
cases=[];comparisons=[]
for did,row in rows.items():
 cpu=json.load(open(OLD/'cpu'/(did+'.json')));raw=json.loads(json.load(open(OLD/'responses'/(did+'.json')))['receipt']['response']['text'])['extractions'];old=previous[did]['validation']['records'];gold=golds[did];doc=row['doc'];windows=row['source']['windows']
 out=retain(doc,[cpu],raw)
 cp=[{'product':{'surface':s['text']}}for s in cpu['spans']if s['label']=='product'];retained=[{'product':{'surface':d['proposed_name']}}for d in out['discoveries']if d['origin']=='CPU'and d['product_candidate']]
 assert [s for s in cpu['spans']]==[d['original_proposal']for d in out['discoveries']if d['origin']=='CPU']
 comparisons.append({'document_id':did,'original_CPU':score_products(cp,gold),'retained_CPU':score_products(retained,gold),
    'CPU_plus_saved_AI_raw_discovery_only':score_products([{'product':{'surface':d['proposed_name']}}for d in out['discoveries']if d['product_candidate']],gold),
    'CPU_plus_prior_source_located_AI_discovery_only':score_products(cp+old,gold),
    'original_CPU_spans':len(cpu['spans']),'CPU_spans_retained':len([d for d in out['discoveries']if d['origin']=='CPU']),
    'actual_events_adopted':0,'new_CPU_runs':0,'new_AI_calls':0})
 oldnames={norm(r['product']['surface'])for r in old}
 for target in physical_targets(gold):
  aliases={norm(target['entity']),*(norm(a)for a in target.get('entity_aliases',[]))}
  if aliases&oldnames:continue
  ref=target['discovery_reference'];assert doc['body'][ref['start']:ref['end']]==ref['quote']
  inside=any(w['start']<=ref['start']<ref['end']<=w['end']for w in windows)
  ai=[(i,r)for i,r in enumerate(raw)if norm(r['event_attributes']['product'])in aliases]
  # Manual, diagnostic-only concept links for two altered model spellings.
  # They are never aliases/repairs for the validator, scorer or stored facts.
  observed_variant=None
  if did.endswith('db610ddf')and target['target_id']=='crude-oil':observed_variant=0
  if did.endswith('120e88f4')and target['target_id']=='electric-generating-capacity':observed_variant=0
  if observed_variant is not None:ai=[(observed_variant,raw[observed_variant])]
  cpumatches=[s for s in cpu['spans']if s['label']=='product'and norm(s['text'])in aliases]
  cause='1_INPUT_NOT_PRESENT'if not inside else'3_MODEL_PROPOSED_BUT_EXACT_CITATION_OR_IDENTITY_REJECTED'if ai else'2_MODEL_OMITTED_KNOWN_PRODUCT_IN_INPUT'
  cases.append({'document_id':did,'target_id':target['target_id'],'gold_entity':target['entity'],'source_reference':ref,
   'body_sha256':doc['body_sha256'],'inside_actual_AI_input':inside,'transmitted_windows':[{'start':w['start'],'end':w['end']}for w in windows],
   'original_model_candidates':[{'index':i,'original':r,'event_literal_in_input':any(r['event']in w['text']for w in windows),
     'product_literal_in_claimed_event':r['event_attributes']['product']in r['event']}for i,r in ai],
   'variant_link_not_validation_or_score_repair':observed_variant is not None,
   'primary_cause':cause,'matching_original_CPU_proposals':cpumatches,'CPU_exploration_recovered':bool(cpumatches),
   'automatic_AI_reading_fixed':False,'valid_fact_rejected_by_semantics_confirmed':False,
   'event_relation_note':'Physical exploration does not prove a purchase/supply event. Raw IC purchase role concerns burn-in use/output and remains held; no source event invented.',
   'next_action':'Keep exact CPU proposal as exploration and review event relation'if cpumatches else'Keep model/citation failure; do not invent/repair a literal name or claim CPU found it'})
assert len(cases)==18
summary={}
for key in ['original_CPU','retained_CPU','CPU_plus_saved_AI_raw_discovery_only','CPU_plus_prior_source_located_AI_discovery_only']:
 c=collections.Counter()
 for r in comparisons:
  for k in ['TP','FP','FN']:c[k]+=r[key][k]
 summary[key]=metrics(c)
assert [summary['retained_CPU'][k]for k in ['TP','FP','FN']]==[16,13,9]
result={'at':now(),'scope':'Consumed six-document development diagnostic; source/gold/responses/scores unchanged; no new inference.',
 'missing18':cases,'primary_cause_counts':dict(collections.Counter(c['primary_cause']for c in cases)),
 'CPU_exploration_recovered_from_AI_missing18':sum(c['CPU_exploration_recovered']for c in cases),'unresolved_in_CPU':sum(not c['CPU_exploration_recovered']for c in cases),
 'model_errors_fixed':0,'confirmed_valid_product_semantic_overfilter':0,'confirmed_product_entity_relationship_primary_cause':0,
 'comparison':comparisons,'metrics':summary,'AI_adoption':'FAIL_UNCHANGED','independent_evaluation':'BLOCKED_UNCHANGED',
 'explicit_limitation':'Union is exploration retention, never AI quality improvement. The two manually linked nonliteral model variants remain invalid and do not change frozen scores.'}
with(R/'development-diagnosis.json').open('x')as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({k:result[k]for k in ['primary_cause_counts','CPU_exploration_recovered_from_AI_missing18','unresolved_in_CPU','metrics']}))
