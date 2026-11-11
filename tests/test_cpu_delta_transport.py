"""Portable exact source bundle contracts; no model, fetch, or V4 import."""
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
import zipfile

import pytest


def module():
    path=Path(__file__).resolve().parents[1]/'.github/scripts/receive_cpu_delta.py'
    spec=importlib.util.spec_from_file_location('cpu_delta_transport',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def bundle(tmp_path, *, mutate=None, extra=None, native_proof=False):
    rss=b'{"format":"bct-new-rss-delta-v1","documents":[]}'
    files={'rss-manifest.json':rss,'cpu-manifest.json':rss,'documents/broken.json':b'{damaged',
           'documents/one.json':b'{"document_id":"one"}','raw/a.html':b'exact native'}
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if native_proof:
        proof=b'{"native":"original supplemental SEC proof"}'
        files['raw/'+sha(proof)+'.json']=proof
        files['documents/one.json']=json.dumps({'document_id':'old','sec_filing_metadata':{'raw_sha256':sha(proof)}}).encode()
    manifest={'format':'bct-cpu-source-delta-1','rss_run_id':1,'acquisition_run_id':2,'acquisition_run_attempt':1,
        'acquisition_head_sha':'a'*40,'rss_manifest_sha256':sha(rss),'cpu_manifest_sha256':sha(rss),
        'files':{name:{'bytes':len(body),'sha256':sha(body)} for name,body in files.items()},
        'documents':[{'document_id':'one','origin_url':'https://example.org/one',
            'body_sha256':'b'*64,'raw_sha256':'c'*64,'document_member':'documents/one.json',
            'native_member':'raw/a.html','metadata_sha256':sha(files['documents/one.json']),'source_kind':'RSS'}]}
    if mutate:mutate(manifest)
    path=tmp_path/'bundle.zip'
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('manifest.json',json.dumps(manifest))
        for name,body in files.items():archive.writestr(name,body)
        if extra:archive.writestr(*extra)
    return path,manifest,files


def test_bundle_preserves_all_metadata_and_original_bytes(tmp_path):
    tool=module();archive,manifest,files=bundle(tmp_path)
    result=tool.extract_bundle(archive,tmp_path/'decoded',run_id=2,head_sha='a'*40,rss_run_id=1)
    for name,body in files.items():assert (tmp_path/'decoded'/name).read_bytes()==body
    assert result['malformed_metadata_rewritten'] is False


@pytest.mark.parametrize('mutation',[lambda m:m.update(acquisition_run_id=99),
    lambda m:m['files']['documents/one.json'].update(sha256='0'*64),
    lambda m:m['documents'][0].update(document_member='../outside')])
def test_unbound_or_rewritten_bundle_fails_before_destination_publish(tmp_path,mutation):
    tool=module();archive,_,_=bundle(tmp_path,mutate=mutation)
    with pytest.raises(ValueError):tool.extract_bundle(archive,tmp_path/'out',run_id=2,head_sha='a'*40,rss_run_id=1)
    assert not (tmp_path/'out').exists()


def test_undeclared_zip_member_and_expansion_over_budget_fail(tmp_path):
    tool=module();archive,_,_=bundle(tmp_path,extra=('../escape',b'bad'))
    with pytest.raises(ValueError):tool.extract_bundle(archive,tmp_path/'out',run_id=2,head_sha='a'*40,rss_run_id=1)
    assert not (tmp_path/'out').exists()
    archive.unlink();archive,_,_=bundle(tmp_path)
    with pytest.raises(ValueError,match='LIMIT'):
        tool.extract_bundle(archive,tmp_path/'out',run_id=2,head_sha='a'*40,rss_run_id=1,max_bytes=10)


def test_pending_descriptor_requires_exact_historical_bundle_never_newer_substitute():
    tool=module()
    source={'body_key':'b'*64,'complete':False,'tasks':[{'key':'pending'}],
        'input_artifact':{'artifact_id':10,'digest':'c'*64,'acquisition_run_id':2,'acquisition_run_attempt':1,'head_sha':'a'*40,
            'document_member':'documents/old.json','native_member':'raw/old.html','metadata_sha256':'d'*64}}
    assert tool.pending_artifacts([source],set())==[source['input_artifact']]
    assert tool.pending_artifacts([source],{'pending'})==[]
    del source['input_artifact']
    with pytest.raises(ValueError,match='LEGACY_INPUT_RECOVERY_REQUIRED'):tool.pending_artifacts([source],set())


def test_expired_old_input_is_isolated_and_current_delta_is_retained(tmp_path,monkeypatch):
    tool=module();archive,manifest,files=bundle(tmp_path)
    artifact={'id':5,'size_in_bytes':archive.stat().st_size,'digest':'sha256:'+tool.digest(archive),'acquisition_run_attempt':1}
    descriptor={'artifact_id':10,'digest':'c'*64,'acquisition_run_id':99,'acquisition_run_attempt':1,'head_sha':'d'*40,
        'document_member':'documents/old.json','native_member':'raw/old.html','metadata_sha256':'e'*64}
    source={'document_id':'old','body_key':'f'*64,'body_sha256':'a'*64,'raw_sha256':'b'*64,'input_artifact':descriptor}
    monkeypatch.setattr(tool,'checkpoint_inputs',lambda p:{'descriptors':[descriptor],'holds':[],'sources':{'f'*64:source}})
    def lookup(t,run,head,**kwargs):
        if run==99:raise ValueError('EXPIRED')
        return artifact
    monkeypatch.setattr(tool,'artifact_for',lookup)
    class Transport:
        free_disk=lambda self,p:10*1024**3
        download=lambda self,a,p:shutil.copyfile(archive,p)
    monkeypatch.setattr(tool,'transport',Transport)
    rss=tmp_path/'rss.json';rss.write_bytes(files['rss-manifest.json'])
    result=tool.receive(2,'a'*40,1,rss,tmp_path/'out',tmp_path/'checkpoint',tmp_path/'receipt.json')
    assert result['isolated_prior_input_holds']==1
    assert (tmp_path/'out/documents/one.json').read_bytes()==files['documents/one.json']
    receipt=json.loads((tmp_path/'receipt.json').read_text())
    assert receipt['input_holds'][0]['body_key']==source['body_key']
    assert receipt['input_holds'][0]['reason_code']=='EXACT_PRIOR_ARTIFACT_UNAVAILABLE_OR_INVALID'
    assert receipt['legacy_full_cache_downloads']==0


def test_invalid_prior_bundles_are_cleaned_before_next_bounded_download(tmp_path,monkeypatch):
    tool=module();archive,manifest,files=bundle(tmp_path)
    artifact={'id':5,'size_in_bytes':archive.stat().st_size,'digest':'sha256:'+tool.digest(archive),'acquisition_run_attempt':1}
    descriptors=[];sources={}
    for number in (10,11):
        descriptor={'artifact_id':number,'digest':tool.digest(archive),'acquisition_run_id':2,'acquisition_run_attempt':1,'head_sha':'a'*40,
            'document_member':f'documents/missing-{number}.json','native_member':None,'metadata_sha256':'e'*64}
        source={'document_id':f'old-{number}','body_key':str(number)*32,'body_sha256':'a'*64,'raw_sha256':'b'*64,'input_artifact':descriptor}
        descriptors.append(descriptor);sources[source['body_key']]=source
    monkeypatch.setattr(tool,'checkpoint_inputs',lambda p:{'descriptors':descriptors,'holds':[],'sources':sources})
    monkeypatch.setattr(tool,'artifact_for',lambda t,r,h,**kw:{**artifact,'id':kw.get('artifact_id',5)})
    class Transport:
        free_disk=lambda self,p:10*1024**3
        def download(self,a,path):
            assert not list(path.parent.glob('artifact-*.zip'))
            assert not list(path.parent.glob('decoded-*'))
            shutil.copyfile(archive,path)
    monkeypatch.setattr(tool,'transport',Transport)
    rss=tmp_path/'rss.json';rss.write_bytes(files['rss-manifest.json'])
    result=tool.receive(2,'a'*40,1,rss,tmp_path/'out',tmp_path/'checkpoint',tmp_path/'receipt.json')
    assert result['isolated_prior_input_holds']==2
    assert (tmp_path/'out/documents/one.json').read_bytes()==files['documents/one.json']


def test_explicit_exact_graph_recovery_is_blocked_before_ingest(tmp_path):
    tool=module();archive,_,_=bundle(tmp_path,mutate=lambda m:m.update(status='EXACT_SOURCE_RECOVERY_REQUIRED'))
    with pytest.raises(ValueError,match='BLOCKED_INPUT_RECOVERY_REQUIRED'):
        tool.extract_bundle(archive,tmp_path/'out',run_id=2,head_sha='a'*40,rss_run_id=1)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('stalled',[False,True])
def test_download_deadline_and_hash_bound_bytes_without_network(tmp_path,monkeypatch,stalled):
    tool=module();real_popen=tool.subprocess.Popen;payload=b'exact bytes'
    def local_process(command,**kwargs):
        assert command[:2]==['gh','api']
        code='import time;time.sleep(10)' if stalled else 'import sys;sys.stdout.buffer.write('+repr(payload)+')'
        return real_popen([sys.executable,'-c',code],**kwargs)
    monkeypatch.setattr(tool.subprocess,'Popen',local_process)
    artifact={'id':1,'size_in_bytes':len(payload),'digest':'sha256:'+hashlib.sha256(payload).hexdigest()}
    target=tmp_path/'download.zip'
    if stalled:
        with pytest.raises(tool.DownloadError,match='TIMEOUT') as error:tool.download(artifact,target,seconds=.1)
        assert error.value.bytes_received==0 and not target.exists()
    else:
        assert tool.download(artifact,target,seconds=2)==len(payload)
        assert target.read_bytes()==payload


def test_exact_prior_input_preserves_supplemental_native_source_proof(tmp_path,monkeypatch):
    tool=module();current_dir=tmp_path/'current';current_dir.mkdir();old_dir=tmp_path/'old';old_dir.mkdir()
    current,_,files=bundle(current_dir);old,old_manifest,old_files=bundle(old_dir,native_proof=True)
    artifacts={number:{'id':number,'size_in_bytes':archive.stat().st_size,'digest':'sha256:'+tool.digest(archive),'acquisition_run_attempt':1}
               for number,archive in ((5,current),(10,old))}
    descriptor={'artifact_id':10,'digest':tool.digest(old),'acquisition_run_id':2,'acquisition_run_attempt':1,'head_sha':'a'*40,
        'document_member':'documents/one.json','native_member':'raw/a.html','metadata_sha256':old_manifest['files']['documents/one.json']['sha256']}
    source={'document_id':'old','body_key':'f'*64,'body_sha256':'a'*64,'raw_sha256':'b'*64,'input_artifact':descriptor}
    monkeypatch.setattr(tool,'checkpoint_inputs',lambda p:{'descriptors':[descriptor],'holds':[],'sources':{'f'*64:source}})
    monkeypatch.setattr(tool,'artifact_for',lambda t,r,h,**kw:artifacts[kw.get('artifact_id',5)])
    class Transport:
        free_disk=lambda self,p:10*1024**3
        download=lambda self,a,p:shutil.copyfile(current if a['id']==5 else old,p)
    monkeypatch.setattr(tool,'transport',Transport)
    rss=tmp_path/'rss.json';rss.write_bytes(files['rss-manifest.json'])
    result=tool.receive(2,'a'*40,1,rss,tmp_path/'out',tmp_path/'checkpoint',tmp_path/'receipt.json')
    assert result['isolated_prior_input_holds']==0
    proof=next(name for name in old_files if name.endswith('.json') and name.startswith('raw/'))
    assert (tmp_path/'out'/proof).read_bytes()==old_files[proof]
