"""Bound acquisition state preserves history; CPU deltas preserve exact versions."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def helper():
    spec = importlib.util.spec_from_file_location('acquisition_sources', ROOT / '.github/scripts/acquisition_sources.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(value):
    return hashlib.sha256(value).hexdigest()


def test_restore_keeps_all_non_evaluation_history_and_controls_exactly(tmp_path):
    module = helper(); archive = tmp_path / 'old.zip'
    original = {'activation.json': b'{"cutover":"2000-01-01"}', '.lock': b'',
                'documents/old.json': b'{bad metadata', 'raw/old.html': b'original',
                'captures/failed.json': b'{"status":"HTTP_403"}',
                'requests/failed.json': b'{"search_status":"HTTP_429"}',
                'pending/request.json': b'pending', 'seed-queue/unread.json': b'unread',
                'cycles/completed.json': b'completed', 'source-holds/corrupt.json': b'hold',
                'activation-amendments/old.json': b'preserved amendment'}
    with zipfile.ZipFile(archive, 'w') as saved:
        for name, payload in original.items(): saved.writestr(name, payload)
        saved.writestr('evaluations/huge.json', b'x' * 100000)
    before = archive.read_bytes(); destination = tmp_path / 'cache'
    receipt = module.restore_state(archive, destination, max_expanded=4096)
    assert {p.relative_to(destination).as_posix(): p.read_bytes() for p in destination.rglob('*') if p.is_file()} == original
    assert receipt['evaluations_expanded'] is False and receipt['skipped_evaluation_members'] == 1
    assert archive.read_bytes() == before and not (destination / 'evaluations').exists()


@pytest.mark.parametrize('kind', ['escape', 'symlink', 'duplicate', 'overlimit'])
def test_restore_rejects_unsafe_or_oversize_state_without_publishing_partial(tmp_path, kind):
    module = helper(); archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as saved:
        if kind == 'escape': saved.writestr('requests/../outside.json', b'bad')
        elif kind == 'symlink':
            info = zipfile.ZipInfo('activation.json'); info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16; saved.writestr(info, b'/secret')
        elif kind == 'duplicate':
            saved.writestr('activation.json', b'one')
            with pytest.warns(UserWarning): saved.writestr('activation.json', b'two')
        else: saved.writestr('raw/large.html', b'x' * 20)
    with pytest.raises(ValueError): module.restore_state(archive, tmp_path / 'cache', max_expanded=10)
    assert not (tmp_path / 'cache').exists()


def source(cache, did, url, raw=b'<p>original</p>', *, filename='one.json'):
    for name in ('documents', 'raw', 'captures'): (cache/name).mkdir(parents=True, exist_ok=True)
    raw_hash = sha(raw); body = 'original'
    doc = {'document_id': did, 'origin_url': url, 'body': body, 'body_sha256': sha(body.encode()),
           'version': sha(body.encode()), 'raw_sha256': raw_hash, 'raw_path': '/old/runner/' + raw_hash + '.html'}
    payload = json.dumps(doc, sort_keys=True).encode()
    (cache/'documents'/filename).write_bytes(payload); (cache/'raw'/(raw_hash+'.html')).write_bytes(raw)
    (cache/'captures'/(sha(url.encode())+'.json')).write_text(json.dumps({**doc,'status':'CAPTURED'}))
    return doc, payload


def manifest(tmp_path, rows):
    path = tmp_path / 'rss-manifest.json'
    path.write_text(json.dumps({'format':'bct-new-rss-delta-v1','collection_started_at':'2026-11-11T00:00:00Z','documents':rows}))
    return path


def test_delta_copies_only_manifest_sources_with_literal_metadata_and_all_versions(tmp_path):
    module = helper(); cache = tmp_path/'cache'
    doc, payload = source(cache, 'new', 'https://publisher.example/new')
    source(cache, 'old', 'https://publisher.example/old', filename='old.json')
    duplicate = cache/'documents'/'new-version.json'; duplicate.write_bytes(payload)
    rss = manifest(tmp_path, [{'document_id':'new','url':doc['origin_url']}]); before = rss.read_bytes()
    dest = tmp_path/'delta'
    receipt = module.build_delta(cache,rss,dest,rss_run_id=10,acquisition_run_id=11,head_sha='a'*40)
    data = json.loads((dest/'manifest.json').read_text())
    assert data['format']=='bct-cpu-source-delta-1' and data['rss_manifest_sha256']==sha(before)
    assert (dest/'rss-manifest.json').read_bytes()==before
    assert len(data['documents'])==2 and {d['document_id'] for d in data['documents']}=={'new'}
    assert not (dest/'documents/old.json').exists()
    assert (dest/'documents/one.json').read_bytes()==payload
    for name, item in data['files'].items():
        assert (dest/name).stat().st_size==item['bytes'] and sha((dest/name).read_bytes())==item['sha256']
    assert receipt['new_CPU_inferences']==receipt['source_HTTP_requests']==0 and rss.read_bytes()==before
    assert receipt['bytes']==sum(p.stat().st_size for p in dest.rglob('*') if p.is_file())
    assert receipt['files']==sum(p.is_file() for p in dest.rglob('*'))


def test_delta_preserves_missing_raw_and_malformed_metadata_for_downstream_holds(tmp_path):
    module=helper();cache=tmp_path/'cache';doc,payload=source(cache,'new','https://publisher.example/new')
    (cache/'raw'/Path(doc['raw_path']).name).unlink()
    (cache/'documents/broken.json').write_bytes(b'{malformed')
    rss=manifest(tmp_path,[{'document_id':'new','url':doc['origin_url']}]);dest=tmp_path/'delta'
    module.build_delta(cache,rss,dest,rss_run_id=10,acquisition_run_id=11,head_sha='a'*40)
    assert (dest/'documents/one.json').read_bytes()==payload
    assert (dest/'documents/broken.json').read_bytes()==b'{malformed'
    data=json.loads((dest/'manifest.json').read_text())
    assert data['documents'][0]['native_member'] is None
    assert not list((dest/'raw').glob('*')) if (dest/'raw').exists() else True


def test_delta_limits_and_existing_destinations_do_not_delete_any_original(tmp_path):
    module=helper();cache=tmp_path/'cache';doc,payload=source(cache,'new','https://publisher.example/new')
    rss=manifest(tmp_path,[{'document_id':'new','url':doc['origin_url']}]);dest=tmp_path/'delta'
    dest.mkdir();(dest/'preserved').write_bytes(b'old')
    with pytest.raises(ValueError):module.build_delta(cache,rss,dest,rss_run_id=10,acquisition_run_id=11,head_sha='a'*40)
    assert (dest/'preserved').read_bytes()==b'old'
    with pytest.raises(ValueError):module.build_delta(cache,rss,tmp_path/'small',rss_run_id=10,acquisition_run_id=11,head_sha='a'*40,max_bytes=1)
    assert not (tmp_path/'small').exists() and (cache/'documents/one.json').read_bytes()==payload


def test_new_opposite_body_has_explicit_seed_relation_and_is_not_relabelled_rss(tmp_path):
    module=helper();cache=tmp_path/'cache'
    doc,payload=source(cache,'new-source-opposite','https://maker.example/source',filename='opposite.json')
    (cache/'requests').mkdir();(cache/'requests/request.json').write_text(json.dumps({
        'request_id':'request-1','seed_document_ids':['buyer'],
        'captures':[{'document_id':doc['document_id'],'origin_url':doc['origin_url']}],
        'capture_validation':[{'state':'VALID_PRIMARY_EVIDENCE'}]}))
    rss=manifest(tmp_path,[{'document_id':'buyer','url':'https://buyer.example/source'}]);dest=tmp_path/'delta'
    module.build_delta(cache,rss,dest,rss_run_id=10,acquisition_run_id=11,head_sha='a'*40,new_document_files=['opposite.json'])
    descriptor=json.loads((dest/'manifest.json').read_text())['documents'][0]
    assert descriptor['source_kind']=='ACQUISITION_OPPOSITE'
    assert descriptor['seed_document_ids']==['buyer'] and descriptor['request_id']=='request-1'
    assert json.loads((dest/'rss-manifest.json').read_text())['documents'][0]['document_id']=='buyer'


def test_acquisition_workflow_uses_bounded_history_and_separate_current_source_delta():
    text=(ROOT/'.github/workflows/precursor-acquisition.yml').read_text()
    assert 'gh run download "$prior_run" --name precursor-private-cache' not in text
    assert 'acquisition_sources.py restore' in text
    assert '!var/new-precursors/evaluations/**' in text
    assert 'name: precursor-cpu-delta' in text and 'name: bct-public-acquisition' in text
    assert 'RSS_RUN_ID: ${{ github.event.workflow_run.id || inputs.rss_run_id }}' in text


def test_matching_metadata_with_invalid_raw_path_stays_for_per_source_hold(tmp_path):
    module=helper();cache=tmp_path/'cache';doc,payload=source(cache,'new','https://publisher.example/new')
    doc['raw_path']=123;original=json.dumps(doc).encode();(cache/'documents/one.json').write_bytes(original)
    rss=manifest(tmp_path,[{'document_id':'new','url':doc['origin_url']}]);dest=tmp_path/'delta'
    module.build_delta(cache,rss,dest,rss_run_id=10,acquisition_run_id=11,head_sha='a'*40)
    assert (dest/'documents/one.json').read_bytes()==original
    assert json.loads((dest/'manifest.json').read_text())['documents'][0]['native_member'] is None



@pytest.mark.parametrize('reverse_restored', [False, True])
def test_new_root_delta_keeps_exact_old_counterpart_and_not_unrelated_old_pairs(tmp_path, reverse_restored):
    from bct import precursor_collection as collection,precursor_evidence_graph as graph
    from test_precursor_evidence_graph import pair,ASOF
    module=helper();buyer,supply=pair();other_buyer,other_supply=pair(contract='OTHER-99')
    other_buyer=collection.structure({**other_buyer,'document_id':'unrelated-buyer','body':other_buyer['body'].replace('tungsten','nickel'),
        'body_sha256':sha(other_buyer['body'].replace('tungsten','nickel').encode())})
    other_supply=collection.structure({**other_supply,'document_id':'unrelated-supply','body':other_supply['body'].replace('tungsten','nickel'),
        'body_sha256':sha(other_supply['body'].replace('tungsten','nickel').encode())})
    documents=[buyer,supply,other_buyer,other_supply]
    full=graph.analyze(documents,mode='SYNTHETIC',now=ASOF)
    assert len(full['protected_result']['candidates'])==2
    selected=module.graph_source_versions(full,{buyer['document_id']})
    assert {row['document_id']for row in selected}=={buyer['document_id'],supply['document_id']}
    cache=tmp_path/'cache'
    for folder in('documents','raw','captures'):(cache/folder).mkdir(parents=True,exist_ok=True)
    for document in documents:
        raw=b'original-'+document['document_id'].encode();document.update(raw_sha256=sha(raw),raw_path='/prior/'+sha(raw)+'.html',version=document['body_sha256'])
        (cache/'documents'/(document['document_id']+'.json')).write_text(json.dumps(document))
        (cache/'raw'/(sha(raw)+'.html')).write_bytes(raw)
    selected=module.graph_source_versions(graph.analyze(documents,mode='SYNTHETIC',now=ASOF),{buyer['document_id']})
    rss=manifest(tmp_path,[{'document_id':buyer['document_id'],'url':buyer['origin_url']}]);dest=tmp_path/'delta'
    module.build_delta(cache,rss,dest,rss_run_id=10,acquisition_run_id=11,head_sha='a'*40,graph_sources=selected)
    bound=json.loads((dest/'manifest.json').read_text())
    assert {row['document_id']for row in bound['documents']}=={buyer['document_id'],supply['document_id']}
    assert next(row for row in bound['documents']if row['document_id']==supply['document_id'])['source_kind']=='GRAPH_CONTEXT'
    derived=json.loads((dest/'cpu-manifest.json').read_text())
    assert [row['document_id']for row in derived['documents']]==[buyer['document_id']]
    restored=[json.loads(path.read_text())for path in sorted((dest/'documents').glob('*.json'),reverse=reverse_restored)]
    # Exact serialized undirected-link proofs follow graph input order. Preserve
    # the original order for this byte-for-byte candidate transport comparison.
    source_order={document['document_id']:i for i,document in enumerate(documents)}
    restored.sort(key=lambda document:source_order[document['document_id']])
    result=graph.analyze(restored,mode='SYNTHETIC',now=ASOF)
    rooted=next(row for row in full['protected_result']['candidates']if row['target_id']==result['protected_result']['candidates'][0]['target_id'])
    assert result['protected_result']['candidates'][0]==rooted
    assert result['pairs'][0]['comparison']['state']=='POSSIBLE_TIMING_GAP'
    assert all('unrelated'not in row['document_id']for row in restored)


def test_size_fallback_names_exact_original_archive_and_never_returns_fake_empty_sources(tmp_path):
    module=helper();rss=manifest(tmp_path,[{'document_id':'root','url':'https://buyer.example/source'}]);dest=tmp_path/'fallback'
    required=[{'document_id':'old-supply','origin_url':'https://maker.example/source','body_sha256':'b'*64,
               'raw_sha256':'c'*64,'root_document_ids':['root']}]
    result=module.build_fallback(rss,dest,rss_run_id=10,rss_run_attempt=1,acquisition_run_id=11,
        acquisition_run_attempt=2,head_sha='a'*40,artifact_id=22,artifact_digest='d'*64,
        graph_sources=required,reason='ACQUISITION_DELTA_LIMIT')
    data=json.loads((dest/'manifest.json').read_text())
    assert data['status']=='EXACT_SOURCE_RECOVERY_REQUIRED' and data['required_graph_sources']==required
    assert data['fallback']['artifact_id']==22 and data['fallback']['digest']=='sha256:'+'d'*64
    assert data['fallback']['acquisition_run_attempt']==2
    assert (dest/'rss-manifest.json').read_bytes()==rss.read_bytes()
    assert result['new_CPU_inferences']==0 and not list((dest/'documents').glob('*'))


def test_rss_attempt_two_cannot_accept_unsigned_original_attempt_one_manifest(tmp_path):
    module=helper();cache=tmp_path/'cache';doc,_=source(cache,'new','https://publisher.example/new')
    rss=manifest(tmp_path,[{'document_id':'new','url':doc['origin_url']}])
    with pytest.raises(ValueError,match='ATTEMPT'):
        module.build_delta(cache,rss,tmp_path/'delta',rss_run_id=10,rss_run_attempt=2,
            acquisition_run_id=11,acquisition_run_attempt=2,head_sha='a'*40)
    assert not (tmp_path/'delta').exists()


@pytest.mark.parametrize('prior_attempt,current_attempt',[(0,2),(1,2),(2,1)])
def test_previous_cache_restore_rejects_wrong_attempt_before_download(tmp_path,monkeypatch,prior_attempt,current_attempt):
    from types import SimpleNamespace
    module=helper();calls=[]
    run={'id':10,'run_attempt':current_attempt,'head_sha':'a'*40,'path':'.github/workflows/precursor-acquisition.yml',
         'head_branch':'main','event':'workflow_run','conclusion':'success',
         'head_repository':{'full_name':'irewon1-lgtm/bottleneck-control-tower'}}
    def request(path):calls.append(path);return run if '/artifacts'not in path else {'artifacts':[]}
    transport=SimpleNamespace(gh_json=request,REPOSITORY='irewon1-lgtm/bottleneck-control-tower')
    monkeypatch.setattr(module,'transport_module',lambda:transport)
    with pytest.raises(ValueError,match='ATTEMPT_BINDING'):
        module.restore_run(10,tmp_path/'cache',run_attempt=prior_attempt)
    assert not (tmp_path/'cache').exists()


def test_restored_failed_capture_never_retries_or_changes_cutover(tmp_path,monkeypatch):
    from bct import precursor_collection as collection
    module=helper();archive=tmp_path/'state.zip';url='https://publisher.example/blocked'
    failed={'document_id':'blocked','origin_url':url,'status':'HTTP_403','error':'preserved failure'}
    activation={'new_document_cutover':'2026-10-05T00:00:00Z','engine_hashes':collection.hashes(),
                'excluded_document_ids':[],'excluded_urls':[]}
    activation_bytes=json.dumps(activation,sort_keys=True).encode();failed_bytes=json.dumps(failed,sort_keys=True).encode()
    with zipfile.ZipFile(archive,'w')as saved:
        saved.writestr('activation.json',activation_bytes)
        saved.writestr('captures/'+sha(url.encode())+'.json',failed_bytes)
        saved.writestr('evaluations/unneeded.json',b'x'*10000)
    destination=tmp_path/'restored';module.restore_state(archive,destination)
    monkeypatch.setattr(collection.acquisition,'fetch',lambda *args:pytest.fail('stored failure must not refetch'))
    assert collection.capture(destination,url,'blocked',activation)==failed
    assert (destination/'activation.json').read_bytes()==activation_bytes
    assert (destination/'captures'/(sha(url.encode())+'.json')).read_bytes()==failed_bytes


def test_referenced_sec_native_metadata_is_carried_with_the_same_source_version(tmp_path):
    module=helper();cache=tmp_path/'cache';doc,_=source(cache,'filing','https://www.sec.gov/Archives/filing.htm')
    native=b'{"filings":{"recent":{}}}';native_hash=sha(native)
    doc['sec_filing_metadata']={'raw_sha256':native_hash,'status':'CAPTURED'}
    (cache/'raw'/(native_hash+'.json')).write_bytes(native)
    (cache/'documents/one.json').write_text(json.dumps(doc))
    rss=manifest(tmp_path,[{'document_id':'filing','url':doc['origin_url']}]);dest=tmp_path/'delta'
    module.build_delta(cache,rss,dest,rss_run_id=10,acquisition_run_id=11,head_sha='a'*40)
    assert (dest/'raw'/(native_hash+'.json')).read_bytes()==native
    assert json.loads((dest/'documents/one.json').read_text())['sec_filing_metadata']==doc['sec_filing_metadata']
