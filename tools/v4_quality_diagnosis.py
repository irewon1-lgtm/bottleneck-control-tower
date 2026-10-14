"""Read-only, non-scoring cause audit; never repairs model replies or gold."""
from collections import Counter
import json
from pathlib import Path
from bct.v4.free_ai import validate_reading, APIError
from bct.v4.store import now

R = Path('docs/v4/stage4-corpus/round3')


def main():
    inputs = {r['document_id']: r for r in json.loads((R/'inputs.json').read_text())['documents']}
    gold = {r['document_id']: r for r in json.loads((R/'event-gold.json').read_text())['documents']}
    causes, documents = Counter(), []
    for path in sorted((R/'responses').glob('*.json')):
        received = json.loads(path.read_text())
        if not received['response']:
            continue
        did = received['document_id']
        row = inputs[did]
        source, body = row['source'], row['doc']['body']
        detail, local = [], Counter()
        try:
            raw = json.loads(received['response']['text'])['items']
            checked = validate_reading(received['response']['text'], row['doc'], source)
        except (ValueError, KeyError, APIError):
            causes['WHOLE_PACKET_FORMAT_FAILURE'] += 1
            documents.append({'document_id': did, 'status': 'FORMAT_NOT_SCORED_HERE'})
            continue
        accepted = {v['input_item_index']: v for v in checked['items']}
        for index, item in enumerate(raw):
            context = next((w['text'] for i,w in enumerate(source['windows']) if 'w'+str(i)==item['context_id']), '')
            values = [('entity',item['entity'])] + [(f['field'],f['value']) for f in item['facts']]
            for field,value in values:
                if value in context:
                    continue
                location = ('OTHER_TRANSMITTED_WINDOW' if any(value in w['text'] for w in source['windows'])
                            else 'UNREAD_BODY' if value in body else 'NOWHERE_LITERAL_IN_BODY')
                local[field.upper()+'_VALUE_'+location] += 1
                detail.append({'item':index,'field':field,'literal_value':value,'location':location})
            if index in accepted:
                a = accepted[index]
                if (item['role'],item['actuality']) != (a['role'],a['actuality']):
                    local['MODEL_CLASSIFICATION_CHANGED_BY_EXISTING_SEMANTICS'] += 1
                    detail.append({'item':index,'model_role':item['role'],'model_actuality':item['actuality'],
                                   'retained_role':a['role'],'retained_actuality':a['actuality']})
        expected = [(t,e) for t in gold[did]['targets'] for e in t['events']
                    if any(f['field']=='product' and f['status']=='VERIFIED_PRESENT' for f in e['facts'])]
        names = {i['entity'].casefold() for i in raw}
        omitted = [e['event_id'] for t,e in expected if not names & {x.casefold() for x in [t['entity'],*t.get('entity_aliases',[])]}]
        local['GOLD_PRODUCT_EVENT_WITH_NO_RAW_NAMED_ALIAS'] += len(omitted)
        if not raw:
            local['EMPTY_WITH_KNOWN_EVENT_PRODUCT' if expected else 'EMPTY_WITHOUT_SCORABLE_EVENT_PRODUCT'] += 1
        causes.update(local)
        documents.append({'document_id':did,'counts':dict(local),'details':detail,
                          'missing_raw_named_event_ids':omitted,'strict_rejections':checked['rejected_items']})
    output = {'at':now(),'scope':'DESCRIPTIVE_CAUSES_NOT_NEW_SCORING_CRITERIA',
              'non_disjoint_counts':dict(causes),'documents':documents,
              'old13_invalid_items_repaired':0,'old13_recalled':0,
              'discovery_only_products':'See measurement-audit.json; no extra product precision/recall invented.',
              'input_outside_frozen_windows':'UNREAD_NOT_MODEL_OMISSION',
              'post_output_inference_or_gold_changes':False}
    with (R/'cause-audit.json').open('x') as f:
        f.write(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(output['non_disjoint_counts'],ensure_ascii=False))


if __name__ == '__main__':
    main()
