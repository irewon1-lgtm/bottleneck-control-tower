"""One sealed BACKFILL A/B comparison on stored events; no production writes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
from bct import precursor_v2 as v
from bct.shadow_v2 import engine_hashes
from source_count_only import build_relaxed, observed_origin_details

ROOT = Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def status(value):return 'PASS' if value else 'FAIL'


def field_condition(a, b, key):
    x, y = v.value(a,key), v.value(b,key)
    return 'UNKNOWN' if v.UNKNOWN in (x,y) else status(x==y)


class Visible(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip=0; self.parts=[]
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'):self.skip+=1
    def handle_endtag(self, tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
    def handle_data(self, data):
        if not self.skip:self.parts.append(data)


def item_conditions(a, b, result, details, relaxed):
    demand_window, supply_window = result['demand_window'], result['supply_window']
    customer = v.value(a,'customer')!=v.UNKNOWN and v.value(a,'customer')==v.value(b,'customer')
    contract = (v.value(a,'contract')!=v.UNKNOWN and v.value(a,'contract')==v.value(b,'contract') and v.fact(b,'allocated'))
    allocation_known = any(v.value(e,k)!=v.UNKNOWN for e in (a,b) for k in ('customer','contract'))
    windows = bool(demand_window and supply_window)
    # These states describe evaluated evidence gates, not global absence proofs.
    return {
        'document_eligibility_and_provenance': 'PASS',
        'source_trace_and_event_integrity': 'PASS',
        'observed_two_independent_origins': status(details['original_independent']),
        'minimum_two_origins_enforcement': status(details['original_independent'] or (relaxed and details['retained_source_checks_pass'])),
        'direct_original_not_requotation': status(all(details['direct_origin'])),
        'distinct_demand_supply_quotes': status(details['distinct_source_quotes']),
        'DEMAND_SUPPLY_roles': status(a['role']=='DEMAND' and b['role']=='SUPPLY'),
        'TARGET_identity': status(result['relation']['state']=='VERIFIED'),
        'region': field_condition(a,b,'region'),
        'qualification_applicability':field_condition(a,b,'qualification'),
        'customer_or_contract_allocation': 'PASS' if customer or contract else 'FAIL' if allocation_known else 'UNKNOWN',
        'qualified_readiness_binding':status(bool(v.fact(b,'qualification_bound'))),
        'committed_demand':status(bool(v.fact(a,'committed'))),
        'demand_need_period':'PASS' if demand_window else 'UNKNOWN',
        'supply_qualified_readiness_period':'PASS' if supply_window else 'UNKNOWN',
        'future_demand_check':status(demand_window['end']>=v.clock(result['evaluated_at']).date().isoformat()) if demand_window else 'NOT_EVALUATED',
        'readiness_order_comparison':status(supply_window['start']>demand_window['end']) if windows else 'NOT_EVALUATED',
        'quantity_same_period_check':status((demand_window['start'],demand_window['end'])==(supply_window['start'],supply_window['end'])) if windows else 'NOT_EVALUATED',
        'quantity_unit_basis_and_gap':'PASS' if result['comparison']=='COMPARABLE_QUANTITY_GAP' else 'UNKNOWN' if windows else 'NOT_EVALUATED',
        'proven_gap_or_readiness_delay': 'PASS' if result['comparison'] else 'FAIL' if windows else 'NOT_EVALUATED',
        'context_refutation_scan':status(not result['refuted']),
        'qualified_alternative_capacity_check':'NOT_EVALUATED' if not windows else 'UNKNOWN',
        'context_confirmation_scan':'PASS' if result['prior_confirmation']=='NONE_OBSERVED' else 'FAIL',
        'global_first_confirmation_T':'UNKNOWN',
        'formal_T_scope':'UNKNOWN',
        'EARLY_eligible':status(result['early_eligible']),
    }


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve()
    if output.exists():raise SystemExit('OUTPUT_EXISTS_SINGLE_VALID_COMPARISON_NOT_REPEATED')
    output.mkdir(parents=True)
    started=datetime.now(timezone.utc).isoformat()
    try:
        manifest=json.loads((ROOT/'manifest.json').read_text())
        seal=json.loads((ROOT/'diagnostic-seal.json').read_text())
        for name, expected in seal['sha256'].items():
            if sha(ROOT/name)!=expected:raise ValueError('PREOUTPUT_DIAGNOSTIC_SEAL_CHANGED:'+name)
        fixed_path=ROOT/'original/fixed-input.json'
        if sha(fixed_path)!=manifest['fixed_input_sha256']:raise ValueError('FIXED_INPUT_CHANGED')
        for name, proof in manifest['original_files'].items():
            path=ROOT/name
            if sha(path)!=proof['stored_sha256']:raise ValueError('ORIGINAL_PRESERVATION_CHANGED:'+name)
            raw=gzip.decompress(path.read_bytes()) if proof['gzip'] else path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=proof['original_sha256']:raise ValueError('ORIGINAL_BYTES_CHANGED:'+name)
        if engine_hashes()!=manifest['engine_hashes']:raise ValueError('FROZEN_ENGINE_HASH_MISMATCH')
        fixed=json.loads(fixed_path.read_text());docs=fixed['documents'];es={e['event_id']:e for e in fixed['events']}
        if v.digest(fixed['events'])!=manifest['fixed_extraction_sha256']:raise ValueError('STORED_EXTRACTION_CHANGED')
        if v.digest(fixed['relationships'])!=manifest['fixed_relationships_sha256']:raise ValueError('STORED_RELATIONSHIPS_CHANGED')
        if [e['pair_id'] for e in fixed['selected_pairs']]!=manifest['pair_ids']:raise ValueError('PAIR_SCOPE_CHANGED')
        ds={d['document_id']:d for d in docs};relaxed,patch=build_relaxed()
        kw={'documents':docs,'as_of':fixed['as_of'],'relationships':fixed['relationships'],
            'context_events':fixed['events'],'previous_first':fixed['previous_first'],'first_frozen_at':fixed['first_frozen_at']}
        source_review=json.loads((ROOT/'source-review.json').read_text())
        rawtext={}
        for did in manifest['primary_document_ids']:
            data=gzip.decompress((ROOT/'original/sources'/(did+'.html.gz')).read_bytes()).decode('utf-8',errors='strict')
            text=Visible();text.feed(data);rawtext[did]=' '.join(' '.join(text.parts).split())
        items=[];A=[];B=[]
        for seq,saved in enumerate(fixed['selected_pairs'],1):
            demand,supply=es[saved['demand_event_id']],es[saved['supply_event_id']]
            a=v.evaluate_pair_v2(demand,supply,**kw)
            if a!=saved:raise ValueError('BASELINE_SAVED_DECISION_MISMATCH:'+saved['pair_id'])
            b=relaxed(demand,supply,**kw)
            # Independent remains an observed fact. Only gate reason and consequent
            # final decision/hash may differ; every other decision value must match.
            allowed={'reasons','state','early_eligible','decision_sha256'}
            differences=[k for k in a if a[k]!=b[k]]
            if any(k not in allowed for k in differences):raise ValueError('NON_ORIGIN_DECISION_CHANGED:'+saved['pair_id'])
            details=observed_origin_details(demand,supply,docs)
            expected=[r for r in a['reasons'] if r!='INDEPENDENT_ORIGINS_MISSING'] if details['retained_source_checks_pass'] else a['reasons']
            if b['reasons']!=expected:raise ValueError('SOURCE_GATE_RELEASE_INCOMPLETE_OR_EXTRA_CHANGE')
            refs=[demand['reference'],supply['reference']]
            for ref in refs:v.verify_reference(ref,ds)
            raw_matches=[(' '.join(ref['quote'].split()) in rawtext[ref['document_id']]) for ref in refs]
            label=next((v.value(demand,k) for k in ('facility','model','product','contract') if v.value(demand,k)!=v.UNKNOWN and v.value(demand,k)==v.value(supply,k)),v.UNKNOWN)
            did=demand['document_id'];review=source_review['documents'][did]
            for note in review['observations']:
                quote=note.get('quote')
                if quote and quote not in ds[did]['body']:raise ValueError('SOURCE_AUDIT_QUOTE_NOT_IN_ORIGINAL:'+did)
            item={'row':seq,'relation_id':saved['pair_id'],'demand_event_id':demand['event_id'],'supply_event_id':supply['event_id'],
                'document_ids':sorted({demand['document_id'],supply['document_id']}),'TARGET_source_identity':label,
                'TARGET_id':a['target_id'],'TARGET_is_formally_created':a['target_id'] is not None,
                'origin_observations':details,'A':a,'B':b,'conditions_A':item_conditions(demand,supply,a,details,False),
                'conditions_B':item_conditions(demand,supply,b,details,True),'decision_fields_changed':differences,
                'other_blockers':b['reasons'],'body_reference_check':'PASS','raw_HTML_quote_check':[status(x) for x in raw_matches],
                'source_review':review,'document_confirmation':review['document_confirmation'],
                'same_TARGET_confirmation':review['same_TARGET_confirmation'],'T':'UNKNOWN','T_scope':'UNKNOWN',
                'observed_confirmation_document_publication':ds[did]['published_at'] if review['document_confirmation']=='YES' else None,
                'not_an_earliest_public_confirmation_proof':True,
                'classification':'BACKFILL_DIAGNOSTIC_NOT_LIVE_NOT_EARLY_PERFORMANCE',
                'conclusion':'All other gates still required; no information absence or population performance claim.'}
            items.append(item);A.append(a);B.append(b)
        valid={'experiment_valid':True,'valid_comparison_runs':1,'invalid_comparison_runs':0,'comparison_started_at':started,
            'original_as_of':fixed['as_of'],'same_documents_and_extractions':True,'no_AI_reextraction':True,
            'automatic_reextraction_only_for_original_integrity_validator':True,'baseline_exactly_reproduces_saved_decisions':True,
            'single_AST_predicate_only_changed':patch['all_other_AST_nodes_identical'],
            'observed_independence_and_origin_counts_unchanged':True,'original_commit':seal['original_commit'],
            'diagnostic_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'fixed_input_sha256':sha(fixed_path),'frozen_diagnostic_seal_sha256':sha(ROOT/'diagnostic-seal.json'),
            'A_input_sha256':v.digest(kw),'B_input_sha256':v.digest(kw),'engine_hashes':engine_hashes()}
        protected=json.loads((ROOT/'protected-before.json').read_text())
        changed=[path for path,h in protected.items() if not Path(path).exists() or sha(path)!=h]
        if changed:raise ValueError('PROTECTED_RECORD_OR_CODE_CHANGED:'+str(changed))
        countA=sum(e['early_eligible'] for e in A);countB=sum(e['early_eligible'] for e in B)
        added=[e['pair_id'] for e in B if e['early_eligible'] and not next(a for a in A if a['pair_id']==e['pair_id'])['early_eligible']]
        summary={**valid,'relations':len(items),'primary_documents':manifest['primary_document_count'],
            'source_identity_TARGETs':manifest['source_identity_target_count'],'formal_TARGETs_created':0,
            'context_documents':len(docs),'context_events':len(es),'baseline_pass':countA,'relaxed_pass':countB,
            'additional_pass':len(added),'additional_pair_ids':added,'source_gate_relaxed_pairs':sum(i['origin_observations']['retained_source_checks_pass'] for i in items),
            'requote_still_blocked':sum(not i['origin_observations']['retained_source_checks_pass'] for i in items),
            'other_blocker_counts':dict(Counter(r for i in items for r in i['other_blockers'])),
            'protected_changes':changed,'interpretation':'이 고정 입력에서 출처 수만 완화한 효과가 확인되지 않았다.',
            'scope_limit':'17 previously VERIFIED relations in four documents only; no population effect, causal source coverage claim, holdout or LIVE success.',
            'next_minimal_action':'별도 작업에서 Hemerdon 원문에 명시된 Q1 2027 ramp 표현의 기간 해석 가능성만 단위시험한다. 본 실험 입력·추출은 수정하지 않는다.'}
        save(output/'comparison-A.json',{'mode':'BACKFILL_DIAGNOSTIC','evaluations':A})
        save(output/'comparison-B.json',{'mode':'BACKFILL_DIAGNOSTIC','evaluations':B})
        save(output/'item-table.json',{'items':items})
        save(output/'validity-and-summary.json',summary)
        save(output/'AST-isolation-proof.json',patch)
        (output/'diagnostic-function.diff').write_text(patch['function_diff'])
        lines=['| 관계 | TARGET 식별자 | 원출처 | A | B | 출처 외 차단 | 문서 confirmation / TARGET confirmation | T / T_scope |',
               '|---|---|---:|---|---|---|---|---|']
        for i in items:
            lines.append(f"| {i['row']:02d} `{i['relation_id'][:12]}` | {i['TARGET_source_identity']} | {i['origin_observations']['observed_origin_id_count']} | {i['A']['state']} | {i['B']['state']} | {'; '.join(i['other_blockers'])} | {i['document_confirmation']} / {i['same_TARGET_confirmation']} | UNKNOWN / UNKNOWN |")
        (output/'item-table.md').write_text('\n'.join(lines)+'\n')
        print(json.dumps({k:summary[k] for k in ('experiment_valid','valid_comparison_runs','relations','primary_documents','baseline_pass','relaxed_pass','additional_pass','source_gate_relaxed_pairs','requote_still_blocked','other_blocker_counts')},ensure_ascii=False))
    except Exception as error:
        save(output/'INVALID.json',{'started_at':started,'experiment_valid':False,'error':repr(error),
            'rule':'Keep failure. Only repair execution errors; do not alter sealed input/sample/predicates.'})
        raise


if __name__=='__main__':main()
