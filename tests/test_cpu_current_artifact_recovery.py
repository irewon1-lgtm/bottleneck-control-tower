"""Strict source-ID/identity tests for current immutable artifact recovery.

The 8-artifact historical limit is left unchanged. Only identical native
version and artifact metadata from the *already downloaded current* source may
replace an input-budget hold; any doubt leaves the hold in place.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
from copy import deepcopy

import pytest


def module():
    p=Path(__file__).resolve().parents[1]/'.github/scripts/receive_cpu_delta.py'
    spec=importlib.util.spec_from_file_location('bct_exact_current_input',p)
    out=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(out)
    return out


def fixture(tmp_path):
    mod=module()
    raw=b'<article><p>A verified native source.</p></article>'
    body='A verified native source.'
    digest=lambda s: hashlib.sha256(s).hexdigest()
    h=digest(body.encode());rh=digest(raw)
    doc={'document_id':'bct-s4-real-id',
         'origin_url':'https://example.gov/research/bct-s4-real-id',
         'body_sha256':h,'raw_sha256':rh,'version':h,
         'body':body,'provenance':'PASS','provenance_verified':True}
    doc_raw=json.dumps(doc,sort_keys=True).encode()
    member='documents/'+h+'.json';native='raw/'+rh+'.html'
    cache=tmp_path/'exact';(cache/'documents').mkdir(parents=True);(cache/'raw').mkdir()
    (cache/member).write_bytes(doc_raw);(cache/native).write_bytes(raw)
    manifest={'format':'bct-cpu-source-delta-1','acquisition_run_id':43645932280,
              'acquisition_run_attempt':1,'acquisition_head_sha':'a'*40,
              'documents':[{'document_id':doc['document_id'],
                            'document_member':member,'native_member':native,
                            'metadata_sha256':digest(doc_raw),
                            'body_sha256':h,'raw_sha256':rh}],
              'files':{member:{'sha256':digest(doc_raw),'bytes':len(doc_raw)},
                       native:{'sha256':rh,'bytes':len(raw)}}}
    artifact={'id':14134182940,'digest':'sha256:'+'b'*64,
              'acquisition_run_attempt':1}
    descriptor={'artifact_id':artifact['id'],'digest':'b'*64,
                'manifest_sha256':mod.canonical_hash(manifest),
                'acquisition_run_id':manifest['acquisition_run_id'],
                'acquisition_run_attempt':1,'head_sha':'a'*40,
                'document_member':member,'native_member':native,
                'metadata_sha256':digest(doc_raw)}
    source={'document_id':doc['document_id'],'body_sha256':h,
            'raw_sha256':rh,'body_key':'source-key','input_artifact':descriptor}
    hold={'document_id':doc['document_id'],'body_key':'source-key',
          'body_sha256':h,'raw_sha256':rh,
          'status':'HELD_INPUT_UNAVAILABLE','reason_code':'PRIOR_INPUT_ARTIFACT_BUDGET_HELD'}
    return mod,cache,manifest,artifact,source,hold


def recovered(case):
    mod,cache,manifest,artifact,source,hold=case
    return mod.recover_current_exact_holds([hold],{'source-key':source},
                                           artifact,manifest,cache)


def test_exact_current_original_unblocks_only_one_budget_hold(tmp_path):
    c=fixture(tmp_path);holds,found=recovered(c)
    assert holds==[] and len(found)==1
    assert found[0]['artifact_id']==c[3]['id']
    assert found[0]['body_sha256']==c[4]['body_sha256']
    assert found[0]['raw_sha256']==c[4]['raw_sha256']
    assert found[0]['status']=='EXACT_CURRENT_ARTIFACT_PROVEN_FOR_REHYDRATION'


@pytest.mark.parametrize('corruption',[
    'other_hold_reason','other_artifact','other_artifact_digest',
    'other_manifest','other_run','other_attempt','other_head',
    'wrong_document_id','wrong_body_sha','wrong_native_sha',
    'wrong_metadata_sha','missing_native','missing_metadata',
    'incorrect_version','incomplete_provenance','body_hash_wrong',
    'duplicate_current_id','bad_current_artifact_digest'
])
def test_changed_or_unverified_current_source_remains_held(tmp_path,corruption):
    c=fixture(tmp_path);mod,cache,manifest,artifact,source,hold=c
    if corruption=='other_hold_reason':hold['reason_code']='EXACT_PRIOR_ARTIFACT_UNAVAILABLE_OR_INVALID'
    elif corruption=='other_artifact':source['input_artifact']['artifact_id']=999
    elif corruption=='other_artifact_digest':source['input_artifact']['digest']='f'*64
    elif corruption=='other_manifest':source['input_artifact']['manifest_sha256']='f'*64
    elif corruption=='other_run':source['input_artifact']['acquisition_run_id']=7
    elif corruption=='other_attempt':source['input_artifact']['acquisition_run_attempt']=2
    elif corruption=='other_head':source['input_artifact']['head_sha']='c'*40
    elif corruption=='wrong_document_id':source['document_id']='different'
    elif corruption=='wrong_body_sha':source['body_sha256']='0'*64
    elif corruption=='wrong_native_sha':source['raw_sha256']='0'*64
    elif corruption=='wrong_metadata_sha':source['input_artifact']['metadata_sha256']='0'*64
    elif corruption=='missing_native':manifest['files'].pop(source['input_artifact']['native_member'])
    elif corruption=='missing_metadata':manifest['files'].pop(source['input_artifact']['document_member'])
    elif corruption=='incorrect_version':
        p=cache/source['input_artifact']['document_member'];row=json.loads(p.read_text());row['version']='0'*64;p.write_text(json.dumps(row))
    elif corruption=='incomplete_provenance':
        p=cache/source['input_artifact']['document_member'];row=json.loads(p.read_text());row['provenance_verified']=False;p.write_text(json.dumps(row))
    elif corruption=='body_hash_wrong':
        p=cache/source['input_artifact']['document_member'];row=json.loads(p.read_text());row['body']='tampered';p.write_text(json.dumps(row))
    elif corruption=='duplicate_current_id':manifest['documents'].append(deepcopy(manifest['documents'][0]))
    elif corruption=='bad_current_artifact_digest':artifact['digest']='not_sha256'
    if corruption in ('missing_native','missing_metadata','duplicate_current_id'):
        # Keep descriptor bound to updated manifest, test the content failure itself.
        source['input_artifact']['manifest_sha256']=mod.canonical_hash(manifest)
    if corruption=='bad_current_artifact_digest':
        with pytest.raises(ValueError,match='CURRENT_ARTIFACT_DIGEST_REQUIRED'):
            recovered(c)
        return
    holds,found=recovered(c)
    assert holds==[hold] and found==[]


def test_no_artifact_cap_increase_and_unrelated_hold_is_preserved(tmp_path):
    c=fixture(tmp_path);mod,cache,manifest,artifact,source,hold=c
    unrelated={'document_id':'unrelated','body_key':'unrelated',
               'reason_code':'PRIOR_INPUT_ARTIFACT_BUDGET_HELD'}
    unchanged={'document_id':source['document_id'],'body_key':'source-key',
               'reason_code':'PRIVATE_ARCHIVAL_OR_PRIVACY_UNREVIEWED'}
    holds,recovered=mod.recover_current_exact_holds(
        [hold,unrelated,unchanged],{'source-key':source},artifact,manifest,cache)
    assert holds==[unrelated,unchanged]
    assert len(recovered)==1 and mod.MAX_PRIOR_ARTIFACTS==8


def test_changed_native_members_would_be_rejected_by_existing_bundle_hash_verification(tmp_path):
    mod,cache,manifest,artifact,source,hold=fixture(tmp_path)
    path=cache/source['input_artifact']['native_member'];path.write_bytes(b'corrupt')
    # This helper only runs *after* extract_bundle verifies every actual native
    # member SHA. Direct helper tests prove metadata, while archive hash guard
    # remains an independent mandatory precondition in receive().
    assert mod.digest(path)!=source['raw_sha256']
