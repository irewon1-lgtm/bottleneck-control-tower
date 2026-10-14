"""Score only pre-frozen round3 inputs under the existing event policy."""
from collections import Counter
import hashlib,json,pathlib
from bct.v4.event_evaluation import metrics,check_gold
from bct.v4.free_ai import validate_reading, APIError
from bct.v4.store import now
from v4_scoped_evaluation import score_document,verify_freeze
R=pathlib.Path('docs/v4/stage4-corpus/round3')

def add(rows):
 c=Counter()
 for row in rows:c.update({k:v for k,v in row.items() if type(v) is int and k not in ('precision_denominator','recall_denominator')})
 return metrics(c)


def main():
 f=verify_freeze(R);read=lambda p:json.loads(p.read_text())
 rows={x['document_id']:x for x in read(R/'inputs.json')['documents']};gold={x['document_id']:x for x in read(R/'event-gold.json')['documents']};cpu={x['document_id']:x for x in read(R/'cpu-baseline.json')['documents']}
 assert hashlib.sha256((R/'event-gold.json').read_bytes()).hexdigest()==read(R/'gold-freeze.json')['gold_sha256']
 responses=[read(p) for p in sorted((R/'responses').glob('*.json'))];docs=[];usage=Counter();causes=Counter();roles=Counter();field_holds=Counter()
 for x in responses:
  did=x['document_id'];row=rows[did];check_gold(gold[did],row['doc'],row['source']['windows'])
  if not x['response']:continue
  assert x['attempt']['request_contract']==f['request_contract'];usage.update(x['response']['usage'])
  c=cpu[did];valid_cpu=c['status']=='PASS'
  if valid_cpu:assert c['model']==f['models']['cpu'] and c['revision']==f['models']['cpu_revision']
  baseline=c if valid_cpu else {'selected_windows':row['source']['windows'],'spans':[]}
  try:
   s=score_document(row,gold[did],baseline,x['response']['text'])
   checked=validate_reading(x['response']['text'],row['doc'],row['source'])
  except (APIError,json.JSONDecodeError) as error:
   # Invalid whole packets adopt no claims; preserve raw packet and count known
   # misses, while raw/context evaluation remains unavailable, not an empty reply.
   s=score_document(row,gold[did],baseline,'{"items":[]}')
   reason=getattr(error,'kind','INVALID_JSON')
   s.update(source_status='FAIL',raw_context_only=None,raw_items=0,format_failure=reason)
   checked={'items':[],'rejected_items':[{'reason':reason}]}
   s['rejected_items']=checked['rejected_items']
  if not valid_cpu:s['common_product']['CPU']=None
  causes.update(y['reason'] for y in checked['rejected_items']);roles.update(y['role'] for y in checked['items'])
  field_holds.update(y['reason'] for item in checked['items'] for y in item.get('semantic_review',[]))
  docs.append({'document_id':did,'CPU_comparable':valid_cpu,**s,'source_and_meaning_advisory':checked['items']})
 common_docs=[d for d in docs if d['CPU_comparable']]
 common={k:add(d['common_product'][k] for d in common_docs) for k in ('CPU','Groq_source_adopted','Groq_context_entity_only')}
 fields=sorted({k for d in docs for k in d['adopted']['by_field']})
 all_groq=add(d['common_product']['Groq_source_adopted'] for d in docs)
 totals=add(d['adopted']['metrics'] for d in docs)
 old=read(pathlib.Path('docs/v4/stage4-corpus/round2/auth-resume/scores.json'))
 report={'at':now(),'status':'MEASURED_NEW_FROZEN_SOURCE_WINDOWS_NOT_LEAD_PERFORMANCE','freeze_sha256':hashlib.sha256((R/'freeze.json').read_bytes()).hexdigest(),
 'scope':'New unused20 before target outputs, no post-output inference/criterion changes. Same chosen page only, not full-body accuracy.',
 'gold_review':read(R/'gold-freeze.json'),
 'processing':{'selected_documents':len(rows),'eligible':sum(r['status']=='ELIGIBLE' for r in rows.values()),'execution_results':len(responses),'attempted':sum(x['attempt'] is not None for x in responses),'received':len(docs),'unattempted':[did for did in rows if did not in {r['document_id'] for r in responses if r['attempt']}],
 'HTTP_or_transport_without_response':[x['document_id'] for x in responses if x['attempt'] and not x['response']],'WAIT_before_attempt':[x['document_id'] for x in responses if not x['attempt']],'CPU_valid_documents':sum(c['status']=='PASS' for c in cpu.values()),'CPU_BLOCKED':[{'document_id':did,'reason':c['reason']} for did,c in cpu.items() if c['status']!='PASS'],
 'raw_items':sum(d['raw_items'] for d in docs),'source_advisory_items':sum(d['accepted_items'] for d in docs),'source_rejected_items':sum(len(d['rejected_items']) for d in docs),'source_rejection_causes':dict(causes),'empty_responses':sum(d['raw_items']==0 and not d.get('format_failure') for d in docs),'whole_packet_format_failures':[{'document_id':d['document_id'],'reason':d['format_failure']} for d in docs if d.get('format_failure')],'strict_source_PASS_documents_including_empty':sum(d['source_status']=='PASS' for d in docs)},
 'coverage':{'all20_body_characters':sum(len(r['doc']['body']) for r in rows.values()),'actual_received_input_characters':sum(rows[d['document_id']]['source']['selected_characters'] for d in docs),'actual_CPU_valid_input_characters':sum(rows[did]['source']['selected_characters'] for did,c in cpu.items() if c['status']=='PASS'),'whole_document_accuracy':'NOT_MEASURED','tables_attachments':'NOT_VERIFIED'},
 'same_input_product_comparison':{'documents':len(common_docs),**common,'CPU_other_meaning_fields':'UNSUPPORTED_NOT_COMPARABLE'},
 'Groq_all_received_product':all_groq,'Groq_all_adopted_fields':{'metrics':totals,'by_field':{field:add(d['adopted']['by_field'].get(field,{}) for d in docs) for field in fields}},
 'Groq_raw_context_fields':add(d['raw_context_only']['metrics'] for d in docs if d['raw_context_only']),
 'old13_reference_not_paired_before_after':{'old_product':old['common_product_comparison'],'old_source_rejected':8,'old_empty':6,'old_actual_input_characters':5717,'old_responses_recalled':0,'different_corpus_cannot_prove_causal_gain_from_this_difference':True},
 'roles_after_source_and_meaning':dict(roles),'field_semantic_holds':dict(field_holds),
 'adoption_gate':{'product_FP_decreased':common['Groq_source_adopted']['FP']<common['CPU']['FP'],'product_FN_not_increased':common['Groq_source_adopted']['FN']<=common['CPU']['FN'],'verified_wrong_adopted_claims':totals['FP'],'all20_comparison_complete':len(common_docs)==20,'AI_Shadow':'HOLD','operating_automation':'DISABLED','status':'HOLD_PENDING_FULL_SAFETY_AND_QUALITY_EVIDENCE'},
 'usage':{'POST_attempts':sum(x['calls'] for x in responses),'received_generations':len(docs),'reported_tokens':dict(usage),'failed_usage':'UNKNOWN' if sum(x['calls'] for x in responses)!=len(docs) else 0,'Free_API_cost_KRW':0,'platform_cost':'UNKNOWN_SEPARATE','auth_GETs':0,'new_model_installations':0},
 'S1_S2_S3':{'previous_known_research':[1,0,0],'evaluation_auto_promotions':0,'research_connection':'Report separately if executed; advisory roles alone are not S1/S2/S3'},'lead_performance':'NOT_RUN','documents':docs}
 with (R/'scores.json').open('x') as stream:stream.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ('processing','same_input_product_comparison','Groq_all_received_product','adoption_gate','usage')},ensure_ascii=False))


if __name__=='__main__':main()
