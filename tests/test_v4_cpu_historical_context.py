"""Historical partial/analysis-only work retains its exact original graph scope."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

from bct.v4 import cpu_automation as q,cpu_resume as resume
from bct.v4.store import sha
from test_v4_cpu_automation import document,Extractor
from test_v4_cpu_review_context import context_bundle


def receiver():
    path=Path(__file__).resolve().parents[1]/'.github/scripts/receive_cpu_delta.py'
    spec=importlib.util.spec_from_file_location('cpu_history_receiver',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('partial',[True,False])
def test_old_root_absent_current_rss_uses_saved_exact_context_and_only_unread_windows(tmp_path,partial):
    doc,native=document('Atlas ordered Helios heat pumps.\nA second separate paragraph.')
    doc['raw_path']=doc['raw_sha256']+'.html'
    cache=tmp_path/'input';(cache/'historical').mkdir(parents=True)
    historical=cache/'historical/10'
    manifest=context_bundle(historical,[(doc,native)],{doc['document_id']:[doc['document_id']]})
    metadata=json.dumps(manifest,sort_keys=True).encode();(historical/'manifest.json').write_bytes(metadata)
    artifact={'artifact_id':10,'digest':'c'*64,'acquisition_run_id':2,'acquisition_run_attempt':1,'head_sha':'a'*40,
        'document_member':'documents/0.json','native_member':'raw/'+doc['raw_sha256']+'.html',
        'metadata_sha256':sha((historical/'documents/0.json').read_bytes()),'manifest_sha256':sha(manifest)}
    ledger=q.open_queue(tmp_path/'original');q.enqueue(ledger,doc,native,{'input_artifact':artifact})
    q.work(ledger,extractor=Extractor(),max_windows=1 if partial else 24);ledger.close()
    resume.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'safe')
    tool=receiver();plan=tool.checkpoint_inputs(tmp_path/'safe/v4.sqlite3')
    assert plan['descriptors']==[artifact]
    assert tool.canonical_hash(tool.current_analysis_code(include_glue=True))==resume.analysis_code_fingerprint()
    # The receiver materializes the selected exact root for hydration while
    # preserving the entire small original bundle as its independent context.
    shutil.copytree(historical/'documents',cache/'documents');shutil.copytree(historical/'raw',cache/'raw')
    pointer={'cache_path':'historical/10','manifest_sha256':sha(metadata),'artifact_id':10,'digest':'c'*64,
             'acquisition_run_attempt':1,**{k:doc[k] for k in ('document_id','body_sha256','raw_sha256')}}
    ledger=q.open_queue(tmp_path/'safe');body_key=q.body_key(doc)
    policy={'source_separated_transient':{'status':'PERMITTED_PUBLIC_VERIFIED_LOCAL_ONLY','format':resume.FORMAT}}
    resume.hydrate(ledger,cache,policy,retry_analysis=True,analysis_document_ids=set(),analysis_body_keys=plan['analysis_needed'])
    model=Extractor();result=q.work(ledger,extractor=model,analysis_context={'cache':cache,'manifest':{
        'format':'bct-cpu-source-delta-1','graph_context_complete':True,'documents':[],
        'required_graph_sources':[],'unavailable_graph_sources':[],'files':{}},'per_body':{body_key:pointer}})
    assert model.calls==result['new_windows']==int(partial)
    analyzed=q.events(ledger,'CPU_ANALYSIS_RESULT')[-1]
    assert analyzed['review_state']=='READ_EVIDENCE_HOLD' and analyzed['read_state']=='READ_COMPLETE'
    assert analyzed['graph_context']['manifest_sha256']==sha(manifest)
    ledger.close();resume.export_state(tmp_path/'safe/v4.sqlite3',tmp_path/'next')
    assert tool.checkpoint_inputs(tmp_path/'next/v4.sqlite3')['descriptors']==[]


def test_unchanged_intrinsically_incomplete_context_is_not_refetched_forever(tmp_path):
    doc,native=document();doc['raw_path']=doc['raw_sha256']+'.html'
    cache=tmp_path/'cache';manifest=context_bundle(cache,[(doc,native)],{},complete=False)
    artifact={'artifact_id':10,'digest':'c'*64,'acquisition_run_id':2,'acquisition_run_attempt':1,'head_sha':'a'*40,
        'document_member':'documents/0.json','native_member':'raw/'+doc['raw_sha256']+'.html',
        'metadata_sha256':sha((cache/'documents/0.json').read_bytes()),'manifest_sha256':sha(manifest)}
    ledger=q.open_queue(tmp_path/'original');q.enqueue(ledger,doc,native,{'input_artifact':artifact})
    q.work(ledger,extractor=Extractor(),analysis_context={'cache':cache,'manifest':manifest})
    assert q.events(ledger,'CPU_ANALYSIS_RESULT')[-1]['review_state']=='GRAPH_CONTEXT_PENDING'
    ledger.close();resume.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'safe')
    assert receiver().checkpoint_inputs(tmp_path/'safe/v4.sqlite3')['descriptors']==[]


def test_verified_legacy_descriptor_is_upgraded_to_stop_unchanged_context_retries(tmp_path):
    doc,native=document();doc['raw_path']=doc['raw_sha256']+'.html'
    cache=tmp_path/'cache';manifest=context_bundle(cache,[(doc,native)],{},complete=False)
    old={'artifact_id':10,'digest':'c'*64,'acquisition_run_id':2,'acquisition_run_attempt':1,'head_sha':'a'*40,
        'document_member':'documents/0.json','native_member':'raw/'+doc['raw_sha256']+'.html',
        'metadata_sha256':sha((cache/'documents/0.json').read_bytes())}
    ledger=q.open_queue(tmp_path/'original');q.enqueue(ledger,doc,native,{'input_artifact':old})
    q.work(ledger,extractor=Extractor(),analysis_context={'cache':cache,'manifest':manifest});ledger.close()
    resume.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'safe')
    plan=receiver().checkpoint_inputs(tmp_path/'safe/v4.sqlite3');assert plan['descriptors']==[old]
    verified={**old,'manifest_sha256':sha(manifest)}
    ledger=q.open_queue(tmp_path/'safe')
    policy={'source_separated_transient':{'status':'PERMITTED_PUBLIC_VERIFIED_LOCAL_ONLY','format':resume.FORMAT}}
    resume.hydrate(ledger,cache,policy,retry_analysis=True,analysis_body_keys=plan['analysis_needed'],
        input_artifacts={'0.json':verified})
    model=Extractor();result=q.work(ledger,extractor=model,analysis_context={'cache':cache,'manifest':manifest})
    assert result['new_windows']==model.calls==0
    ledger.close();resume.export_state(tmp_path/'safe/v4.sqlite3',tmp_path/'next')
    ledger=q.open_queue(tmp_path/'next');assert resume.latest_sources(ledger)[q.body_key(doc)]['input_artifact']==verified;ledger.close()
    assert receiver().checkpoint_inputs(tmp_path/'next/v4.sqlite3')['descriptors']==[]


def test_runtime_failure_retries_only_after_processing_glue_code_changes(tmp_path,monkeypatch):
    from test_v4_cpu_analysis_pipeline import adapter
    doc,native=document();doc['raw_path']=doc['raw_sha256']+'.html'
    cache=tmp_path/'cache';manifest=context_bundle(cache,[(doc,native)],{})
    artifact={'artifact_id':10,'digest':'c'*64,'acquisition_run_id':2,'acquisition_run_attempt':1,'head_sha':'a'*40,
        'document_member':'documents/0.json','native_member':'raw/'+doc['raw_sha256']+'.html',
        'metadata_sha256':sha((cache/'documents/0.json').read_bytes()),'manifest_sha256':sha(manifest)}
    ledger=q.open_queue(tmp_path/'original');q.enqueue(ledger,doc,native,{'input_artifact':artifact})
    with monkeypatch.context() as scoped:
        def broken(*args,**kwargs):raise RuntimeError('synthetic glue failure')
        adapter(scoped,broken);q.work(ledger,extractor=Extractor())
    ledger.close();resume.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'safe')
    tool=receiver();assert tool.checkpoint_inputs(tmp_path/'safe/v4.sqlite3')['descriptors']==[]
    current=tool.current_analysis_code
    def changed(*,include_glue=False):
        value=current(include_glue=include_glue)
        if include_glue:value['cpu_automation']='0'*64
        return value
    monkeypatch.setattr(tool,'current_analysis_code',changed)
    assert tool.checkpoint_inputs(tmp_path/'safe/v4.sqlite3')['descriptors']==[artifact]


def test_missing_old_original_remains_in_unread_pending_count_without_model(tmp_path):
    doc,native=document('Atlas ordered Helios heat pumps.\nA second separate paragraph.')
    ledger=q.open_queue(tmp_path/'original');q.enqueue(ledger,doc,native,{})
    q.work(ledger,extractor=Extractor(),max_windows=1);ledger.close()
    resume.export_state(tmp_path/'original/v4.sqlite3',tmp_path/'safe')
    ledger=q.open_queue(tmp_path/'safe');model=Extractor()
    from bct.v4 import cpu_operations as op
    observed=op.observe(ledger,trigger='SYNTHETIC_MISSING_SOURCE',execute=True,extractor=model)
    assert observed['new_CPU_windows']==model.calls==0
    assert observed['CPU_pending']==observed['queue']['withheld_pending_windows']==1
    ledger.close()
