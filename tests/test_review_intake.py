from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest
from bct import review_intake as intake, review_leads as r
from bct.objective_lock import stamp_export
from test_review_leads import fixture


def packets(bundle):
    d=bundle['documents'][0]
    return [stamp_export({'document_id':d['document_id'],'body_sha256':d['body_sha256'],
        'annotation':deepcopy(bundle['annotations'][0])})]


def test_unannotated_events_hold_not_machine_truth(tmp_path):
    b,c,_=fixture();out=intake.process(b,c,tmp_path)
    assert out['counts']['HOLD']==1
    item=out['records'][0]
    assert item['semantic_review']['status']=='PENDING'
    assert not item['automatic_extraction']['facts_verified_semantically']
    assert item['review_id'] is None


def test_pending_completed_immutable_and_replay(tmp_path):
    b,c,_=fixture();intake.process(b,c,tmp_path)
    original=list((tmp_path/'intake').glob('*.json'))[0].read_bytes()
    out=intake.process(b,c,tmp_path,semantic_packets=packets(b));assert out['counts']['REVIEW_LEAD']==1
    again=intake.process(b,c,tmp_path,semantic_packets=packets(b));assert not any(again['counts'].values())
    assert original in [p.read_bytes() for p in (tmp_path/'intake').glob('*.json')]


def test_same_scope_hypothesis_new_evidence_append(tmp_path):
    b,c,_=fixture();out=intake.process(b,c,tmp_path,semantic_packets=packets(b))
    first=out['records'][0]['review_id'];p=tmp_path/'first'/(first+'.json');before=p.read_bytes()
    new=deepcopy(b);d=new['documents'][0];d['document_id']='new';d['body']+=' Additional observation.';d['body_sha256']=d['version']=r.digest(d['body'].encode());d['origin_id']='independent'
    def rebind(x):
        if isinstance(x,dict):
            if 'locator' in x and 'document_id' in x:x.update(document_id='new',body_sha256=d['body_sha256'])
            for v in x.values():rebind(v)
        elif isinstance(x,list):
            for v in x:rebind(v)
    rebind(new['annotations']);result=intake.process(new,c,tmp_path,semantic_packets=packets(new))
    assert result['records'][0]['review_id']==first and p.read_bytes()==before
    assert len(r.load_store(tmp_path)['records'][0]['history'])==1
    intake.process(new,c,tmp_path,semantic_packets=packets(new))
    assert len(r.load_store(tmp_path)['records'][0]['history'])==1


def test_different_model_scope_not_merged(tmp_path):
    b,c,ref=fixture();intake.process(b,c,tmp_path,semantic_packets=packets(b))
    b['documents'][0]['body']+=' A new statement.';d=b['documents'][0];d['body_sha256']=d['version']=r.digest(d['body'].encode())
    def update(x):
        if isinstance(x,dict):
            if 'locator' in x:x['body_sha256']=d['body_sha256']
            for v in x.values():update(v)
        elif isinstance(x,list):
            for v in x:update(v)
    update(b['annotations']);a=b['annotations'][0];a['scope_fields']['model']={'value':'BX-2','reference':{**ref('BX-2'),'body_sha256':d['body_sha256']}}
    out=intake.process(b,c,tmp_path,semantic_packets=packets(b));assert out['records'][0]['review_id'] != r.load_store(tmp_path)['records'][0]['first']['review_id'] or len(r.load_store(tmp_path)['records'])==2


def test_binding_scope_confirmation_and_unknown(tmp_path):
    b,c,ref=fixture();ps=packets(b);ps[0]['body_sha256']='wrong'
    with pytest.raises(ValueError,match='BINDING'):intake.process(b,c,tmp_path/'bad',semantic_packets=ps)
    ps=packets(b);ps[0]['annotation']['scope_relation']='MISMATCH'
    assert intake.process(b,c,tmp_path/'mismatch',semantic_packets=ps)['counts']['EXCLUDED']==1
    ps=packets(b);ps[0]['annotation']['confirmation']={'document':'YES','same_TARGET':'YES','references':[ref('Actual shortage at facility PX-1 is confirmed.')]}
    assert intake.process(b,c,tmp_path/'confirmed',semantic_packets=ps)['counts']['CONFIRMATION']==1
    ps=packets(b);ps[0]['annotation']['unknowns'][0]['status']='PASS'
    with pytest.raises(ValueError,match='UNKNOWN_NOT_PASS'):intake.process(b,c,tmp_path/'unknown',semantic_packets=ps)


