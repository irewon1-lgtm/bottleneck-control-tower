"""Measure literal recognition and safe binding separately on frozen gold.

All gold locators are checked against the exact body. Recognition elsewhere in
the same original is reported separately from recognition at the gold locator.
No previously inspected source is claimed as an untouched holdout.
"""
import argparse
import json
from pathlib import Path
from bct import precursor_collection as c, precursor_evidence_graph as g


def run(cache, gold_paths):
    docs={d['document_id']:d for d in c.stored_documents(cache)}
    rows=[];positive=recognized=bound=exact_locator=0
    for path in gold_paths:
        gold=json.loads(path.read_text())
        for case in gold['cases']:
            d=docs[case['document_id']]
            if d['body_sha256']!=case['body_sha256']:raise ValueError('GOLD_BODY_VERSION_MISMATCH')
            obs=g.observations(d)
            for key,label in case['fields'].items():
                value=label.get('source_value')
                if value is None:continue  # no exhaustive negative gold claim
                loc=label['locator']
                if d['body'][loc['start']:loc['end']]!=value:raise ValueError('GOLD_SOURCE_LOCATOR_MISMATCH')
                literals=[f for o in obs for f in o.get('literal_fields',{}).get(key,[])]
                linked=[o['fields'][key] for o in obs if key in o['fields']]
                def matches(f):
                    return g.norm(value) in g.norm(f['value']) and value.casefold() in d['body'][f['locator']['start']:f['locator']['end']].casefold()
                found=[f for f in literals if matches(f)]
                at_locator=any(f['locator']['start']<=loc['start'] and loc['end']<=f['locator']['end'] for f in found)
                bound_found=any(g.norm(value)==g.norm(f['value']) for f in linked)
                positive+=1;recognized+=bool(found);bound+=bound_found;exact_locator+=at_locator
                rows.append({'document_id':d['document_id'],'body_sha256':d['body_sha256'],'field':key,'gold':value,'gold_locator':loc,
                             'literal_recognized':bool(found),'recognized_at_gold_locator':at_locator,'exact_value_bound':bound_found,
                             'recognition_references':[f['reference'] for f in found],
                             'binding_state':'SOURCE_BOUND_VALUE_RECOGNIZED_TARGET_NOT_IMPLIED' if bound_found else 'RELATION_UNKNOWN_LITERAL_ONLY' if found else 'SOURCE_PRESENT_RECOGNITION_FAILURE'})
    return {'mode':'FROZEN_SOURCE_REGRESSION','positive_selected_fields':positive,'literal_recognized':recognized,
            'recognized_at_gold_locator':exact_locator,'exact_values_in_bound_observations':bound,
            'whole_corpus_precision':'UNKNOWN_NONEXHAUSTIVE_GOLD','actual_target_link_accuracy':'UNKNOWN_NO_COMPLETE_REAL_GOLD',
            'state':'PASS_LITERAL_RECOGNITION_ONLY' if positive==recognized else 'FAIL','rows':rows}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--gold',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();value=run(a.cache,a.gold);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='rows'}))
    raise SystemExit(0 if value['state'].startswith('PASS') else 1)
