"""Consumed-source oracle injection, not automatic or independent performance."""
import json,pathlib
from collections import Counter
from bct.v4.free_ai import validate_reading,APIError
from bct.v4.research_adapter import analyze as old_analyze
from bct.v4.evidence_path import analyze,save
from bct.v4.store import Ledger,now,sha
R=pathlib.Path('docs/v4/path-comparison')
C=pathlib.Path('docs/v4/stage4-corpus')


def located(value,ref):
    q=ref['quote'];a=q.find(value)
    if a<0 or q.find(value,a+1)>=0:raise ValueError('ORACLE_LITERAL_POSITION_AMBIGUOUS')
    return {'value':value,'reference':{'start':ref['start']+a,'end':ref['start']+a+len(value),'quote':value}}


def sources():
    groups=[]
    manifest=json.loads((C/'manifest.json').read_text())['documents'];safe={r['document_id']:r for r in json.loads((C/'safe-inputs-v1.json').read_text())['documents']}
    rows={}
    for m in manifest:
        s=safe.get(m['document_id'])
        if not s or not s.get('source'):continue
        body=pathlib.Path(m['body_path']).read_text();doc={'document_id':m['document_id'],'body':body,'body_sha256':sha(body.encode()),'origin_url':m['url'],'origin_id':m['url'],'origin_publisher':m.get('publisher','UNKNOWN'),'published_at':m.get('published_at','UNKNOWN'),'acquired_at':m.get('acquired_at','UNKNOWN')}
        rows[m['document_id']]={'doc':doc,'source':s['source']}
    groups.append(('development',rows,json.loads((C/'event-gold-development-v1.json').read_text())['documents']))
    for name in ('round2','round3'):
        rows={r['document_id']:r for r in json.loads((C/name/'inputs.json').read_text())['documents']}
        groups.append((name+'_CONSUMED',rows,json.loads((C/name/'event-gold.json').read_text())['documents']))
    return groups


def main():
    pool=[]
    for group,rows,golds in sources():
        for gold in golds:
            if not gold['review_complete']or gold['document_id']not in rows:continue
            row=rows[gold['document_id']]
            for target in gold['targets']:
                for event in target['events']:
                    facts={}
                    for fact in event['facts']:
                        if fact['status']=='VERIFIED_PRESENT':facts.setdefault(fact['field'],fact)
                    if not {'product','role','actuality'}<=facts.keys():continue
                    if facts['role']['value']not in ('DEMAND_INCREASE','SUPPLY_INCREASE','SUPPLY_DECREASE','SUPPLY_DELAY','RELIEF'):continue
                    pool.append((group,row,target,event,facts))
    selected=[]
    for role in ('DEMAND_INCREASE','SUPPLY_DECREASE','SUPPLY_DELAY','RELIEF','SUPPLY_INCREASE'):
        selected.extend([x for x in pool if x[-1]['role']['value']==role][:4])
    selected.extend(x for x in pool if x not in selected);selected=selected[:24]
    result=[];docs={};proposals={};counts=Counter()
    for group,row,target,event,facts in selected:
        doc=row['doc'];did=doc['document_id'];reference=event['reference']
        assert doc['body'][reference['start']:reference['end']]==reference['quote']
        try:product=located(facts['product']['value'],facts['product']['reference'])
        except ValueError as error:
            counts.update({'cases':1,'oracle_location_held':1})
            result.append({'group':group,'document_id':did,'event_id':event['event_id'],'reference':reference,'oracle_location_held':str(error)})
            continue
        p={'reference':reference,'product':product,'role':facts['role']['value'],'actuality':facts['actuality']['value'],'fields':{},'independent_review':{'type':'SOURCE_ONLY_AI','exposed_to_target_outputs':False,'source_group':group,'event_id':event['event_id'],'human_verified':False}}
        for k,f in facts.items():
            if k in ('product','role','actuality'):continue
            try:p['fields'][k]=located(f['value'],f['reference'])
            except ValueError:pass
        legacy={'text':json.dumps({'items':[{'kind':'PHYSICAL_PRODUCT','role':p['role'],'actuality':p['actuality'],'context':{'quote':reference['quote']},'entity':{'value':product['value'],'quote':facts['product']['reference']['quote']},'facts':[]}]}),'source':{'windows':[{'start':reference['start'],'end':reference['end'],'text':reference['quote']}]}}
        try:
            checked=validate_reading(legacy['text'],doc,legacy['source'])
            old=old_analyze([doc],{did:legacy},enabled=True,mode='BACKFILL',as_of='2026-10-14T12:00:00+00:00')
            holds=old['held'];forwarded=len(old['forwarded_events'])
            stage='LEGACY_CONNECTED'if forwarded else 'SOURCE_VALIDATOR'if checked['rejected_items']else'LEGACY_RELATION_OR_PARSER'
            reasons=[x['reason']for x in checked['rejected_items']+holds]
            if not forwarded and not reasons:reasons=['NO_PHYSICAL_LEAD_OR_MEANING_UNKNOWN']
        except (APIError,ValueError,KeyError)as e:stage='LEGACY_EXCEPTION';reasons=[str(e)];forwarded=0
        alt=analyze([doc],{did:[p]},enabled=True,reviewed=True)
        counts.update({'cases':1,'legacy_events':forwarded,'alternative_events':alt['counts']['events']});counts.update('legacy:'+x for x in reasons)
        result.append({'group':group,'document_id':did,'event_id':event['event_id'],'product':product['value'],'role':p['role'],'actuality':p['actuality'],'reference':reference,'legacy_stage':stage,'legacy_reasons':reasons,'legacy_forwarded':forwarded,'alternative':alt})
        docs[did]=doc;proposals.setdefault(did,[]).append(p)
    ledger=Ledger('var/v4/path-comparison/oracle-ledger')
    with ledger.worker():stored=save(ledger,list(docs.values()),proposals,enabled=True,reviewed=True)
    ledger.close()
    output={'at':now(),'scope':'MAX24_CONSUMED_ACTUAL_SOURCE_ORACLE_INJECTION_NOT_MODEL_READING_NOT_NEW_HOLDOUT','counts':dict(counts),'synthetic_cases':0,'source_groups':sorted({x[0]for x in selected}),'documents':list(docs.values()),'proposals':proposals,'cases':result,'stored_counts':stored['counts'],'review_type':'SOURCE_ONLY_AI_REUSED_NOT_HUMAN','selection':'Four per available role first then existing ordered pool up to24; no final comparison use.'}
    (R/'oracle-results.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(counts)))


if __name__=='__main__':main()