def test_prospective_acquisition_cutover_no_backdating(tmp_path,monkeypatch):
    b,c,_=fixture();monkeypatch.setattr(r,'now',lambda:'2026-10-05T17:00:00+00:00')
    intake.process(stamp_export({'documents':[]}),c,tmp_path)
    d=b['documents'][0];d.update(published_at='2026-10-05T17:01:00+00:00',acquired_at='2026-10-05T17:02:00+00:00')
    monkeypatch.setattr(r,'now',lambda:'2026-10-05T17:03:00+00:00')
    out=intake.process(b,c,tmp_path,semantic_packets=packets(b),prospective=True)
    card=r.load_store(tmp_path)['records'][0]['first'];assert card['mode']=='PROSPECTIVE_REVIEW'
    assert card['first_review_recorded_at']=='2026-10-05T17:03:00+00:00'
    assert card['strict_candidate_first_met_at']=='UNKNOWN'


def test_optional_hook_failure_does_not_fail_collector(tmp_path):
    spec=importlib.util.spec_from_file_location('hook','.github/scripts/review_lead_intake.py');hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)
    result=hook.run(tmp_path/'absent',tmp_path/'store',tmp_path/'out')
    assert result['review_intake_status']=='BLOCKED' and not result['collector_failed_by_review']


def test_repost_different_document_id_is_duplicate(tmp_path):
    b,c,_=fixture();intake.process(b,c,tmp_path,semantic_packets=packets(b))
    b['documents'][0]['document_id']='repost'
    def rebind(x):
        if isinstance(x,dict):
            if 'locator' in x:x['document_id']='repost'
            for v in x.values():rebind(v)
        elif isinstance(x,list):
            for v in x:rebind(v)
    rebind(b['annotations']);out=intake.process(b,c,tmp_path,semantic_packets=packets(b))
    assert out['records'][0]['delivery']=='DUPLICATE'
    assert len(r.load_store(tmp_path)['records'])==1 and not any(out['counts'].values())


def test_unknown_scope_cannot_promote(tmp_path):
    b,c,_=fixture();d=b['documents'][0];d['body']+=' UNKNOWN';d['body_sha256']=d['version']=r.digest(d['body'].encode())
    a=b['annotations'][0]
    def update(x):
        if isinstance(x,dict):
            if 'locator' in x:x['body_sha256']=d['body_sha256']
            for v in x.values():update(v)
        elif isinstance(x,list):
            for v in x:update(v)
    update(a);i=d['body'].index('UNKNOWN');a['scope_fields']={'facility':{'value':'UNKNOWN','reference':{'document_id':d['document_id'],'body_sha256':d['body_sha256'],'quote':'UNKNOWN','locator':{'start':i,'end':i+7}}}}
    a['facts'][0]['scope_fields']={}
    assert intake.process(b,c,tmp_path,semantic_packets=packets(b))['counts']['HOLD']==1


def test_saved_delta_reads_only_named_capture_not_corpus(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('hook','.github/scripts/review_lead_intake.py');hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)
    b,c,_=fixture();d=b['documents'][0];raw=b'synthetic HTML controlled fixture'
    d.update(provenance='PASS',raw_sha256=hook.acquisition.digest(raw))
    cache=tmp_path/'cache';(cache/'raw').mkdir(parents=True);(cache/'captures').mkdir()
    (cache/'raw'/(d['raw_sha256']+'.html')).write_bytes(raw)
    (cache/'captures'/(hook.acquisition.digest(d['origin_url'])+'.json')).write_text(json.dumps(d))
    # Unrelated corrupt cached input must never be read.
    (cache/'captures'/'unrelated.json').write_text('corrupt')
    delta=tmp_path/'delta.json';delta.write_text(json.dumps({'documents':[{'document_id':d['document_id'],'url':d['origin_url']},{'document_id':'missing','url':'https://missing.example'}]}))
    monkeypatch.setattr(hook.acquisition,'verify',lambda *args:d)
    out,skipped=hook.load_saved_delta(delta,cache)
    assert [x['document_id'] for x in out['documents']]==[d['document_id']]
    assert len(skipped)==1 and skipped[0]['document_id']=='missing'


def test_unverified_missing_publication_remains_hold(tmp_path):
    b,c,_=fixture();b['documents'][0].update(provenance_verified=False,published_at=None)
    out=intake.process(b,c,tmp_path,semantic_packets=packets(b))
    assert out['counts']['HOLD']==1
    card=r.load_store(tmp_path)['records'][0]['first'];assert card['sources'][0]['published_at']=='UNKNOWN'
    assert card['mode']=='BACKFILL'


def test_four_preserved_semantic_readings_current_code():
    b=json.loads(Path('review-leads/examples-20261005/input.json').read_text());docs=r.documents(b)
    ps=json.loads(Path('review-leads/intake-20261005/regression-semantic.json').read_text())['packets']
    counts={s:0 for s in ('REVIEW_LEAD','HOLD','EXCLUDED','CONFIRMATION')}
    for packet in ps:
        item,_=intake.screen(docs[packet['document_id']],packet,docs);counts[item['final_status']]+=1
    assert counts=={'REVIEW_LEAD':2,'HOLD':1,'EXCLUDED':1,'CONFIRMATION':0}
