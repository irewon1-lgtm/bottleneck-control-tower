"""Literal acquisition-state restore and small CPU source bundles; no engines."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

MAX_STATE = 4 * 1024**3
MAX_DELTA = 128 * 1024**2
MAX_METADATA_SCAN = 128 * 1024**2
DISK_RESERVE = 2 * 1024**3


def file_hash(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('ACQUISITION_SOURCE_NOT_REGULAR')
    return path.stat().st_size


def safe_name(name):
    parts = name.split('/')
    if (not name or name.startswith('/') or '\\' in name or len(name) > 4096
            or any(part in ('', '.', '..') for part in parts)
            or any(ord(c) < 32 for c in name)):
        raise ValueError('ACQUISITION_UNSAFE_MEMBER')
    return PurePosixPath(name)


def vacant(path):
    if path.exists() or path.is_symlink():
        raise ValueError('ACQUISITION_DESTINATION_EXISTS')


def graph_source_versions(graph, root_document_ids):
    """Carry existing graph dependencies; never invent a new comparison rule."""
    documents={row['document_id']:row for row in graph.get('protected_batch',{}).get('documents',[])}
    roots=set(root_document_ids)&documents.keys()
    nodes={row['observation_id']:row for row in graph.get('observations',[])}

    def references(value):
        found=set()
        if isinstance(value,dict):
            if isinstance(value.get('document_id'),str):found.add(value['document_id'])
            for item in value.values():found.update(references(item))
        elif isinstance(value,list):
            for item in value:found.update(references(item))
        return found

    required_by={}
    for root in roots:
        selected={root}
        for row in nodes.values():
            if row['document_id']==root:
                selected.update(nodes[key]['document_id'] for key in row.get('connected_observations',[]) if key in nodes)
        targets={row['target_id'] for row in graph.get('targets',[]) if root in references(row)}
        for row in graph.get('targets',[]):
            if row['target_id'] in targets:selected.update(references(row))
        for row in graph.get('pairs',[]):
            if row['target_id'] in targets:selected.update(references(row))
        if not selected<=documents.keys():raise ValueError('ACQUISITION_GRAPH_SOURCE_REFERENCE_MISSING')
        for did in selected:required_by.setdefault(did,set()).add(root)
    return [{key:documents[did].get(key) for key in ('document_id','origin_url','body_sha256','raw_sha256')}
            | {'root_document_ids':sorted(required_by[did])} for did in sorted(required_by)]


def restore_state(archive, destination, *, max_expanded=MAX_STATE):
    """Retain all source/control bytes; only historical evaluations stay archived."""
    destination = Path(destination); vacant(destination)
    selected = {}; skipped = 0; size = 0
    with zipfile.ZipFile(archive) as saved:
        for entry in saved.infolist():
            name = entry.filename.rstrip('/') if entry.is_dir() else entry.filename
            parts = safe_name(name)
            if parts.parts[0] == 'evaluations':
                skipped += int(not entry.is_dir()); continue
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError('ACQUISITION_NONREGULAR_MEMBER')
            if entry.is_dir(): continue
            if entry.flag_bits & 1 or name in selected:
                raise ValueError('ACQUISITION_ENCRYPTED_OR_DUPLICATE_MEMBER')
            selected[name] = entry; size += entry.file_size
        if size > max_expanded:
            raise ValueError('ACQUISITION_EXPANDED_LIMIT')
        if shutil.disk_usage(destination.parent).free < size + DISK_RESERVE:
            raise ValueError('ACQUISITION_INSUFFICIENT_DISK')
        with tempfile.TemporaryDirectory(prefix='acquisition-state-', dir=destination.parent) as tmp:
            staging = Path(tmp)/'cache'; staging.mkdir(); written = 0
            for name, entry in selected.items():
                target = staging/name; target.parent.mkdir(parents=True, exist_ok=True)
                count = 0
                with saved.open(entry) as source, target.open('xb') as output:
                    for block in iter(lambda: source.read(1024**2), b''):
                        written += len(block); count += len(block)
                        if written > max_expanded or count > entry.file_size:
                            raise ValueError('ACQUISITION_EXPANDED_LIMIT')
                        output.write(block)
                if count != entry.file_size:
                    raise ValueError('ACQUISITION_MEMBER_SIZE_MISMATCH')
            vacant(destination); staging.rename(destination)
    return {'status':'PASS_LITERAL_ACQUISITION_STATE', 'expanded_bytes':size,
            'expanded_limit':max_expanded, 'members':len(selected),
            'skipped_evaluation_members':skipped, 'evaluations_expanded':False,
            'all_source_and_control_files_preserved':True, 'source_HTTP_requests':0}


def build_delta(cache, rss_manifest, destination, *, rss_run_id, acquisition_run_id,
                head_sha, rss_run_attempt=1,acquisition_run_attempt=1,new_document_files=(), graph_sources=(), graph_context_complete=True,max_bytes=MAX_DELTA):
    cache, rss_manifest, destination = Path(cache), Path(rss_manifest), Path(destination)
    vacant(destination)
    if (cache.is_symlink() or not cache.is_dir() or any((cache/p).is_symlink() for p in ('documents','raw','captures'))
            or type(rss_run_id) is not int or rss_run_id <= 0
            or type(acquisition_run_id) is not int or acquisition_run_id <= 0
            or type(rss_run_attempt)is not int or rss_run_attempt<=0
            or type(acquisition_run_attempt)is not int or acquisition_run_attempt<=0
            or not re.fullmatch('[0-9a-f]{40}', head_sha)):
        raise ValueError('ACQUISITION_DELTA_BINDING')
    if regular(rss_manifest) > 20*1024**2:
        raise ValueError('ACQUISITION_MANIFEST_LIMIT')
    raw_manifest = rss_manifest.read_bytes(); manifest = json.loads(raw_manifest)
    if manifest.get('format') != 'bct-new-rss-delta-v1' or not isinstance(manifest.get('documents'), list):
        raise ValueError('ACQUISITION_MANIFEST_BINDING')
    if 'run_id'in manifest or 'run_attempt'in manifest:
        if (type(manifest.get('run_id'))is not int or manifest['run_id']!=rss_run_id
                or type(manifest.get('run_attempt'))is not int or manifest['run_attempt']!=rss_run_attempt):
            raise ValueError('ACQUISITION_RSS_ATTEMPT_BINDING')
    elif rss_run_attempt!=1:raise ValueError('ACQUISITION_RSS_LEGACY_ATTEMPT_UNPROVEN')
    wanted = {(row['document_id'], row['url']) for row in manifest['documents']}
    fresh_names = set(new_document_files)
    graph_versions={(row['document_id'],row.get('body_sha256'),row.get('raw_sha256')):row for row in graph_sources}
    files = {'rss-manifest.json': (rss_manifest, len(raw_manifest), hashlib.sha256(raw_manifest).hexdigest())}
    documents = []; scan_bytes = 0; malformed = 0

    def include(path, member):
        safe_name(member); size = regular(path)
        files[member] = (path, size, file_hash(path))

    for path in sorted((cache/'documents').glob('*.json')):
        scan_bytes += regular(path)
        if scan_bytes > MAX_METADATA_SCAN:
            raise ValueError('ACQUISITION_METADATA_SCAN_LIMIT')
        try:
            doc = json.loads(path.read_bytes())
            key = (doc.get('document_id'), doc.get('origin_url'))
            hash(key)
        except (ValueError, TypeError, AttributeError):
            # Same downstream malformed-metadata hold behavior, literal bytes.
            include(path, 'documents/'+path.name); malformed += 1; continue
        kind = 'RSS' if key in wanted else ('ACQUISITION_OPPOSITE' if path.name in fresh_names
                    and str(doc.get('document_id','')).startswith('new-source-') else
                    'GRAPH_CONTEXT' if (doc.get('document_id'),doc.get('body_sha256'),doc.get('raw_sha256')) in graph_versions else None)
        if kind is None: continue
        member = 'documents/'+path.name; include(path, member)
        native = None
        raw_value=doc.get('raw_path')
        filename = Path(raw_value).name if isinstance(raw_value,str) else ''
        raw_hash = doc.get('raw_sha256')
        if isinstance(raw_hash,str) and re.fullmatch('[0-9a-f]{64}',raw_hash) and filename.startswith(raw_hash+'.'):
            raw_path = cache/'raw'/filename
            if raw_path.exists() or raw_path.is_symlink():
                native = 'raw/'+filename; include(raw_path,native)
        metadata=doc.get('sec_filing_metadata')
        metadata_hash=metadata.get('raw_sha256') if isinstance(metadata,dict) else None
        if isinstance(metadata_hash,str) and re.fullmatch('[0-9a-f]{64}',metadata_hash):
            metadata_path=cache/'raw'/(metadata_hash+'.json')
            if metadata_path.exists() or metadata_path.is_symlink():include(metadata_path,'raw/'+metadata_path.name)
        url = doc.get('origin_url')
        if isinstance(url,str):
            captured = cache/'captures'/(hashlib.sha256(url.encode()).hexdigest()+'.json')
            if captured.exists() or captured.is_symlink(): include(captured,'captures/'+captured.name)
        documents.append({k:doc.get(k) for k in ('document_id','origin_url','body_sha256','raw_sha256')}
                         | {'document_member':member,'native_member':native,
                            'metadata_sha256':files[member][2],'source_kind':kind})
        context=graph_versions.get((doc.get('document_id'),doc.get('body_sha256'),doc.get('raw_sha256')))
        if context is not None:documents[-1]['root_document_ids']=context['root_document_ids']
    opposite={row['document_id']:row for row in documents if row['source_kind']=='ACQUISITION_OPPOSITE'}
    relation_bytes=0
    if opposite:
        for path in sorted((cache/'requests').glob('*.json')):
            relation_bytes+=regular(path)
            if relation_bytes>MAX_METADATA_SCAN:raise ValueError('ACQUISITION_RELATION_SCAN_LIMIT')
            try:
                request=json.loads(path.read_bytes())
                for captured,validation in zip(request.get('captures',[]),request.get('capture_validation',[])):
                    descriptor=opposite.get(captured.get('document_id'))
                    if descriptor is not None and captured.get('origin_url')==descriptor['origin_url']:
                        descriptor.update(request_id=request.get('request_id'),
                            seed_document_ids=request.get('seed_document_ids',[]),
                            capture_validation_state=validation.get('state'))
            except (ValueError,TypeError,AttributeError):continue
    # Failed current RSS captures remain distinguishable from absent originals.
    for _, url in wanted:
        captured = cache/'captures'/(hashlib.sha256(url.encode()).hexdigest()+'.json')
        if captured.exists() or captured.is_symlink(): include(captured,'captures/'+captured.name)
    derived={**manifest,'documents':list(manifest['documents'])}
    for row in documents:
        if (row['source_kind']=='ACQUISITION_OPPOSITE'
                and row.get('capture_validation_state') in ('VALID_PRIMARY_EVIDENCE','VALID_ORIGINAL_SCOPE_EVIDENCE')
                and row.get('seed_document_ids') and (row['document_id'],row['origin_url']) not in wanted):
            derived['documents'].append({'document_id':row['document_id'],'url':row['origin_url'],
                'source_kind':'ACQUISITION_OPPOSITE','acquisition_request_id':row.get('request_id'),
                'seed_document_ids':row['seed_document_ids']})
            wanted.add((row['document_id'],row['origin_url']))
    derived_bytes=(json.dumps(derived,sort_keys=True)+'\n').encode()
    size = sum(row[1] for row in files.values())+len(derived_bytes)
    if size > max_bytes:
        raise ValueError('ACQUISITION_DELTA_LIMIT')
    if shutil.disk_usage(destination.parent).free < size + DISK_RESERVE:
        raise ValueError('ACQUISITION_INSUFFICIENT_DISK')
    vector = {name:{'bytes':size,'sha256':digest} for name,(_,size,digest) in files.items()}
    vector['cpu-manifest.json']={'bytes':len(derived_bytes),'sha256':hashlib.sha256(derived_bytes).hexdigest()}
    delta = {'format':'bct-cpu-source-delta-1','status':'READY','rss_run_id':rss_run_id,
             'rss_run_attempt':rss_run_attempt,'acquisition_run_attempt':acquisition_run_attempt,
             'acquisition_run_id':acquisition_run_id,'acquisition_head_sha':head_sha,
             'rss_manifest_sha256':hashlib.sha256(raw_manifest).hexdigest(),
             'cpu_manifest_sha256':hashlib.sha256(derived_bytes).hexdigest(),
             'files':vector,'documents':documents,'malformed_metadata_files':malformed,
             'required_graph_sources':list(graph_sources),
             'graph_context_complete':graph_context_complete,
             'graph_context_fallback':None if graph_context_complete else
                 {'reason':'LEGACY_CYCLE_CONTEXT_UNAVAILABLE','root_document_ids':sorted({did for did,_ in wanted}),
                  'required_recovery':'EXACT_PRIOR_ACQUISITION_STATE_GRAPH_HANDOFF'},
             'unavailable_graph_sources':[row for key,row in graph_versions.items()
                if not any((d['document_id'],d['body_sha256'],d['raw_sha256'])==key and d['native_member']
                           for d in documents)]}
    manifest_bytes=(json.dumps(delta,sort_keys=True)+'\n').encode()
    if size+len(manifest_bytes)>max_bytes:raise ValueError('ACQUISITION_DELTA_LIMIT')
    with tempfile.TemporaryDirectory(prefix='acquisition-delta-',dir=destination.parent) as tmp:
        staging = Path(tmp)/'bundle'; staging.mkdir()
        written=0
        for name,(path,expected_size,digest) in files.items():
            target=staging/name;target.parent.mkdir(parents=True,exist_ok=True)
            count=0
            with path.open('rb') as source,target.open('xb') as output:
                for block in iter(lambda:source.read(1024**2),b''):
                    count+=len(block);written+=len(block)
                    if count>expected_size or written>max_bytes:raise ValueError('ACQUISITION_DELTA_LIMIT')
                    output.write(block)
            if target.stat().st_size!=expected_size or file_hash(target)!=digest:
                raise ValueError('ACQUISITION_SOURCE_CHANGED_DURING_COPY')
        (staging/'cpu-manifest.json').write_bytes(derived_bytes)
        (staging/'manifest.json').write_bytes(manifest_bytes)
        vacant(destination);staging.rename(destination)
    return {'status':'PASS_LITERAL_CPU_SOURCE_DELTA','files':len(vector)+1,'documents':len(documents),
            'source_kinds':dict(Counter(d['source_kind'] for d in documents)),
            'bytes':size+len(manifest_bytes),'limit':max_bytes,'manifest_sha256':file_hash(destination/'manifest.json'),
            'source_HTTP_requests':0,'new_CPU_inferences':0,'source_metadata_rewritten':False}


def build_fallback(rss_manifest,destination,*,rss_run_id,rss_run_attempt,acquisition_run_id,
                   acquisition_run_attempt,head_sha,artifact_id,artifact_digest,graph_sources,reason):
    """A resource failure is explicit recovery work, never an empty-source HOLD."""
    destination=Path(destination);vacant(destination)
    digest=artifact_digest.removeprefix('sha256:')
    if (reason not in ('ACQUISITION_DELTA_LIMIT','ACQUISITION_METADATA_SCAN_LIMIT','ACQUISITION_RELATION_SCAN_LIMIT')
            or type(artifact_id)is not int or artifact_id<=0 or not re.fullmatch('[0-9a-f]{64}',digest)
            or not re.fullmatch('[0-9a-f]{40}',head_sha)
            or any(type(n)is not int or n<=0 for n in (rss_run_id,rss_run_attempt,acquisition_run_id,acquisition_run_attempt))):
        raise ValueError('ACQUISITION_FALLBACK_BINDING')
    path=Path(rss_manifest)
    if regular(path)>20*1024**2:raise ValueError('ACQUISITION_MANIFEST_LIMIT')
    rss=path.read_bytes();cpu=rss
    files={'rss-manifest.json':{'bytes':len(rss),'sha256':hashlib.sha256(rss).hexdigest()},
           'cpu-manifest.json':{'bytes':len(cpu),'sha256':hashlib.sha256(cpu).hexdigest()}}
    manifest={'format':'bct-cpu-source-delta-1','status':'EXACT_SOURCE_RECOVERY_REQUIRED',
        'rss_run_id':rss_run_id,'rss_run_attempt':rss_run_attempt,
        'acquisition_run_id':acquisition_run_id,'acquisition_run_attempt':acquisition_run_attempt,
        'acquisition_head_sha':head_sha,'rss_manifest_sha256':files['rss-manifest.json']['sha256'],
        'cpu_manifest_sha256':files['cpu-manifest.json']['sha256'],'files':files,'documents':[],
        'required_graph_sources':list(graph_sources),'unavailable_graph_sources':list(graph_sources),
        'graph_context_complete':False,'fallback':{'artifact_id':artifact_id,'digest':'sha256:'+digest,
            'acquisition_run_id':acquisition_run_id,'acquisition_run_attempt':acquisition_run_attempt,
            'head_sha':head_sha,'reason':reason}}
    with tempfile.TemporaryDirectory(prefix='acquisition-fallback-',dir=destination.parent)as tmp:
        staging=Path(tmp)/'bundle';staging.mkdir()
        (staging/'rss-manifest.json').write_bytes(rss);(staging/'cpu-manifest.json').write_bytes(cpu)
        (staging/'manifest.json').write_text(json.dumps(manifest,sort_keys=True)+'\n')
        vacant(destination);staging.rename(destination)
    return {'status':'EXACT_SOURCE_RECOVERY_REQUIRED','reason':reason,
        'fallback_artifact_id':artifact_id,'manifest_sha256':file_hash(destination/'manifest.json'),
        'source_HTTP_requests':0,'new_CPU_inferences':0}


def transport_module():
    path=Path(__file__).with_name('receive_cpu_sources.py')
    spec=importlib.util.spec_from_file_location('acquisition_existing_transport',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def restore_run(run_id, destination, *,run_attempt=0):
    destination=Path(destination);vacant(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    transport=transport_module()
    endpoint='actions/runs/'+str(run_id)+(f'/attempts/{run_attempt}' if run_attempt else '')
    run=transport.gh_json(endpoint)
    listing=transport.gh_json(f'actions/runs/{run_id}/artifacts?per_page=100')
    expected_name='precursor-private-cache'+(f'-{run_attempt}' if run_attempt else '')
    if (run.get('id')!=run_id or run.get('run_attempt')!=(run_attempt or 1)
            or not re.fullmatch('[0-9a-f]{40}',run.get('head_sha',''))
            or run.get('path')!='.github/workflows/precursor-acquisition.yml'
            or run.get('head_branch')!='main' or run.get('event')!='workflow_run'
            or run.get('conclusion')!='success'
            or run.get('head_repository',{}).get('full_name')!=transport.REPOSITORY
            or listing.get('total_count',len(listing.get('artifacts',[])))>len(listing.get('artifacts',[]))):
        raise ValueError('ACQUISITION_PRIOR_ATTEMPT_BINDING')
    matches=[row for row in listing['artifacts'] if row.get('name')==expected_name]
    if (len(matches)!=1 or matches[0].get('expired')is not False or type(matches[0].get('id'))is not int
            or type(matches[0].get('size_in_bytes'))is not int or not 0<matches[0]['size_in_bytes']<=transport.MAX_ARCHIVE
            or not re.fullmatch(r'sha256:[0-9a-f]{64}',matches[0].get('digest')or'')):
        raise ValueError('ACQUISITION_PRIOR_ARTIFACT_BINDING')
    artifact=matches[0]
    if transport.free_disk(destination.parent)<artifact['size_in_bytes']+MAX_STATE+DISK_RESERVE:
        raise ValueError('ACQUISITION_INSUFFICIENT_DISK')
    with tempfile.TemporaryDirectory(prefix='acquisition-download-',dir=destination.parent) as tmp:
        archive=Path(tmp)/'state.zip';transport.download(artifact,archive)
        result=restore_state(archive,destination)
    history=destination/'archive-history';history.mkdir(exist_ok=True)
    pointer=history/(artifact['digest'].split(':',1)[1]+'.json')
    if not pointer.exists():
        with pointer.open('x') as saved:json.dump({'artifact_id':artifact['id'],'run_id':run_id,
            'head_sha':run['head_sha'],'digest':artifact['digest'],'bytes':artifact['size_in_bytes'],
            'contains_historical_evaluations':bool(result['skipped_evaluation_members'])},saved,sort_keys=True)
    return {**result,'prior_run_id':run_id,'prior_run_attempt':run_attempt or 1,'prior_head_sha':run['head_sha'],
            'archive_artifact_id':artifact['id'],'archive_digest':artifact['digest'],
            'archive_bytes':artifact['size_in_bytes'],'original_archive_immutable_reference_preserved':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    restore=sub.add_parser('restore');restore.add_argument('--run-id',type=int,required=True);restore.add_argument('--destination',type=Path,required=True)
    restore.add_argument('--run-attempt',type=int,default=0)
    delta=sub.add_parser('delta');delta.add_argument('--cache',type=Path,required=True);delta.add_argument('--rss-manifest',type=Path,required=True)
    delta.add_argument('--destination',type=Path,required=True);delta.add_argument('--rss-run-id',type=int,required=True)
    delta.add_argument('--acquisition-run-id',type=int,required=True);delta.add_argument('--head-sha',required=True)
    delta.add_argument('--rss-run-attempt',type=int,default=1);delta.add_argument('--acquisition-run-attempt',type=int,default=1)
    delta.add_argument('--new-document-files',type=Path)
    delta.add_argument('--graph-sources',type=Path)
    delta.add_argument('--fallback-artifact-id',type=int);delta.add_argument('--fallback-artifact-digest')
    args=parser.parse_args()
    if args.action=='restore':result=restore_run(args.run_id,args.destination,run_attempt=args.run_attempt)
    else:
        selected=json.loads(args.graph_sources.read_text()) if args.graph_sources else {'sources':[],'complete':False}
        try:
            result=build_delta(args.cache,args.rss_manifest,args.destination,rss_run_id=args.rss_run_id,
                acquisition_run_id=args.acquisition_run_id,head_sha=args.head_sha,
                rss_run_attempt=args.rss_run_attempt,acquisition_run_attempt=args.acquisition_run_attempt,
                new_document_files=json.loads(args.new_document_files.read_text()) if args.new_document_files else (),
                graph_sources=selected['sources'],graph_context_complete=selected['complete'])
        except ValueError as error:
            if str(error)not in ('ACQUISITION_DELTA_LIMIT','ACQUISITION_METADATA_SCAN_LIMIT','ACQUISITION_RELATION_SCAN_LIMIT'):
                raise
            result=build_fallback(args.rss_manifest,args.destination,rss_run_id=args.rss_run_id,
                rss_run_attempt=args.rss_run_attempt,acquisition_run_id=args.acquisition_run_id,
                acquisition_run_attempt=args.acquisition_run_attempt,head_sha=args.head_sha,
                artifact_id=args.fallback_artifact_id,artifact_digest=args.fallback_artifact_digest or'',
                graph_sources=selected['sources'],reason=str(error))
    print('BCT_ACQUISITION_SOURCE_JSON='+json.dumps(result,sort_keys=True))
