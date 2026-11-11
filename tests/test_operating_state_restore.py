import importlib.util
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import zipfile
import pytest

spec = importlib.util.spec_from_file_location('operating_restore',
    Path(__file__).parents[1]/'.github/scripts/bct_restore_operating_state.py')
module = importlib.util.module_from_spec(spec)
sys.path.insert(0,str(Path(__file__).parents[1]/'.github/scripts'))
try:spec.loader.exec_module(module)
finally:sys.path.pop(0)


@pytest.mark.parametrize('name', ['../old-checkpoint.json', '/absolute', 'a\\b'])
def test_archive_cannot_escape_or_alias_the_restore_directory(tmp_path, name):
    archive = tmp_path/'unsafe.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr(name, b'bytes')
    with pytest.raises(ValueError, match='unsafe'):
        module.unpack(archive, tmp_path/'restored')
    assert not (tmp_path/'restored').exists()


def test_normalized_alias_and_symlink_are_rejected_before_writing(tmp_path):
    archive = tmp_path/'aliases.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr('safe/file.txt', b'original')
        stream.writestr('safe/./file.txt', b'overwrite')
    with pytest.raises(ValueError, match='duplicate'):
        module.unpack(archive, tmp_path/'restored')
    with zipfile.ZipFile(archive, 'w') as stream:
        entry = zipfile.ZipInfo('link')
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        stream.writestr(entry, b'/existing/cache')
    with pytest.raises(ValueError, match='unsafe'):
        module.unpack(archive, tmp_path/'restored')


def test_restore_never_overwrites_an_existing_checkpoint(tmp_path):
    archive = tmp_path/'valid.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr('checkpoint.json', b'new')
    target = tmp_path/'restored'
    target.mkdir()
    (target/'checkpoint.json').write_bytes(b'preserved')
    with pytest.raises(ValueError, match='empty'):
        module.unpack(archive, target)
    assert (target/'checkpoint.json').read_bytes() == b'preserved'


def test_signed_download_redirect_does_not_forward_authenticated_request():
    assert module.NoRedirect().redirect_request(None, None, 302, '', {},
        'https://storage.blob.core.windows.net/signed') is None


def test_authenticated_extractor_preserves_normalized_alias_rejection(tmp_path):
    archive=tmp_path/'aliases.zip'
    with zipfile.ZipFile(archive,'w') as saved:
        saved.writestr('safe/file.txt',b'original');saved.writestr('safe/./file.txt',b'overwrite')
    target=tmp_path/'restored';target.mkdir()
    with pytest.raises(ValueError):module.transport.extract_recovery(archive,target)
    assert not list(target.iterdir())


