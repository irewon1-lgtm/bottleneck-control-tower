"""Frozen-cohort diagnostics: physical targets, events and processing separate."""
import json,pathlib
from collections import Counter
from bct.v4.comparison_evaluation import score_products,score_events
from bct.v4.evidence_path import accept
from bct.v4.event_evaluation import assess,metrics,check_gold
from bct.v4.store import now,sha
R=pathlib.Path('docs/v4/path-comparison/final')


def total(rows):
    c=Counter()
    for x in rows:
        c.update({k:v for k,v in x.items()if type(v)is int and k not in('precision_denominator','recall_denominator')})
    return metrics(c)


def legacy_records(x):
    out=[]
    old=x['legacy_connection'];forward={e.get('advisory_item')for e in old['forwarded_events']}
    for reading in old['validated_readings'].values():
        for i in reading['items']:
            if not i['physical_exploration_lead']:continue
            out.append({'id':sha(i),'product':{'surface':i['entity']['value']},'context':i['context'],
                        'role':i['role'],'actuality':i['actuality'],
                        'event_status':'ADOPTED_RESEARCH_EVENT'if i['input_item_index']in forward else'DISCOVERY_ONLY'})
    return out


def field_view(records):
    return [{'kind':'PHYSICAL_PRODUCT','entity':{'value':r['product']['surface']},'context':r['context'],
             'role':r['role']if r['event_status']=='ADOPTED_RESEARCH_EVENT'else'UNKNOWN',
             'actuality':r['actuality']if r['event_status']=='ADOPTED_RESEARCH_EVENT'else'UNKNOWN',
             'facts':[{'field':k,'value':v['surface']}for k,v in r.get('fields',{}).items()]}for r in records]


def main():
    f=json.loads((R/'freeze.json').read_text())
    for p,h in f['file_sha256'].items():assert sha(pathlib.Path(p).read_bytes())==h
    assert sha((R/'event-gold.json').read_bytes())==json.loads((R/'gold-freeze.json').read_text())['gold_sha256']
    rows={r['document_id']:r for r in json.loads((R/'inputs.json').read_text())['documents']};golds={g['document_id']:g for g in json.loads((R/'event-gold.json').read_text())['documents']};documents=[];usage=Counter();processing=Counter()
    for did,row in rows.items():
        cpu=json.loads((R/'cpu'/(did+'.json')).read_text());response=R/'responses'/(did+'.json')
        if not response.exists():processing['unattempted']+=1;continue
        x=json.loads(response.read_text());receipt=x['receipt'];processing['attempted']+=int(bool(receipt.get('attempt_id')))
        if receipt['status']!='RECEIVED':processing['HTTP_or_provider_failed']+=1;continue
        processing['received']+=1;usage.update(receipt['response']['usage']);check_gold(golds[did],row['doc'],row['source']['windows'])
        if 'packet_error'in x:processing['packet_invalid']+=1;continue
        processing['source_held_items']+=len(x['source_held']);alternative=x['alternative']['records'];old=legacy_records(x)
        physical_cpu=[{'product':{'surface':s['text']}}for s in cpu.get('spans',[])if s['label']=='product']
        fields=assess(field_view(alternative),golds[did],row['doc'],row['source']['windows'])
        d={'document_id':did,'CPU_status':cpu['status'],'CPU_product':score_products(physical_cpu,golds[did])if cpu['status']=='PASS'else None,
           'old_connection_product':score_products(old,golds[did]),'alternative_product':score_products(alternative,golds[did]),
           'old_connection_events':score_events(old,golds[did]),'alternative_events':score_events(alternative,golds[did]),
           'literal_field_diagnostic_not_semantic_adoption':fields,'old_holds':x['legacy_connection']['held'],
           'alternative_holds':x['alternative']['held'],'source_held':x['source_held'],'S1_targets':[list(r['target'].keys())for r in alternative if r['s_stage']=='S1'],
           'counts':x['alternative']['counts']}
        documents.append(d)
    common=[d for d in documents if d['CPU_product']is not None]
    summary={k:total(d[k]for d in common)for k in('CPU_product','old_connection_product','alternative_product','old_connection_events','alternative_events')}
    old,new=summary['old_connection_events'],summary['alternative_events']
    comparable=all(x is not None for x in(old['precision'],old['recall'],new['precision'],new['recall']))
    gate=(comparable and new['precision']>=old['precision']and new['recall']>=old['recall']and(new['precision']>old['precision']or new['recall']>old['recall']))
    report={'at':now(),'scope':'One final6 source-reviewed partial-input cohort; separate blind AI review, not human. No re-tuning after outputs. Same new JSON-mode model facts to two connectors; historical strict Groq generation NOT_RUN/BLOCKED, not represented by this comparison.',
      'processing':dict(processing),'comparison_documents':len(common),'metrics':summary,
      'actual_received_input_chars':sum(rows[d['document_id']]['source']['selected_characters']for d in documents),
      'all_selected_body_chars':sum(len(r['doc']['body'])for r in rows.values()),'unread_body_is_not_model_FN':True,
      'adoption_gate':{'metric_comparable':comparable,'minimum_event_P_R_gate':gate,'precision_zero_denominator':'N/A_not0or100','serious_evidence_violations':'Source-unmatched facts held; semantic errors counted separately. No global S3 activation.','scope':'Research connector source-verified records only; broad auto-reader deployment NOT_AUTHORIZED'},
      'usage':{'generation_POST_attempts':processing['attempted'],'reported_tokens':dict(usage),'failed_tokens':'UNKNOWN'if processing['attempted']!=processing['received']else 0,'Free_API_cost_KRW':0,'platform_cost':'UNKNOWN_SEPARATE'},
      'S1_S2_S3':{'new_research_item_counts':{k:sum(d['counts'][k]for d in documents)for k in('S1','S2','S3')},'new_unique_target_counts_require_cross_doc_review':True,'operating_changes':0,'independent_verified_demand_supply_pairs':0,'lead_performance':'NOT_RUN'},
      'documents':documents}
    with(R/'scores.json').open('x')as f:f.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in('processing','metrics','adoption_gate','usage','S1_S2_S3')},ensure_ascii=False))


if __name__=='__main__':main()
