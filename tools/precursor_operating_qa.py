"""Run the deployed RSS wrapper on a copy of a historical cache, offline."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

from bct import precursor_collection as c, prospective
from precursor_backfill_qa import run, snapshot


def verify(cache,output):
    cache=Path(cache);output=Path(output);before=snapshot(cache)
    report=run(cache,'2026-10-08T14:11:35+00:00')
    assert report['preservation']['source_input_sha256']=='acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec'
    assert report['before']['verified_documents']==report['after']['verified_documents']==230
    root=output.parent/'operating-cache-copy'
    if root.exists():raise ValueError('QA copy already exists; preserve original run evidence')
    shutil.copytree(cache,root)
    def denied(*args,**kwargs):raise AssertionError('QA MUST NOT FETCH OR SEARCH')
    c.acquisition.fetch=denied;c.acquisition.search=denied
    script=Path(__file__).resolve().parents[1]/'.github/scripts/new_precursor_cycle.py'
    spec=importlib.util.spec_from_file_location('operating_wrapper',script);wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
    summary=wrapper.run({'collection_started_at':c.acquisition.now(),'documents':[], 'qa_copy_only':True},root,search_endpoint=c.DEFAULT_SEARCH_ENDPOINT)[-1]
    assert summary['scope_reader_version']=='source-scope-reader-2'
    assert summary['backfill_qa_documents']==230 and summary['requests_this_cycle']==0
    assert summary['live_execution']=={'state':'NO_EARLY_CANDIDATE','frozen':0}
    assert snapshot(cache)==before
    report['operating_wrapper']={'state':'PASS','module':str(script.relative_to(script.parents[2])),
        'scope_reader_version':summary['scope_reader_version'],'backfill_qa_documents':230,
        'external_requests':0,'new_live_early_candidates':0,'live_write_count':0,'cache_original_unchanged':True}
    report.pop('examples')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['operating_wrapper']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();verify(args.cache,args.output)
