"""Research diagnostic units; never overwrites historical frozen scores."""
from .event_evaluation import metrics,norm


def physical_targets(gold):
    targets=[]
    for t in gold['targets']:
        states={f['status'] for e in t['events'] for f in e['facts'] if f['field']=='product'}
        kind=t.get('discovery_kind','')
        if 'VERIFIED_PRESENT'in states or (t.get('discovery_reference')and not any(x in kind for x in ('SOFTWARE','PROJECT','SERVICE','NON_PHYSICAL')) and 'VERIFIED_ABSENT'not in states):targets.append(t)
    return targets


def score_products(predictions,gold):
    expected=physical_targets(gold);found=set();extra=set();ambiguous=0
    for p in predictions:
        matches=[t for t in expected if norm(p['product']['surface'])in {norm(t['entity']),*(norm(a)for a in t.get('entity_aliases',[]))}]
        if len(matches)==1:found.add(matches[0]['target_id'])
        elif len(matches)>1:ambiguous+=1
        else:extra.add(norm(p['product']['surface']))
    return metrics({'TP':len(found),'FP':len(extra),'FN':len(expected)-len(found),'ambiguous':ambiguous})


def score_events(predictions,gold):
    expected=[]
    for t in gold['targets']:
        for e in t['events']:
            f={x['field']:x['value']for x in e['facts']if x['status']=='VERIFIED_PRESENT'}
            if {'product','role','actuality'}<=f.keys():expected.append((t,e,f))
    tp=set();fp=set();held=0
    for p in predictions:
        if p['event_status']!='ADOPTED_RESEARCH_EVENT':continue
        m=[(t,e,f)for t,e,f in expected if norm(p['product']['surface'])in{norm(t['entity']),*(norm(a)for a in t.get('entity_aliases',[]))} and e['reference']['start']<p['context']['end']and p['context']['start']<e['reference']['end']]
        if len(m)>1:held+=1;continue
        if len(m)==1 and p['role']==m[0][2]['role']and p['actuality']==m[0][2]['actuality']:tp.add(m[0][1]['event_id'])
        else:fp.add(p['id'])
    return metrics({'TP':len(tp),'FP':len(fp),'FN':len(expected)-len(tp),'ambiguous_event_predictions':held})