def current_fixture(tmp_path,monkeypatch,*,expired=False):
    """Synthetic source bytes; the actual saved input is not downloaded again."""
    transport=module.transport
    files={'checkpoint.json':json.dumps({'run_id':'20','code_sha':'a'*40}).encode(),
           'source-recovery-attempts.jsonl':b''}
    body=b'SYNTHETIC retained source'
    files['private-source-cache/'+hashlib.sha256(body).hexdigest()+'.txt']=body
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w') as saved:
        for name,value in files.items():saved.writestr(name,value)
    original=raw.getvalue();entry={'artifact_id':10,'run_id':20,'head_sha':'a'*40,
        'name':'bct-recovery-checkpoint-20','bytes':len(original),'sha256':hashlib.sha256(original).hexdigest()}
    proof={'format':'bct-input-preservation-1','original':entry,
           'new_gate_execution':False,'release_proof_renewed':False}
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w') as saved:
        saved.writestr('input.zip',original);saved.writestr('preservation.json',json.dumps(proof))
    wrapper=raw.getvalue()
    request={'resume_run_id':'20','resume_archive':entry,
             'resume_file_sha256':{name:hashlib.sha256(value).hexdigest() for name,value in files.items() if '/' not in name},
             'resume_cache_inventory_sha256':hashlib.sha256(json.dumps(sorted(name for name in files if name.startswith('private-source-cache/')),separators=(',',':')).encode()).hexdigest()}
    release={'gate_run_id':20,'validated_code_sha':'a'*40,'artifact_id':10,'artifact_sha256':entry['sha256']}
    root=tmp_path/'checkout';(root/'.github').mkdir(parents=True);(root/'config').mkdir()
    (root/'.github/bct-recovery-request.json').write_text(json.dumps(request))
    (root/'config/bct-operating-release.json').write_text(json.dumps(release))
    artifact={'id':10,'name':entry['name'],'size_in_bytes':len(original),'digest':'sha256:'+entry['sha256'],
              'expired':expired,'expires_at':'2099-01-01T00:00:00Z','workflow_run':{'id':20,'head_sha':'a'*40}}
    preserved={'id':60,'name':transport.copy_name(entry),'size_in_bytes':len(wrapper),
               'digest':'sha256:'+hashlib.sha256(wrapper).hexdigest(),'expired':False,
               'expires_at':'2099-01-01T00:00:00Z','workflow_run':{'id':50}}
    calls=[]
    class API:
        def read(self,suffix):
            calls.append(suffix)
            if suffix=='':return {'private':False,'visibility':'public'}
            if suffix=='/actions/artifacts/10':return artifact
            if suffix.startswith('/actions/artifacts?'):return {'total_count':1,'artifacts':[preserved]}
            if suffix=='/actions/runs/20':
                return {'id':20,'status':'completed','head_sha':'a'*40,'path':'.github/workflows/bct-recovery.yml',
                        'head_repository':{'full_name':transport.REPOSITORY}}
            if suffix=='/actions/runs/50':
                return {'id':50,'status':'completed','conclusion':'success','event':'workflow_dispatch',
                        'head_branch':'main','path':'.github/workflows/bct-recovery.yml',
                        'head_repository':{'full_name':transport.REPOSITORY}}
            raise AssertionError('unexpected historical run enumeration: '+suffix)
    def download(metadata,destination,maximum):
        data=wrapper if metadata['id']==60 else original
        assert len(data)<=maximum and metadata['digest']=='sha256:'+hashlib.sha256(data).hexdigest()
        Path(destination).write_bytes(data)
    monkeypatch.setattr(transport,'download',download)
    return root,API(),calls,entry


@pytest.mark.parametrize('expired',[False,True])
def test_operating_restore_uses_authenticated_latest_resume_and_copy_fallback(tmp_path,monkeypatch,expired):
    root,api,calls,entry=current_fixture(tmp_path,monkeypatch,expired=expired)
    target=tmp_path/'restored'
    result=module.restore_current(root,target,api=api)
    assert result['artifact_run_id']==20 and result['artifact_sha256']==entry['sha256']
    assert result['transport']['source']==('preserved' if expired else 'original')
    assert result['verified_cache_files']['private-source-cache']==1
    assert not result['new_gate_execution'] and not result['release_proof_renewed']
    assert json.loads((target/'operating-state-restore.json').read_text())==result
    assert not any('branch=' in suffix for suffix in calls)


@pytest.mark.parametrize('change',['run','head','digest','pin'])
def test_operating_restore_refuses_wrong_origin_or_journal_before_use(tmp_path,monkeypatch,change):
    root,api,_,_=current_fixture(tmp_path,monkeypatch)
    path=root/'.github/bct-recovery-request.json';request=json.loads(path.read_text())
    if change=='run':request['resume_archive']['run_id']=19
    elif change=='head':request['resume_archive']['head_sha']='b'*40
    elif change=='digest':request['resume_archive']['sha256']='b'*64
    else:request['resume_file_sha256']['checkpoint.json']='b'*64
    path.write_text(json.dumps(request));target=tmp_path/'restored'
    with pytest.raises(ValueError):module.restore_current(root,target,api=api)
    assert not target.exists()


def test_newer_failed_gate_input_cannot_be_used_as_automatic_operating_proof(tmp_path,monkeypatch):
    root,api,calls,_=current_fixture(tmp_path,monkeypatch)
    path=root/'.github/bct-recovery-request.json';request=json.loads(path.read_text())
    request.update(resume_run_id='21',resume_input_only=True)
    request['resume_archive'].update(run_id=21,name='bct-recovery-checkpoint-21')
    path.write_text(json.dumps(request))
    # This is valid explicit Gate continuation input, but is not a release.
    release=json.loads((root/'config/bct-operating-release.json').read_text())
    assert module.transport.resume_origin(request,release)['run_id']==21
    with pytest.raises(ValueError,match='OPERATING_RESTORE_SUCCESSFUL_RELEASE_INPUT_REQUIRED'):
        module.restore_current(root,tmp_path/'forbidden',api=api)
    assert not calls and not (tmp_path/'forbidden').exists()
