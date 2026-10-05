"""Offline source identity and loader regressions; no corpus performance claims."""
import json
from copy import deepcopy
import pytest

from bct import precursor_v2 as v2
from bct.shadow_input_v2 import load_documents
from test_precursor_v2 import document, NOW


def sites(owner='Orion',site='Lark Mine',verified=True):
    buyer=document('buyer',f'The buyer signed an offtake agreement with {owner} covering production from the {site} in Devon, England (“Lark”).')
    supplier=document('supplier',f'Project - {site}\nThe {site} at Devon is {owner}\'s wholly-owned asset.\nThe Timeline\nH2 2031\nSteady State production achieved',provenance_verified=verified)
    return buyer,supplier


@pytest.mark.parametrize('kind',['Mine','Project','Plant','Facility','Refinery','Factory','Terminal'])
def test_named_site_cross_document_identity_preserves_unknowns(kind):
    ds=sites(site='Lark '+kind)
    es=[e for d in ds for e in v2.extract(d)]
    d=next(e for e in es if e['role']=='DEMAND')
    s=next(e for e in es if e['document_id']=='supplier' and e['role']=='SUPPLY')
    r=v2.relationship(d,s,[],{x['document_id']:x for x in ds})
    assert r['state']=='VERIFIED' and r['kind']=='SAME_FACILITY'
    for ref in r['references']:v2.verify_reference(ref,{x['document_id']:x for x in ds})
    assert d['period'] is None and s['period'] is None
    assert 'qualification' not in d['fields'] and 'quantity' not in s['facts']
    result=v2.synthesize(ds,as_of=NOW)
    assert not any(e['early_eligible'] for e in result['evaluations'])


def test_unverified_supplier_cannot_be_a_pair():
    p=v2.synthesize(sites(verified=False),as_of=NOW)
    assert p['document_rejections']==[{'document_id':'supplier','reason':'PROVENANCE_UNVERIFIED'}]
    assert not p['evaluations']


@pytest.mark.parametrize('owner,site',[('Boreal','Lark Mine'),('Orion','Finch Mine')])
def test_different_site_or_owner_never_links(owner,site):
    a,_=sites();_,b=sites(owner,site)
    p=v2.synthesize([a,b],as_of=NOW)
    assert all(e['relation']['state']!='VERIFIED' for e in p['evaluations'])


def test_same_mine_name_without_owner_is_not_identity():
    a,_=sites();b=document('supplier','Lark Mine production ramps in H2 2031.')
    p=v2.synthesize([a,b],as_of=NOW)
    assert all(e['relation']['state']!='VERIFIED' for e in p['evaluations'])


def test_distinct_products_at_same_site_do_not_merge():
    a,b=sites()
    a['body']+=' product "tungsten" grade WO3.'
    b['body']=b['body'].replace('Steady State production achieved','Steady State production achieved for product "tin" grade SN.')
    for d in (a,b):d['body_sha256']=d['version']=v2.digest(d['body'].encode())
    assert all(e['relation']['state']!='VERIFIED' for e in v2.synthesize([a,b],as_of=NOW)['evaluations'])


def proof_fixture(tmp_path):
    d=document('buyer','Buyer signed orders for model AX-1.')
    d['origin_id']=d['origin_url']+'#article'
    html=f'<link rel="canonical" href="{d["origin_url"]}"><meta property="og:site_name" content="buyer"><meta property="article:published_time" content="{d["published_at"]}"><article>{d["body"]}</article>'
    h=tmp_path/'source.html';h.write_text(html)
    t=tmp_path/'source.txt';t.write_text(d['body'])
    proof={'document_id':d['document_id'],'provenance':'PASS','source_sha256':v2.digest(h.read_bytes()),'body_sha256':d['body_sha256'],'body_version':d['version'],'url':d['origin_url'],'publisher':'buyer','published_at_original':d['published_at'],'acquired_at_snapshot':d['available_at'],'http':200,'body_equals_snapshot':True,'article_id':d['origin_id']}
    p=tmp_path/'proof.json';p.write_text(json.dumps(proof))
    idx=tmp_path/'index.json';idx.write_text(json.dumps({'proofs':[{'proof':str(p),'source_html':str(h),'source_text':str(t)}]}))
    raw={'document_id':d['document_id'],'body':d['body'],'body_sha256':d['body_sha256'],'original_url':d['origin_url'],'collected_at':d['available_at']}
    inp=tmp_path/'input.json';inp.write_text(json.dumps({'documents':[]}))
    snap=tmp_path/'snapshot.json';snap.write_text(json.dumps({'documents':[raw]}))
    return inp,snap,idx,h,p


def test_existing_pass_source_is_loaded_not_silently_omitted(tmp_path):
    inp,snap,idx,_,_=proof_fixture(tmp_path)
    ds,r=load_documents(inp,source_snapshots=[snap],provenance_indexes=[idx])
    assert len(ds)==1 and ds[0]['provenance_verified']
    assert r['provenance_pass_documents_missing']==0 and r['pass_proofs_applied']==1
    v2.validate_document(ds[0],NOW)


def test_tampered_pass_html_is_blocked(tmp_path):
    inp,snap,idx,h,_=proof_fixture(tmp_path);h.write_text('forged')
    ds,r=load_documents(inp,source_snapshots=[snap],provenance_indexes=[idx])
    assert not ds[0]['provenance_verified'] and r['provenance_pass_documents_missing']==1


def test_pass_index_recovers_document_omitted_from_selected_input(tmp_path):
    inp,_,idx,_,_=proof_fixture(tmp_path)
    ds,r=load_documents(inp,provenance_indexes=[idx])
    assert len(ds)==1 and ds[0]['provenance_verified']
    assert r['provenance_pass_documents_missing']==0 and not r['proof_errors']


def test_source_metadata_cannot_be_claimed_by_pass_label(tmp_path):
    inp,snap,idx,_,p=proof_fixture(tmp_path)
    proof=json.loads(p.read_text());proof['publisher']='Other';p.write_text(json.dumps(proof))
    ds,r=load_documents(inp,source_snapshots=[snap],provenance_indexes=[idx])
    assert not ds[0]['provenance_verified'] and r['proof_errors']


def test_duplicate_snapshot_does_not_replace_existing_verified_document(tmp_path):
    inp,snap,idx,_,_=proof_fixture(tmp_path)
    ds,_=load_documents(inp,source_snapshots=[snap],provenance_indexes=[idx])
    inp.write_text(json.dumps({'documents':ds}))
    again,r=load_documents(inp,source_snapshots=[snap])
    assert again[0]['provenance_verified'] and r['duplicate_versions_excluded']==1
