"""Exercise the actual production executor's immutable review merge contract."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
import pytest
from bct.future_review import review_patch,document_complete,READER_VERSION,queue_items
from bct.future_store import PatchError


spec=importlib.util.spec_from_file_location('queue_executor',Path(__file__).parents[1]/'.github/scripts/bct_queue_recovery.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_actual_executor_merge_preserves_old_history_and_requires_complete_review():
    body='Demand exists but qualified capacity and readiness are unknown.'
    digest=sha256(body.encode()).hexdigest()
    item={'document_id':'doc','body_sha256':digest,'body_status':'FULL','body_chars':len(body)}
    candidates={'results':{'doc':{**item,'versions':{digest:item}}}}
    prior={'reviews':{'legacy':{'kind':'access','reason':'Original historical failure.'}},'runs':{}}
    review={'review_id':'new','document_id':'doc','body_sha256':digest,'kind':'quick',
            'reader_version':READER_VERSION,'reviewed_at':'2026-10-09T20:00:00+00:00',
            'read_start':0,'read_end':len(body),'disposition':'DATA_INSUFFICIENT',
            'reason':'Qualified capacity and readiness remain unknown.'}
    patch=review_patch(candidates,prior,review)
    before=deepcopy(prior)
    merged=module.merge_review_patch(prior,patch,'actual-run')
    assert prior==before and merged['reviews']['legacy']==before['reviews']['legacy']
    assert document_complete(merged,item)
    assert module.merge_review_patch(merged,patch,'actual-run')==merged
    changed=deepcopy(patch);changed['reviews']['new']['reason']='Changed old judgment.'
    with pytest.raises(PatchError):module.merge_review_patch(merged,changed,'other-run')


def test_corrected_excerpt_blocks_next_normal_read_without_mutating_prior_full_history():
    body='Related headline\nA different article stops...';digest=sha256(body.encode()).hexdigest()
    item={'document_id':'doc','body_sha256':digest,'body_status':'FULL','body_chars':len(body),
          'candidate':True,'url':'https://example.test/original'}
    candidates={'results':{'doc':{**item,'versions':{digest:dict(item)}}}}
    tracking={'reviews':{},'runs':{}}
    observation={'body_status':'PARTIAL','reclassification_rule':'ARTICLE_TERMINAL_ELLIPSIS_V1',
                 'classification_corrected_at':'2026-10-09T20:20:00+00:00'}
    review=module.completeness_review(item,observation,'real-run','unused-time')
    patch=review_patch(candidates,tracking,review)
    merged=module.merge_review_patch(tracking,patch,'real-run')
    lanes=queue_items(candidates,merged)
    assert lanes['quick']==[] and len(lanes['material'])==1
    assert not document_complete(merged,item)
    assert candidates['results']['doc']['versions'][digest]['body_status']=='FULL'
    assert merged['reviews'][review['review_id']]['source_completeness_status']=='PARTIAL'
