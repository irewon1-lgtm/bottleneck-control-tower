"""Receive exact small source bundles and pending versions; no source HTTP."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import selectors
import sqlite3
import stat
import subprocess
import tempfile
import time
import zipfile

MAX_BYTES=128*1024**2
MAX_TOTAL=512*1024**2
MAX_PRIOR_ARTIFACTS=8
RESERVE=2*1024**3
REPOSITORY='irewon1-lgtm/bottleneck-control-tower'


def digest(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()


def canonical_hash(value):
    # Same source-free identity serialization as bct.v4.store.sha, without
    # importing the execution package into this standard-library transport.
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def current_analysis_code(*,include_glue=False):
    root=Path(__file__).resolve().parents[2]/'src/bct'
    paths={'cpu_review':'v4/cpu_review.py','collection':'precursor_collection.py','scope_reader':'precursor_scope_reader.py',
           'graph':'precursor_evidence_graph.py','forecast':'forecast_discovery.py','official_adapter':'v4/official_discovery.py'}
    if include_glue:paths.update(cpu_automation='v4/cpu_automation.py',cpu_resume='v4/cpu_resume.py')
    return {name:digest(root/path) for name,path in paths.items() if (root/path).is_file()}


def safe_member(name):
    if name in ('rss-manifest.json','cpu-manifest.json'):return name
    parts=name.split('/')
    if (len(parts)!=2 or parts[0] not in ('documents','raw','captures') or parts[1] in ('','.','..')
            or '\\' in name or any(ord(c)<32 for c in name)):
        raise ValueError('CPU_DELTA_UNSAFE_MEMBER')
    return name


def vacant(path):
    if path.exists() or path.is_symlink():raise ValueError('CPU_DELTA_DESTINATION_EXISTS')


def extract_bundle(archive,destination,*,run_id,head_sha,run_attempt=1,rss_run_id=None,rss_run_attempt=None,max_bytes=MAX_BYTES):
    destination=Path(destination);vacant(destination)
    with zipfile.ZipFile(archive) as saved:
        entries={};expanded=0
        for row in saved.infolist():
            if row.is_dir():continue
            if row.filename!='manifest.json':safe_member(row.filename)
            mode=row.external_attr>>16
            if (row.filename in entries or row.flag_bits&1 or stat.S_ISLNK(mode)
                    or stat.S_IFMT(mode) not in (0,stat.S_IFREG)):
                raise ValueError('CPU_DELTA_DUPLICATE_OR_NONREGULAR')
            entries[row.filename]=row;expanded+=row.file_size
        if expanded>max_bytes:raise ValueError('CPU_DELTA_EXPANDED_LIMIT')
        if 'manifest.json' not in entries or entries['manifest.json'].file_size>8*1024**2:
            raise ValueError('CPU_DELTA_MANIFEST_LIMIT')
        manifest=json.loads(saved.read(entries['manifest.json']))
        if manifest.get('status')=='EXACT_SOURCE_RECOVERY_REQUIRED':raise ValueError('BLOCKED_INPUT_RECOVERY_REQUIRED')
        if manifest.get('status','READY')!='READY':raise ValueError('CPU_DELTA_STATUS_INVALID')
        if (manifest.get('format')!='bct-cpu-source-delta-1' or manifest.get('acquisition_run_id')!=run_id
                or manifest.get('acquisition_run_attempt')!=run_attempt
                or manifest.get('acquisition_head_sha')!=head_sha or not re.fullmatch('[0-9a-f]{40}',head_sha)
                or (rss_run_id is not None and manifest.get('rss_run_id')!=rss_run_id)
                or (rss_run_attempt is not None and manifest.get('rss_run_attempt')!=rss_run_attempt)):
            raise ValueError('CPU_DELTA_INPUT_BINDING')
        files=manifest['files']
        if set(entries)!=set(files)|{'manifest.json'}:raise ValueError('CPU_DELTA_UNDECLARED_MEMBER')
        for name,row in files.items():
            safe_member(name)
            if (type(row.get('bytes')) is not int or row['bytes']<0 or row['bytes']!=entries[name].file_size
                    or not re.fullmatch('[0-9a-f]{64}',row.get('sha256',''))):
                raise ValueError('CPU_DELTA_FILE_BINDING')
        for doc in manifest['documents']:
            member=doc['document_member'];safe_member(member)
            if not member.startswith('documents/') or member not in files or doc['metadata_sha256']!=files[member]['sha256']:
                raise ValueError('CPU_DELTA_DOCUMENT_BINDING')
            native=doc['native_member']
            if native is not None and (not safe_member(native).startswith('raw/') or native not in files):
                raise ValueError('CPU_DELTA_NATIVE_BINDING')
        if shutil.disk_usage(destination.parent).free<expanded+RESERVE:raise ValueError('CPU_DELTA_INSUFFICIENT_DISK')
        with tempfile.TemporaryDirectory(prefix='cpu-delta-',dir=destination.parent) as tmp:
            stage=Path(tmp)/'cache';stage.mkdir();written=0
            for name,row in files.items():
                path=stage/name;path.parent.mkdir(parents=True,exist_ok=True);count=0;hash_=hashlib.sha256()
                with saved.open(entries[name]) as source,path.open('xb') as output:
                    for block in iter(lambda:source.read(1024**2),b''):
                        count+=len(block);written+=len(block)
                        if count>row['bytes'] or written>max_bytes:raise ValueError('CPU_DELTA_EXPANDED_LIMIT')
                        hash_.update(block);output.write(block)
                if count!=row['bytes'] or hash_.hexdigest()!=row['sha256']:raise ValueError('CPU_DELTA_LITERAL_HASH_MISMATCH')
            if (digest(stage/'rss-manifest.json')!=manifest['rss_manifest_sha256']
                    or digest(stage/'cpu-manifest.json')!=manifest['cpu_manifest_sha256']):
                raise ValueError('CPU_DELTA_RSS_MANIFEST_BINDING')
            (stage/'manifest.json').write_bytes(saved.read(entries['manifest.json']))
            vacant(destination);stage.rename(destination)
    return {'manifest':manifest,'expanded_bytes':expanded,'malformed_metadata_rewritten':False}


def pending_artifacts(sources,done,*,analysis_needed=()):
    selected=[];seen=set()
    for source in sources:
        need=(not source['complete'] and any(t['key'] not in done for t in source['tasks'])) or source['body_key'] in analysis_needed
        if not need:continue
        descriptor=source.get('input_artifact')
        if descriptor is None:raise ValueError('CPU_LEGACY_INPUT_RECOVERY_REQUIRED')
        identity=(descriptor['artifact_id'],descriptor['document_member'],descriptor['metadata_sha256'])
        if identity not in seen:selected.append(descriptor);seen.add(identity)
    if len({d['artifact_id'] for d in selected})>MAX_PRIOR_ARTIFACTS:raise ValueError('CPU_PENDING_ARTIFACT_BUDGET')
    return selected


def transport():
    path=Path(__file__).with_name('receive_cpu_sources.py')
    spec=importlib.util.spec_from_file_location('cpu_existing_source_transport',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.MAX_ARCHIVE=MAX_BYTES;module.MAX_EXPANDED=MAX_BYTES
    module.download=download
    module.gh_json=metadata
    return module


def metadata(path):
    try:
        result=subprocess.run(['gh','api','repos/'+REPOSITORY+'/'+path],capture_output=True,text=True,timeout=10)
    except subprocess.TimeoutExpired:raise ValueError('CPU_DELTA_METADATA_TIMEOUT') from None
    if result.returncode:raise ValueError('CPU_DELTA_METADATA_UNAVAILABLE')
    return json.loads(result.stdout)


class DownloadError(ValueError):
    def __init__(self,reason,received):
        super().__init__(reason);self.bytes_received=received


def download(artifact,destination,*,seconds=90):
    """Bound pipe reads and time, so one old unavailable bundle can be held."""
    destination=Path(destination);vacant(destination);created=False;written=0
    if shutil.disk_usage(destination.parent).free<artifact['size_in_bytes']+MAX_BYTES+RESERVE:
        raise DownloadError('CPU_DELTA_INSUFFICIENT_DISK',0)
    deadline=time.monotonic()+seconds
    try:
        with tempfile.TemporaryFile() as errors,destination.open('xb') as output:
            created=True
            with subprocess.Popen(['gh','api',f'repos/{REPOSITORY}/actions/artifacts/{artifact["id"]}/zip',
                    '-H','Accept: application/vnd.github+json'],stdout=subprocess.PIPE,stderr=errors) as process:
                try:
                    with selectors.DefaultSelector() as ready:
                        ready.register(process.stdout,selectors.EVENT_READ)
                        while ready.get_map():
                            remaining=deadline-time.monotonic()
                            if remaining<=0:raise DownloadError('CPU_DELTA_DOWNLOAD_TIMEOUT',written)
                            if not ready.select(remaining):raise DownloadError('CPU_DELTA_DOWNLOAD_TIMEOUT',written)
                            block=os.read(process.stdout.fileno(),1024**2)
                            if not block:ready.unregister(process.stdout);break
                            written+=len(block)
                            if written>min(MAX_BYTES,artifact['size_in_bytes']):raise DownloadError('CPU_DELTA_COMPRESSED_LIMIT',written)
                            output.write(block)
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise DownloadError('CPU_DELTA_DOWNLOAD_TIMEOUT',written)
                    try:code=process.wait(timeout=remaining)
                    except subprocess.TimeoutExpired:raise DownloadError('CPU_DELTA_DOWNLOAD_TIMEOUT',written) from None
                    if code:raise DownloadError('CPU_DELTA_DOWNLOAD_FAILED',written)
                except BaseException:
                    process.kill();process.wait();raise
        if written!=artifact['size_in_bytes'] or digest(destination)!=artifact['digest'].split(':',1)[1]:
            raise DownloadError('CPU_DELTA_ARCHIVE_SIZE_OR_HASH_MISMATCH',written)
        return written
    except BaseException:
        if created:destination.unlink(missing_ok=True)
        raise


def artifact_for(tool,run_id,head_sha,*,artifact_id=None,expected_digest=None,run_attempt=None):
    run=tool.gh_json('actions/runs/'+str(run_id)+(f'/attempts/{run_attempt}' if run_attempt else ''))
    if (run.get('id')!=run_id or run.get('head_sha')!=head_sha or run.get('path')!='.github/workflows/precursor-acquisition.yml'
            or run.get('head_branch')!='main' or run.get('event')!='workflow_run' or run.get('conclusion')!='success'
            or run.get('head_repository',{}).get('full_name')!=REPOSITORY):raise ValueError('CPU_DELTA_ACQUISITION_BINDING')
    attempt=run.get('run_attempt')
    if type(attempt) is not int or attempt<1 or (run_attempt is not None and attempt!=run_attempt):raise ValueError('CPU_DELTA_ATTEMPT_BINDING')
    rows=[a for a in tool.gh_json(f'actions/runs/{run_id}/artifacts?per_page=100')['artifacts'] if a.get('name')==f'precursor-cpu-delta-{attempt}']
    if (len(rows)!=1 or rows[0].get('expired') is not False or type(rows[0].get('id')) is not int
            or type(rows[0].get('size_in_bytes')) is not int or not 0<rows[0]['size_in_bytes']<=MAX_BYTES
            or not re.fullmatch('sha256:[0-9a-f]{64}',rows[0].get('digest') or '')
            or (artifact_id is not None and rows[0]['id']!=artifact_id)
            or (expected_digest is not None and rows[0]['digest']!='sha256:'+expected_digest)):
        raise ValueError('CPU_DELTA_ARTIFACT_BINDING_OR_EXPIRED')
    return {**rows[0],'acquisition_run_attempt':attempt}


def checkpoint_inputs(path):
    path=Path(path)
    if path.is_dir():
        proof=json.loads((path/'checkpoint.json').read_text())
        if proof['archive']!='checkpoint.sqlite3.gz' or digest(path/proof['archive'])!=proof['archive_sha256']:
            raise ValueError('CPU_INPUT_CHECKPOINT_ARCHIVE_BINDING')
        with tempfile.TemporaryDirectory(prefix='cpu-source-plan-',dir=path.parent) as tmp:
            sqlite=Path(tmp)/'v4.sqlite3';count=0
            with gzip.open(path/proof['archive'],'rb') as source,sqlite.open('xb') as output:
                for block in iter(lambda:source.read(1024**2),b''):
                    count+=len(block)
                    if count>128*1024**2:raise ValueError('CPU_INPUT_CHECKPOINT_LIMIT')
                    output.write(block)
            if digest(sqlite)!=proof['sqlite_sha256']:raise ValueError('CPU_INPUT_CHECKPOINT_SQLITE_BINDING')
            return checkpoint_inputs(sqlite)
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as db:
        sources={};done=set();analysis={}
        for kind,payload in db.execute('SELECT kind,payload FROM events ORDER BY seq'):
            row=json.loads(payload)
            if kind=='CPU_RESUME_SOURCE':sources[row['body_key']]=row
            if kind in ('CPU_RESUME_WINDOW','CPU_RESUME_FAILURE'):done.add(row['key'])
            if kind in ('CPU_ANALYSIS_RESULT','CPU_ANALYSIS_FAILURE'):analysis[row['body_key']]=row
    code=current_analysis_code();needed=set()
    for key,source in sources.items():
        if not source.get('input_artifact'):continue
        row=analysis.get(key,{})
        prior_code={'cpu_review':row.get('analysis_implementation_sha256'),**row.get('dependency_sha256',{})}
        code_changed=(row.get('analysis_code_sha256')!=canonical_hash(current_analysis_code(include_glue=True)) if row.get('reason_code')=='ANALYSIS_RUNTIME_FAILED' else prior_code!=code)
        context_changed=(row.get('graph_context',{}).get('manifest_sha256')!=source['input_artifact'].get('manifest_sha256'))
        if (not row or (row.get('reason_code') in ('ANALYSIS_RUNTIME_FAILED','ANALYSIS_DEPENDENCY_FAILED') and code_changed)
                or (row.get('reason_code') in ('GRAPH_CONTEXT_UNAVAILABLE','GRAPH_CONTEXT_VERSION_MISMATCH','GRAPH_CONTEXT_LIMIT_EXCEEDED')
                    and (code_changed or (row.get('reason_code')=='GRAPH_CONTEXT_UNAVAILABLE' and context_changed)))):
            needed.add(key)
    selected=[];holds=[];artifact_ids=set()
    ordered=sorted(sources.values(),key=lambda s:not (not s['complete'] and any(t['key'] not in done for t in s['tasks'])))
    for source in ordered:
        needs=(not source['complete'] and any(t['key'] not in done for t in source['tasks'])) or source['body_key'] in needed
        if not needs:continue
        descriptor=source.get('input_artifact')
        reason=None
        if descriptor is None:reason='LEGACY_EXACT_INPUT_RECOVERY_REQUIRED'
        elif descriptor['artifact_id'] not in artifact_ids and len(artifact_ids)>=MAX_PRIOR_ARTIFACTS:reason='PRIOR_INPUT_ARTIFACT_BUDGET_HELD'
        if reason:
            holds.append(input_hold(source,reason));continue
        artifact_ids.add(descriptor['artifact_id']);selected.append(descriptor)
    return {'descriptors':selected,'holds':holds,'sources':sources,'analysis_needed':sorted(needed)}


def input_hold(source,reason):
    return {k:source[k] for k in ('document_id','body_key','body_sha256','raw_sha256')}|{'status':'HELD_INPUT_UNAVAILABLE','reason_code':reason}


def receive(run_id,head_sha,rss_run_id,rss_manifest,destination,checkpoint,receipt,*,run_attempt=None,rss_run_attempt=None):
    destination,receipt=Path(destination),Path(receipt);vacant(destination);vacant(receipt)
    destination.parent.mkdir(parents=True,exist_ok=True)
    tool=transport();current=artifact_for(tool,run_id,head_sha,run_attempt=run_attempt)
    plan=checkpoint_inputs(checkpoint);old=plan['descriptors'];groups={};holds=plan['holds']
    for descriptor in old:groups.setdefault(descriptor['artifact_id'],[]).append(descriptor)
    free=tool.free_disk(destination.parent)
    if free<MAX_TOTAL+MAX_BYTES*2+RESERVE:raise ValueError('CPU_DELTA_INSUFFICIENT_DISK')
    total=0;downloaded=0;artifacts=[];input_artifacts={};analysis_contexts={}
    with tempfile.TemporaryDirectory(prefix='cpu-inputs-',dir=destination.parent) as tmp:
        tmp=Path(tmp);stage=tmp/'output';stage.mkdir()
        def merge(cache,names,descriptors,artifact):
            nonlocal total
            mapped={};copies=[];additional=0
            for name in names:
                source=cache/name;target=stage/name
                if target.exists() and digest(target)!=digest(source):
                    if not name.startswith('documents/'):raise ValueError('CPU_DELTA_NATIVE_COLLISION')
                    target=stage/'documents'/(digest(source)+'-'+Path(name).name)
                if not target.exists():
                    additional+=source.stat().st_size;copies.append((source,target))
                mapped[name]=target.name
            if total+additional>MAX_TOTAL:raise ValueError('CPU_DELTA_TOTAL_LIMIT')
            for source,target in copies:
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            total+=additional
            for doc in descriptors:
                descriptor={'artifact_id':artifact['id'],'digest':artifact['digest'].split(':',1)[1],
                    'acquisition_run_id':doc['acquisition_run_id'],'acquisition_run_attempt':artifact['acquisition_run_attempt'],
                    'head_sha':doc.get('head_sha',head_sha),'document_member':doc['document_member'],
                    'native_member':doc['native_member'],'metadata_sha256':doc['metadata_sha256'],
                    'manifest_sha256':canonical_hash(json.loads((cache/'manifest.json').read_bytes()))}
                input_artifacts[mapped[doc['document_member']]]=descriptor
        def load(artifact,producer,head,rss=None,rss_attempt=None):
            nonlocal downloaded
            archive=tmp/('artifact-'+str(artifact['id'])+'.zip')
            try:
                if tool.download is download:tool.download(artifact,archive,seconds=90 if rss is not None else 20)
                else:tool.download(artifact,archive)
            except Exception as error:
                downloaded+=getattr(error,'bytes_received',0);raise
            downloaded+=archive.stat().st_size
            cache=tmp/('decoded-'+str(artifact['id']))
            result=extract_bundle(archive,cache,run_id=producer,head_sha=head,run_attempt=artifact['acquisition_run_attempt'],rss_run_id=rss,rss_run_attempt=rss_attempt)
            artifacts.append({'artifact_id':artifact['id'],'digest':artifact['digest'],'bytes':artifact['size_in_bytes'],'run_id':producer,'run_attempt':artifact['acquisition_run_attempt']})
            return archive,cache,result['manifest']
        archive,cache,manifest=load(current,run_id,head_sha,rss_run_id,rss_run_attempt)
        if digest(rss_manifest)!=manifest['rss_manifest_sha256']:raise ValueError('CPU_DELTA_ORIGINAL_RSS_BINDING')
        merge(cache,manifest['files'],[{**d,'acquisition_run_id':run_id,'head_sha':head_sha} for d in manifest['documents']],current)
        shutil.copyfile(cache/'manifest.json',stage/'bundle-manifest.json')
        total+=(stage/'bundle-manifest.json').stat().st_size
        shutil.rmtree(cache);archive.unlink()
        historical_deadline=time.monotonic()+100
        for artifact_id,descriptors in groups.items():
            if artifact_id==current['id']:continue
            first=descriptors[0]
            archive=tmp/('artifact-'+str(artifact_id)+'.zip')
            cache=tmp/('decoded-'+str(artifact_id))
            try:
                if time.monotonic()>=historical_deadline:raise ValueError('CPU_PRIOR_INPUT_TIME_BUDGET')
                artifact=artifact_for(tool,first['acquisition_run_id'],first['head_sha'],artifact_id=artifact_id,expected_digest=first['digest'],run_attempt=first['acquisition_run_attempt'])
                archive,cache,manifest=load(artifact,first['acquisition_run_id'],first['head_sha'])
                names=set()
                for descriptor in descriptors:
                    if (descriptor['document_member'] not in manifest['files'] or
                            manifest['files'][descriptor['document_member']]['sha256']!=descriptor['metadata_sha256']):
                        raise ValueError('CPU_PENDING_EXACT_VERSION_NOT_AVAILABLE')
                    names.add(descriptor['document_member'])
                    if descriptor['native_member']:names.add(descriptor['native_member'])
                    metadata_doc=json.loads((cache/descriptor['document_member']).read_bytes())
                    if not isinstance(metadata_doc,dict):raise ValueError('CPU_PENDING_METADATA_SCHEMA')
                    proof=metadata_doc.get('sec_filing_metadata') or {}
                    if proof:
                        if not isinstance(proof,dict):raise ValueError('CPU_PENDING_NATIVE_PROOF_SCHEMA')
                        proof_sha=proof.get('raw_sha256')
                        if not isinstance(proof_sha,str) or not re.fullmatch('[0-9a-f]{64}',proof_sha):
                            raise ValueError('CPU_PENDING_NATIVE_PROOF_HASH')
                        proof_member='raw/'+proof_sha+'.json'
                        if proof_member not in manifest['files'] or manifest['files'][proof_member]['sha256']!=proof_sha:
                            raise ValueError('CPU_PENDING_NATIVE_PROOF_MISSING')
                        names.add(proof_member)
                    if isinstance(metadata_doc.get('origin_url'),str):
                        capture='captures/'+hashlib.sha256(metadata_doc['origin_url'].encode()).hexdigest()+'.json'
                        if capture in manifest['files']:names.add(capture)
                # Bound each historical source group before changing current inputs.
                retained=sum(p.stat().st_size for p in cache.rglob('*') if p.is_file())
                if total+retained+sum(manifest['files'][name]['bytes'] for name in names)>MAX_TOTAL:
                    raise ValueError('CPU_PENDING_CUMULATIVE_BUDGET')
                merge(cache,names,descriptors,artifact)
                history=stage/'historical'/str(artifact_id);history.parent.mkdir(exist_ok=True)
                cache.rename(history);total+=retained;archive.unlink()
                for body_key,source in plan['sources'].items():
                    if source.get('input_artifact',{}).get('artifact_id')==artifact_id:
                        analysis_contexts[body_key]={'cache_path':'historical/'+str(artifact_id),
                            'manifest_sha256':digest(history/'manifest.json'),'artifact_id':artifact_id,
                            'digest':artifact['digest'].split(':',1)[1],'acquisition_run_attempt':artifact['acquisition_run_attempt'],
                            **{k:source[k] for k in ('document_id','body_sha256','raw_sha256')}}
            except (ValueError,OSError,KeyError,TypeError,zipfile.BadZipFile) as error:
                for source in plan['sources'].values():
                    if source.get('input_artifact',{}).get('artifact_id')==artifact_id:
                        reason='PRIOR_INPUT_ARTIFACT_BUDGET_HELD' if isinstance(error,ValueError) and str(error)=='CPU_PRIOR_INPUT_TIME_BUDGET' else 'EXACT_PRIOR_ARTIFACT_UNAVAILABLE_OR_INVALID'
                        holds.append(input_hold(source,reason))
            finally:
                # Unavailable history must neither block current input nor
                # consume the reserve across successive bounded attempts.
                if cache.is_dir():shutil.rmtree(cache)
                archive.unlink(missing_ok=True)
        # The CPU manifest is derived by the acquisition producer; the original
        # RSS bytes remain separately bound and cannot acquire opposite IDs.
        vacant(destination);stage.rename(destination)
    result={'status':'PASS_SMALL_EXACT_CPU_INPUTS_WITH_ISOLATED_HOLDS' if holds else 'PASS_SMALL_EXACT_CPU_INPUTS','input_artifacts':input_artifacts,'artifacts':artifacts,
        'input_holds':holds,'isolated_prior_input_holds':len(holds),
        'analysis_retry_body_keys':plan.get('analysis_needed',[]),
        'analysis_contexts':analysis_contexts,
        'downloaded_bytes':downloaded,'expanded_source_bytes':total,'free_disk_bytes_before':free,
        'max_delta_bytes':MAX_BYTES,'max_cumulative_bytes':MAX_TOTAL,'max_prior_artifacts':MAX_PRIOR_ARTIFACTS,
        'historical_seconds_budget':100,'current_download_seconds_limit':90,'prior_download_seconds_limit':20,'metadata_seconds_limit':10,
        'RSS_run_id':rss_run_id,'RSS_run_attempt':rss_run_attempt,'acquisition_run_id':run_id,
        'acquisition_run_attempt':current['acquisition_run_attempt'],'scheduled_claim':False,
        'source_HTTP_requests':0,'new_CPU_inferences':0,'legacy_full_cache_downloads':0}
    receipt.parent.mkdir(parents=True,exist_ok=True)
    with receipt.open('x') as output:json.dump(result,output,sort_keys=True)
    return {k:v for k,v in result.items() if k not in ('input_artifacts','artifacts','input_holds','analysis_contexts')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',type=int,required=True);parser.add_argument('--expected-head',required=True)
    parser.add_argument('--run-attempt',type=int,required=True);parser.add_argument('--rss-run-attempt',type=int,required=True)
    parser.add_argument('--rss-run-id',type=int,required=True);parser.add_argument('--rss-manifest',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True);parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True);args=parser.parse_args()
    print('BCT_CPU_INPUT_JSON='+json.dumps(receive(args.run_id,args.expected_head,args.rss_run_id,args.rss_manifest,
        args.destination,args.checkpoint,args.receipt,run_attempt=args.run_attempt,rss_run_attempt=args.rss_run_attempt),sort_keys=True))
