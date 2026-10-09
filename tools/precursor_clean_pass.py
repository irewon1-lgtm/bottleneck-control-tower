"""Sequential clean verification with immutable per-gate evidence receipts.

This runner verifies implementation and source replay. Actual prospective
discovery is a separate required performance gate and never defaults to PASS.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from bct import precursor_collection as c, precursor_evidence_graph as g
from precursor_source_span_qa import run as source_spans
from precursor_backfill_qa import snapshot,validate,metrics


def run(output,baseline,caches,golds):
    output.mkdir(parents=True,exist_ok=False)
    repository=Path(__file__).resolve().parents[1]
    inputs={str(p):snapshot(p) for p in caches};expected=json.loads(baseline.read_text())
    version={str(p.relative_to(repository)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('src','tools','tests','.github/scripts') for p in sorted((repository/folder).rglob('*')) if p.is_file() and p.suffix in ('.py','.js')}
    receipt={'started_at':datetime.now(timezone.utc).isoformat(),'base_commit':expected['commit'],'code_manifest_sha256':hashlib.sha256(json.dumps(version,sort_keys=True).encode()).hexdigest(),'code_files':version,'gates':[],
             'prospective_performance':'NOT_RUN_REQUIRES_SEPARATE_NEW_SOURCE_TRIAL','full_corpus_coverage':'NOT_ASSESSED_BY_THIS_SUBSET_RUN'}
    def save(): (output/'receipt.json').write_text(json.dumps(receipt,indent=2))
    def gate(name,fn):
        at=datetime.now(timezone.utc).isoformat()
        try:
            observed=fn();row={'gate':name,'started_at':at,'state':'PASS','observed':observed}
        except Exception as exc:
            row={'gate':name,'started_at':at,'state':'FAIL','error':str(exc)}
            receipt['gates'].append(row);save();raise
        receipt['gates'].append(row);save()
    def command(name,args):
        result=subprocess.run(args,cwd=repository,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (output/(name+'.log')).write_text(result.stdout)
        if result.returncode:raise RuntimeError(name+' exited '+str(result.returncode))
        return {'returncode':result.returncode,'log':name+'.log','tail':result.stdout.splitlines()[-10:]}
    def preservation():
        for path,value in expected['preserved_files'].items():
            if hashlib.sha256((repository/path).read_bytes()).hexdigest()!=value:raise AssertionError('protected file changed: '+path)
        return {'protected_files':len(expected['preserved_files']),'engine_hashes':c.hashes()}
    gate('0_protected_baseline',preservation)
    gate('0_all_python_regression',lambda:command('python',[sys.executable,'-m','pytest','-q']))
    gate('1_frozen_source_recognition',lambda:recognition(caches[0],golds,output))
    gate('2_3_same_target_and_temporal_falsification',lambda:command('target-gap',[sys.executable,'-m','pytest','-q','tests/test_precursor_target_gap.py','tests/test_precursor_collection.py','tests/test_precursor_evidence_graph.py','tests/test_precursor_source_pipeline.py','tests/test_precursor_probe_metadata.py']))
    def replay():
        documents=[d for cache in caches for d in c.stored_documents(cache)]
        at=datetime.now(timezone.utc).isoformat()
        first=g.analyze(documents,mode='BACKFILL',now=at);second=g.analyze(documents,mode='BACKFILL',now=at)
        keys=('observations','edges','rejected_links','targets','pairs','blocked','complete_target_events','independent_pairs','comparable_period_pairs','reference_checks')
        if {k:first[k] for k in keys}!={k:second[k] for k in keys}:raise AssertionError('non-deterministic source replay')
        refs=validate(documents)
        if inputs!={str(p):snapshot(p) for p in caches}:raise AssertionError('original cache bytes changed')
        (output/'actual-source-graph.json').write_text(json.dumps(first,ensure_ascii=False))
        value={'mode':'BACKFILL_REGRESSION_NOT_LIVE','documents':len(documents),'source_facts_references_checked':refs,'graph_references_checked':first['reference_checks'],
               'input_caches_unchanged':True,'deterministic_replay':True,'complete_target_events':first['complete_target_events'],'independent_pairs':first['independent_pairs'],
               'comparable_period_pairs':first['comparable_period_pairs'],'cross_document_edges':sum(e['references'][0]['document_id']!=e['references'][1]['document_id'] for e in first['edges']),
               'backfill_early':len(first['protected_result']['candidates']),'metrics':metrics(documents,at)[0]}
        (output/'actual-source-summary.json').write_text(json.dumps(value,indent=2));return value
    gate('4_actual_source_replay_available_subset',replay)
    gate('4_javascript_regression',lambda:command('javascript',['node','--test',*map(str,sorted((repository/'tests').glob('*.js')))]))
    gate('4_final_protected_baseline',preservation)
    receipt['implementation_state']='PASS';receipt['objective_state']='NOT_COMPLETE_PERFORMANCE_NOT_RUN';save()
    print(json.dumps({k:receipt[k] for k in ('implementation_state','objective_state','code_manifest_sha256')}))
    return receipt


def recognition(cache,golds,output):
    value=source_spans(cache,golds);(output/'source-spans.json').write_text(json.dumps(value,ensure_ascii=False,indent=2))
    if value['state']=='FAIL':raise AssertionError('labelled literal source recognition failed')
    return {k:v for k,v in value.items() if k!='rows'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--cache',type=Path,action='append',required=True);p.add_argument('--gold',type=Path,action='append',required=True)
    a=p.parse_args();run(a.output,a.baseline,a.cache,a.gold)
